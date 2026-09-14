import re
from typing import Dict, Any, List, Optional, Tuple

def parse_number_from_string(val: Any) -> Optional[float]:
    """
    Safely parses a numerical float value from financial string disclosures.
    Handles currency symbols (₹, $), commas (1,250.5), scale suffixes (Cr, Lakhs, Million, Billion, %),
    and negative indicators (losses in parentheses or minus signs).
    Returns None if parsing is impossible.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip().lower()
    if not s or s in ["null", "none", "n/a", "-", "--", "nil", "na"]:
        return None

    # Check for negative indication: (120) or -120 or loss
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()
    elif s.startswith("-"):
        is_negative = True
        s = s[1:].strip()
    elif "loss" in s:
        is_negative = True

    # Extract numerical digits and decimal point
    clean_str = re.sub(r"[^\d\.]", "", s)
    if not clean_str:
        return None

    try:
        num = float(clean_str)
        if is_negative:
            num = -num

        # Apply multiplier scaling if present in text
        if "lakh" in s or "lacs" in s:
            num = num / 100.0  # Scale Lakhs to Cr standard if needed or keep raw
        elif "billion" in s:
            num = num * 100.0  # Scale Billion to Cr
        elif "million" in s:
            num = num * 0.1

        return num
    except (ValueError, TypeError):
        return None

def normalize_multi_period_facts(financial_facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalizes raw extracted financial facts into structured multi-period series.
    Structures facts by metric name with ordered periods:
    {
      "revenue": {
        "metric": "Revenue",
        "unit": "INR Cr",
        "periods": [
          {"year": "FY23", "value": 1000.0, "raw_val": "1,000 Cr", "source_page": 127, "evidence_text": "..."},
          {"year": "FY24", "value": 1250.0, "raw_val": "1,250 Cr", "source_page": 127, "evidence_text": "..."}
        ]
      }
    }
    """
    structured: Dict[str, Any] = {}

    for f in financial_facts:
        if not isinstance(f, dict):
            continue

        metric_name = str(f.get("metric") or "").strip()
        if not metric_name:
            continue

        metric_key = metric_name.lower().replace(" ", "_")

        # Check if item contains multi-year 'periods' array
        periods_raw = f.get("periods")
        periods = []

        if isinstance(periods_raw, list) and len(periods_raw) > 0:
            for p in periods_raw:
                if isinstance(p, dict):
                    year = str(p.get("year") or p.get("period") or "").strip()
                    val_raw = p.get("value")
                    num_val = parse_number_from_string(val_raw)
                    p_num = p.get("source_page") or f.get("source_page")
                    try:
                        p_num = int(p_num) if p_num is not None else None
                    except (ValueError, TypeError):
                        p_num = None

                    periods.append({
                        "year": year or "Period",
                        "value": num_val,
                        "raw_value": str(val_raw) if val_raw is not None else "N/A",
                        "source_page": p_num,
                        "evidence_text": str(p.get("evidence_text") or f.get("evidence_text") or "")
                    })
        else:
            # Single period fact
            val_raw = f.get("value")
            num_val = parse_number_from_string(val_raw)
            p_num = f.get("source_page")
            try:
                p_num = int(p_num) if p_num is not None else None
            except (ValueError, TypeError):
                p_num = None

            period_yr = str(f.get("period") or "Latest").strip()
            periods.append({
                "year": period_yr,
                "value": num_val,
                "raw_value": str(val_raw) if val_raw is not None else "N/A",
                "source_page": p_num,
                "evidence_text": str(f.get("evidence_text") or "")
            })

        # Sort periods if years match FY pattern
        def sort_key(p_item):
            yr = p_item["year"].upper()
            match = re.search(r"(\d{2,4})", yr)
            if match:
                return int(match.group(1))
            return 0

        periods.sort(key=sort_key)

        structured[metric_key] = {
            "metric": metric_name,
            "unit": f.get("unit") or "INR Cr",
            "periods": periods
        }

    return structured

