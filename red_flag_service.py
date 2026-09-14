import os
from typing import Dict, Any, List, Optional
from gemini_service import test_gemini_connection, analyze_drhp_structured

def generate_red_flags(text: str, pages: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Analyzes DRHP text and identifies major investment risks and forensic red flags.
    Returns markdown formatted text.
    """
    health = test_gemini_connection()
    if not health["success"]:
        return f"Red Flag Analysis is unavailable: {health['error']}"

    result = analyze_drhp_structured(text, pages=pages)
    if not result["success"] or not result["data"]:
        return f"Red Flag Analysis is unavailable: {result.get('error', 'Processing failed')}"

    flags = result["data"].get("red_flags", [])
    if not flags:
        return "No major critical forensic red flags identified in extracted DRHP sections."

    out = ["### 🚨 Forensic Red Flag Analysis\n"]
    for idx, rf in enumerate(flags, 1):
        sev = rf.get("severity", "Medium")
        badge = "🔴 High Risk" if sev == "High" else ("🟡 Moderate Risk" if sev == "Medium" else "🔵 Low Risk")
        cat = rf.get("category", "General Operational Risk")
        title = rf.get("title", f"Risk Factor #{idx}")
        explanation = rf.get("explanation", "")

        ev = rf.get("evidence")
        p_num = None
        ev_text = ""
        if isinstance(ev, dict):
            p_num = ev.get("page")
            ev_text = ev.get("text", "")
        elif isinstance(ev, str):
            ev_text = ev

        p_str = f"DRHP Page {p_num}" if p_num else "Page location unavailable"

        out.append(f"#### {idx}. {title} [{badge}]")
        out.append(f"- **Category**: {cat}")
        out.append(f"- **Explanation**: {explanation}")
        out.append(f"- **Evidence Source**: {p_str}")
        if ev_text:
            out.append(f"- **Evidence Text**: *\"{ev_text}\"*\n")
        else:
            out.append("")

    return "\n".join(out)

def analyze_red_flags_structured(text: str, pages: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Returns structured list of red flags with title, severity, category, explanation, evidence.
    """
    health = test_gemini_connection()
    if not health["success"]:
        return []

    result = analyze_drhp_structured(text, pages=pages)
    if not result["success"] or not result["data"]:
        return []

    return result["data"].get("red_flags", [])