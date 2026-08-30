import os
import requests
from typing import List, Dict, Any
from textblob import TextBlob
from dotenv import load_dotenv

load_dotenv(override=True)

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
    Fetches recent news articles for a given company using NewsAPI and analyzes sentiment.
    """
    load_dotenv(override=True)
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key or not api_key.strip():
        raise MissingAPIKeyError("NEWS_API_KEY is not configured in environment (.env).")

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": company_name,
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": 10,
        "apiKey": api_key.strip()
    }

    try:
        response = requests.get(url, params=params, timeout=8)
    except requests.exceptions.RequestException as e:
        raise APIRequestError(f"Network request to NewsAPI failed: {str(e)}")

    if response.status_code != 200:
        error_msg = f"NewsAPI returned status code {response.status_code}."
        try:
            error_data = response.json()
            if "message" in error_data:
                error_msg += f" Details: {error_data['message']}"
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

        if headline and source_name and art_url:
            formatted_date = pub_date.split("T")[0] if pub_date else "N/A"
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
                sentiment = "Neutral"

            formatted_articles.append({
                "headline": headline,
                "source": source_name,
                "publication_date": formatted_date,
                "url": art_url,
                "sentiment": sentiment
            })

            if len(formatted_articles) == 5:
                break

    if not formatted_articles:
        raise NoNewsFoundError(f"No valid news articles found for '{company_name}'.")

    return formatted_articles
