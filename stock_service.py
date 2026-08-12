import yfinance as yf
import pandas as pd
from typing import Dict, Any, Optional

def get_stock_info(symbol: str) -> Dict[str, Any]:
    """
    Fetches real-time financial metrics for a given stock ticker using yfinance.
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        company_name = info.get("longName") or info.get("shortName")
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        
        if not company_name and not current_price:
            return {
                "success": False,
                "error": f"Symbol '{symbol}' not found. Please verify the ticker."
            }
            
        return {
            "success": True,
            "symbol": symbol.upper(),
            "company_name": company_name or "N/A",
            "current_price": current_price,
            "open_price": info.get("open") or info.get("regularMarketOpen"),
            "day_high": info.get("dayHigh") or info.get("regularMarketDayHigh"),
            "day_low": info.get("dayLow") or info.get("regularMarketDayLow"),
            "volume": info.get("volume") or info.get("regularMarketVolume"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "currency": info.get("currency", "INR"),
            "summary": info.get("longBusinessSummary", "No company summary available."),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "dividend_yield": info.get("dividendYield"),
            "average_volume": info.get("averageVolume"),
            "beta": info.get("beta")
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch data for '{symbol}': {str(e)}"
        }

def get_stock_history(symbol: str, period: str = "1mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    """
    Fetches historical stock prices (Open, High, Low, Close, Volume) for plotting.
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)
        if hist.empty:
            return None
        # Clean timezone from DatetimeIndex if present for clean Plotly rendering
        if hasattr(hist.index, "tz") and hist.index.tz is not None:
            hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return None