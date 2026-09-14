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

# Central Gemini Model Configuration
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

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

    # Use central GEMINI_MODEL configuration
    candidate_models = [GEMINI_MODEL]
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

def validate_and_normalize_structured_json(data: Any, pages: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """
    Validates and normalizes JSON parsed from Gemini response.
    Integrates Python deterministic scoring engine and page evidence locator.
    """
    from pdf_processor import find_source_page
    from scoring_engine import calculate_ipo_score

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

    company_name = get_str("company_name", "Specified Entity in DRHP")
    industry = get_str("industry", "Not Specified")
    business_summary = get_str("business_summary")
    business_model = get_str("business_model")

    # Strict check: If core summary fields are completely missing, fail gracefully
    if not business_summary and not business_model:
        return None

    # IPO details list
    ipo_details_raw = data.get("ipo_details")
    if isinstance(ipo_details_raw, dict):
        ipo_details = [f"{k}: {v}" for k, v in ipo_details_raw.items() if v]
    elif isinstance(ipo_details_raw, list):
        ipo_details = [str(x) for x in ipo_details_raw if x]
    else:
        ipo_details = []

    # Process Financial Facts & Multi-Period Disclosures
    from ratio_engine import (
        normalize_multi_period_facts,
        calculate_financial_ratios,
        analyze_financial_trends,
        generate_financial_health_interpretations
    )

    raw_facts = data.get("financial_facts", [])
    normalized_facts = []
    if isinstance(raw_facts, list):
        for f in raw_facts:
            if isinstance(f, dict):
                metric = get_str_val(f, "metric")
                unit = get_str_val(f, "unit") or None
                
                # Check for multi-year periods list
                periods_raw = f.get("periods")
                periods = []
                if isinstance(periods_raw, list) and len(periods_raw) > 0:
                    for p in periods_raw:
                        if isinstance(p, dict):
                            yr = str(p.get("year") or p.get("period") or "").strip()
                            v_val = p.get("value")
                            v_str = str(v_val).strip() if v_val is not None and str(v_val).strip() not in ["null", "None", "N/A", ""] else None
                            e_text = get_str_val(p, "evidence_text") or get_str_val(p, "evidence")
                            p_num = p.get("source_page") or p.get("page") or f.get("source_page")
                            
                            if p_num is not None:
                                try:
                                    p_num = int(p_num)
                                except (ValueError, TypeError):
                                    p_num = None
                            if p_num is None and pages and e_text:
                                p_num = find_source_page(pages, e_text)

                            periods.append({
                                "year": yr or "FY",
                                "value": v_str,
                                "source_page": p_num,
                                "evidence_text": e_text or None
                            })

                val = f.get("value")
                val_str = str(val).strip() if val is not None and str(val).strip() not in ["null", "None", "N/A", ""] else None
                evidence_text = get_str_val(f, "evidence_text") or get_str_val(f, "evidence")
                page_num = f.get("source_page") or f.get("page")

                if page_num is not None:
                    try:
                        page_num = int(page_num)
                    except (ValueError, TypeError):
                        page_num = None

                if page_num is None and pages and evidence_text:
                    page_num = find_source_page(pages, evidence_text)

                fact_obj = {
                    "metric": metric or "Financial Metric",
                    "value": val_str,
                    "unit": unit,
                    "period": get_str_val(f, "period") or None,
                    "source_page": page_num,
                    "evidence_text": evidence_text or ("Not available in document." if val_str is None and not periods else None)
                }
                if periods:
                    fact_obj["periods"] = periods

                normalized_facts.append(fact_obj)

    # NORMALIZE MULTI-PERIOD FACTS & CALCULATE RATIOS IN PYTHON
    norm_facts_map = normalize_multi_period_facts(normalized_facts)
    calculated_ratios = calculate_financial_ratios(norm_facts_map)
    financial_trends = analyze_financial_trends(norm_facts_map)
    financial_interpretations = generate_financial_health_interpretations(calculated_ratios)

    # Process Red Flags
    raw_red_flags = data.get("red_flags", [])
    normalized_red_flags = []
    if isinstance(raw_red_flags, list):
        for rf in raw_red_flags:
            if isinstance(rf, dict):
                title = str(rf.get("title") or rf.get("risk_title") or "Identified Risk").strip()
                sev = str(rf.get("severity") or "Medium").capitalize()
                if sev not in ["High", "Medium", "Low"]:
                    sev = "Medium"
                cat = str(rf.get("category") or "Operational Risk").strip()
                explanation = str(rf.get("explanation") or rf.get("reason") or rf.get("details") or "").strip()

                evidence_raw = rf.get("evidence")
                p_num = None
                e_text = ""

                if isinstance(evidence_raw, dict):
                    e_text = str(evidence_raw.get("text") or "").strip()
                    p_num = evidence_raw.get("page")
                elif isinstance(evidence_raw, str):
                    e_text = evidence_raw.strip()

                if p_num is not None:
                    try:
                        p_num = int(p_num)
                    except (ValueError, TypeError):
                        p_num = None

                if p_num is None and pages and e_text:
                    p_num = find_source_page(pages, e_text)

                if p_num is None and pages and explanation:
                    p_num = find_source_page(pages, explanation)

                normalized_red_flags.append({
                    "title": title,
                    "severity": sev,
                    "category": cat,
                    "explanation": explanation or e_text or "Document disclosure.",
                    "evidence": {
                        "page": p_num,
                        "text": e_text or explanation or "Referenced in DRHP."
                    }
                })

    strengths = get_list("strengths")
    growth_opps = get_list("growth_opportunities")

    # DETERMINISTIC PYTHON SCORING ENGINE INTEGRATION (PASSED CALCULATED RATIOS)
    score_res = calculate_ipo_score(
        financial_facts=normalized_facts,
        red_flags=normalized_red_flags,
        ipo_details=ipo_details,
        business_summary=business_summary,
        strengths=strengths,
        growth_opportunities=growth_opps,
        ratios=calculated_ratios
    )

    inv_score = score_res["overall_score"]
    cat_scores = score_res["category_scores"]

    # Determine risk level deterministically from score and high/medium red flag counts
    high_count = sum(1 for rf in normalized_red_flags if rf["severity"] == "High")
    med_count = sum(1 for rf in normalized_red_flags if rf["severity"] == "Medium")

    if high_count >= 2 or inv_score < 50.0:
        risk_level = "High"
    elif high_count == 1 or med_count >= 3 or inv_score < 70.0:
        risk_level = "Moderate"
    else:
        risk_level = "Low"

    # Recommendation normalization: Strong Positive | Positive | Neutral | Cautious | Negative
    raw_rec = get_str("recommendation").upper()
    if inv_score >= 80 and high_count == 0:
        recommendation = "Strong Positive"
    elif inv_score >= 68 and high_count == 0:
        recommendation = "Positive"
    elif inv_score >= 55 and high_count <= 1:
        recommendation = "Neutral"
    elif inv_score >= 40:
        recommendation = "Cautious"
    else:
        recommendation = "Negative"

    if "STRONG" in raw_rec and "POSITIVE" in raw_rec:
        recommendation = "Strong Positive"
    elif "POSITIVE" in raw_rec or "SUBSCRIBE" in raw_rec:
        if recommendation not in ["Strong Positive", "Negative"]:
            recommendation = "Positive"

    rec_reason = get_str("recommendation_reason") or f"Score of {inv_score}/100 with {risk_level.lower()} risk profile."

    # Strict confidence policy: return None if unverified or incomplete
    raw_conf = data.get("confidence")
    confidence = None
    if raw_conf is not None:
        try:
            val_c = float(raw_conf)
            if 0 <= val_c <= 100:
                confidence = round(val_c, 1)
        except (ValueError, TypeError):
            confidence = None

    return {
        "company_name": company_name,
        "industry": industry,
        "business_summary": business_summary or "Information not available in DRHP sections.",
        "business_model": business_model or "Information not available in DRHP sections.",
        "products_services": get_list("products_services"),
        "revenue_sources": get_list("revenue_sources"),
        "financial_highlights": get_list("financial_highlights"),
        "financial_facts": normalized_facts,
        "normalized_fact_map": norm_facts_map,
        "financial_ratios": calculated_ratios,
        "financial_trends": financial_trends,
        "financial_interpretations": financial_interpretations,
        "strengths": strengths,
        "risks": get_list("risks"),
        "red_flags": normalized_red_flags,
        "growth_opportunities": growth_opps,
        "competitors": get_list("competitors"),
        "ipo_details": ipo_details,
        "use_of_proceeds": get_list("use_of_proceeds"),
        "investment_score": inv_score,  # Deterministic score
        "score_breakdown": {
            "financial_health": cat_scores["financial_health"]["score"],
            "business_quality": cat_scores["business_quality"]["score"],
            "growth_potential": cat_scores["growth"]["score"],
            "ipo_fundamentals": cat_scores["ipo_fundamentals"]["score"],
            "risk_profile": cat_scores["risk"]["score"]
        },
        "category_scores": cat_scores,  # Full detailed reasons + sources
        "risk_level": risk_level,      # "Low" | "Moderate" | "High"
        "recommendation": recommendation, # "Strong Positive" | "Positive" | "Neutral" | "Cautious" | "Negative"
        "recommendation_reason": rec_reason,
        "confidence": confidence       # Float or None (Renders as N/A in UI when None)
    }

def get_str_val(d: Dict[str, Any], k: str) -> str:
    v = d.get(k)
    return str(v).strip() if v is not None else ""

def analyze_drhp_structured(text: str, pages: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Performs forensic AI analysis on DRHP text using Gemini and returns a validated structured dictionary.
    Integrates page awareness and deterministic scoring.
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

Analyze the provided DRHP document text and extract financial facts, risk disclosures, and company details into JSON format matching the EXACT schema below.

JSON Schema:
{{
  "company_name": "Full legal company name",
  "industry": "Industry or Sector",
  "business_summary": "Comprehensive overview of company business operations",
  "business_model": "Revenue generation model and unit economics",
  "products_services": ["List of main products or services offered"],
  "revenue_sources": ["List of primary revenue streams"],
  "financial_facts": [
    {{
      "metric": "Revenue" | "Revenue growth" | "EBITDA" | "Net profit" | "Profit growth" | "EPS" | "Total assets" | "Total liabilities" | "Total debt" | "Debt-to-equity" | "Operating cash flow" | "Free cash flow" | "Promoter shareholding" | "IPO size" | "Fresh issue" | "Offer for Sale" | "Use of proceeds" | "Customer concentration" | "Supplier concentration" | "Related-party transactions" | "Litigation" | "Contingent liabilities" | "Regulatory issues",
      "value": "Exact value string or number, or null if unavailable in text",
      "unit": "Cr / Lakhs / % / USD or null",
      "period": "FY24 / FY23 or null",
      "source_page": null,
      "evidence_text": "Exact quote or figure sentence from DRHP, or null if unavailable"
    }}
  ],
  "financial_highlights": ["List of key financial summary lines"],
  "strengths": ["List of competitive advantages / moats"],
  "risks": ["List of general business & industry risks"],
  "red_flags": [
    {{
      "title": "Short title of severe risk/red flag",
      "severity": "High" | "Medium" | "Low",
      "category": "High debt" | "Negative cash flow" | "Continuous losses" | "Revenue concentration" | "Customer concentration" | "Supplier concentration" | "Promoter selling" | "Promoter concerns" | "Related-party transactions" | "Pending litigation" | "Regulatory issues" | "Auditor qualifications" | "Contingent liabilities" | "Corporate governance concerns" | "Industry-specific risks",
      "explanation": "Detailed explanation of why this is a red flag",
      "evidence": "Specific quoted text or quantitative figures from the DRHP"
    }}
  ],
  "growth_opportunities": ["List of business growth catalysts"],
  "competitors": ["List of key market competitors / peers"],
  "ipo_details": ["Fresh Issue size, OFS size, Price Band, Listing details"],
  "use_of_proceeds": ["Specific objects of the offer / deployment of funds"],
  "recommendation": "Strong Positive" | "Positive" | "Neutral" | "Cautious" | "Negative",
  "recommendation_reason": "Detailed qualitative rationale for recommendation",
  "confidence": null
}}

Critical Guidelines:
1. Base all metrics, red flags, and facts strictly on evidence present in the DRHP text.
2. If a financial metric is unavailable in the document, set value = null and evidence_text = null. Do NOT invent missing values.
3. Every red flag MUST include specific evidence quote from the DRHP. Do not flag generic risks unless evidence exists in text.
4. Output strictly valid JSON without conversational markdown commentary.

DRHP Document Text:
{drhp_context}
"""

    # Use central GEMINI_MODEL configuration
    candidate_models = [GEMINI_MODEL]
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
            validated_data = validate_and_normalize_structured_json(parsed_json, pages=pages)

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
