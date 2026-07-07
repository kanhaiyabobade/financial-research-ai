# Financial Research AI Dashboard

A modern, interactive Streamlit application designed for equity analysis and research. It fetches stock market data from `yfinance`, displays key financial metrics, plots interactive historical performance charts, and retrieves the latest company-specific news coverage.

## Features
- **Key Equity Metrics**: Real-time lookup of stock price, market cap, and PE ratio.
- **Indian Market Formatting**: Automatic conversion of market caps to Crores/Lakhs for NSE/BSE tickers.
- **Interactive charts**: 1-year historical closing price trend lines using Plotly.
- **News Integration**: Top 5 latest news articles regarding the searched firm.
- **Database Initializer**: Easily sets up structured tables in SQLite for persistent tracking.

---

## Getting Started

### 1. Install Dependencies
Run pip to install the required libraries:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
The application uses NewsAPI to fetch the latest stock news. 
1. Get a free API key at [NewsAPI.org](https://newsapi.org/).
2. Copy the `.env.example` file to create a `.env` file:
   ```bash
   cp .env.example .env
   ```
3. Open the `.env` file and replace `your_api_key_here` with your actual NewsAPI key:
   ```env
   NEWS_API_KEY=your_actual_newsapi_key
   ```

### 3. Initialize the Database
Before running the main app, initialize the local SQLite database (`finance.db`) by running:
```bash
python3 database.py
```
To verify the database tables were generated successfully, you can run:
```bash
python3 check_db.py
```

### 4. Run the Streamlit Dashboard
Launch the dashboard by running:
```bash
streamlit run app.py
```
This will open the application in your default web browser (usually at `http://localhost:8501`).
