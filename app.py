import os
import re
import json
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv

# Load environment variables FIRST before importing any services
load_dotenv(override=True)

# Import services maintaining strict architectural separation
from stock_service import get_stock_info, get_stock_history
from news_service import get_stock_news, NewsAPIError
from pdf_processor import extract_pdf_data
from ipo_service import save_drhp_report, get_all_reports
from gemini_service import (
    analyze_drhp_structured,
    test_gemini_connection
)
from red_flag_service import analyze_red_flags_structured
from database import init_database
from portfolio_service import (
    add_holding,
    get_all_holdings,
    get_holding_by_id,
    update_holding,
    delete_holding,
    get_portfolio_market_data,
)
from watchlist_service import (
    add_watchlist_item,
    remove_watchlist_item,
    get_watchlist,
)
from alert_service import (
    add_alert,
    get_alerts,
    remove_alert,
)
from risk_service import analyze_portfolio_holdings

# Set page configuration with a modern, high-contrast theme
st.set_page_config(
    page_title="Financial Research AI: Stock Analysis & IPO Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ensure database and migrations are applied on startup
try:
    init_database()
except Exception:
    pass

# Custom Premium Styling
st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(90deg, #1e3c72, #2a5298, #00bcd4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.2rem;
            font-family: 'Inter', system-ui, sans-serif;
        }
        .sub-header {
            font-size: 1.05rem;
            color: #718096;
            margin-bottom: 1.5rem;
            font-family: 'Inter', system-ui, sans-serif;
        }
        .hero-card {
            background: linear-gradient(135deg, rgba(255,255,255,0.95), rgba(240,244,248,0.95));
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 4px 14px rgba(0,0,0,0.06);
            border: 1px solid rgba(0,0,0,0.08);
            text-align: center;
            height: 100%;
        }
        @media (prefers-color-scheme: dark) {
            .hero-card {
                background: linear-gradient(135deg, #1e2430, #141824);
                border: 1px solid rgba(255,255,255,0.1);
                box-shadow: 0 4px 14px rgba(0,0,0,0.4);
            }
        }
        .news-article {
            padding: 1rem;
            border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        }
        .news-headline {
            font-size: 1.05rem;
            font-weight: 600;
            color: #00bcd4;
            text-decoration: none;
        }
        .news-headline:hover {
            text-decoration: underline;
        }
        .news-meta {
            font-size: 0.85rem;
            color: #718096;
            margin-top: 0.25rem;
        }
        .sentiment-badge {
            display: inline-block;
            padding: 0.2rem 0.5rem;
            font-size: 0.7rem;
            font-weight: 700;
            border-radius: 4px;
            text-transform: uppercase;
            margin-right: 0.5rem;
        }
        .sentiment-positive { background-color: #2e7d32; color: #ffffff; }
        .sentiment-neutral { background-color: #757575; color: #ffffff; }
        .sentiment-negative { background-color: #c62828; color: #ffffff; }
        .severity-high { background-color: rgba(198, 40, 40, 0.15); color: #d32f2f; border: 1px solid #d32f2f; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.8rem; }
        .severity-medium { background-color: rgba(255, 152, 0, 0.15); color: #f57c00; border: 1px solid #f57c00; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.8rem; }
        .severity-low { background-color: rgba(25, 118, 210, 0.15); color: #1976d2; border: 1px solid #1976d2; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.8rem; }
        .status-badge-healthy { color: #2e7d32; font-weight: 700; }
        .status-badge-unconfigured { color: #f57c00; font-weight: 700; }
        .status-badge-failed { color: #c62828; font-weight: 700; }
    </style>
""", unsafe_allow_html=True)

# Helper formatting functions
def format_market_cap(val: Optional[float], currency: str) -> str:
    if val is None:
        return "N/A"
    if currency == "INR":
        if val >= 10**7:
            return f"₹{val / 10**7:,.2f} Cr"
        elif val >= 10**5:
            return f"₹{val / 10**5:,.2f} Lakhs"
        return f"₹{val:,.2f}"
    else:
        symbol = "$" if currency == "USD" else f"{currency} "
        if val >= 10**12:
            return f"{symbol}{val / 10**12:,.2f} T"
        elif val >= 10**9:
            return f"{symbol}{val / 10**9:,.2f} B"
        elif val >= 10**6:
            return f"{symbol}{val / 10**6:,.2f} M"
        return f"{symbol}{val:,.2f}"

def format_price(val: Optional[float], currency: str) -> str:
    if val is None:
        return "N/A"
    symbol = "₹" if currency == "INR" else ("$" if currency == "USD" else f"{currency} ")
    return f"{symbol}{val:,.2f}"

def format_pe(val: Optional[float]) -> str:
    return f"{val:,.2f}" if val is not None else "N/A"

def format_volume(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    if val >= 10**6:
        return f"{val / 10**6:,.2f} M"
    elif val >= 10**3:
        return f"{val / 10**3:,.2f} K"
    return f"{val:,.0f}"

def format_percentage(val: Optional[float]) -> str:
    return f"{val:.2f}%" if val is not None else "N/A"

def format_beta(val: Optional[float]) -> str:
    return f"{val:.2f}" if val is not None else "N/A"

# Sidebar Navigation & System Health Check
st.sidebar.markdown("<h2 style='font-family: \"Inter\", sans-serif; font-weight: 700;'>Navigation</h2>", unsafe_allow_html=True)
page = st.sidebar.radio(
    "Select Module:",
    [
        "🏠 Market Overview",
        "📈 Stock Dashboard",
        "🚀 IPO Intelligence",
        "💼 Portfolio Intelligence",
        "🛡️ Risk Intelligence",
        "🔔 Watchlist",
        "📰 Market Intelligence",
        "🧠 AI Research Assistant",
        "🏭 Sector Intelligence",
        "📑 Research Reports",
    ],
    index=2,
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🤖 System Diagnostics")

# Perform internal Gemini Health Check
gemini_health = test_gemini_connection()
if gemini_health["status"] == "HEALTHY":
    st.sidebar.success(f"🟢 **Gemini AI Operational**\n\nModel: `{gemini_health['model']}`")
elif gemini_health["status"] == "UNCONFIGURED":
    st.sidebar.warning("🟡 **Gemini Not Configured**\n\nAdd `GEMINI_API_KEY` to `.env` file to enable AI analysis.")
else:
    st.sidebar.error(f"🔴 **Gemini Request Failed**\n\n{gemini_health['error']}")

st.sidebar.markdown("---")
st.sidebar.info("💡 **Financial Research AI Platform**\n\nAI-powered Prospectus Parsing, Equity Intelligence & Technical Analysis.")

# ==============================================================================
# 🚀 MODULE 1: IPO INTELLIGENCE
# ==============================================================================
if page == "🚀 IPO Intelligence":
    st.markdown("<h1 class='main-header'>🚀 IPO Intelligence Platform</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Draft Red Herring Prospectus (DRHP) forensic analysis, investment scoring & risk detection.</p>", unsafe_allow_html=True)

    # Document Uploader Container
    with st.container(border=True):
        st.markdown("### 📄 DRHP Document Processing Engine")
        uploaded_file = st.file_uploader(
            "Upload Draft Red Herring Prospectus (DRHP) PDF:",
            type=["pdf"],
            help="Upload official DRHP file registered with regulators (SEBI, SEC, etc.)."
        )

    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        filename = uploaded_file.name
        analysis_key = f"drhp_analysis_v3_{filename}_{len(file_bytes)}"

        if analysis_key not in st.session_state:
            with st.spinner("Extracting DRHP sections and generating forensic AI analysis..."):
                pdf_result = extract_pdf_data(file_bytes, filename)

                if not pdf_result["success"]:
                    st.session_state[analysis_key] = {
                        "success": False,
                        "filename": filename,
                        "error": pdf_result["error"],
                        "data": None
                    }
                else:
                    text_content = pdf_result["text"]
                    pages_content = pdf_result.get("pages", [])
                    ai_result = analyze_drhp_structured(text_content, pages=pages_content)

                    st.session_state[analysis_key] = {
                        "success": ai_result["success"],
                        "filename": filename,
                        "page_count": pdf_result["page_count"],
                        "char_count": pdf_result["char_count"],
                        "pages": pages_content,
                        "raw_text": text_content,
                        "error": ai_result.get("error"),
                        "data": ai_result.get("data")
                    }

        analysis = st.session_state[analysis_key]

        if not analysis["success"] or not analysis.get("data"):
            # SAFE FALLBACK STATE (PHASE 5 REQUIREMENT: NO FAKE DEFAULT NUMBERS!)
            st.error(f"⚠️ {analysis.get('error', 'AI Analysis is unavailable.')}")

            # Render Decision Cards with N/A state
            col_score, col_risk, col_rec, col_conf = st.columns(4)
            with col_score:
                st.markdown("""
                <div class="hero-card">
                    <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #718096; font-weight: 700;">OVERALL SCORE</div>
                    <div style="font-size: 3rem; font-weight: 800; color: #718096; line-height: 1.1; margin: 0.5rem 0;">N/A</div>
                    <div style="font-size: 0.8rem; color: #718096;">Analysis Unavailable</div>
                </div>
                """, unsafe_allow_html=True)
            with col_risk:
                st.markdown("""
                <div class="hero-card">
                    <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #718096; font-weight: 700;">RISK LEVEL</div>
                    <div style="font-size: 2.2rem; font-weight: 800; color: #718096; line-height: 1.2; margin: 0.5rem 0;">N/A</div>
                    <div style="font-size: 0.8rem; color: #718096;">Risk Unassessed</div>
                </div>
                """, unsafe_allow_html=True)
            with col_rec:
                st.markdown("""
                <div class="hero-card">
                    <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #718096; font-weight: 700;">RECOMMENDATION</div>
                    <div style="font-size: 1.6rem; font-weight: 800; color: #718096; line-height: 1.2; margin: 0.5rem 0;">Analysis Unavailable</div>
                    <div style="font-size: 0.8rem; color: #718096;">Check Gemini Config</div>
                </div>
                """, unsafe_allow_html=True)
            with col_conf:
                st.markdown("""
                <div class="hero-card">
                    <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #718096; font-weight: 700;">CONFIDENCE</div>
                    <div style="font-size: 3rem; font-weight: 800; color: #718096; line-height: 1.1; margin: 0.5rem 0;">N/A</div>
                    <div style="font-size: 0.8rem; color: #718096;">Data Unverified</div>
                </div>
                """, unsafe_allow_html=True)

            if analysis.get("raw_text"):
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("🔍 View Extracted DRHP Text"):
                    st.text_area("Extracted Document Text", value=analysis["raw_text"], height=300)
        else:
            d = analysis["data"]

            # File Header Stats Row
            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
            with col_s1:
                st.metric("Company Name", d.get("company_name", "Unknown Entity"))
            with col_s2:
                st.metric("Industry / Sector", d.get("industry", "Not Specified"))
            with col_s3:
                st.metric("DRHP Page Count", f"{analysis.get('page_count', 0)} Pages")
            with col_s4:
                st.metric("Extracted Characters", f"{analysis.get('char_count', 0):,} Chars")

            st.markdown("<br>", unsafe_allow_html=True)

            # ==================================================================
            # 🏆 HIGH-LEVEL DECISION BANNER (SCORE, RISK LEVEL, RECOMMENDATION, CONFIDENCE)
            # ==================================================================
            col_score, col_risk, col_rec, col_conf = st.columns(4)

            score_val = d.get("investment_score")
            if score_val is not None:
                score_str = f"{score_val:.0f}"
                if score_val >= 75:
                    score_color = "#2e7d32"
                    score_label = "Strong Investment Quality"
                elif score_val >= 50:
                    score_color = "#f57c00"
                    score_label = "Moderate Quality"
                else:
                    score_color = "#c62828"
                    score_label = "High Risk / Caution"
            else:
                score_str = "N/A"
                score_color = "#718096"
                score_label = "Score Unavailable"

            with col_score:
                st.markdown(f"""
                <div class="hero-card">
                    <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #718096; font-weight: 700;">AI / INVESTMENT SCORE</div>
                    <div style="font-size: 3.4rem; font-weight: 800; color: {score_color}; line-height: 1.1; margin: 0.4rem 0;">
                        {score_str} <span style="font-size: 1.1rem; color: #718096;">/ 100</span>
                    </div>
                    <div style="font-size: 0.8rem; font-weight: 700; color: {score_color}; text-transform: uppercase;">
                        {score_label}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            risk_level = d.get("risk_level", "N/A")
            if risk_level == "Low":
                risk_color = "#2e7d32"
            elif risk_level == "High":
                risk_color = "#c62828"
            elif risk_level == "Moderate":
                risk_color = "#f57c00"
            else:
                risk_color = "#718096"

            with col_risk:
                st.markdown(f"""
                <div class="hero-card">
                    <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #718096; font-weight: 700;">RISK LEVEL</div>
                    <div style="font-size: 2.5rem; font-weight: 800; color: {risk_color}; line-height: 1.2; margin: 0.6rem 0;">
                        {risk_level.upper()}
                    </div>
                    <div style="font-size: 0.8rem; color: #718096; font-weight: 600;">
                        Forensic Risk Matrix
                    </div>
                </div>
                """, unsafe_allow_html=True)

            rec_val = d.get("recommendation", "Analysis unavailable").upper()
            if "STRONG POSITIVE" in rec_val or "STRONG" in rec_val:
                rec_color = "#2e7d32"
                rec_icon = "🟢"
            elif "POSITIVE" in rec_val or "SUBSCRIBE" in rec_val:
                rec_color = "#2e7d32"
                rec_icon = "🟢"
            elif "NEGATIVE" in rec_val or "AVOID" in rec_val:
                rec_color = "#c62828"
                rec_icon = "🔴"
            elif "CAUTIOUS" in rec_val:
                rec_color = "#e65100"
                rec_icon = "🟠"
            elif "NEUTRAL" in rec_val or "WATCH" in rec_val:
                rec_color = "#f57c00"
                rec_icon = "🟡"
            else:
                rec_color = "#718096"
                rec_icon = "⚪"

            with col_rec:
                st.markdown(f"""
                <div class="hero-card">
                    <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #718096; font-weight: 700;">RECOMMENDATION</div>
                    <div style="font-size: 1.6rem; font-weight: 800; color: {rec_color}; line-height: 1.2; margin: 0.6rem 0;">
                        {rec_icon} {rec_val}
                    </div>
                    <div style="font-size: 0.8rem; color: #718096; font-weight: 600;">
                        Evidence-Based Stance
                    </div>
                </div>
                """, unsafe_allow_html=True)

            conf_val = d.get("confidence")
            conf_str = f"{conf_val:.0f}%" if conf_val is not None else "N/A"

            with col_conf:
                st.markdown(f"""
                <div class="hero-card">
                    <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #718096; font-weight: 700;">CONFIDENCE</div>
                    <div style="font-size: 3.4rem; font-weight: 800; color: #00bcd4; line-height: 1.1; margin: 0.4rem 0;">
                        {conf_str}
                    </div>
                    <div style="font-size: 0.8rem; color: #718096; font-weight: 600;">
                        Data Completeness
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.warning("⚠️ **Forensic Investment Advisory**: Deterministic score computed by Python based on extracted DRHP disclosures. Intended solely for academic & research reference.")

            st.markdown("---")

            # ==================================================================
            # 📊 SCORE BREAKDOWN
            # ==================================================================
            st.markdown("### 📊 SCORE BREAKDOWN")
            cat_scores = d.get("category_scores", {})
            
            sb_c1, sb_c2, sb_c3, sb_c4, sb_c5 = st.columns(5)
            
            fh_cat = cat_scores.get("financial_health", {})
            bq_cat = cat_scores.get("business_quality", {})
            gp_cat = cat_scores.get("growth", {}) or cat_scores.get("growth_potential", {})
            ipo_cat = cat_scores.get("ipo_fundamentals", {})
            risk_cat = cat_scores.get("risk", {}) or cat_scores.get("risk_profile", {})

            with sb_c1:
                st.metric("Financial Health", f"{fh_cat.get('score', 0):.0f}/{fh_cat.get('max_score', 30):.0f}")
            with sb_c2:
                st.metric("Business Quality", f"{bq_cat.get('score', 0):.0f}/{bq_cat.get('max_score', 20):.0f}")
            with sb_c3:
                st.metric("Growth", f"{gp_cat.get('score', 0):.0f}/{gp_cat.get('max_score', 20):.0f}")
            with sb_c4:
                st.metric("IPO Fundamentals", f"{ipo_cat.get('score', 0):.0f}/{ipo_cat.get('max_score', 15):.0f}")
            with sb_c5:
                st.metric("Risk", f"{risk_cat.get('score', 0):.0f}/{risk_cat.get('max_score', 15):.0f}")

            st.markdown("---")

            # ==================================================================
            # 🔍 WHY THIS SCORE? (TRACEABLE EVIDENCE REASONS)
            # ==================================================================
            st.markdown("### 🔍 WHY THIS SCORE?")
            st.markdown("<p style='color: #718096; margin-bottom: 1rem;'>Deterministic scoring factors traced directly to source pages in the DRHP document.</p>", unsafe_allow_html=True)

            categories_display = [
                ("Financial Health", fh_cat, 30),
                ("Business Quality", bq_cat, 20),
                ("Growth", gp_cat, 20),
                ("IPO Fundamentals", ipo_cat, 15),
                ("Risk", risk_cat, 15),
            ]

            for cat_name, cat_obj, cat_max in categories_display:
                c_score = cat_obj.get("score", 0)
                reasons = cat_obj.get("reasons", [])

                with st.container(border=True):
                    st.markdown(f"#### {cat_name} — **{c_score:.0f}/{cat_max}**")
                    if not reasons:
                        st.write("Standard category baseline disclosures.")
                    else:
                        for r in reasons:
                            r_type = r.get("type", "positive")
                            r_text = r.get("text", "")
                            p_num = r.get("source_page")
                            
                            icon = "✅" if r_type == "positive" else ("⚠" if r_type == "risk" else "ℹ️")
                            src_str = f"Source: DRHP p. {p_num}" if p_num else "Source: DRHP disclosures"

                            st.markdown(f"""
                            <div style="margin-bottom: 0.6rem; padding: 0.4rem 0.6rem; background-color: rgba(128,128,128,0.05); border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                                <div><strong>{icon}</strong> {r_text}</div>
                                <span style="font-size: 0.75rem; font-weight: 600; padding: 2px 8px; background-color: rgba(0,188,212,0.15); color: #00bcd4; border-radius: 4px;">{src_str}</span>
                            </div>
                            """, unsafe_allow_html=True)

            # ==================================================================
            # 📈 FINANCIAL FUNDAMENTALS & RATIO ANALYSIS
            # ==================================================================
            st.markdown("### 📈 FINANCIAL FUNDAMENTALS & RATIO ANALYSIS")
            st.markdown("<p style='color: #718096; margin-bottom: 1rem;'>Calculated in Python strictly from extracted prospectus financial statements.</p>", unsafe_allow_html=True)

            ratios = d.get("financial_ratios", {})
            norm_map = d.get("normalized_fact_map", {})
            fin_trends = d.get("financial_trends", [])
            fin_interps = d.get("financial_interpretations", [])

            # 1. Ratio KPI Cards Row
            r_col1, r_col2, r_col3, r_col4, r_col5, r_col6, r_col7 = st.columns(7)

            rg_val = ratios.get("revenue_growth_pct")
            pg_val = ratios.get("profit_growth_pct")
            pm_val = ratios.get("profit_margin_pct")
            de_val = ratios.get("debt_equity_ratio")
            roe_val = ratios.get("roe_pct")
            ocf_val = ratios.get("operating_cash_flow_latest")
            eps_val = ratios.get("eps_reported")

            with r_col1:
                st.metric("Revenue Growth", f"{rg_val:+.1f}%" if rg_val is not None else "N/A")
            with r_col2:
                st.metric("Profit Growth", f"{pg_val:+.1f}%" if pg_val is not None else "N/A")
            with r_col3:
                st.metric("Profit Margin", f"{pm_val:.1f}%" if pm_val is not None else "N/A")
            with r_col4:
                st.metric("Debt / Equity", f"{de_val:.2f}" if de_val is not None else "N/A")
            with r_col5:
                st.metric("ROE", f"{roe_val:.1f}%" if roe_val is not None else "N/A")
            with r_col6:
                st.metric("Operating Cash Flow", f"₹{ocf_val:.1f} Cr" if ocf_val is not None else "N/A")
            with r_col7:
                st.metric("EPS", f"₹{eps_val}" if eps_val is not None else "N/A")

            st.markdown("<br>", unsafe_allow_html=True)

            # 2. Multi-Year Financial Statements Table
            with st.container(border=True):
                st.markdown("#### 📅 Multi-Year Financial Performance Disclosures")
                
                # Build Table Rows across reported periods
                table_metrics = ["revenue", "net_profit", "ebitda", "eps", "total_debt", "operating_cash_flow"]
                metric_labels = {
                    "revenue": "Revenue (from Operations)",
                    "net_profit": "Net Profit / (Loss)",
                    "ebitda": "EBITDA / Operating Profit",
                    "eps": "Diluted EPS (₹)",
                    "total_debt": "Total Debt",
                    "operating_cash_flow": "Operating Cash Flow"
                }

                # Collect all distinct years
                all_years = []
                for m_k in table_metrics:
                    m_data = norm_map.get(m_k, {})
                    for p in m_data.get("periods", []):
                        yr = p.get("year")
                        if yr and yr not in all_years:
                            all_years.append(yr)

                if not all_years:
                    st.info("Multi-period financial table data unavailable in extracted text.")
                else:
                    rows = []
                    for m_k in table_metrics:
                        m_data = norm_map.get(m_k, {})
                        periods_map = {p.get("year"): p.get("raw_value") for p in m_data.get("periods", []) if p.get("raw_value")}
                        row_dict = {"Metric": metric_labels.get(m_k, m_k.capitalize())}
                        for yr in all_years:
                            row_dict[yr] = periods_map.get(yr, "N/A")
                        rows.append(row_dict)

                    df_fin = pd.DataFrame(rows)
                    st.dataframe(df_fin, hide_index=True)

            # 3. Financial Trend Charts & "WHAT DO THESE NUMBERS MEAN?"
            chart_col, interp_col = st.columns([1, 1])

            with chart_col:
                with st.container(border=True):
                    st.markdown("#### 📊 Financial Trajectory Charts")
                    
                    # Prepare data for Revenue & Profit plot
                    rev_periods = norm_map.get("revenue", {}).get("periods", [])
                    profit_periods = norm_map.get("net_profit", {}).get("periods", [])

                    valid_rev = [p for p in rev_periods if p.get("value") is not None]
                    valid_profit = [p for p in profit_periods if p.get("value") is not None]

                    if len(valid_rev) >= 2 or len(valid_profit) >= 2:
                        fig_trend = go.Figure()
                        if valid_rev:
                            fig_trend.add_trace(go.Bar(
                                x=[p["year"] for p in valid_rev],
                                y=[p["value"] for p in valid_rev],
                                name="Revenue",
                                marker_color="#00bcd4"
                            ))
                        if valid_profit:
                            fig_trend.add_trace(go.Scatter(
                                x=[p["year"] for p in valid_profit],
                                y=[p["value"] for p in valid_profit],
                                name="Net Profit",
                                mode="lines+markers",
                                line=dict(color="#2e7d32", width=3)
                            ))
                        fig_trend.update_layout(
                            margin=dict(l=10, r=10, t=30, b=10),
                            height=320,
                            hovermode="x unified",
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)"
                        )
                        st.plotly_chart(fig_trend)
                    else:
                        st.info("Insufficient multi-year data points to render trend visualization charts.")

            with interp_col:
                with st.container(border=True):
                    st.markdown("#### 💡 WHAT DO THESE NUMBERS MEAN?")
                    st.markdown("<p style='font-size: 0.85rem; color: #718096;'>Evidence-grounded analytical interpretations of financial ratios and balance sheet health.</p>", unsafe_allow_html=True)

                    if not fin_interps:
                        st.write("Insufficient ratio data for detailed interpretation.")
                    else:
                        for item in fin_interps:
                            status = item.get("status", "Neutral")
                            badge_cls = "sentiment-positive" if status == "Positive" else ("sentiment-negative" if status == "Concern" else "sentiment-neutral")
                            st.markdown(f"""
                            <div style="margin-bottom: 0.6rem; padding: 0.5rem; border-radius: 6px; background-color: rgba(128,128,128,0.05);">
                                <span class="sentiment-badge {badge_cls}">{status.upper()}</span>
                                <strong>{item.get('metric')} ({item.get('value')})</strong>
                                <div style="font-size: 0.85rem; margin-top: 0.2rem; color: inherit;">{item.get('explanation')}</div>
                            </div>
                            """, unsafe_allow_html=True)

            st.markdown("---")

            # ==================================================================
            # 📂 EXTRACTED FINANCIAL FACTS LAYER (PHASE 3 & 14)
            # ==================================================================
            with st.container(border=True):
                st.markdown("### 📊 Extracted Financial Facts Layer")
                st.markdown("<p style='color: #718096;'>Verifiable quantitative metrics extracted from prospectus disclosures with source page citations.</p>", unsafe_allow_html=True)

                fin_facts = d.get("financial_facts", [])
                if not fin_facts:
                    st.info("Financial facts table not populated.")
                else:
                    fact_cols = st.columns(3)
                    for idx, ff in enumerate(fin_facts):
                        m_name = ff.get("metric", "Metric")
                        val = ff.get("value")
                        unit = ff.get("unit") or ""
                        period = ff.get("period") or ""
                        p_num = ff.get("source_page")
                        ev_t = ff.get("evidence_text") or ""

                        if val is None or str(val).strip() == "":
                            display_val = "Not available in document."
                            val_color = "#718096"
                        else:
                            display_val = f"{val} {unit}".strip()
                            if period:
                                display_val += f" ({period})"
                            val_color = "#2e7d32"

                        p_str = f"DRHP Page {p_num}" if p_num else "Page location unavailable"

                        with fact_cols[idx % 3]:
                            st.markdown(f"""
                            <div style="padding: 0.8rem; border-radius: 8px; border: 1px solid rgba(128,128,128,0.2); margin-bottom: 0.8rem;">
                                <div style="font-size: 0.8rem; font-weight: 700; color: #718096; text-transform: uppercase;">{m_name}</div>
                                <div style="font-size: 1.15rem; font-weight: 800; color: {val_color}; margin: 0.3rem 0;">{display_val}</div>
                                <div style="font-size: 0.75rem; color: #00bcd4;">{p_str}</div>
                            </div>
                            """, unsafe_allow_html=True)

            st.markdown("---")

            # ==================================================================
            # 🔎 EVIDENCE VIEWER (PHASE 11)
            # ==================================================================
            with st.container(border=True):
                st.markdown("### 🔎 DRHP Evidence Viewer")
                st.markdown("<p style='color: #718096;'>Inspect exact prospectus evidence text supporting risk assessments and scoring factors.</p>", unsafe_allow_html=True)

                red_flags = d.get("red_flags", [])
                if not red_flags:
                    st.success("No severe risk factors requiring evidence inspection.")
                else:
                    for rf in red_flags:
                        title = rf.get("title", "Risk Factor")
                        sev = rf.get("severity", "Medium")
                        ev = rf.get("evidence", {})
                        
                        p_num = None
                        e_text = ""
                        if isinstance(ev, dict):
                            p_num = ev.get("page")
                            e_text = ev.get("text", "")
                        elif isinstance(ev, str):
                            e_text = ev

                        p_display = f"DRHP — Page {p_num}" if p_num else "Evidence location unavailable"
                        exp_label = f"Risk: {title} [{sev.upper()}] — {p_display}"

                        with st.expander(exp_label):
                            st.markdown(f"**Risk Title**: {title}")
                            st.markdown(f"**Severity**: `{sev.upper()}` | **Category**: `{rf.get('category', 'General')}`")
                            st.markdown(f"**Source**: `{p_display}`")
                            if e_text:
                                st.markdown(f"**Evidence Snippet**:\n> *\"{e_text}\"*")
                            else:
                                st.info("Exact quote text unavailable in extracted sections.")

            st.markdown("---")

            # ==================================================================
            # 🚨 INVESTOR RED FLAG UI (PHASE 12)
            # ==================================================================
            with st.container(border=True):
                st.markdown("### 🚨 Investor Red Flags & Forensic Warnings")

                red_flags = d.get("red_flags", [])
                if not red_flags:
                    st.success("🎉 No severe critical forensic red flags identified in prospect disclosures.")
                else:
                    high_rf = [rf for rf in red_flags if rf.get("severity") == "High"]
                    med_rf = [rf for rf in red_flags if rf.get("severity") == "Medium"]
                    low_rf = [rf for rf in red_flags if rf.get("severity") == "Low"]

                    ordered_flags = high_rf + med_rf + low_rf

                    for rf in ordered_flags:
                        sev = rf.get("severity", "Medium")
                        cat = rf.get("category", "Operational Risk")
                        title = rf.get("title", "Risk Factor")
                        explanation = rf.get("explanation") or ""
                        
                        ev = rf.get("evidence", {})
                        p_num = None
                        ev_text = ""
                        if isinstance(ev, dict):
                            p_num = ev.get("page")
                            ev_text = ev.get("text", "")
                        elif isinstance(ev, str):
                            ev_text = ev

                        if sev == "High":
                            icon_badge = "🔴 HIGH"
                            border_color = "#d32f2f"
                            bg_color = "rgba(211, 47, 47, 0.05)"
                        elif sev == "Medium":
                            icon_badge = "🟡 MEDIUM"
                            border_color = "#f57c00"
                            bg_color = "rgba(245, 124, 0, 0.05)"
                        else:
                            icon_badge = "🟢 LOW"
                            border_color = "#1976d2"
                            bg_color = "rgba(25, 118, 210, 0.05)"

                        p_str = f"DRHP Page {p_num}" if p_num else "Page location unavailable"

                        st.markdown(f"""
                        <div style="background-color: {bg_color}; padding: 1rem; border-radius: 8px; border-left: 4px solid {border_color}; margin-bottom: 0.8rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;">
                                <strong style="font-size: 1.05rem;">{icon_badge}: {title}</strong>
                                <span style="font-size: 0.8rem; font-weight: 700; color: #00bcd4;">{p_str}</span>
                            </div>
                            <div style="font-size: 0.85rem; color: #718096; margin-bottom: 0.3rem;">Category: <strong>{cat}</strong></div>
                            <div style="font-size: 0.95rem; margin-bottom: 0.3rem;"><strong>Reason</strong>: {explanation}</div>
                            {f'<div style="font-size: 0.85rem; color: #00bcd4;"><strong>Evidence</strong>: <em>"{ev_text}"</em></div>' if ev_text else ''}
                        </div>
                        """, unsafe_allow_html=True)

            st.markdown("---")

            # ==================================================================
            # 🏢 COMPANY & IPO DETAILS CARDS
            # ==================================================================
            c_col1, c_col2 = st.columns(2)
            with c_col1:
                with st.container(border=True):
                    st.markdown("### 🏢 Company Overview & Business Model")
                    st.markdown(f"**Business Summary**: {d.get('business_summary', 'Summary unavailable.')}")
                    st.markdown(f"**Business Model**: {d.get('business_model', 'Details unavailable.')}")

            with c_col2:
                with st.container(border=True):
                    st.markdown("### 📋 IPO Offering Structure & Use of Proceeds")
                    ipo_items = d.get("ipo_details", [])
                    uop_items = d.get("use_of_proceeds", [])

                    st.markdown("**IPO Details**:")
                    if ipo_items:
                        for item in ipo_items:
                            st.markdown(f"• {item}")
                    else:
                        st.info("IPO details not specified.")

                    st.markdown("**Use of Proceeds**:")
                    if uop_items:
                        for uop in uop_items:
                            st.markdown(f"• {uop}")
                    else:
                        st.info("Use of proceeds not specified.")

            st.markdown("---")

            # Expandable Raw Text View
            with st.expander("🔍 View Extracted DRHP Text"):
                st.text_area("Extracted Document Text", value=analysis.get("raw_text", ""), height=300)

            st.markdown("---")

            # Save to Database Section
            st.subheader("💾 Save DRHP Report to Database")
            save_c1, save_c2 = st.columns([3, 1])
            with save_c1:
                comp_save_name = st.text_input("Company Name to Register:", value=d.get("company_name", "Unknown Company"))
            with save_c2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                save_clicked = st.button("Save Report", type="primary", use_container_width=True)

            if save_clicked:
                if not comp_save_name.strip():
                    st.warning("Please enter a valid company name.")
                else:
                    saved_ok = save_drhp_report(
                        company_name=comp_save_name.strip(),
                        summary=d.get("business_summary", ""),
                        red_flags=json.dumps(d.get("red_flags", [])),
                        ipo_score=d.get("investment_score"),
                        recommendation=d.get("recommendation", "Analysis unavailable"),
                        industry=d.get("industry", "Not Specified"),
                        risk_level=d.get("risk_level", "N/A"),
                        confidence=d.get("confidence"),
                        structured_data=d
                    )
                    if saved_ok:
                        st.success(f"Successfully saved DRHP Analysis for {comp_save_name} to database!")
                    else:
                        st.error("Failed to save report to SQLite database.")

    # Saved Reports Section (NULL-Safe Handling for Historical Data)
    st.markdown("---")
    st.subheader("🗄️ Saved DRHP Reports in Database")
    saved_reports = get_all_reports()

    if not saved_reports:
        st.info("No saved reports found in database yet. Upload a DRHP PDF above to analyze and store.")
    else:
        for r in saved_reports:
            r_name = r.get("company_name") or "Unknown Company"
            r_score = r.get("ipo_score")
            r_rec = r.get("recommendation") or "N/A"
            r_date = r.get("created_at") or ""
            r_ind = r.get("industry") or "Not Specified"

            if r_score is not None:
                try:
                    r_score_str = f"{float(r_score):.1f}"
                except (ValueError, TypeError):
                    r_score_str = "N/A"
            else:
                r_score_str = "N/A"

            rec_upper = str(r_rec).upper()
            badge_icon = "🟢" if "SUBSCRIBE" in rec_upper or "POSITIVE" in rec_upper else ("🔴" if "AVOID" in rec_upper or "NEGATIVE" in rec_upper else "🟡")
            exp_title = f"📄 {r_name} ({r_ind}) | {badge_icon} Score: {r_score_str}/100 — Recommendation: {r_rec} (Saved {r_date})"

            with st.expander(exp_title):
                parsed = r.get("parsed_structured_data")
                if parsed and isinstance(parsed, dict):
                    p_score = parsed.get("investment_score")
                    p_score_str = f"{float(p_score):.1f}" if p_score is not None else "N/A"
                    p_conf = parsed.get("confidence")
                    p_conf_str = f"{float(p_conf):.0f}%" if p_conf is not None else "N/A"

                    st.markdown(f"### {parsed.get('company_name', r_name)} - {parsed.get('industry', r_ind)}")
                    m1, m2, m3, m4 = st.columns(4)
                    with m1:
                        st.metric("Investment Score", f"{p_score_str} / 100")
                    with m2:
                        st.metric("Risk Level", str(parsed.get("risk_level", "N/A")))
                    with m3:
                        st.metric("Recommendation", str(parsed.get("recommendation", "N/A")))
                    with m4:
                        st.metric("Confidence", p_conf_str)

                    st.markdown("#### Business Summary")
                    st.write(parsed.get("business_summary") or "No summary available.")
                    st.markdown("#### Recommendation Rationale")
                    st.write(parsed.get("recommendation_reason") or "No details available.")
                else:
                    st.markdown(f"### {r_name}")
                    m1, m2 = st.columns(2)
                    with m1:
                        st.metric("Investment Score", f"{r_score_str} / 100")
                    with m2:
                        st.metric("Recommendation", str(r_rec))
                    st.markdown("#### Summary")
                    st.write(r.get("summary") or "No summary available.")

# ==============================================================================
# 💼 MODULE 3: PORTFOLIO INTELLIGENCE
# ==============================================================================
elif page == "💼 Portfolio Intelligence":
    st.markdown("<h1 class='main-header'>💼 Portfolio Intelligence</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Real-time P&amp;L tracking, allocation analysis &amp; position management — powered by live market data.</p>", unsafe_allow_html=True)

    # ---- Session state defaults ----
    if "portfolio_edit_id" not in st.session_state:
        st.session_state["portfolio_edit_id"] = None

    # ==================================================================
    # ➕ ADD HOLDING FORM
    # ==================================================================
    with st.container(border=True):
        st.markdown("### ➕ Add New Holding")
        add_c1, add_c2, add_c3 = st.columns([2, 1, 1])
        with add_c1:
            new_symbol = st.text_input(
                "Stock Ticker Symbol",
                placeholder="e.g. RELIANCE.NS, TCS.NS, AAPL",
                key="portfolio_add_symbol",
            ).strip().upper()
        with add_c2:
            new_qty = st.number_input(
                "Quantity (Shares)",
                min_value=0.0001, step=1.0, value=1.0,
                key="portfolio_add_qty", format="%g"
            )
        with add_c3:
            new_price = st.number_input(
                "Avg Buy Price (₹ / $)",
                min_value=0.0, step=0.01, value=0.0,
                key="portfolio_add_price", format="%.2f"
            )

        add_c4, add_c5 = st.columns([3, 1])
        with add_c4:
            new_notes = st.text_input(
                "Notes (optional)",
                placeholder="e.g. Long-term hold, SIP entry",
                key="portfolio_add_notes"
            )
        with add_c5:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("Add Holding", type="primary", key="portfolio_add_btn"):
                if not new_symbol:
                    st.warning("Please enter a ticker symbol.")
                elif new_price <= 0:
                    st.warning("Average buy price must be greater than zero.")
                else:
                    result_id = add_holding(
                        symbol=new_symbol,
                        quantity=new_qty,
                        avg_buy_price=new_price,
                        company_name="",
                        notes=new_notes,
                    )
                    if result_id:
                        st.success(f"✅ Added {new_symbol} (×{new_qty:g} shares @ {new_price:.2f}) to portfolio!")
                        st.rerun()
                    else:
                        st.error("Failed to save holding. Please check inputs.")

    st.markdown("---")

    # ==================================================================
    # FETCH HOLDINGS + MARKET DATA
    # ==================================================================
    holdings = get_all_holdings()

    if not holdings:
        st.info("📭 No holdings yet. Use the form above to add your first position.")
    else:
        # Deduplicate symbols for market data fetch
        unique_symbols = list({h["symbol"] for h in holdings})

        @st.cache_data(ttl=60, show_spinner=False)
        def _fetch_prices(syms: tuple) -> dict:
            return get_portfolio_market_data(list(syms))

        with st.spinner("Fetching live market prices…"):
            mkt = _fetch_prices(tuple(sorted(unique_symbols)))

        # ---- Enrich each holding with computed P&L ----
        enriched = []
        for h in holdings:
            sym = h["symbol"]
            qty = float(h["quantity"])
            avg = float(h["avg_buy_price"]) if h.get("avg_buy_price") else float(h.get("buy_price", 0))
            mdata = mkt.get(sym, {})

            cur_price = mdata.get("current_price")
            prev_close = mdata.get("prev_close")
            company = mdata.get("company_name") or h.get("company_name") or sym
            currency = mdata.get("currency", "INR")
            fetch_err = mdata.get("error")

            invested = qty * avg
            cur_value = qty * cur_price if cur_price is not None else None
            pnl = (cur_value - invested) if cur_value is not None else None
            pnl_pct = (pnl / invested * 100) if (pnl is not None and invested > 0) else None

            # Today's P&L = (current - prev_close) × qty  when both available
            todays_pnl = None
            if cur_price is not None and prev_close is not None:
                todays_pnl = (cur_price - prev_close) * qty

            enriched.append({
                "id": h["id"],
                "symbol": sym,
                "company": company,
                "currency": currency,
                "qty": qty,
                "avg": avg,
                "cur_price": cur_price,
                "prev_close": prev_close,
                "invested": invested,
                "cur_value": cur_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "todays_pnl": todays_pnl,
                "notes": h.get("notes") or "",
                "created_at": str(h.get("created_at") or "")[:10],
                "fetch_err": fetch_err,
            })

        # ---- Portfolio-level aggregates ----
        total_invested = sum(e["invested"] for e in enriched)
        total_cur_value = sum(e["cur_value"] for e in enriched if e["cur_value"] is not None)
        priced_invested = sum(e["invested"] for e in enriched if e["cur_value"] is not None)
        total_pnl = total_cur_value - priced_invested if total_cur_value else None
        total_pnl_pct = (total_pnl / priced_invested * 100) if (total_pnl is not None and priced_invested > 0) else None
        total_todays_pnl = sum(e["todays_pnl"] for e in enriched if e["todays_pnl"] is not None) or None

        # ==================================================================
        # 📊 SUMMARY METRIC CARDS
        # ==================================================================
        st.markdown("### 📊 Portfolio Summary")

        def _pnl_delta(val, pct=None):
            """Format a P&L value as a Streamlit metric delta string."""
            if val is None:
                return None
            sign = "+" if val >= 0 else ""
            pct_str = f" ({sign}{pct:.2f}%)" if pct is not None else ""
            return f"{sign}₹{val:,.2f}{pct_str}"

        sm1, sm2, sm3, sm4 = st.columns(4)
        with sm1:
            st.metric(
                "Total Portfolio Value",
                f"₹{total_cur_value:,.2f}" if total_cur_value else "N/A",
                help="Sum of current market value across all priced holdings."
            )
        with sm2:
            st.metric(
                "Total Invested",
                f"₹{total_invested:,.2f}",
                help="Cost basis: sum of (quantity × avg buy price) across all holdings."
            )
        with sm3:
            delta_pnl = _pnl_delta(total_pnl, total_pnl_pct)
            st.metric(
                "Unrealised P&L",
                f"₹{total_pnl:,.2f}" if total_pnl is not None else "N/A",
                delta=delta_pnl,
                help="Portfolio Value minus Cost Basis for holdings with available prices."
            )
        with sm4:
            delta_today = _pnl_delta(total_todays_pnl)
            st.metric(
                "Today's P&L",
                f"₹{total_todays_pnl:,.2f}" if total_todays_pnl is not None else "N/A",
                delta=delta_today,
                help="(Current price − previous close) × quantity. Based on latest available data, not necessarily live intra-day."
            )

        if any(e["cur_price"] is None for e in enriched):
            st.caption("⚠️ Some holdings could not be priced (see table below). Totals reflect priced positions only.")

        st.markdown("---")

        # ==================================================================
        # ✏️ INLINE EDIT FORM  (rendered before holdings table)
        # ==================================================================
        if st.session_state["portfolio_edit_id"] is not None:
            edit_h = get_holding_by_id(st.session_state["portfolio_edit_id"])
            if edit_h:
                with st.container(border=True):
                    edit_avg = float(edit_h["avg_buy_price"]) if edit_h.get("avg_buy_price") else float(edit_h.get("buy_price", 0))
                    st.markdown(f"### ✏️ Edit Holding — **{edit_h['symbol']}**")
                    ec1, ec2, ec3 = st.columns([2, 1, 1])
                    with ec1:
                        e_sym = st.text_input(
                            "Ticker Symbol", value=edit_h["symbol"], key="portfolio_edit_sym"
                        ).strip().upper()
                    with ec2:
                        e_qty = st.number_input(
                            "Quantity", min_value=0.0001, step=1.0,
                            value=float(edit_h["quantity"]),
                            key="portfolio_edit_qty", format="%g"
                        )
                    with ec3:
                        e_price = st.number_input(
                            "Avg Buy Price", min_value=0.0, step=0.01,
                            value=edit_avg,
                            key="portfolio_edit_price", format="%.2f"
                        )
                    e_notes = st.text_input(
                        "Notes", value=edit_h.get("notes") or "", key="portfolio_edit_notes"
                    )
                    save_col, cancel_col = st.columns(2)
                    with save_col:
                        if st.button("💾 Save Changes", type="primary", key="portfolio_save_btn"):
                            ok = update_holding(
                                holding_id=edit_h["id"],
                                symbol=e_sym,
                                quantity=e_qty,
                                avg_buy_price=e_price,
                                company_name=edit_h.get("company_name", ""),
                                notes=e_notes,
                            )
                            if ok:
                                st.success("✅ Holding updated successfully.")
                                st.session_state["portfolio_edit_id"] = None
                                st.rerun()
                            else:
                                st.error("Update failed. Check inputs.")
                    with cancel_col:
                        if st.button("✖ Cancel", key="portfolio_cancel_btn"):
                            st.session_state["portfolio_edit_id"] = None
                            st.rerun()
                st.markdown("---")

        # ==================================================================
        # 📋 HOLDINGS TABLE
        # ==================================================================
        st.markdown("### 📋 Holdings & P&L")

        def _fmt_price(val, currency="INR"):
            if val is None:
                return "N/A"
            sym = "₹" if currency in ("INR", "GBp") else ("$" if currency == "USD" else f"{currency} ")
            return f"{sym}{val:,.2f}"

        def _fmt_pnl(val):
            if val is None:
                return "N/A"
            sign = "+" if val >= 0 else ""
            return f"{sign}₹{val:,.2f}"

        def _fmt_pct(val):
            if val is None:
                return "N/A"
            sign = "+" if val >= 0 else ""
            return f"{sign}{val:.2f}%"

        for e in enriched:
            pnl_color = "#2e7d32" if (e["pnl"] or 0) >= 0 else "#c62828"
            cur_price_str = _fmt_price(e["cur_price"], e["currency"])
            cur_val_str = _fmt_price(e["cur_value"], e["currency"])
            invested_str = _fmt_price(e["invested"], e["currency"])
            pnl_str = _fmt_pnl(e["pnl"])
            pnl_pct_str = _fmt_pct(e["pnl_pct"])

            with st.container(border=True):
                # Row 1 — Company + symbol + error badge
                r1a, r1b = st.columns([8, 2])
                with r1a:
                    badge = f"<span style='font-size:0.75rem; padding:2px 8px; border-radius:4px; background:rgba(0,188,212,0.15); color:#00bcd4; font-weight:700; margin-left:6px;'>{e['currency']}</span>"
                    err_badge = ""
                    if e["fetch_err"]:
                        err_badge = f"<span style='font-size:0.75rem; padding:2px 8px; border-radius:4px; background:rgba(198,40,40,0.1); color:#d32f2f; font-weight:700; margin-left:6px;'>⚠ Price Unavailable</span>"
                    st.markdown(
                        f"**{e['company']}** &nbsp;<code>{e['symbol']}</code>{badge}{err_badge}",
                        unsafe_allow_html=True
                    )
                    if e["notes"]:
                        st.caption(e["notes"])
                with r1b:
                    edit_del_c1, edit_del_c2 = st.columns(2)
                    with edit_del_c1:
                        if st.button(":material/edit:", key=f"edit_btn_{e['id']}", help="Edit holding"):
                            st.session_state["portfolio_edit_id"] = e["id"]
                            st.rerun()
                    with edit_del_c2:
                        if st.button(":material/delete:", key=f"del_btn_{e['id']}", help="Delete holding"):
                            delete_holding(e["id"])
                            st.rerun()

                # Row 2 — Metrics
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                with m1:
                    st.metric("Shares", f"{e['qty']:g}")
                with m2:
                    st.metric("Avg Buy Price", _fmt_price(e["avg"], e["currency"]))
                with m3:
                    st.metric("Current Price", cur_price_str if e["cur_price"] else "N/A")
                with m4:
                    st.metric("Invested", invested_str)
                with m5:
                    st.metric("Current Value", cur_val_str if e["cur_value"] else "N/A")
                with m6:
                    st.markdown(
                        f"<div style='font-size:0.85rem;color:#718096;font-weight:600;margin-bottom:4px;'>Unrealised P&amp;L</div>"
                        f"<div style='font-size:1.3rem;font-weight:800;color:{pnl_color};'>{pnl_str}</div>"
                        f"<div style='font-size:0.85rem;font-weight:700;color:{pnl_color};'>{pnl_pct_str}</div>",
                        unsafe_allow_html=True
                    )

                if e["fetch_err"]:
                    st.caption(f"ℹ️ {e['fetch_err']}")

        st.markdown("---")

        # ==================================================================
        # 🥧 PORTFOLIO ALLOCATION
        # ==================================================================
        st.markdown("### 🥧 Portfolio Allocation")

        priced_holdings = [e for e in enriched if e["cur_value"] is not None and e["cur_value"] > 0]

        if not priced_holdings:
            st.info("Allocation chart unavailable — no holdings with live price data.")
        else:
            total_val_for_alloc = sum(e["cur_value"] for e in priced_holdings)

            alloc_labels = [e["symbol"] for e in priced_holdings]
            alloc_values = [e["cur_value"] for e in priced_holdings]
            alloc_pcts = [(v / total_val_for_alloc * 100) for v in alloc_values]

            donut_col, table_col = st.columns([1, 1])

            with donut_col:
                fig_donut = go.Figure(data=[go.Pie(
                    labels=alloc_labels,
                    values=alloc_values,
                    hole=0.52,
                    textinfo="label+percent",
                    textfont_size=13,
                    marker=dict(
                        colors=[
                            "#00bcd4", "#2e7d32", "#f57c00", "#e91e63",
                            "#7b1fa2", "#1976d2", "#ff8f00", "#00695c",
                            "#5d4037", "#455a64"
                        ],
                        line=dict(color="rgba(0,0,0,0.1)", width=1)
                    ),
                    hovertemplate="<b>%{label}</b><br>Value: ₹%{value:,.2f}<br>Allocation: %{percent}<extra></extra>"
                )])
                fig_donut.update_layout(
                    showlegend=True,
                    legend=dict(orientation="v", x=1.02, y=0.5),
                    margin=dict(l=10, r=10, t=20, b=20),
                    height=340,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_donut, use_container_width=True)

            with table_col:
                alloc_rows = []
                for e, pct in zip(priced_holdings, alloc_pcts):
                    alloc_rows.append({
                        "Symbol": e["symbol"],
                        "Company": e["company"],
                        "Current Value": f"₹{e['cur_value']:,.2f}",
                        "Allocation %": f"{pct:.2f}%",
                    })
                df_alloc = pd.DataFrame(alloc_rows)
                st.dataframe(df_alloc, hide_index=True, use_container_width=True)

                total_alloc = sum(alloc_pcts)
                st.caption(f"Total allocation: **{total_alloc:.2f}%** (should be ≈ 100% for priced holdings)")


# ==============================================================================
# Additional Modules: Market Overview, Watchlist, Risk Intelligence, Stock Dashboard
# ==============================================================================
elif page == "🏠 Market Overview":
    st.markdown("<h1 class='main-header'>🏠 Market Overview</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Major index snapshots and recent market news.</p>", unsafe_allow_html=True)

    # Simple index snapshots (NIFTY 50 and SENSEX)
    idx1 = get_stock_info("^NSEI")
    idx2 = get_stock_info("^BSESN")

    c1, c2 = st.columns(2)
    with c1:
        if idx1.get("success"):
            st.metric("NIFTY 50", format_price(idx1.get("current_price"), idx1.get("currency")), delta=None)
        else:
            st.info("NIFTY data unavailable")
    with c2:
        if idx2.get("success"):
            st.metric("SENSEX", format_price(idx2.get("current_price"), idx2.get("currency")), delta=None)
        else:
            st.info("SENSEX data unavailable")

    st.markdown("---")
    st.subheader("Recent Market News")
    try:
        articles = get_stock_news("India stock market")
        for art in articles:
            st.markdown(f"- [{art['headline']}]({art['url']}) — {art['source']} ({art['publication_date']}) — {art['sentiment']}")
    except Exception as e:
        st.info(f"Market news unavailable: {str(e)}")

    st.markdown("---")

elif page == "🔔 Watchlist":
    st.markdown("<h1 class='main-header'>🔔 Watchlist</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Track symbols you care about with quick price checks.</p>", unsafe_allow_html=True)

    # Add to watchlist
    w_col1, w_col2 = st.columns([3,1])
    with w_col1:
        watch_sym = st.text_input("Ticker to watch", placeholder="e.g. TCS.NS, AAPL", key="watch_add_sym")
    with w_col2:
        if st.button("Add to Watchlist", key="watch_add_btn"):
            if not watch_sym.strip():
                st.warning("Enter a ticker symbol to add.")
            else:
                rid = add_watchlist_item(watch_sym.strip().upper())
                if rid:
                    st.success(f"Added {watch_sym.strip().upper()} to watchlist")
                    st.experimental_rerun()
                else:
                    st.error("Failed to add to watchlist")

    st.markdown("---")
    items = get_watchlist()
    if not items:
        st.info("No symbols in watchlist yet.")
    else:
        syms = [it['symbol'] for it in items]
        prices = get_portfolio_market_data(syms)

        for it in items:
            s = it['symbol']
            m = prices.get(s, {})
            cur = m.get('current_price')
            prev = m.get('prev_close')
            comp = m.get('company_name') or s
            delta = None
            if cur is not None and prev is not None:
                delta = cur - prev
            st.markdown(f"**{comp}** `{s}` — Price: {format_price(cur, m.get('currency','INR')) if cur is not None else 'N/A'} {f'Δ {delta:+.2f}' if delta is not None else ''}")
            if st.button("Remove", key=f"watch_rm_{it['id']}"):
                remove_watchlist_item(it['id'])
                st.experimental_rerun()

    st.markdown("---")

elif page == "🛡️ Risk Intelligence":
    st.markdown("<h1 class='main-header'>🛡️ Risk Intelligence</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Deterministic portfolio risk metrics and observations.</p>", unsafe_allow_html=True)

    holdings = get_all_holdings()
    if not holdings:
        st.info("Add holdings to your portfolio to see risk metrics.")
    else:
        syms = list({h['symbol'] for h in holdings})
        mkt = get_portfolio_market_data(syms)

        priced = []
        for h in holdings:
            sym = h['symbol']
            qty = float(h['quantity'])
            avg = float(h.get('avg_buy_price') or h.get('buy_price', 0))
            md = mkt.get(sym, {})
            cur = md.get('current_price')
            cur_value = cur * qty if cur is not None else 0
            priced.append({
                'symbol': sym,
                'cur_value': cur_value,
                'sector': md.get('sector')
            })

        res = analyze_portfolio_holdings([p for p in priced if p['cur_value'] > 0])
        st.metric("Diversification Score", res.get('diversification_score') or "N/A")
        st.metric("Diversification Status", res.get('diversification_status'))
        st.metric("Concentration Status", res.get('concentration_status'))

        st.markdown("---")
        st.subheader("Concentration Details")
        st.write({
            'Number of Holdings': res.get('num_holdings'),
            'Largest Holding %': f"{res.get('largest_holding_pct')}%",
            'Top 3 Holdings %': f"{res.get('top_3_pct')}%",
            'Largest Sector %': (f"{res.get('largest_sector_pct')}%" if res.get('largest_sector_pct') is not None else 'N/A')
        })

        if res.get('sector_breakdown'):
            st.subheader('Sector Breakdown')
            dfsec = pd.DataFrame([{'sector': k, 'allocation_pct': v} for k, v in res['sector_breakdown'].items()])
            st.dataframe(dfsec, hide_index=True)

    st.markdown('---')

elif page == "📈 Stock Dashboard":
    st.markdown("<h1 class='main-header'>📈 Financial Research AI</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Equity dashboard with Plotly candlestick charting, moving averages, and news sentiment.</p>", unsafe_allow_html=True)

    # Search Box
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        ticker_input = st.text_input(
            "Enter Stock Ticker Symbol:",
            value="RELIANCE.NS",
            placeholder="e.g. RELIANCE.NS, TCS.NS, AAPL, MSFT",
            help="For Indian stocks listed on NSE, append '.NS' (e.g. RELIANCE.NS). For BSE, append '.BO'."
        ).strip()

    with col_btn:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        analyze_stock_btn = st.button("Analyze Ticker", type="primary", use_container_width=True)

    if ticker_input or analyze_stock_btn:
        with st.spinner(f"Fetching market data for {ticker_input.upper()}..."):
            stock_data = get_stock_info(ticker_input)

            if not stock_data["success"]:
                st.error(stock_data["error"])
            else:
                curr = stock_data["currency"]
                st.markdown(f"### {stock_data['company_name']} (`{stock_data['symbol']}`)")

                # Metric Cards Row 1
                mc1, mc2, mc3, mc4 = st.columns(4)
                with mc1:
                    st.metric("Current Price", format_price(stock_data["current_price"], curr))
                with mc2:
                    st.metric("Market Cap", format_market_cap(stock_data["market_cap"], curr))
                with mc3:
                    st.metric("PE Ratio (P/E)", format_pe(stock_data["pe_ratio"]))
                with mc4:
                    st.metric("Volume", format_volume(stock_data["volume"]))

                # Metric Cards Row 2
                k1, k2, k3, k4, k5 = st.columns(5)
                with k1:
                    st.metric("52W High", format_price(stock_data["fifty_two_week_high"], curr))
                with k2:
                    st.metric("52W Low", format_price(stock_data["fifty_two_week_low"], curr))
                with k3:
                    st.metric("Dividend Yield", format_percentage(stock_data["dividend_yield"]))
                with k4:
                    st.metric("Avg Volume", format_volume(stock_data["average_volume"]))
                with k5:
                    st.metric("Beta", format_beta(stock_data["beta"]))

                st.markdown("---")

                # Interactive Candlestick + Moving Average + Volume Chart
                st.subheader("📊 Interactive Technical Performance Chart")

                timeframe = st.radio(
                    "Select Timeframe Range:",
                    options=["1 Day", "5 Days", "1 Month", "6 Months", "1 Year", "5 Years", "All Time"],
                    index=4,
                    horizontal=True,
                    label_visibility="collapsed"
                )

                tf_map = {
                    "1 Day": {"period": "1d", "interval": "15m", "dma": False},
                    "5 Days": {"period": "5d", "interval": "30m", "dma": False},
                    "1 Month": {"period": "1mo", "interval": "1d", "dma": False},
                    "6 Months": {"period": "6mo", "interval": "1d", "dma": False},
                    "1 Year": {"period": "2y", "interval": "1d", "dma": True, "tail": 252},
                    "5 Years": {"period": "6y", "interval": "1d", "dma": True, "tail": 1260},
                    "All Time": {"period": "max", "interval": "1d", "dma": True, "tail": None}
                }

                cfg = tf_map[timeframe]
                hist_df = get_stock_history(stock_data["symbol"], period=cfg["period"], interval=cfg["interval"])

                if hist_df is not None and not hist_df.empty:
                    if cfg["dma"]:
                        hist_df["50_DMA"] = hist_df["Close"].rolling(window=50).mean()
                        hist_df["200_DMA"] = hist_df["Close"].rolling(window=200).mean()

                    if cfg.get("tail") and len(hist_df) > cfg["tail"]:
                        chart_df = hist_df.tail(cfg["tail"])
                    else:
                        chart_df = hist_df

                    fig = make_subplots(
                        rows=2, cols=1,
                        shared_xaxes=True,
                        vertical_spacing=0.03,
                        subplot_titles=(f"{stock_data['symbol']} Technical Price Action ({curr})", "Volume"),
                        row_heights=[0.75, 0.25]
                    )

                    fig.add_trace(
                        go.Candlestick(
                            x=chart_df.index,
                            open=chart_df["Open"],
                            high=chart_df["High"],
                            low=chart_df["Low"],
                            close=chart_df["Close"],
                            name="Price (OHLC)",
                            increasing_line_color="#2e7d32",
                            decreasing_line_color="#c62828"
                        ),
                        row=1, col=1
                    )

                    if cfg["dma"] and "50_DMA" in chart_df.columns:
                        fig.add_trace(
                            go.Scatter(
                                x=chart_df.index, y=chart_df["50_DMA"],
                                name="50 DMA", line=dict(color="#ff9800", width=1.5)
                            ),
                            row=1, col=1
                        )
                    if cfg["dma"] and "200_DMA" in chart_df.columns:
                        fig.add_trace(
                            go.Scatter(
                                x=chart_df.index, y=chart_df["200_DMA"],
                                name="200 DMA", line=dict(color="#e91e63", width=1.5)
                            ),
                            row=1, col=1
                        )

                    colors = ["#2e7d32" if c >= o else "#c62828" for c, o in zip(chart_df["Close"], chart_df["Open"])]
                    fig.add_trace(
                        go.Bar(
                            x=chart_df.index, y=chart_df["Volume"],
                            name="Volume", marker_color=colors, opacity=0.7
                        ),
                        row=2, col=1
                    )

                    fig.update_layout(
                        xaxis_rangeslider_visible=False,
                        hovermode="x unified",
                        margin=dict(l=10, r=10, t=30, b=10),
                        height=500,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)"
                    )

                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning(f"Could not retrieve historical price chart for timeframe '{timeframe}'.")

                st.markdown("---")

                # Company Summary
                with st.expander("🏢 Company Profile & Overview", expanded=True):
                    st.write(stock_data["summary"])

                st.markdown("---")

                # News Coverage & Sentiment Analysis
                st.subheader("📰 Recent Market News & Sentiment Analysis")
                try:
                    articles = get_stock_news(stock_data["company_name"])

                    pos = sum(1 for a in articles if a["sentiment"] == "Positive")
                    neu = sum(1 for a in articles if a["sentiment"] == "Neutral")
                    neg = sum(1 for a in articles if a["sentiment"] == "Negative")

                    s_col1, s_col2, s_col3 = st.columns(3)
                    with s_col1:
                        st.metric("Positive Articles", pos)
                    with s_col2:
                        st.metric("Neutral Articles", neu)
                    with s_col3:
                        st.metric("Negative Articles", neg)

                    st.markdown("<br>", unsafe_allow_html=True)
                    for art in articles:
                        st.markdown(f"""
                        <div class="news-article">
                            <span class="sentiment-badge sentiment-{art['sentiment'].lower()}">{art['sentiment']}</span>
                            <a class="news-headline" href="{art['url']}" target="_blank">{art['headline']}</a>
                            <div class="news-meta">Source: {art['source']} | Published: {art['publication_date']}</div>
                        </div>
                        """, unsafe_allow_html=True)

                except NewsAPIError as e:
                    st.warning(f"Could not fetch news articles: {str(e)}")
