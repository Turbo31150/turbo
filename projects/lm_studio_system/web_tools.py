#!/usr/bin/env python3
"""
WEB ACCESS TOOLS v1.0
Accès web autonome pour LM Studio:
- Web scraping
- Search
- Page reading
- Data extraction
"""
import json
import urllib.request
import urllib.parse
from typing import Dict, List
import re

# ============================================
# WEB SEARCH
# ============================================

def search_web(query: str, num_results: int = 5) -> Dict:
    """Search web using DuckDuckGo API"""
    try:
        # DuckDuckGo Instant Answer API
        encoded_query = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1"

        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())

        results = []

        # Abstract
        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", "Result"),
                "snippet": data["Abstract"],
                "url": data.get("AbstractURL", "")
            })

        # Related topics
        for topic in data.get("RelatedTopics", [])[:num_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:100],
                    "snippet": topic.get("Text", ""),
                    "url": topic.get("FirstURL", "")
                })

        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results)
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================
# WEB FETCH
# ============================================

def fetch_url(url: str, extract_text: bool = True) -> Dict:
    """Fetch and extract text from URL"""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )

        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8', errors='ignore')

        if extract_text:
            # Simple HTML to text conversion
            text = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
            text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'\s+', ' ', text).strip()

            # Limit to 5000 chars
            if len(text) > 5000:
                text = text[:5000] + "..."

            return {
                "success": True,
                "url": url,
                "text": text,
                "length": len(text)
            }
        else:
            return {
                "success": True,
                "url": url,
                "html": html[:10000],  # First 10k chars
                "length": len(html)
            }

    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================
# CRYPTO PRICE (CoinGecko)
# ============================================

def get_crypto_price(symbol: str) -> Dict:
    """Get crypto price from CoinGecko"""
    try:
        # Convert symbol to CoinGecko ID
        symbol_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "XRP": "ripple",
            "BNB": "binancecoin",
            "SOL": "solana",
            "ADA": "cardano",
            "DOGE": "dogecoin"
        }

        coin_id = symbol_map.get(symbol.upper(), symbol.lower())

        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true"

        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())

        if coin_id in data:
            price_data = data[coin_id]
            return {
                "success": True,
                "symbol": symbol.upper(),
                "price_usd": price_data.get("usd"),
                "change_24h": price_data.get("usd_24h_change")
            }
        else:
            return {"success": False, "error": "Symbol not found"}

    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================
# NEWS SEARCH (NewsAPI alternative - RSS)
# ============================================

def get_crypto_news(topic: str = "bitcoin", limit: int = 5) -> Dict:
    """Get crypto news from RSS feeds"""
    try:
        # CoinDesk RSS
        url = "https://www.coindesk.com/arc/outboundfeeds/rss/"

        with urllib.request.urlopen(url, timeout=10) as response:
            rss = response.read().decode('utf-8')

        # Simple RSS parsing
        items = re.findall(r'<item>(.*?)</item>', rss, re.DOTALL)
        news = []

        for item in items[:limit]:
            title_match = re.search(r'<title>(.*?)</title>', item)
            link_match = re.search(r'<link>(.*?)</link>', item)
            desc_match = re.search(r'<description>(.*?)</description>', item)

            if title_match:
                news.append({
                    "title": title_match.group(1),
                    "url": link_match.group(1) if link_match else "",
                    "description": desc_match.group(1) if desc_match else ""
                })

        return {
            "success": True,
            "topic": topic,
            "news": news,
            "count": len(news)
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================
# CLI
# ============================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("""Usage:
  python web_tools.py search <query>
  python web_tools.py fetch <url>
  python web_tools.py price <symbol>
  python web_tools.py news [topic]
        """)
    else:
        command = sys.argv[1]

        if command == "search" and len(sys.argv) > 2:
            query = " ".join(sys.argv[2:])
            result = search_web(query)
            print(json.dumps(result, indent=2, ensure_ascii=False))

        elif command == "fetch" and len(sys.argv) > 2:
            url = sys.argv[2]
            result = fetch_url(url)
            print(json.dumps(result, indent=2, ensure_ascii=False))

        elif command == "price" and len(sys.argv) > 2:
            symbol = sys.argv[2]
            result = get_crypto_price(symbol)
            print(json.dumps(result, indent=2, ensure_ascii=False))

        elif command == "news":
            topic = sys.argv[2] if len(sys.argv) > 2 else "bitcoin"
            result = get_crypto_news(topic)
            print(json.dumps(result, indent=2, ensure_ascii=False))
