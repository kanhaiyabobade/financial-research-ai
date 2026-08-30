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

# Set page configuration with a modern, high-contrast theme
st.set_page_config(
    page_title="Financial Research AI: Stock Analysis & IPO Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    ["🚀 IPO Intelligence", "📈 Stock Dashboard"],
    index=0,
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
                    ai_result = analyze_drhp_structured(text_content)

                    st.session_state[analysis_key] = {
                        "success": ai_result["success"],
                        "filename": filename,
                        "page_count": pdf_result["page_count"],
                        "char_count": pdf_result["char_count"],
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
                score_str = f"{score_val:.1f}"
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
                    <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #718096; font-weight: 700;">AI SCORE</div>
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
            if "SUBSCRIBE" in rec_val or "POSITIVE" in rec_val:
                rec_color = "#2e7d32"
                rec_icon = "🟢"
            elif "AVOID" in rec_val or "NEGATIVE" in rec_val:
                rec_color = "#c62828"
                rec_icon = "🔴"
            elif "WATCH" in rec_val or "NEUTRAL" in rec_val:
                rec_color = "#f57c00"
                rec_icon = "🟡"
            else:
                rec_color = "#718096"
                rec_icon = "⚪"

            with col_rec:
                st.markdown(f"""
                <div class="hero-card">
                    <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #718096; font-weight: 700;">RECOMMENDATION</div>
                    <div style="font-size: 1.8rem; font-weight: 800; color: {rec_color}; line-height: 1.2; margin: 0.6rem 0;">
                        {rec_icon} {rec_val}
                    </div>
                    <div style="font-size: 0.8rem; color: #718096; font-weight: 600;">
                        AI Investment Stance
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
                        DRHP Data Completeness
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.warning("⚠️ **Investment Advisory Notice**: Generated by Gemini AI based on extracted prospectus disclosures. Intended solely for academic & research reference.")

            st.markdown("---")

            # ==================================================================
            # 📊 12 STRUCTURED CARDS & EXPANDERS
            # ==================================================================

            # 1. Company Overview & 2. Business Model
            c_col1, c_col2 = st.columns(2)
            with c_col1:
                with st.container(border=True):
                    st.markdown("### 🏢 1. Company Overview")
                    st.write(d.get("business_summary", "Summary unavailable."))

            with c_col2:
                with st.container(border=True):
                    st.markdown("### ⚙️ 2. Business Model")
                    st.write(d.get("business_model", "Business model details unavailable."))

            # 3. Products & Services & 4. IPO Structure
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                with st.container(border=True):
                    st.markdown("### 📦 3. Products & Services")
                    prods = d.get("products_services", [])
                    if prods:
                        for prod in prods:
                            st.markdown(f"• {prod}")
                    else:
                        st.info("Product details not specified.")

            with p_col2:
                with st.container(border=True):
                    st.markdown("### 📋 4. IPO Structure & Details")
                    ipo_items = d.get("ipo_details", [])
                    if ipo_items:
                        for item in ipo_items:
                            st.markdown(f"• {item}")
                    else:
                        st.info("IPO structure details not explicitly defined in extracted sections.")

            # 5. Financial Highlights & Revenue Sources
            with st.container(border=True):
                st.markdown("### 📈 5. Financial Highlights & Revenue Breakdown")
                f_col1, f_col2 = st.columns(2)
                with f_col1:
                    st.markdown("#### Key Financial Metrics")
                    fin_items = d.get("financial_highlights", [])
                    if fin_items:
                        for fh in fin_items:
                            st.markdown(f"• **{fh}**")
                    else:
                        st.info("Financial statements metrics not extracted.")
                with f_col2:
                    st.markdown("#### Revenue Streams")
                    rev_items = d.get("revenue_sources", [])
                    if rev_items:
                        for rev in rev_items:
                            st.markdown(f"• {rev}")
                    else:
                        st.info("Revenue stream details not specified.")

            # 6. Strengths & Competitive Moats
            with st.container(border=True):
                st.markdown("### 🛡️ 6. Company Strengths & Competitive Advantages")
                strengths = d.get("strengths", [])
                if strengths:
                    s_cols = st.columns(2)
                    for idx, str_item in enumerate(strengths):
                        with s_cols[idx % 2]:
                            st.success(f"✓ **{str_item}**")
                else:
                    st.info("No explicit strengths highlighted.")

            # 7. Red Flags & Forensic Risk Detection
            with st.container(border=True):
                st.markdown("### 🚨 7. Forensic Red Flag Analysis")
                red_flags = d.get("red_flags", [])
                if not red_flags:
                    st.success("🎉 No severe critical forensic red flags detected in extracted sections.")
                else:
                    for rf in red_flags:
                        sev = rf.get("severity", "Medium")
                        sev_class = "severity-high" if sev == "High" else ("severity-medium" if sev == "Medium" else "severity-low")
                        cat = rf.get("category", "Operational Risk")
                        title = rf.get("title", "Risk Factor")
                        explanation = rf.get("explanation") or rf.get("evidence", "")
                        evidence = rf.get("evidence", "")

                        border_color = '#d32f2f' if sev=='High' else ('#f57c00' if sev=='Medium' else '#1976d2')

                        st.markdown(f"""
                        <div style="background-color: rgba(128,128,128,0.05); padding: 1rem; border-radius: 8px; border-left: 4px solid {border_color}; margin-bottom: 0.75rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;">
                                <strong style="font-size: 1.05rem;">{title}</strong>
                                <span class="{sev_class}">{sev.upper()} SEVERITY</span>
                            </div>
                            <div style="font-size: 0.85rem; color: #718096; margin-bottom: 0.3rem;">Category: <strong>{cat}</strong></div>
                            <div style="font-size: 0.95rem; color: inherit; margin-bottom: 0.3rem;"><strong>Explanation</strong>: {explanation}</div>
                            <div style="font-size: 0.85rem; color: #00bcd4;"><strong>DRHP Evidence</strong>: <em>{evidence}</em></div>
                        </div>
                        """, unsafe_allow_html=True)

            # 8. Risk Factors & 9. Growth Opportunities
            rg_col1, rg_col2 = st.columns(2)
            with rg_col1:
                with st.container(border=True):
                    st.markdown("### ⚠️ 8. General Risk Factors")
                    risks = d.get("risks", [])
                    if risks:
                        for rk in risks:
                            st.markdown(f"• {rk}")
                    else:
                        st.info("No general risks listed.")

            with rg_col2:
                with st.container(border=True):
                    st.markdown("### 🚀 9. Growth Catalysts & Opportunities")
                    growth_items = d.get("growth_opportunities", [])
                    if growth_items:
                        for go_item in growth_items:
                            st.markdown(f"• {go_item}")
                    else:
                        st.info("Growth opportunities not specified.")

            # 10. Competitor Analysis & 11. Use of Proceeds
            cp_col1, cp_col2 = st.columns(2)
            with cp_col1:
                with st.container(border=True):
                    st.markdown("### ⚔️ 10. Competitors & Industry Peers")
                    comps = d.get("competitors", [])
                    if comps:
                        for comp in comps:
                            st.markdown(f"• **{comp}**")
                    else:
                        st.info("Competitor information not listed.")

            with cp_col2:
                with st.container(border=True):
                    st.markdown("### 🎯 11. Objects of the Offer & Use of Proceeds")
                    uop_items = d.get("use_of_proceeds", [])
                    if uop_items:
                        for uop in uop_items:
                            st.markdown(f"• {uop}")
                    else:
                        st.info("Use of proceeds not specified.")

            # 12. Transparent AI Investment Score Breakdown & Reasoning
            with st.container(border=True):
                st.markdown("### 🧠 12. AI Investment Score Rationale & Category Breakdown")

                sb = d.get("score_breakdown", {})
                sb_c1, sb_c2, sb_c3, sb_c4, sb_c5 = st.columns(5)
                with sb_c1:
                    val = sb.get("financial_health")
                    st.metric("Financial Health", f"{val:.1f} / 20" if val is not None else "N/A")
                with sb_c2:
                    val = sb.get("growth_potential")
                    st.metric("Growth Potential", f"{val:.1f} / 20" if val is not None else "N/A")
                with sb_c3:
                    val = sb.get("business_quality")
                    st.metric("Business Quality", f"{val:.1f} / 20" if val is not None else "N/A")
                with sb_c4:
                    val = sb.get("industry_position")
                    st.metric("Industry Position", f"{val:.1f} / 20" if val is not None else "N/A")
                with sb_c5:
                    val = sb.get("risk_profile")
                    st.metric("Risk Profile", f"{val:.1f} / 20" if val is not None else "N/A")

                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(f"**Investment Rationale**: {d.get('recommendation_reason', 'N/A')}")

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
# 📈 MODULE 2: STOCK DASHBOARD
# ==============================================================================
else:
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
