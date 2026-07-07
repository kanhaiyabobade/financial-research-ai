import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv
from stock_service import get_stock_info, get_stock_history
from news_service import get_stock_news, NewsAPIError

# Load environment variables from .env
load_dotenv()

# Set page configuration with a premium look
st.set_page_config(
    page_title="Financial Research AI Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Premium Styling
st.markdown("""
    <style>
        /* Modern title styling */
        .main-header {
            font-size: 2.8rem;
            font-weight: 800;
            background: linear-gradient(90deg, #3f51b5, #00bcd4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.2rem;
            font-family: 'Inter', sans-serif;
        }
        .sub-header {
            font-size: 1.1rem;
            color: #718096;
            margin-bottom: 2rem;
            font-family: 'Inter', sans-serif;
        }
        /* Custom card style */
        .metric-card {
            background-color: #ffffff;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
            border-left: 5px solid #3f51b5;
            margin-bottom: 1rem;
        }
        /* Dark mode compatibility support */
        @media (prefers-color-scheme: dark) {
            .metric-card {
                background-color: #1e1e24;
                border-left: 5px solid #00bcd4;
                box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5);
            }
        }
        /* News article styling */
        .news-article {
            padding: 1rem;
            border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        }
        .news-headline {
            font-size: 1.1rem;
            font-weight: 600;
            color: #00bcd4;
            text-decoration: none;
            vertical-align: middle;
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
            vertical-align: middle;
            font-family: 'Inter', sans-serif;
        }
        .sentiment-positive {
            background-color: #2e7d32;
            color: #ffffff;
        }
        .sentiment-neutral {
            background-color: #757575;
            color: #ffffff;
        }
        .sentiment-negative {
            background-color: #c62828;
            color: #ffffff;
        }
    </style>
""", unsafe_allow_html=True)

# Helper formatting functions
def format_market_cap(val: float, currency: str) -> str:
    if val is None:
        return "N/A"
    
    if currency == "INR":
        # Format Indian numbering (Crores, Lakhs)
        if val >= 10**7:
            return f"₹{val / 10**7:,.2f} Cr"
        elif val >= 10**5:
            return f"₹{val / 10**5:,.2f} Lakhs"
        return f"₹{val:,.2f}"
    else:
        # Standard Global formats (T, B, M)
        symbol = "$" if currency == "USD" else f"{currency} "
        if val >= 10**12:
            return f"{symbol}{val / 10**12:,.2f} T"
        elif val >= 10**9:
            return f"{symbol}{val / 10**9:,.2f} B"
        elif val >= 10**6:
            return f"{symbol}{val / 10**6:,.2f} M"
        return f"{symbol}{val:,.2f}"

def format_price(val: float, currency: str) -> str:
    if val is None:
        return "N/A"
    symbol = "₹" if currency == "INR" else ("$" if currency == "USD" else f"{currency} ")
    return f"{symbol}{val:,.2f}"

def format_pe(val: float) -> str:
    if val is None:
        return "N/A"
    return f"{val:,.2f}"

def format_volume(val: float) -> str:
    if val is None:
        return "N/A"
    if val >= 10**6:
        return f"{val / 10**6:,.2f} M"
    elif val >= 10**3:
        return f"{val / 10**3:,.2f} K"
    return f"{val:,.0f}"

def format_percentage(val: float) -> str:
    if val is None:
        return "N/A"
    return f"{val:.2f}%"

def format_beta(val: float) -> str:
    if val is None:
        return "N/A"
    return f"{val:.2f}"

# Main Application Title
st.markdown("<h1 class='main-header'>📈 Financial Research AI</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>State-of-the-art equity analytics for Indian and global markets.</p>", unsafe_allow_html=True)

# Search Input Section
col1, col2 = st.columns([3, 1])

with col1:
    ticker_input = st.text_input(
        "Enter Stock Symbol:",
        value="RELIANCE.NS",
        placeholder="e.g. RELIANCE.NS, TCS.NS, INFY.NS, AAPL",
        help="For Indian stocks listed on NSE, append '.NS' (e.g. RELIANCE.NS). For BSE, append '.BO'."
    ).strip()

with col2:
    # Add vertical space to align the button
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    analyze_button = st.button("Analyze Stock", type="primary", width="stretch")

# State initialization or trigger of analyze action
if analyze_button or ticker_input:
    if not ticker_input:
        st.warning("Please enter a valid stock ticker symbol.")
    else:
        with st.spinner(f"Analyzing {ticker_input.upper()}..."):
            stock_data = get_stock_info(ticker_input)
            
            if not stock_data["success"]:
                st.error(stock_data["error"])
            else:
                # 1. Header Metrics Card
                st.markdown(f"### {stock_data['company_name']} ({stock_data['symbol']})")
                
                # 2. Key Metrics Row (Kept unchanged)
                m_col1, m_col2, m_col3 = st.columns(3)
                
                # Format variables
                curr = stock_data["currency"]
                price_formatted = format_price(stock_data["current_price"], curr)
                mcap_formatted = format_market_cap(stock_data["market_cap"], curr)
                pe_formatted = format_pe(stock_data["pe_ratio"])
                
                with m_col1:
                    st.metric(
                        label="Current Price",
                        value=price_formatted,
                        help="Last traded price of the security."
                    )
                with m_col2:
                    st.metric(
                        label="Market Capitalization",
                        value=mcap_formatted,
                        help="Total value of the company's outstanding shares."
                    )
                with m_col3:
                    st.metric(
                        label="PE Ratio (Price/Earnings)",
                        value=pe_formatted,
                        help="Ratio of stock price to earnings per share."
                    )
                
                st.markdown("---")
                
                # 2b. Key Stock Indicators (Task)
                st.markdown("##### Key Stock Indicators")
                k_col1, k_col2, k_col3, k_col4, k_col5 = st.columns(5)
                
                high_formatted = format_price(stock_data["fifty_two_week_high"], curr)
                low_formatted = format_price(stock_data["fifty_two_week_low"], curr)
                div_formatted = format_percentage(stock_data["dividend_yield"])
                vol_formatted = format_volume(stock_data["average_volume"])
                beta_formatted = format_beta(stock_data["beta"])
                
                with k_col1:
                    st.metric(label="52 Week High", value=high_formatted)
                with k_col2:
                    st.metric(label="52 Week Low", value=low_formatted)
                with k_col3:
                    st.metric(label="Dividend Yield", value=div_formatted)
                with k_col4:
                    st.metric(label="Average Volume", value=vol_formatted)
                with k_col5:
                    st.metric(label="Beta", value=beta_formatted)
                
                st.markdown("---")
                
                # 3. Interactive Historical Price Chart with Moving Averages
                st.subheader(
                    "Historical Performance", 
                    help=(
                        "Technical Indicators:\n\n"
                        "• **Close Price**: The closing price trend (blue line).\n"
                        "• **50 Day Moving Average (50 DMA)**: The rolling average of the last 50 trading days (orange line). Indicates short-term trend direction.\n"
                        "• **200 Day Moving Average (200 DMA)**: The rolling average of the last 200 trading days (pink line). Indicates long-term trend direction.\n\n"
                        "💡 **Interpretation**: A 'Golden Cross' occurs when the 50 DMA crosses above the 200 DMA, suggesting a bullish upward trend. A 'Death Cross' occurs when the 50 DMA crosses below the 200 DMA, suggesting a bearish trend.\n\n"
                        "⚠️ *Note: Moving Averages are calculated on daily historical intervals and are shown for 1 Year, 5 Years, and All Time timeframes.*"
                    )
                )
                
                # Horizontal Timeframe Selector (Task)
                timeframe = st.radio(
                    "Select Timeframe:",
                    options=["1 Day", "5 Days", "1 Week", "1 Month", "6 Months", "1 Year", "5 Years", "All Time"],
                    index=5,  # Defaults to "1 Year"
                    horizontal=True,
                    label_visibility="collapsed"
                )
                
                # Configuration map for different chart ranges
                timeframe_configs = {
                    "1 Day": {"period": "1d", "interval": "15m", "dma": False, "slice": None},
                    "5 Days": {"period": "5d", "interval": "30m", "dma": False, "slice": None},
                    "1 Week": {"period": "7d", "interval": "30m", "dma": False, "slice": None},
                    "1 Month": {"period": "1mo", "interval": "1d", "dma": False, "slice": None},
                    "6 Months": {"period": "6mo", "interval": "1d", "dma": False, "slice": None},
                    "1 Year": {"period": "2y", "interval": "1d", "dma": True, "slice": 252},
                    "5 Years": {"period": "6y", "interval": "1d", "dma": True, "slice": 1260},
                    "All Time": {"period": "max", "interval": "1d", "dma": True, "slice": "all_time"}
                }
                
                cfg = timeframe_configs[timeframe]
                
                # Fetch history according to config
                history_df = get_stock_history(stock_data["symbol"], period=cfg["period"], interval=cfg["interval"])
                
                if history_df is not None and not history_df.empty:
                    # Calculate Moving Averages if applicable
                    if cfg["dma"]:
                        history_df["50_DMA"] = history_df["Close"].rolling(window=50).mean()
                        history_df["200_DMA"] = history_df["Close"].rolling(window=200).mean()
                        
                        # Slice data for the visual range
                        if cfg["slice"] == "all_time":
                            # For All Time, start from row 200 onwards to skip early NaN averages
                            chart_df = history_df.iloc[200:] if len(history_df) > 200 else history_df
                        elif cfg["slice"] is not None:
                            chart_df = history_df.tail(cfg["slice"])
                        else:
                            chart_df = history_df
                    else:
                        chart_df = history_df
                    
                    # Render Plotly Chart
                    fig = go.Figure()
                    
                    # Close Price trace
                    fig.add_trace(
                        go.Scatter(
                            x=chart_df.index,
                            y=chart_df["Close"],
                            name="Close Price",
                            line=dict(color="#00bcd4", width=2.5),
                            fill="tozeroy",
                            fillcolor="rgba(0, 188, 212, 0.05)"
                        )
                    )
                    
                    # Overlay moving averages if configured
                    if cfg["dma"] and "50_DMA" in chart_df.columns:
                        fig.add_trace(
                            go.Scatter(
                                x=chart_df.index,
                                y=chart_df["50_DMA"],
                                name="50 Day MA (50 DMA)",
                                line=dict(color="#ff9800", width=1.5, dash="dash")
                            )
                        )
                    if cfg["dma"] and "200_DMA" in chart_df.columns:
                        fig.add_trace(
                            go.Scatter(
                                x=chart_df.index,
                                y=chart_df["200_DMA"],
                                name="200 Day MA (200 DMA)",
                                line=dict(color="#e91e63", width=1.5, dash="dot")
                            )
                        )
                    
                    xaxis_title = "Time" if timeframe in ["1 Day", "5 Days", "1 Week"] else "Date"
                    
                    fig.update_layout(
                        margin=dict(l=0, r=0, t=10, b=10),
                        xaxis=dict(
                            showgrid=True,
                            gridcolor="rgba(128, 128, 128, 0.15)",
                            title=xaxis_title
                        ),
                        yaxis=dict(
                            showgrid=True,
                            gridcolor="rgba(128, 128, 128, 0.15)",
                            title=f"Price ({curr})"
                        ),
                        hovermode="x unified",
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        height=400
                    )
                    
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.warning(f"Historical price data could not be retrieved for period '{timeframe}'.")
                
                st.markdown("---")
                
                # 4. About / Summary Section
                with st.expander("About the Company", expanded=True):
                    st.write(stock_data["summary"])
                
                st.markdown("---")
                
                # 5. News Integration Section (Task 2)
                st.subheader("Latest News Coverage")
                try:
                    news_articles = get_stock_news(stock_data["company_name"])
                    
                    # Calculate sentiment metrics
                    pos_count = sum(1 for a in news_articles if a["sentiment"] == "Positive")
                    neu_count = sum(1 for a in news_articles if a["sentiment"] == "Neutral")
                    neg_count = sum(1 for a in news_articles if a["sentiment"] == "Negative")
                    
                    # Classification logic based on positive vs negative article count voting
                    if pos_count > neg_count:
                        overall_sentiment = "Bullish"
                        sentiment_color = "#2e7d32"  # green
                    elif neg_count > pos_count:
                        overall_sentiment = "Bearish"
                        sentiment_color = "#c62828"  # red
                    else:
                        overall_sentiment = "Neutral"
                        sentiment_color = "#757575"  # gray
                        
                    # Overall news sentiment summary card
                    st.markdown(
                        f"""
                        <div style="background-color: rgba(128, 128, 128, 0.05); padding: 1.25rem; border-radius: 8px; border-left: 5px solid {sentiment_color}; margin-bottom: 1.5rem; font-family: 'Inter', sans-serif;">
                            <h4 style="margin: 0 0 0.5rem 0; font-weight: 700;">Overall News Sentiment: <span style="color: {sentiment_color};">{overall_sentiment}</span></h4>
                            <div style="font-size: 0.9rem; color: #718096;">
                                Sentiment category calculated by comparing the volume of Positive and Negative articles. 
                                (Voting logic: Bullish if Positive > Negative, Bearish if Negative > Positive, otherwise Neutral).
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                    # 3-column metric layout for distribution counts
                    s_col1, s_col2, s_col3 = st.columns(3)
                    with s_col1:
                        st.metric(label="Positive Articles", value=pos_count)
                    with s_col2:
                        st.metric(label="Neutral Articles", value=neu_count)
                    with s_col3:
                        st.metric(label="Negative Articles", value=neg_count)
                        
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # Render individual articles
                    for article in news_articles:
                        st.markdown(
                            f"""
                            <div class="news-article">
                                <span class="sentiment-badge sentiment-{article['sentiment'].lower()}">{article['sentiment']}</span>
                                <a class="news-headline" href="{article['url']}" target="_blank">{article['headline']}</a>
                                <div class="news-meta">Source: {article['source']} | Published: {article['publication_date']}</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                except NewsAPIError as e:
                    # Graceful error handling for news failures
                    st.warning(f"Could not retrieve news articles: {str(e)}")
