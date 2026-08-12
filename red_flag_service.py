import os
from typing import Dict, Any, List
from gemini_service import ensure_gemini_configured, analyze_drhp_structured

def generate_red_flags(text: str) -> str:
    """
    Analyzes a DRHP text and identifies major investment risks and red flags.
    Delegates to the structured analysis in gemini_service to ensure proper API configuration.
    """
    key = ensure_gemini_configured()
    if not key:
        return "Gemini API key is not configured. Please add GEMINI_API_KEY to your .env file."

    result = analyze_drhp_structured(text)
    if not result["success"]:
        return result["error"]

    flags = result["data"].get("red_flags", [])
    if not flags:
        return "No major critical red flags identified in the extracted sections."

    out = ["### ⚠️ Forensic Red Flag Analysis\n"]
    for idx, rf in enumerate(flags, 1):
        sev = rf.get("severity", "Medium")
        badge = "🔴 High Risk" if sev == "High" else ("🟡 Moderate Risk" if sev == "Medium" else "🔵 Low Risk")
        cat = rf.get("category", "Operational")
        out.append(f"#### {idx}. {rf['title']} [{badge}]")
        out.append(f"**Category**: {cat}")
        out.append(f"**Evidence & Details**: {rf['evidence']}\n")

    return "\n".join(out)

def analyze_red_flags_structured(text: str) -> List[Dict[str, Any]]:
    """
    Returns structured list of red flags with title, severity, evidence, category.
    """
    key = ensure_gemini_configured()
    if not key:
        return []

    result = analyze_drhp_structured(text)
    if not result["success"]:
        return []

    return result["data"].get("red_flags", [])