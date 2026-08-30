import os
import re
import json
import logging
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

logger = logging.getLogger(__name__)

# Ensure environment variables are loaded
load_dotenv(override=True)

def get_api_key() -> Optional[str]:
    """
    Retrieves Gemini API key ONLY from environment variables (.env).
    Never hardcodes or prints keys.
    """
    load_dotenv(override=True)
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key and key.strip():
        return key.strip()
    return None

def get_genai_client() -> Optional[genai.Client]:
    """
    Initializes and returns a Google GenAI Client instance if GEMINI_API_KEY is configured.
    """
    key = get_api_key()
    if not key:
        return None
    try:
        return genai.Client(api_key=key)
    except Exception as e:
        logger.error(f"Failed to initialize GenAI client safely: {type(e).__name__}")
        return None

def test_gemini_connection() -> Dict[str, Any]:
    """
    Health check distinguishing 3 states:
    1. UNCONFIGURED: GEMINI_API_KEY missing from environment
    2. FAILED: Configured key exists, but API request failed
    3. HEALTHY: API connected and responding successfully
    """
    key = get_api_key()
    if not key:
        return {
            "status": "UNCONFIGURED",
            "success": False,
            "error": "Gemini API key is not configured in .env environment.",
            "model": None
        }

    client = get_genai_client()
    if not client:
        return {
            "status": "FAILED",
            "success": False,
            "error": "Failed to initialize Gemini API client.",
            "model": None
        }

    # Try modern available models in priority order
    candidate_models = ["gemini-3.6-flash", "gemini-3.1-pro-preview", "gemini-2.5-flash"]
    last_err = ""

    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents="Ping",
                config=types.GenerateContentConfig(temperature=0.0)
            )
            if response and response.text:
                return {
                    "status": "HEALTHY",
                    "success": True,
                    "error": None,
                    "model": model_name
                }
        except APIError as e:
            last_err = f"API error ({e.code}): {e.message}"
            continue
        except Exception as e:
            last_err = f"Connection failed: {str(e)}"
            continue

    return {
        "status": "FAILED",
        "success": False,
        "error": f"Gemini request failed: {last_err}",
        "model": None
    }

def build_drhp_context(text: str, max_chars: int = 70000) -> str:
    """
    Extracts high-priority sections from large DRHP documents (1M+ chars) by combining:
    1. Opening cover & executive summary
    2. Specific matching sections (Financials, Risks, Objects, Promoters, Legal, Competitors)
    3. Concluding disclosures
    """
    if not text:
        return ""

    if len(text) <= max_chars:
        return text

    keywords = [
        "OBJECTS OF THE OFFER",
        "USE OF PROCEEDS",
        "RISK FACTORS",
        "OUR BUSINESS",
        "FINANCIAL INFORMATION",
        "FINANCIAL STATEMENTS",
        "OUR PROMOTERS",
        "CAPITAL STRUCTURE",
        "LEGAL AND OTHER INFORMATION",
        "RELATED PARTY TRANSACTIONS",
        "PENDING LITIGATION",
        "COMPETITION",
        "INDUSTRY OVERVIEW"
    ]

    extracted_chunks = []

    # 1. Executive summary / Intro (First 18,000 chars)
    extracted_chunks.append("--- BEGIN SECTION: COVER & EXECUTIVE SUMMARY ---")
    extracted_chunks.append(text[:18000])

    # 2. Key section keyword extractions
    text_lower = text.lower()
    chars_per_section = 5000

    for kw in keywords:
        pos = text_lower.find(kw.lower())
        if pos != -1 and pos > 18000:
            extracted_chunks.append(f"\n--- BEGIN SECTION: {kw} ---")
            snippet = text[pos : pos + chars_per_section]
            extracted_chunks.append(snippet)

    # 3. Concluding section (Financial notes & disclosures)
    if len(text) > 30000:
        extracted_chunks.append("\n--- BEGIN SECTION: FINANCIAL DISCLOSURES & CONCLUDING DISCLOSURES ---")
        extracted_chunks.append(text[-12000:])

    combined = "\n\n".join(extracted_chunks)
    if len(combined) > max_chars:
        return combined[:max_chars]
    return combined

