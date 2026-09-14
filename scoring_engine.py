from typing import Dict, Any, List, Optional

def calculate_ipo_score(
    financial_facts: List[Dict[str, Any]],
    red_flags: List[Dict[str, Any]],
    ipo_details: List[str],
    business_summary: str,
    strengths: List[str],
    growth_opportunities: List[str],
    ratios: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Computes a transparent, deterministic IPO investment score out of 100
    divided across 5 distinct categories:
    1. Financial Health (Max 30)
    2. Business Quality (Max 20)
    3. Growth Potential (Max 20)
    4. IPO Fundamentals (Max 15)
    5. Risk Profile (Max 15)
    """
    def get_fact(metric_name: str) -> Optional[Dict[str, Any]]:
        for f in financial_facts:
            m = str(f.get("metric") or "").lower()
            if metric_name.lower() in m:
                if f.get("value") is not None and str(f.get("value")).strip() != "":
                    return f
        return None

    # -------------------------------------------------------------------------
    # 1. Financial Health (Max 30 Points)
    # -------------------------------------------------------------------------
    fh_score = 0.0
    fh_reasons = []

    if ratios and isinstance(ratios, dict):
        rg_pct = ratios.get("revenue_growth_pct")
        pm_pct = ratios.get("profit_margin_pct")
        de_ratio = ratios.get("debt_equity_ratio")
        ocf_latest = ratios.get("operating_cash_flow_latest")
        ocf_trend = ratios.get("operating_cash_flow_trend")
        src_cits = ratios.get("source_citations", {})

        # Profitability & Margins (Max 7.5 pts)
        if pm_pct is not None:
            if pm_pct >= 12.0:
                fh_score += 7.5
                fh_reasons.append({"text": f"Strong net profit margin of {pm_pct:.1f}%", "source_page": src_cits.get("profit", {}).get("page"), "type": "positive"})
            elif pm_pct > 0:
                fh_score += 5.5
                fh_reasons.append({"text": f"Positive net profit margin of {pm_pct:.1f}%", "source_page": src_cits.get("profit", {}).get("page"), "type": "positive"})
            else:
                fh_score += 1.0
                fh_reasons.append({"text": f"Unprofitable / Negative profit margin of {pm_pct:.1f}%", "source_page": src_cits.get("profit", {}).get("page"), "type": "risk"})
        else:
            fh_score += 4.0

        # Revenue Growth (Max 7.5 pts)
        if rg_pct is not None:
            if rg_pct >= 15.0:
                fh_score += 7.5
                fh_reasons.append({"text": f"High top-line revenue growth rate (+{rg_pct:.1f}%)", "source_page": src_cits.get("revenue", {}).get("page"), "type": "positive"})
            elif rg_pct > 0:
                fh_score += 5.5
                fh_reasons.append({"text": f"Positive revenue growth (+{rg_pct:.1f}%)", "source_page": src_cits.get("revenue", {}).get("page"), "type": "positive"})
            else:
                fh_score += 1.5
                fh_reasons.append({"text": f"Top-line revenue contraction ({rg_pct:.1f}%)", "source_page": src_cits.get("revenue", {}).get("page"), "type": "risk"})
        else:
            fh_score += 4.0

        # Debt / Equity Leverage (Max 7.5 pts)
        if de_ratio is not None:
            if de_ratio <= 0.8:
                fh_score += 7.5
                fh_reasons.append({"text": f"Low balance sheet leverage (Debt/Equity {de_ratio:.2f})", "source_page": src_cits.get("debt", {}).get("page"), "type": "positive"})
            elif de_ratio <= 2.0:
                fh_score += 5.0
                fh_reasons.append({"text": f"Moderate balance sheet leverage (Debt/Equity {de_ratio:.2f})", "source_page": src_cits.get("debt", {}).get("page"), "type": "neutral"})
            else:
                fh_score += 1.5
                fh_reasons.append({"text": f"Elevated balance sheet leverage (Debt/Equity {de_ratio:.2f})", "source_page": src_cits.get("debt", {}).get("page"), "type": "risk"})
        else:
            fh_score += 4.5

        # Operating Cash Flow (Max 7.5 pts)
        if ocf_latest is not None:
            if ocf_latest > 0:
                fh_score += 7.5
                fh_reasons.append({"text": f"Positive operating cash flow (₹{ocf_latest:.1f} Cr, {ocf_trend})", "source_page": src_cits.get("ocf", {}).get("page"), "type": "positive"})
            else:
                fh_score += 1.0
                fh_reasons.append({"text": f"Negative operating cash flow burn (₹{ocf_latest:.1f} Cr)", "source_page": src_cits.get("ocf", {}).get("page"), "type": "risk"})
        else:
            fh_score += 4.0

    else:
        # Fallback fact-based scoring if ratios object is unavailable
        rev_fact = get_fact("revenue")
        profit_fact = get_fact("profit") or get_fact("net profit")
        debt_fact = get_fact("debt")
        ocf_fact = get_fact("operating cash flow") or get_fact("cash flow")

        if profit_fact:
            p_val_str = str(profit_fact.get("value") or "").lower()
            if "loss" in p_val_str or "-" in p_val_str or "negative" in p_val_str:
                fh_reasons.append({"text": f"Operating loss reported ({profit_fact.get('value')})", "source_page": profit_fact.get("source_page"), "type": "risk"})
                fh_score += 1.0
            else:
                fh_reasons.append({"text": f"Positive net profitability reported ({profit_fact.get('value')})", "source_page": profit_fact.get("source_page"), "type": "positive"})
                fh_score += 7.5
        else:
            fh_score += 4.0

        if rev_fact:
            fh_reasons.append({"text": f"Reported revenue scale ({rev_fact.get('value')})", "source_page": rev_fact.get("source_page"), "type": "positive"})
            fh_score += 7.5
        else:
            fh_score += 4.0

        if debt_fact:
            d_val_str = str(debt_fact.get("value") or "").lower()
            if "high" in d_val_str or "heavy" in d_val_str:
                fh_reasons.append({"text": f"Significant debt burden ({debt_fact.get('value')})", "source_page": debt_fact.get("source_page"), "type": "risk"})
                fh_score += 2.0
            else:
                fh_reasons.append({"text": f"Manageable debt balance reported ({debt_fact.get('value')})", "source_page": debt_fact.get("source_page"), "type": "positive"})
                fh_score += 6.0
        else:
            fh_score += 4.5

        if ocf_fact:
            c_val_str = str(ocf_fact.get("value") or "").lower()
            if "negative" in c_val_str or "-" in c_val_str:
                fh_reasons.append({"text": f"Negative operating cash flow ({ocf_fact.get('value')})", "source_page": ocf_fact.get("source_page"), "type": "risk"})
                fh_score += 1.0
            else:
                fh_reasons.append({"text": f"Positive operating cash flow ({ocf_fact.get('value')})", "source_page": ocf_fact.get("source_page"), "type": "positive"})
                fh_score += 6.5
        else:
            fh_score += 4.0

    fh_score = round(min(30.0, max(0.0, fh_score)), 1)


    # -------------------------------------------------------------------------
    # 2. Business Quality (Max 20 Points)
    # -------------------------------------------------------------------------
    bq_score = 12.0
    bq_reasons = []

    if strengths:
        bq_score += min(5.0, len(strengths) * 1.5)
        for s in strengths[:2]:
            bq_reasons.append({
                "text": f"Competitive strength: {s}",
                "source_page": None,
                "type": "positive"
            })

    cust_fact = get_fact("customer concentration")
    if cust_fact:
        c_val = str(cust_fact.get("value") or "").lower()
        if "high" in c_val or "concentration" in c_val or "%" in c_val:
            bq_score -= 3.0
            bq_reasons.append({
                "text": f"Customer concentration risk ({cust_fact.get('value')})",
                "source_page": cust_fact.get("source_page"),
                "type": "risk"
            })
    else:
        bq_reasons.append({
            "text": "Established operational business foundation.",
            "source_page": None,
            "type": "positive"
        })

    bq_score = round(min(20.0, max(0.0, bq_score)), 1)

    # -------------------------------------------------------------------------
    # 3. Growth Potential (Max 20 Points)
    # -------------------------------------------------------------------------
    gp_score = 11.0
    gp_reasons = []

    if growth_opportunities:
        gp_score += min(6.0, len(growth_opportunities) * 2.0)
        for g in growth_opportunities[:2]:
            gp_reasons.append({
                "text": f"Growth catalyst: {g}",
                "source_page": None,
                "type": "positive"
            })
    else:
        gp_reasons.append({
            "text": "Standard market expansion potential.",
            "source_page": None,
            "type": "neutral"
        })

    gp_score = round(min(20.0, max(0.0, gp_score)), 1)

    # -------------------------------------------------------------------------
    # 4. IPO Fundamentals (Max 15 Points)
    # -------------------------------------------------------------------------
    ipo_score_cat = 9.0
    ipo_reasons = []

    ofs_fact = get_fact("offer for sale") or get_fact("ofs")
    fresh_fact = get_fact("fresh issue")

    if fresh_fact:
        ipo_score_cat += 3.0
        ipo_reasons.append({
            "text": f"Fresh issue proceeds capital growth ({fresh_fact.get('value')})",
            "source_page": fresh_fact.get("source_page"),
            "type": "positive"
        })

    if ofs_fact:
        o_val = str(ofs_fact.get("value") or "").lower()
        if "100%" in o_val or "entire" in o_val or "major" in o_val:
            ipo_score_cat -= 2.5
            ipo_reasons.append({
                "text": f"High Offer for Sale (OFS) promoter exit component ({ofs_fact.get('value')})",
                "source_page": ofs_fact.get("source_page"),
                "type": "risk"
            })

    if not ipo_reasons:
        ipo_reasons.append({
            "text": "Standard public issue offering structure.",
            "source_page": None,
            "type": "neutral"
        })

    ipo_score_cat = round(min(15.0, max(0.0, ipo_score_cat)), 1)

    # -------------------------------------------------------------------------
    # 5. Risk Profile (Max 15 Points)
    # -------------------------------------------------------------------------
    # Starts at 15 and deducts based on verified red flags
    risk_cat_score = 15.0
    risk_reasons = []

    if red_flags:
        for rf in red_flags:
            sev = str(rf.get("severity") or "Medium").capitalize()
            p_num = None
            if isinstance(rf.get("evidence"), dict):
                p_num = rf["evidence"].get("page")
            elif rf.get("source_page"):
                p_num = rf.get("source_page")

            if sev == "High":
                risk_cat_score -= 4.0
            elif sev == "Medium":
                risk_cat_score -= 2.0
            else:
                risk_cat_score -= 1.0

            risk_reasons.append({
                "text": f"[{sev.upper()} RISK] {rf.get('title')}: {rf.get('explanation') or rf.get('reason', '')}",
                "source_page": p_num,
                "type": "risk"
            })
    else:
        risk_reasons.append({
            "text": "No high-severity forensic red flags identified in prospect disclosures.",
            "source_page": None,
            "type": "positive"
        })

    risk_cat_score = round(min(15.0, max(0.0, risk_cat_score)), 1)

    # Calculate overall deterministic total out of 100
    overall_total = round(fh_score + bq_score + gp_score + ipo_score_cat + risk_cat_score, 1)

    return {
        "overall_score": overall_total,
        "category_scores": {
            "financial_health": {
                "score": fh_score,
                "max_score": 30.0,
                "reasons": fh_reasons
            },
            "business_quality": {
                "score": bq_score,
                "max_score": 20.0,
                "reasons": bq_reasons
            },
            "growth": {
                "score": gp_score,
                "max_score": 20.0,
                "reasons": gp_reasons
            },
            "ipo_fundamentals": {
                "score": ipo_score_cat,
                "max_score": 15.0,
                "reasons": ipo_reasons
            },
            "risk": {
                "score": risk_cat_score,
                "max_score": 15.0,
                "reasons": risk_reasons
            }
        }
    }
