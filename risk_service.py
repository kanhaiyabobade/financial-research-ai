"""
risk_service.py

Deterministic portfolio diversification and concentration heuristics.
"""
from typing import List, Dict, Any, Optional


def analyze_portfolio_holdings(priced_holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    priced_holdings: list of holdings where each item has at least:
      - symbol
      - cur_value (float)
      - company
      - sector (optional)

    Returns a dict with diversification score, statuses, concentrations, and intermediate metrics.
    """
    total = sum(h.get("cur_value", 0) for h in priced_holdings)
    if total <= 0 or not priced_holdings:
        return {
            "num_holdings": len(priced_holdings),
            "diversification_score": None,
            "diversification_status": "Unassessed",
            "concentration_status": "Unassessed",
            "largest_holding_pct": None,
            "top_3_pct": None,
            "largest_sector_pct": None,
        }

    # compute allocations
    allocs = sorted([(h["symbol"], h.get("cur_value", 0)) for h in priced_holdings], key=lambda x: x[1], reverse=True)
    alloc_pcts = [(s, v / total * 100) for s, v in allocs]
    largest_pct = alloc_pcts[0][1]
    top3_pct = sum(p for _, p in alloc_pcts[:3])

    # sector aggregation when available
    sector_map = {}
    for h in priced_holdings:
        sec = h.get("sector")
        if not sec:
            continue
        sector_map.setdefault(sec, 0)
        sector_map[sec] += h.get("cur_value", 0)

    largest_sector_pct = None
    if sector_map:
        largest_sector_val = max(sector_map.values())
        largest_sector_pct = largest_sector_val / total * 100

    # Heuristic scoring (explicit thresholds)
    # Base score
    score = 100.0

    # Holdings count penalty
    n = len(priced_holdings)
    if n < 5:
        score -= 30  # Very concentrated due to few holdings
    elif n < 10:
        score -= 15

    # Largest holding penalty (threshold 30%)
    if largest_pct > 30:
        score -= (largest_pct - 30) * 0.8

    # Top 3 holdings penalty (threshold 60%)
    if top3_pct > 60:
        score -= (top3_pct - 60) * 0.5

    # Sector concentration penalty (threshold 40%)
    if largest_sector_pct and largest_sector_pct > 40:
        score -= (largest_sector_pct - 40) * 0.6

    # Bound and round
    score = max(0.0, min(100.0, score))
    score_rounded = round(score)

    # Status mapping
    if score_rounded >= 70:
        status = "Good"
    elif score_rounded >= 40:
        status = "Moderate"
    else:
        status = "Poor"

    # Concentration
    if largest_pct < 25:
        conc = "Low"
    elif largest_pct < 50:
        conc = "Moderate"
    else:
        conc = "High"

    return {
        "num_holdings": n,
        "diversification_score": score_rounded,
        "diversification_status": status,
        "concentration_status": conc,
        "largest_holding_pct": round(largest_pct, 2),
        "top_3_pct": round(top3_pct, 2),
        "largest_sector_pct": round(largest_sector_pct, 2) if largest_sector_pct is not None else None,
        "sector_breakdown": {k: round(v / total * 100, 2) for k, v in sector_map.items()} if sector_map else {},
    }
