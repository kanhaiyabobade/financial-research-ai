# Financial Research AI: Stock Analysis & IPO Intelligence

A comprehensive, AI-powered financial research platform built with Streamlit. Designed for equity analysis, market monitoring, DRHP forensic analysis, portfolio tracking, and risk evaluation.

---

## Key Features

- **🏠 Market Overview**: Live tracking of key market benchmarks (NIFTY 50, SENSEX) and sentiment-aware market news.
- **📈 Stock Dashboard**: Real-time equity metrics (price, market cap in Cr/Lakhs, P/E ratio), historical performance charts, and company news.
- **🚀 IPO Intelligence**: DRHP PDF processing, automated ratio extraction, red flag detection, and AI investment scoring.
- **💼 Portfolio Intelligence**: Track portfolio holdings, calculate gain/loss, asset allocation, and average buy price.
- **🛡️ Risk Intelligence**: Portfolio concentration analysis, volatility assessment, and risk breakdown.
- **🔔 Watchlist & Alerts**: Monitor watchlist tickers and configure custom price alerts.
- **🧠 AI Research Assistant & Sector Intelligence**: Conversational financial Q&A and sector-specific insights.

---

## Technology Stack

- **Frontend / Framework**: Streamlit
- **Data & Charts**: Pandas, Plotly, yfinance
- **AI & Sentiment**: Google GenAI SDK (`google-genai`), TextBlob
- **Document Processing**: PyMuPDF (`fitz`)
- **Database**: SQLite
- **API & Utilities**: Requests, Python-Dotenv

---

## Local Setup

### 1. Install Dependencies

Ensure Python 3.9+ is installed, then run:

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables (Optional)

Create a `.env` file in the project root or copy from `.env.example`:

```env
GEMINI_API_KEY=your_google_gemini_api_key
NEWS_API_KEY=your_news_api_key
```

*Note: If API keys are missing, non-AI features continue operating normally with safe warning notifications.*

### 3. Run the Streamlit Application

Start the application with:

```bash
streamlit run app.py
```

The app will launch at `http://localhost:8501`. Database tables in `finance.db` are initialized automatically on startup.

---

## Deployment to Streamlit Community Cloud

1. Push your repository to GitHub.
2. Log in to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Click **New app** and select your repository and branch.
4. Set **Main file path** to `app.py`.
5. Under **Advanced settings -> Secrets**, add your credentials:
   ```toml
   GEMINI_API_KEY = "your_key_here"
   NEWS_API_KEY = "your_key_here"
   ```
6. Click **Deploy!**