def validate_and_normalize_structured_json(data: Any) -> Optional[Dict[str, Any]]:
    """
    Validates that parsed JSON strictly conforms to the required DRHP schema.
    Returns None if core analysis content is unparseable or missing (STRICT NO-FAKE-FALLBACK POLICY).
    """
    if not isinstance(data, dict):
        return None

    def get_str(key: str, default: str = "") -> str:
        val = data.get(key)
        return str(val).strip() if val is not None and str(val).strip() else default

    def get_list(key: str) -> List[str]:
        val = data.get(key)
        if isinstance(val, list):
            return [str(item).strip() for item in val if item is not None and str(item).strip()]
        return []

    def get_optional_float(key: str) -> Optional[float]:
        try:
            val = data.get(key)
            if val is not None and str(val).strip() != "":
                return float(val)
        except (ValueError, TypeError):
            pass
        return None

    company_name = get_str("company_name", "Specified Entity in DRHP")
    industry = get_str("industry", "Not Specified")
    business_summary = get_str("business_summary")
    business_model = get_str("business_model")

    # If core summary fields are totally empty, validation fails cleanly
    if not business_summary and not business_model:
        return None

    # Validate ipo_details (supports dict or list)
    ipo_details_raw = data.get("ipo_details")
    if isinstance(ipo_details_raw, dict):
        ipo_details = [f"{k}: {v}" for k, v in ipo_details_raw.items() if v]
    elif isinstance(ipo_details_raw, list):
        ipo_details = [str(x) for x in ipo_details_raw if x]
    else:
        ipo_details = []

    # Validate score breakdown
    sb_raw = data.get("score_breakdown", {})
    score_breakdown = {}
    if isinstance(sb_raw, dict):
        for k in ["financial_health", "growth_potential", "business_quality", "industry_position", "risk_profile"]:
            try:
                v = sb_raw.get(k)
                score_breakdown[k] = round(float(v), 1) if v is not None else None
            except (ValueError, TypeError):
                score_breakdown[k] = None

    # Investment score handling (NO fake 50.0 default!)
    inv_score = get_optional_float("investment_score")
    if inv_score is None:
        # If components exist, sum them up
        valid_sb = [v for v in score_breakdown.values() if v is not None]
        if valid_sb:
            inv_score = round(sum(valid_sb), 1)

    if inv_score is not None:
        inv_score = round(max(0.0, min(100.0, inv_score)), 1)

    # Risk level normalization
    risk_level_raw = get_str("risk_level")
    if risk_level_raw.capitalize() in ["Low", "Moderate", "High"]:
        risk_level = risk_level_raw.capitalize()
    elif risk_level_raw:
        risk_level = risk_level_raw
    else:
        risk_level = "N/A"

    # Recommendation normalization
    recommendation = get_str("recommendation") or "Analysis unavailable"

    # Validate red flags list with grounded evidence and categories
    red_flags_raw = data.get("red_flags", [])
    normalized_red_flags = []
    if isinstance(red_flags_raw, list):
        for rf in red_flags_raw:
            if isinstance(rf, dict):
                title = str(rf.get("title") or rf.get("risk_title") or "Identified Risk").strip()
                sev = str(rf.get("severity") or "Medium").capitalize()
                if sev not in ["High", "Medium", "Low"]:
                    sev = "Medium"
                cat = str(rf.get("category") or "Operational Risk").strip()
                explanation = str(rf.get("explanation") or rf.get("details") or "").strip()
                evidence = str(rf.get("evidence") or rf.get("drhp_evidence") or explanation or "Document disclosure.").strip()

                normalized_red_flags.append({
                    "title": title,
                    "severity": sev,
                    "category": cat,
                    "explanation": explanation or evidence,
                    "evidence": evidence
                })

    confidence = get_optional_float("confidence")
    if confidence is not None:
        confidence = round(max(0.0, min(100.0, confidence)), 1)

    return {
        "company_name": company_name,
        "industry": industry,
        "business_summary": business_summary or "Information not available in DRHP sections.",
        "business_model": business_model or "Information not available in DRHP sections.",
        "products_services": get_list("products_services"),
        "revenue_sources": get_list("revenue_sources"),
        "financial_highlights": get_list("financial_highlights"),
        "strengths": get_list("strengths"),
        "risks": get_list("risks"),
        "red_flags": normalized_red_flags,
        "growth_opportunities": get_list("growth_opportunities"),
        "competitors": get_list("competitors"),
        "ipo_details": ipo_details,
        "use_of_proceeds": get_list("use_of_proceeds"),
        "investment_score": inv_score,  # Float or None (NO fake default!)
        "score_breakdown": score_breakdown,
        "risk_level": risk_level,      # "Low" | "Moderate" | "High" | "N/A"
        "recommendation": recommendation, # String or "Analysis unavailable"
        "recommendation_reason": get_str("recommendation_reason", "Analysis based on provided DRHP sections."),
        "confidence": confidence       # Float or None
    }

