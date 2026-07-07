import os
import requests
from typing import List, Dict, Any
from textblob import TextBlob

class NewsAPIError(Exception):
    """Base exception for NewsAPI service errors."""
    pass

class MissingAPIKeyError(NewsAPIError):
    """Raised when the NEWS_API_KEY environment variable is not set."""
    pass

class APIRequestError(NewsAPIError):
    """Raised when the NewsAPI request fails or returns an error status."""
    pass

class NoNewsFoundError(NewsAPIError):
    """Raised when no news articles are found for the given company query."""
    pass

def get_stock_news(company_name: str) -> List[Dict[str, str]]:
    """
    Fetches recent news articles for a given company using NewsAPI.
    
    Args:
        company_name (str): The name of the company to search news for.
        
    Returns:
        List[Dict[str, str]]: A list of dictionaries containing article details:
                              - headline (str)
                              - source (str)
                              - publication_date (str)
                              - url (str)
                              
    Raises:
        MissingAPIKeyError: If NEWS_API_KEY is not configured.
        APIRequestError: If the HTTP request fails or returns an API error.
        NoNewsFoundError: If no articles are returned for the query.
    """
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        raise MissingAPIKeyError("NEWS_API_KEY environment variable is not configured.")
        
    url = "https://newsapi.org/v2/everything"
    
    params = {
        "q": company_name,
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": 10,  # Fetch slightly more to filter out incomplete articles
        "apiKey": api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
    except requests.exceptions.RequestException as e:
        raise APIRequestError(f"Network request to NewsAPI failed: {str(e)}")
        
    if response.status_code != 200:
        error_msg = f"NewsAPI returned status code {response.status_code}."
        try:
            error_data = response.json()
            if "message" in error_data:
                error_msg += f" Error detail: {error_data['message']}"
        except Exception:
            pass
        raise APIRequestError(error_msg)
        
    data = response.json()
    articles = data.get("articles", [])
    
    if not articles:
        raise NoNewsFoundError(f"No news articles found for '{company_name}'.")
        
    formatted_articles = []
    for art in articles:
        headline = art.get("title")
        source_name = art.get("source", {}).get("name")
        pub_date = art.get("publishedAt")
        art_url = art.get("url")
        
        # Validate that the core fields are populated
        if headline and source_name and art_url:
            # Format date for cleaner display: e.g., '2026-07-07T12:00:00Z' -> '2026-07-07'
            formatted_date = pub_date.split("T")[0] if pub_date else "N/A"
            
            # Perform sentiment analysis on the headline using TextBlob
            try:
                analysis = TextBlob(headline)
                polarity = analysis.sentiment.polarity
                if polarity > 0.1:
                    sentiment = "Positive"
                elif polarity < -0.1:
                    sentiment = "Negative"
                else:
                    sentiment = "Neutral"
            except Exception:
                sentiment = "Neutral"  # Graceful fallback
                
            formatted_articles.append({
                "headline": headline,
                "source": source_name,
                "publication_date": formatted_date,
                "url": art_url,
                "sentiment": sentiment
            })
            
            # Stop when we collect 5 valid articles
            if len(formatted_articles) == 5:
                break
                
    if not formatted_articles:
        raise NoNewsFoundError(f"No valid articles found for '{company_name}'.")
        
    return formatted_articles
