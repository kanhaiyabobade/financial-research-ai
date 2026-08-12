import os
import re
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def get_api_key() -> Optional[str]:
    """
    Dynamically loads environment variables and retrieves the Gemini API key.
    """
    load_dotenv(override=True)
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

def ensure_gemini_configured() -> Optional[str]:
    """
    Ensures google-generativeai is configured with a valid API key if available.
    Returns the API key or None.
    """
    key = get_api_key()
    if key:
        try:
            genai.configure(api_key=key)
        except Exception as e:
            logger.error(f"Failed to configure genai: {e}")
    return key

def test_gemini_connection() -> Dict[str, Any]:
    """
    Performs a small, fast request to test Gemini API key validity before heavy processing.
    """
    key = ensure_gemini_configured()
    if not key:
        return {
            "success": False,
            "error": "Gemini API key is not configured. Please add GEMINI_API_KEY to your .env file."
        }
    
    models_to_try = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
    last_err = ""
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content("Ping")
            if response and response.text:
                return {"success": True, "model": model_name, "error": None}
        except Exception as e:
            last_err = str(e)
            continue
            
    return {
        "success": False,
        "error": f"Failed to connect to Gemini API: {last_err}"
    }

def build_drhp_context(text: str, max_chars: int = 60000) -> str:
    """
    Extracts relevant sections from large DRHP documents (1M+ chars) by combining 
    the opening overview, key section matches (Financials, Risks, Objects, Promoters), 
    and document summary snippets instead of naive top truncation.
    """
    if not text:
        return ""
        
    if len(text) <= max_chars:
        return text
        
    # Standard DRHP section headers to look for
    keywords = [
        "OBJECTS OF THE OFFER",
        "USE OF PROCEEDS",
        "RISK FACTORS",
        "OUR BUSINESS",
        "FINANCIAL INFORMATION",
        "FINANCIAL STATEMENTS",
        "OUR PROMOTERS AND GROUP COMPANIES",
        "CAPITAL STRUCTURE",
        "LEGAL AND OTHER INFORMATION",
        "INDUSTRY OVERVIEW",
        "SUMMARY OF FINANCIAL INFORMATION"
    ]
    
    extracted_chunks = []
    
    # 1. Include first 15,000 chars (Executive Summary / Intro / Cover)
    extracted_chunks.append("--- BEGIN SECTION: COVER & EXECUTIVE SUMMARY ---")
    extracted_chunks.append(text[:15000])
    
    # 2. Search for keyword section occurrences throughout the document
    text_lower = text.lower()
    chars_per_keyword = 5000
    
    for kw in keywords:
        pos = text_lower.find(kw.lower())
        if pos != -1 and pos > 15000:
            extracted_chunks.append(f"\n--- BEGIN SECTION: {kw} ---")
            snippet = text[pos : pos + chars_per_keyword]
            extracted_chunks.append(snippet)
            
    # 3. Include last 10,000 chars (Financial Notes & Legal disclosures often at end)
    if len(text) > 25000:
        extracted_chunks.append("\n--- BEGIN SECTION: FINANCIAL NOTES & CONCLUDING DISCLOSURES ---")
        extracted_chunks.append(text[-10000:])
        
    combined = "\n\n".join(extracted_chunks)
    
    # Cap at max_chars to ensure safe token limit
    if len(combined) > max_chars:
        return combined[:max_chars]
    return combined