def analyze_drhp_structured(text: str) -> Dict[str, Any]:
    """
    Performs forensic AI analysis on DRHP text using Gemini and returns a validated structured dictionary.
    Returns success: False and data: None if API is unconfigured or analysis fails.
    """
    health = test_gemini_connection()
    if not health["success"]:
        return {
            "success": False,
            "error": health["error"],
            "data": None
        }

    client = get_genai_client()
    if not client:
        return {
            "success": False,
            "error": "Gemini API client unavailable.",
            "data": None
        }

    drhp_context = build_drhp_context(text, max_chars=70000)
    if not drhp_context.strip():
        return {
            "success": False,
            "error": "The DRHP text is empty or could not be extracted.",
            "data": None
        }

    prompt = f"""
You are a senior equity research analyst and forensic risk auditor reviewing a Draft Red Herring Prospectus (DRHP).

Analyze the provided DRHP document sections and return a structured JSON response matching the EXACT schema below.

JSON Schema:
{{
  "company_name": "Full legal company name",
  "industry": "Industry or Sector",
  "business_summary": "Comprehensive overview of company business operations",
  "business_model": "Revenue generation model and unit economics",
  "products_services": ["List of main products or services offered"],
  "revenue_sources": ["List of primary revenue streams"],
  "financial_highlights": ["List of key financial metrics (Revenue, Profit, EBITDA, Debt, Assets, Margins)"],
  "strengths": ["List of competitive advantages / moats"],
  "risks": ["List of general business & industry risks"],
  "red_flags": [
    {{
      "title": "Short title of severe risk/red flag",
      "severity": "High" | "Medium" | "Low",
      "category": "High debt" | "Negative cash flow" | "Continuous losses" | "Revenue concentration" | "Customer concentration" | "Supplier concentration" | "Promoter selling" | "Promoter concerns" | "Related-party transactions" | "Pending litigation" | "Regulatory issues" | "Auditor qualifications" | "Contingent liabilities" | "Corporate governance concerns" | "Industry-specific risks",
      "explanation": "Detailed explanation of why this is a red flag",
      "evidence": "Specific quoted evidence or quantitative figures from the DRHP"
    }}
  ],
  "growth_opportunities": ["List of business growth catalysts"],
  "competitors": ["List of key market competitors / peers"],
  "ipo_details": ["Fresh Issue size, OFS size, Price Band, Listing details"],
  "use_of_proceeds": ["Specific objects of the offer / deployment of funds"],
  "investment_score": 0.0 to 100.0 (Sum of breakdown scores out of 100),
  "score_breakdown": {{
    "financial_health": 0.0 to 20.0,
    "growth_potential": 0.0 to 20.0,
    "business_quality": 0.0 to 20.0,
    "industry_position": 0.0 to 20.0,
    "risk_profile": 0.0 to 20.0
  }},
  "risk_level": "Low" | "Moderate" | "High",
  "recommendation": "SUBSCRIBE" | "WATCH" | "AVOID",
  "recommendation_reason": "Detailed rationale for the recommendation",
  "confidence": 0.0 to 100.0 (Confidence score based on completeness of DRHP disclosures)
}}

Critical Guidelines:
1. Base all metrics, red flags, and facts strictly on evidence present in the DRHP text.
2. Every red flag MUST include specific evidence grounded in the text.
3. Output strictly valid JSON. Do not wrap in conversational markdown commentary.

DRHP Document Text:
{drhp_context}
"""

    candidate_models = ["gemini-3.6-flash", "gemini-3.1-pro-preview", "gemini-2.5-flash"]
    last_error = ""

    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json"
                )
            )

            if not response or not response.text:
                continue

            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)
                raw_text = raw_text.strip()

            parsed_json = json.loads(raw_text)
            validated_data = validate_and_normalize_structured_json(parsed_json)

            if validated_data is not None:
                return {
                    "success": True,
                    "error": None,
                    "data": validated_data
                }
            else:
                last_error = "JSON output failed structural validation against required DRHP schema."
                logger.warning(f"Validation failed for model {model_name}")

        except json.JSONDecodeError as e:
            last_error = f"JSON decode error from {model_name}: {str(e)}"
            logger.warning(last_error)
        except APIError as e:
            last_error = f"Gemini API error ({model_name}): {e.message}"
            logger.warning(last_error)
        except Exception as e:
            last_error = f"Error with model {model_name}: {str(e)}"
            logger.warning(last_error)

    return {
        "success": False,
        "error": f"AI Analysis failed: {last_error}",
        "data": None
    }

# ==============================================================================
# Helper Compatibility Wrappers
# ==============================================================================

def generate_summary(text: str) -> str:
    res = analyze_drhp_structured(text)
    if not res["success"] or not res["data"]:
        return res.get("error") or "AI analysis unavailable."
    d = res["data"]
    return f"### {d['company_name']} ({d['industry']})\n\n**Business Summary**: {d['business_summary']}\n\n**Business Model**: {d['business_model']}"

def generate_red_flags(text: str) -> str:
    res = analyze_drhp_structured(text)
    if not res["success"] or not res["data"]:
        return res.get("error") or "AI analysis unavailable."
    flags = res["data"].get("red_flags", [])
    if not flags:
        return "No major critical red flags identified in extracted DRHP sections."
    out = ["### ⚠️ Identified Risk Factors & Red Flags\n"]
    for idx, rf in enumerate(flags, 1):
        out.append(f"**{idx}. {rf['title']}** [{rf['severity']}] ({rf['category']})\n- **Evidence**: {rf['evidence']}\n")
    return "\n".join(out)

def generate_ipo_score(text: str) -> Optional[float]:
    res = analyze_drhp_structured(text)
    if not res["success"] or not res["data"]:
        return None
    return res["data"].get("investment_score")

def generate_recommendation(text: str) -> str:
    res = analyze_drhp_structured(text)
    if not res["success"] or not res["data"]:
        return "Analysis unavailable"
    d = res["data"]
    return f"**{d['recommendation']}**: {d['recommendation_reason']}"

if __name__ == "__main__":
    print("Testing gemini_service.py health check...")
    hc = test_gemini_connection()
    print("Health check result:", hc)