def calculate_financial_ratios(normalized_facts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes financial ratios deterministically in Python:
    1. Revenue Growth %
    2. Profit Growth %
    3. Profit Margin %
    4. Debt-to-Equity
    5. Return on Equity (ROE) %
    6. Return on Capital Employed (ROCE) %
    7. Operating Cash Flow Trend
    8. Reported EPS
    """
    def get_latest_and_prev(metric_key: str) -> Tuple[Optional[float], Optional[float], Optional[int], Optional[str], Optional[str], Optional[str]]:
        data = normalized_facts.get(metric_key, {})
        periods = data.get("periods", [])
        valid_periods = [p for p in periods if p.get("value") is not None]

        if not valid_periods:
            return None, None, None, None, None, None

        latest_p = valid_periods[-1]
        prev_p = valid_periods[-2] if len(valid_periods) >= 2 else None

        latest_val = latest_p["value"]
        prev_val = prev_p["value"] if prev_p else None
        p_num = latest_p.get("source_page")
        ev_text = latest_p.get("evidence_text")
        latest_yr = latest_p.get("year")
        prev_yr = prev_p.get("year") if prev_p else None

        return latest_val, prev_val, p_num, ev_text, latest_yr, prev_yr

    # Extract primary metrics
    rev_latest, rev_prev, rev_page, rev_ev, rev_yr_latest, rev_yr_prev = get_latest_and_prev("revenue")
    profit_latest, profit_prev, profit_page, profit_ev, p_yr_latest, p_yr_prev = get_latest_and_prev("net_profit")
    debt_latest, _, debt_page, debt_ev, _, _ = get_latest_and_prev("total_debt")
    equity_latest, _, equity_page, equity_ev, _, _ = get_latest_and_prev("shareholders'_equity")
    if equity_latest is None:
        equity_latest, _, equity_page, equity_ev, _, _ = get_latest_and_prev("net_worth")
    
    ebitda_latest, _, ebitda_page, ebitda_ev, _, _ = get_latest_and_prev("ebitda")
    ocf_latest, ocf_prev, ocf_page, ocf_ev, ocf_yr_latest, ocf_yr_prev = get_latest_and_prev("operating_cash_flow")
    eps_latest, _, eps_page, eps_ev, _, _ = get_latest_and_prev("eps")
    assets_latest, _, assets_page, assets_ev, _, _ = get_latest_and_prev("total_assets")
    liab_latest, _, liab_page, liab_ev, _, _ = get_latest_and_prev("total_liabilities")

    # 1. Revenue Growth %
    rev_growth_pct = None
    rev_growth_reason = ""
    if rev_latest is not None and rev_prev is not None:
        if rev_prev > 0:
            rev_growth_pct = round(((rev_latest - rev_prev) / rev_prev) * 100.0, 2)
            rev_growth_reason = f"Revenue grew from {rev_prev} in {rev_yr_prev} to {rev_latest} in {rev_yr_latest} ({rev_growth_pct:+.2f}%)."
        elif rev_prev == 0:
            rev_growth_reason = f"Previous revenue in {rev_yr_prev} was zero; standard growth percentage calculation is not meaningful."
        else:
            rev_growth_reason = f"Previous revenue in {rev_yr_prev} was negative ({rev_prev}); growth percentage calculation is not meaningful."
    else:
        rev_growth_reason = "Insufficient multi-period revenue disclosures available to compute growth percentage."

    # 2. Profit Growth %
    profit_growth_pct = None
    profit_growth_reason = ""
    if profit_latest is not None and profit_prev is not None:
        if profit_prev > 0:
            profit_growth_pct = round(((profit_latest - profit_prev) / profit_prev) * 100.0, 2)
            profit_growth_reason = f"Net profit expanded from {profit_prev} in {p_yr_prev} to {profit_latest} in {p_yr_latest} ({profit_growth_pct:+.2f}%)."
        elif profit_prev < 0 and profit_latest > 0:
            profit_growth_reason = f"Company turned around from net loss of {profit_prev} in {p_yr_prev} to net profit of {profit_latest} in {p_yr_latest}."
        elif profit_prev < 0 and profit_latest < 0:
            profit_growth_reason = f"Company reported consecutive net losses ({profit_prev} in {p_yr_prev} vs {profit_latest} in {p_yr_latest}); standard growth % is not meaningful."
        else:
            profit_growth_reason = "Previous net profit was zero; growth percentage calculation is not meaningful."
    else:
        profit_growth_reason = "Insufficient multi-period net profit disclosures available to compute growth percentage."

    # 3. Profit Margin %
    profit_margin_pct = None
    if profit_latest is not None and rev_latest is not None and rev_latest > 0:
        profit_margin_pct = round((profit_latest / rev_latest) * 100.0, 2)

    # 4. Debt-to-Equity
    debt_equity_ratio = None
    if debt_latest is not None and equity_latest is not None and equity_latest > 0:
        debt_equity_ratio = round(debt_latest / equity_latest, 2)

    # 5. Return on Equity (ROE) %
    roe_pct = None
    if profit_latest is not None and equity_latest is not None and equity_latest > 0:
        roe_pct = round((profit_latest / equity_latest) * 100.0, 2)

    # 6. Return on Capital Employed (ROCE) %
    roce_pct = None
    ebit_val = ebitda_latest if ebitda_latest is not None else profit_latest
    if ebit_val is not None and assets_latest is not None and liab_latest is not None:
        capital_employed = assets_latest - liab_latest
        if capital_employed > 0:
            roce_pct = round((ebit_val / capital_employed) * 100.0, 2)

    # 7. Operating Cash Flow Trajectory
    ocf_trend = "N/A"
    if ocf_latest is not None and ocf_prev is not None:
        if ocf_latest > ocf_prev and ocf_latest > 0:
            ocf_trend = "Improving & Positive"
        elif ocf_latest < ocf_prev and ocf_latest > 0:
            ocf_trend = "Positive but Moderating"
        elif ocf_latest < 0:
            ocf_trend = "Negative Operating Cash Flow"
        else:
            ocf_trend = "Stable"
    elif ocf_latest is not None:
        ocf_trend = "Positive" if ocf_latest > 0 else "Negative"

    return {
        "revenue_growth_pct": rev_growth_pct,
        "revenue_growth_reason": rev_growth_reason,
        "profit_growth_pct": profit_growth_pct,
        "profit_growth_reason": profit_growth_reason,
        "profit_margin_pct": profit_margin_pct,
        "debt_equity_ratio": debt_equity_ratio,
        "roe_pct": roe_pct,
        "roce_pct": roce_pct,
        "operating_cash_flow_latest": ocf_latest,
        "operating_cash_flow_trend": ocf_trend,
        "eps_reported": eps_latest,
        "source_citations": {
            "revenue": {"page": rev_page, "evidence": rev_ev},
            "profit": {"page": profit_page, "evidence": profit_ev},
            "debt": {"page": debt_page, "evidence": debt_ev},
            "equity": {"page": equity_page, "evidence": equity_ev},
            "ocf": {"page": ocf_page, "evidence": ocf_ev},
            "eps": {"page": eps_page, "evidence": eps_ev}
        }
    }

def analyze_financial_trends(normalized_facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Identifies evidence-based multi-year financial trends across reported periods.
    """
    trends = []

    for metric_key, data in normalized_facts.items():
        metric_name = data.get("metric", metric_key.capitalize())
        periods = [p for p in data.get("periods", []) if p.get("value") is not None]

        if len(periods) < 2:
            continue

        vals = [p["value"] for p in periods]
        years = [p["year"] for p in periods]
        p_page = periods[-1].get("source_page")
        p_ev = periods[-1].get("evidence_text")

        is_increasing = all(vals[i] < vals[i+1] for i in range(len(vals)-1))
        is_decreasing = all(vals[i] > vals[i+1] for i in range(len(vals)-1))

        trajectory_str = " → ".join([f"{y}: {v}" for y, v in zip(years, vals)])

        if is_increasing:
            trends.append({
                "metric": metric_name,
                "direction": "Increasing",
                "trajectory": trajectory_str,
                "source_page": p_page,
                "evidence_text": p_ev or f"{metric_name} grew consistently across reported periods ({trajectory_str})."
            })
        elif is_decreasing:
            trends.append({
                "metric": metric_name,
                "direction": "Decreasing",
                "trajectory": trajectory_str,
                "source_page": p_page,
                "evidence_text": p_ev or f"{metric_name} declined across reported periods ({trajectory_str})."
            })
        else:
            trends.append({
                "metric": metric_name,
                "direction": "Fluctuating",
                "trajectory": trajectory_str,
                "source_page": p_page,
                "evidence_text": p_ev or f"{metric_name} fluctuated across reported periods ({trajectory_str})."
            })

    return trends

def generate_financial_health_interpretations(ratios: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generates analytical interpretations grounded strictly in calculated Python ratio metrics.
    Uses status labels: Positive | Neutral | Concern.
    """
    interpretations = []

    # 1. Revenue Growth
    rg = ratios.get("revenue_growth_pct")
    if rg is not None:
        if rg >= 15.0:
            interpretations.append({
                "metric": "Revenue Growth",
                "value": f"+{rg:.1f}%",
                "status": "Positive",
                "explanation": f"Strong top-line expansion rate of {rg:.1f}% year-over-year.",
                "source_page": ratios["source_citations"]["revenue"]["page"]
            })
        elif rg > 0:
            interpretations.append({
                "metric": "Revenue Growth",
                "value": f"+{rg:.1f}%",
                "status": "Neutral",
                "explanation": f"Moderate top-line revenue growth rate of {rg:.1f}%.",
                "source_page": ratios["source_citations"]["revenue"]["page"]
            })
        else:
            interpretations.append({
                "metric": "Revenue Growth",
                "value": f"{rg:.1f}%",
                "status": "Concern",
                "explanation": f"Top-line revenue declined by {abs(rg):.1f}% over reported period.",
                "source_page": ratios["source_citations"]["revenue"]["page"]
            })

    # 2. Profit Margin
    pm = ratios.get("profit_margin_pct")
    if pm is not None:
        if pm >= 12.0:
            interpretations.append({
                "metric": "Profit Margin",
                "value": f"{pm:.1f}%",
                "status": "Positive",
                "explanation": f"Healthy net profit margin of {pm:.1f}%.",
                "source_page": ratios["source_citations"]["profit"]["page"]
            })
        elif pm > 0:
            interpretations.append({
                "metric": "Profit Margin",
                "value": f"{pm:.1f}%",
                "status": "Neutral",
                "explanation": f"Thin net profit margin of {pm:.1f}%.",
                "source_page": ratios["source_citations"]["profit"]["page"]
            })
        else:
            interpretations.append({
                "metric": "Profit Margin",
                "value": f"{pm:.1f}%",
                "status": "Concern",
                "explanation": f"Unprofitable operations with negative net margin of {pm:.1f}%.",
                "source_page": ratios["source_citations"]["profit"]["page"]
            })

    # 3. Debt-to-Equity
    de = ratios.get("debt_equity_ratio")
    if de is not None:
        if de <= 0.8:
            interpretations.append({
                "metric": "Debt-to-Equity",
                "value": f"{de:.2f}",
                "status": "Positive",
                "explanation": f"Conservative balance sheet leverage with Debt/Equity of {de:.2f}.",
                "source_page": ratios["source_citations"]["debt"]["page"]
            })
        elif de <= 2.0:
            interpretations.append({
                "metric": "Debt-to-Equity",
                "value": f"{de:.2f}",
                "status": "Neutral",
                "explanation": f"Moderate financial leverage with Debt/Equity of {de:.2f}.",
                "source_page": ratios["source_citations"]["debt"]["page"]
            })
        else:
            interpretations.append({
                "metric": "Debt-to-Equity",
                "value": f"{de:.2f}",
                "status": "Concern",
                "explanation": f"Elevated balance sheet leverage with Debt/Equity of {de:.2f}.",
                "source_page": ratios["source_citations"]["debt"]["page"]
            })

    # 4. Operating Cash Flow
    ocf_val = ratios.get("operating_cash_flow_latest")
    ocf_trend = ratios.get("operating_cash_flow_trend")
    if ocf_val is not None:
        if ocf_val > 0:
            interpretations.append({
                "metric": "Operating Cash Flow",
                "value": f"₹{ocf_val:.1f} Cr",
                "status": "Positive",
                "explanation": f"Positive operating cash flow generation ({ocf_trend}).",
                "source_page": ratios["source_citations"]["ocf"]["page"]
            })
        else:
            interpretations.append({
                "metric": "Operating Cash Flow",
                "value": f"₹{ocf_val:.1f} Cr",
                "status": "Concern",
                "explanation": f"Negative operating cash flow of ₹{ocf_val:.1f} Cr indicating cash burn risk.",
                "source_page": ratios["source_citations"]["ocf"]["page"]
            })

    return interpretations
