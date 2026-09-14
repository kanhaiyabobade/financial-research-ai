import pymupdf as fitz
import json
from pdf_processor import extract_pdf_data, find_source_page
from scoring_engine import calculate_ipo_score
from ratio_engine import (
    normalize_multi_period_facts,
    calculate_financial_ratios,
    analyze_financial_trends,
    generate_financial_health_interpretations
)
from gemini_service import analyze_drhp_structured, test_gemini_connection
from ipo_service import save_drhp_report, get_all_reports
from database import init_database

def run_tests():
    print("==================================================")
    print("RUNNING END-TO-END VERIFICATION FOR FINANCIAL ENGINE")
    print("==================================================")

    # 1. Initialize Database
    init_database()
    print("✓ Database initialized.")

    # 2. Test PDF Creation with explicit multi-page DRHP content
    print("\n--- Testing Phase 2: Page-Aware DRHP Extraction ---")
    doc = fitz.open()

    p1 = doc.new_page()
    p1.insert_text((50, 50), "DRAFT RED HERRING PROSPECTUS\nABC TECH LIMITED\nCompany Overview & Business Model\nWe are a leading software company delivering enterprise cloud solutions.")

    p2 = doc.new_page()
    p2.insert_text((50, 50), "FINANCIAL STATEMENTS & HIGHLIGHTS\nRevenue from operations: FY23 Rs 1,000 Cr, FY24 Rs 1,250 Cr.\nNet profit: FY23 Rs 140 Cr, FY24 Rs 180 Cr.\nTotal debt outstanding: Rs 45 Cr.\nShareholders Equity: Rs 300 Cr.\nOperating cash flow: FY23 Rs 120 Cr, FY24 Rs 165 Cr.\nDiluted EPS: Rs 14.50")

    p3 = doc.new_page()
    p3.insert_text((50, 50), "RISK FACTORS & DISCLOSURES\nCustomer Concentration: Our top three customers contributed 68.4% of our total revenue from operations.\nPending Litigation: Ongoing tax dispute of Rs 12 Cr pending before court.")

    pdf_bytes = doc.write()
    doc.close()

    res = extract_pdf_data(pdf_bytes, "test_drhp.pdf")
    assert res["success"] is True, f"PDF extraction failed: {res['error']}"
    assert res["page_count"] == 3, f"Expected 3 pages, got {res['page_count']}"
    assert len(res["pages"]) == 3, f"Expected 3 page records, got {len(res['pages'])}"
    print(f"✓ PDF page extraction successful: {res['page_count']} pages extracted.")

    # 3. Test Ratio Engine & Multi-Period Calculation (Python Arithmetic)
    print("\n--- Testing Ratio Engine & Python Arithmetic ---")
    raw_sample_facts = [
        {
            "metric": "Revenue",
            "unit": "INR Cr",
            "periods": [
                {"year": "FY23", "value": "1000 Cr", "source_page": 2, "evidence_text": "FY23 Rs 1,000 Cr"},
                {"year": "FY24", "value": "1250 Cr", "source_page": 2, "evidence_text": "FY24 Rs 1,250 Cr"}
            ]
        },
        {
            "metric": "Net profit",
            "unit": "INR Cr",
            "periods": [
                {"year": "FY23", "value": "140 Cr", "source_page": 2, "evidence_text": "FY23 Rs 140 Cr"},
                {"year": "FY24", "value": "180 Cr", "source_page": 2, "evidence_text": "FY24 Rs 180 Cr"}
            ]
        },
        {
            "metric": "Total debt",
            "value": "45 Cr",
            "unit": "INR Cr",
            "period": "FY24",
            "source_page": 2,
            "evidence_text": "Total debt: Rs 45 Cr."
        },
        {
            "metric": "Shareholders' Equity",
            "value": "300 Cr",
            "unit": "INR Cr",
            "period": "FY24",
            "source_page": 2,
            "evidence_text": "Shareholders Equity: Rs 300 Cr."
        },
        {
            "metric": "Operating cash flow",
            "unit": "INR Cr",
            "periods": [
                {"year": "FY23", "value": "120 Cr", "source_page": 2, "evidence_text": "FY23 Rs 120 Cr"},
                {"year": "FY24", "value": "165 Cr", "source_page": 2, "evidence_text": "FY24 Rs 165 Cr"}
            ]
        }
    ]

    norm_facts = normalize_multi_period_facts(raw_sample_facts)
    ratios = calculate_financial_ratios(norm_facts)
    trends = analyze_financial_trends(norm_facts)
    interps = generate_financial_health_interpretations(ratios)

    print(f"✓ Revenue Growth %: {ratios['revenue_growth_pct']}% (Expected: +25.0%)")
    print(f"✓ Profit Growth %: {ratios['profit_growth_pct']}% (Expected: +28.57%)")
    print(f"✓ Profit Margin %: {ratios['profit_margin_pct']}% (Expected: 14.4%)")
    print(f"✓ Debt-to-Equity: {ratios['debt_equity_ratio']} (Expected: 0.15)")
    print(f"✓ Return on Equity (ROE): {ratios['roe_pct']}% (Expected: 60.0%)")
    print(f"✓ Operating Cash Flow Trend: {ratios['operating_cash_flow_trend']}")

    assert ratios['revenue_growth_pct'] == 25.0
    assert ratios['profit_growth_pct'] == 28.57
    assert ratios['profit_margin_pct'] == 14.4
    assert ratios['debt_equity_ratio'] == 0.15
    assert len(trends) >= 2
    assert len(interps) >= 3

    # 4. Test Deterministic Scoring Engine with Ratios
    print("\n--- Testing Scoring Engine Integration ---")
    score_result = calculate_ipo_score(
        financial_facts=raw_sample_facts,
        red_flags=[],
        ipo_details=["Fresh Issue: 500 Cr", "OFS: 200 Cr"],
        business_summary="Leading enterprise software company.",
        strengths=["Strong profitability", "High operating margins"],
        growth_opportunities=["Global cloud market expansion"],
        ratios=ratios
    )

    print(f"✓ Calculated Overall Score: {score_result['overall_score']}/100")
    cats = score_result["category_scores"]
    print(f"  - Financial Health: {cats['financial_health']['score']}/30")
    print(f"  - Business Quality: {cats['business_quality']['score']}/20")
    print(f"  - Growth: {cats['growth']['score']}/20")
    print(f"  - IPO Fundamentals: {cats['ipo_fundamentals']['score']}/15")
    print(f"  - Risk: {cats['risk']['score']}/15")

    assert score_result["overall_score"] > 0 and score_result["overall_score"] <= 100

    # 5. Test Gemini Analysis & End-to-End Persistence
    print("\n--- Testing Gemini Analysis & Persistence ---")
    health = test_gemini_connection()
    print(f"Gemini API Health: {health['status']} ({health.get('model')})")

    if health["success"]:
        ai_res = analyze_drhp_structured(res["text"], pages=res["pages"])
        assert ai_res["success"] is True, f"AI Analysis failed: {ai_res.get('error')}"
        d = ai_res["data"]
        print(f"✓ AI Analysis succeeded for {d.get('company_name')}")
        print(f"  - Recommendation: {d.get('recommendation')}")
        print(f"  - Risk Level: {d.get('risk_level')}")
        print(f"  - Financial Ratios Calculated: {bool(d.get('financial_ratios'))}")

        saved_ok = save_drhp_report(
            company_name=d.get("company_name", "ABC Tech Limited"),
            summary=d.get("business_summary", ""),
            red_flags=json.dumps(d.get("red_flags", [])),
            ipo_score=d.get("investment_score"),
            recommendation=d.get("recommendation"),
            industry=d.get("industry"),
            risk_level=d.get("risk_level"),
            confidence=d.get("confidence"),
            structured_data=d
        )
        assert saved_ok is True
        print("✓ Successfully saved report with ratios & trends to SQLite database.")

        reports = get_all_reports()
        assert len(reports) > 0
        latest = reports[0]
        print(f"✓ Retrieved report ID {latest['id']} for {latest['company_name']}.")

    print("\n==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
