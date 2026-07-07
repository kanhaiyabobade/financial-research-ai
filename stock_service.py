import yfinance as yf
import pandas as pd
from typing import Dict, Any, Optional

def get_stock_info(symbol: str) -> Dict[str, Any]:
    """
    Fetches real-time financial metrics for a given stock ticker using yfinance.
    
    Args:
        symbol (str): The ticker symbol (e.g. 'RELIANCE.NS', 'AAPL').
        
    Returns:
        Dict[str, Any]: A dictionary containing stock info or error details.
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Check if the returned dict is valid/populated. Invalid symbols return minimal or empty dict.
        # Check for standard fields like longName or currentPrice.
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
    Fetches historical stock prices for plotting.
    
    Args:
        symbol (str): The ticker symbol.
        period (str): The time period (e.g. '1mo', '3mo', '1y').
        interval (str): The data interval (e.g. '1m', '5m', '15m', '1d').
        
    Returns:
        Optional[pd.DataFrame]: Historical close prices or None if failed.
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)
        if hist.empty:
            return None
        return hist
    except Exception:
        return None