def analyze_drhp_structured(text: str) -> Dict[str, Any]:
    """
    Analyzes DRHP text using Gemini and returns a validated structured dictionary 
    conforming to the required IPO Intelligence JSON schema.
    """
    key = ensure_gemini_configured()
    if not key:
        return {
            "success": False,
            "error": "Gemini API key is not configured. Please add GEMINI_API_KEY to your .env file.",
            "data": None
        }
        
    drhp_context = build_drhp_context(text, max_chars=60000)
    if not drhp_context.strip():
        return {
            "success": False,
            "error": "The DRHP text is empty or could not be extracted.",
            "data": None
        }
        
    prompt = f"""
You are a senior equity research analyst and forensic risk auditor reviewing a Draft Red Herring Prospectus (DRHP).

Analyze the provided DRHP text and extract structured financial insights. Respond ONLY with a valid JSON object matching the EXACT key structure below. Do not wrap in conversational text.

Required JSON Schema:
{{
  "company_name": "String (Full legal company name)",
  "industry": "String (Industry / Sector)",
  "business_summary": "String (Detailed summary of what the company does)",
  "business_model": "String (How the company generates revenue and unit economics)",
  "products_services": ["String list of major products/services"],
  "revenue_sources": ["String list of primary revenue streams"],
  "financial_highlights": ["String list of key metrics e.g. Revenue, EBITDA, PAT, Debt, Margins"],
  "growth_opportunities": ["String list of growth catalysts"],
  "strengths": ["String list of key competitive advantages/moats"],
  "risks": ["String list of operational and market risks"],
  "red_flags": [
    {{
      "title": "String (Short risk title)",
      "severity": "High" | "Medium" | "Low",
      "evidence": "String (Grounded evidence with specific details/figures from DRHP)",
      "category": "Debt" | "Legal" | "Concentration" | "Governance" | "Valuation" | "Operational" | "Regulatory"
    }}
  ],
  "competitors": ["String list of peer companies"],
  "ipo_details": ["String list of IPO details e.g. Fresh Issue size, OFS size, Price Band if mentioned"],
  "use_of_proceeds": ["String list of objects of the issue"],
  "investment_score": 0.0 to 100.0 (Numeric score based transparently on Financials, Growth, Business Quality, Industry, Risk),
  "score_breakdown": {{
    "financial_health": 0 to 20,
    "growth_potential": 0 to 20,
    "business_quality": 0 to 20,
    "industry_position": 0 to 20,
    "risk_profile": 0 to 20
  }},
  "risk_level": "Low" | "Moderate" | "High",
  "recommendation": "Strong Positive" | "Positive" | "Neutral" | "Cautious" | "Negative",
  "recommendation_reason": "String (Detailed reasoning for the investment recommendation)",
  "confidence": 0 to 100 (Numeric percentage confidence based on data completeness)
}}

Important Guidelines:
1. Base all facts, numbers, and red flags strictly on evidence present in the DRHP text.
2. If specific financial figures or details are unavailable in the text, explicitly state "Information not available in provided DRHP sections" rather than inventing data.
3. Compute the investment_score transparently as the sum of score_breakdown components (out of 100).
4. Ensure red_flags list contains items with title, severity, evidence, and category.

DRHP Document Content:
{drhp_context}
"""

    models_to_try = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
    last_error = ""

    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.2}
            )
            
            raw_text = response.text.strip()
            
            # Clean Markdown code fences if present
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)
                raw_text = raw_text.strip()

            data = json.loads(raw_text)
            
            # Validate core fields and ensure defaults
            validated = validate_and_normalize_structured_json(data)
            return {
                "success": True,
                "error": None,
                "data": validated
            }
            
        except json.JSONDecodeError as e:
            last_error = f"Failed to parse JSON response from model {model_name}: {str(e)}"
            logger.warning(last_error)
            # If model returned semi-structured text, try fallback recovery
            continue
        except Exception as e:
            last_error = f"Gemini API error ({model_name}): {str(e)}"
            logger.warning(last_error)
            continue

    return {
        "success": False,
        "error": f"Failed to perform Gemini analysis: {last_error}",
        "data": None
    }

