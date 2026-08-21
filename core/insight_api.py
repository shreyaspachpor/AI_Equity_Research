import os
import requests
import json
from typing import Optional

def fetch_market_data(company_name: str) -> Optional[str]:
    """
    Fetches market data using the InsightSentry RapidAPI in two steps:
    1. Search for the company to get the exact ticker (code).
    2. Fetch the 'Basic Info' using that ticker for rich financials.
    This data is injected into the LLM prompt to supplement information missing from the PDF.
    """
    api_key = os.getenv("INSIGHTENTRY_KEY")
    if not api_key:
        return None

    # Step 1: Search for the symbol
    search_url = "https://insightsentry.p.rapidapi.com/v3/symbols/search"
    search_querystring = {
        "query": company_name,
        "type": "stock",
        "country": "IN",
        "page": "1"
    }
    
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "insightsentry.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    
    try:
        search_response = requests.get(search_url, headers=headers, params=search_querystring, timeout=10)
        
        if search_response.status_code != 200:
            print(f"InsightSentry Search API returned {search_response.status_code}: {search_response.text}")
            return None
            
        search_data = search_response.json()
        symbols = search_data.get("symbols", [])
        
        if not symbols:
            return "No matching Indian stocks found in InsightSentry for this company."
            
        # Grab the first matching ticker code
        ticker_code = symbols[0].get("code")
        if not ticker_code:
            return "Found the company, but no ticker code was available in InsightSentry."
            
        print(f"  - InsightSentry found ticker: {ticker_code}. Fetching Basic Info...")
        
        # Step 2: Fetch Basic Info using the ticker code
        info_url = f"https://insightsentry.p.rapidapi.com/v3/symbols/{ticker_code}/info"
        info_response = requests.get(info_url, headers=headers, timeout=10)
        
        if info_response.status_code != 200:
            print(f"InsightSentry Basic Info API returned {info_response.status_code}: {info_response.text}")
            # Fallback to returning just the search result if info fails
            return f"Found Ticker: {ticker_code}, but failed to fetch basic info."
            
        info_data = info_response.json()
        
        # Format the rich basic info for the LLM
        # Only extract the most useful metrics to save token space
        info_str = (
            f"Company Name: {info_data.get('name')}\n"
            f"Ticker: {info_data.get('code')}\n"
            f"Exchange: {info_data.get('exchange')}\n"
            f"Sector/Industry: {info_data.get('sector')} / {info_data.get('industry')}\n"
            f"Market Cap: {info_data.get('market_cap')} {info_data.get('currency_code')}\n"
            f"Shares Outstanding: {info_data.get('total_shares_outstanding')}\n"
            f"Total Revenue: {info_data.get('total_revenue')} {info_data.get('currency_code')}\n"
            f"P/E Ratio (TTM): {info_data.get('price_earnings_ttm')}\n"
            f"EPS (TTM): {info_data.get('earnings_per_share_basic_ttm')}\n"
            f"Dividend Yield: {info_data.get('dividends_yield')}\n"
            f"52-Week High: {info_data.get('all_time_high')} (Note: Check if this represents 52W or All Time)\n"
            f"52-Week Low: {info_data.get('all_time_low')}\n"
            f"Current Price (Prev Close): {info_data.get('prev_close_price')}\n"
            f"Description: {info_data.get('description')}\n"
        )
        
        return f"Market Data from InsightSentry (Basic Info):\n\n{info_str}"
            
    except Exception as e:
        print(f"Error fetching from InsightSentry API: {e}")
        return None