def validate_and_normalize_structured_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensures all expected keys exist in the dictionary with valid types.
    """
    if not isinstance(data, dict):
        data = {}

    def get_str(key: str, default: str = "Not specified") -> str:
        val = data.get(key)
        return str(val) if val is not None and str(val).strip() else default

    def get_list(key: str) -> list:
        val = data.get(key)
        if isinstance(val, list):
            return [str(item) for item in val if item is not None]
        return []

    def get_float(key: str, default: float = 0.0) -> float:
        try:
            val = data.get(key)
            if val is not None:
                return float(val)
        except (ValueError, TypeError):
            pass
        return default

    # Normalize score breakdown
    raw_breakdown = data.get("score_breakdown", {})
    if not isinstance(raw_breakdown, dict):
        raw_breakdown = {}
        
    breakdown = {
        "financial_health": float(raw_breakdown.get("financial_health", 10.0)),
        "growth_potential": float(raw_breakdown.get("growth_potential", 10.0)),
        "business_quality": float(raw_breakdown.get("business_quality", 10.0)),
        "industry_position": float(raw_breakdown.get("industry_position", 10.0)),
        "risk_profile": float(raw_breakdown.get("risk_profile", 10.0))
    }

    calculated_score = sum(breakdown.values())
    raw_score = get_float("investment_score", calculated_score)
    inv_score = round(max(0.0, min(100.0, raw_score)), 1)

    # Risk level normalization
    risk_level = get_str("risk_level", "Moderate")
    if risk_level.capitalize() not in ["Low", "Moderate", "High"]:
        risk_level = "Moderate"

    # Recommendation normalization
    recommendation = get_str("recommendation", "Neutral")

    # Normalize red flags list
    raw_red_flags = data.get("red_flags", [])
    normalized_red_flags = []
    if isinstance(raw_red_flags, list):
        for rf in raw_red_flags:
            if isinstance(rf, dict):
                normalized_red_flags.append({
                    "title": str(rf.get("title", "Risk Factor")),
                    "severity": str(rf.get("severity", "Medium")).capitalize(),
                    "evidence": str(rf.get("evidence", "Mentioned in DRHP disclosures.")),
                    "category": str(rf.get("category", "Operational"))
                })
            elif isinstance(rf, str):
                normalized_red_flags.append({
                    "title": "Identified Risk",
                    "severity": "Medium",
                    "evidence": rf,
                    "category": "Operational"
                })

    return {
        "company_name": get_str("company_name", "Unknown Company"),
        "industry": get_str("industry", "Not Specified"),
        "business_summary": get_str("business_summary", "Summary not available."),
        "business_model": get_str("business_model", "Business model details not provided."),
        "products_services": get_list("products_services"),
        "revenue_sources": get_list("revenue_sources"),
        "financial_highlights": get_list("financial_highlights"),
        "growth_opportunities": get_list("growth_opportunities"),
        "strengths": get_list("strengths"),
        "risks": get_list("risks"),
        "red_flags": normalized_red_flags,
        "competitors": get_list("competitors"),
        "ipo_details": get_list("ipo_details"),
        "use_of_proceeds": get_list("use_of_proceeds"),
        "investment_score": inv_score,
        "score_breakdown": breakdown,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "recommendation_reason": get_str("recommendation_reason", "Analysis completed based on available DRHP content."),
        "confidence": round(max(0.0, min(100.0, get_float("confidence", 75.0))), 1)
    }

# ==============================================================================
# Backward Compatibility Wrappers
# ==============================================================================

def generate_summary(text: str) -> str:
    """Legacy helper function returning Markdown summary string."""
    res = analyze_drhp_structured(text)
    if not res["success"]:
        return res["error"]
    
    d = res["data"]
    lines = [
        f"### {d['company_name']} ({d['industry']})",
        f"**Business Summary**: {d['business_summary']}\n",
        f"**Business Model**: {d['business_model']}\n",
        "#### Key Products & Services",
    ]
    lines.extend([f"- {p}" for p in d["products_services"]] or ["- Information not available"])
    lines.append("\n#### Financial Highlights")
    lines.extend([f"- {f}" for f in d["financial_highlights"]] or ["- Information not available"])
    lines.append("\n#### Objects of the Offer / Use of Proceeds")
    lines.extend([f"- {u}" for u in d["use_of_proceeds"]] or ["- Information not available"])
    
    return "\n".join(lines)

def generate_red_flags(text: str) -> str:
    """Legacy helper function returning Markdown red flags string."""
    res = analyze_drhp_structured(text)
    if not res["success"]:
        return res["error"]
        
    flags = res["data"].get("red_flags", [])
    if not flags:
        return "No major critical red flags identified in the extracted sections."
        
    out = ["### ⚠️ Identified Risk Factors & Red Flags\n"]
    for idx, rf in enumerate(flags, 1):
        sev = rf.get("severity", "Medium")
        badge = "🔴 High" if sev == "High" else ("🟡 Medium" if sev == "Medium" else "🔵 Low")
        out.append(f"**{idx}. {rf['title']}** [{badge}] ({rf.get('category', 'General')})")
        out.append(f"- **Evidence**: {rf['evidence']}\n")
        
    return "\n".join(out)

def generate_ipo_score(text: str) -> Optional[float]:
    """
    Evaluates IPO metrics and returns numeric score between 0 and 100.
    Returns None if Gemini is unconfigured or analysis fails (no fake scores!).
    """
    res = analyze_drhp_structured(text)
    if not res["success"]:
        return None
    return res["data"].get("investment_score")

def generate_recommendation(text: str) -> str:
    """Legacy helper returning recommendation markdown."""
    res = analyze_drhp_structured(text)
    if not res["success"]:
        return res["error"]
        
    d = res["data"]
    return f"**{d['recommendation'].upper()}**: {d['recommendation_reason']}"

