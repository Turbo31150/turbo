#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PERPLEXITY CLIENT - Compatible with Perplexity Sonar API
Uses OpenAI-compatible endpoint with search capabilities
"""
import os
import sys
import json
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Encodage UTF-8
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass


@dataclass
class Message:
    role: str
    content: str


@dataclass
class Choice:
    index: int
    message: Message
    finish_reason: str


@dataclass
class Citation:
    url: str
    title: Optional[str] = None


@dataclass
class Completion:
    id: str
    model: str
    choices: List[Choice]
    citations: List[Citation]
    usage: Dict[str, int]


class Perplexity:
    """
    Client Perplexity API compatible avec le SDK officiel
    Supporte: sonar, sonar-pro, sonar-reasoning, sonar-deep-research
    """

    API_URL = "https://api.perplexity.ai/chat/completions"

    # Modèles disponibles (Dec 2024)
    MODELS = {
        "sonar": "sonar",
        "sonar-pro": "sonar-pro",
        "sonar-reasoning": "sonar-reasoning",
        "sonar-deep-research": "sonar-deep-research"
    }

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("PERPLEXITY_API_KEY", "")
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY required. Set via environment or pass api_key parameter.")
        self.session = requests.Session()
        self.chat = self.Chat(self)
        self.search = self.Search(self)

    class Chat:
        def __init__(self, client):
            self.client = client
            self.completions = self.Completions(client)

        class Completions:
            def __init__(self, client):
                self.client = client

            def create(
                self,
                messages: List[Dict],
                model: str = "sonar",
                temperature: float = 0.2,
                max_tokens: int = 1024,
                web_search_options: Dict = None,
                response_format: Dict = None,
                stream: bool = False
            ) -> 'Completion':
                """Create a chat completion with optional web search"""

                # Map model name to actual model ID
                actual_model = Perplexity.MODELS.get(model, model)

                headers = {
                    "Authorization": f"Bearer {self.client.api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": actual_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }

                # Add web search options if provided
                if web_search_options:
                    if "search_domain_filter" in web_search_options:
                        payload["search_domain_filter"] = web_search_options["search_domain_filter"]
                    if "search_recency_filter" in web_search_options:
                        payload["search_recency_filter"] = web_search_options["search_recency_filter"]

                # Add response format if provided
                if response_format:
                    payload["response_format"] = response_format

                try:
                    resp = self.client.session.post(
                        Perplexity.API_URL,
                        headers=headers,
                        json=payload,
                        timeout=60
                    )

                    if resp.status_code == 200:
                        data = resp.json()

                        # Parse choices
                        choices = []
                        for i, choice in enumerate(data.get("choices", [])):
                            msg = choice.get("message", {})
                            choices.append(Choice(
                                index=i,
                                message=Message(
                                    role=msg.get("role", "assistant"),
                                    content=msg.get("content", "")
                                ),
                                finish_reason=choice.get("finish_reason", "stop")
                            ))

                        # Parse citations if available
                        citations = []
                        for cite in data.get("citations", []):
                            if isinstance(cite, str):
                                citations.append(Citation(url=cite))
                            elif isinstance(cite, dict):
                                citations.append(Citation(
                                    url=cite.get("url", ""),
                                    title=cite.get("title")
                                ))

                        return Completion(
                            id=data.get("id", ""),
                            model=data.get("model", actual_model),
                            choices=choices,
                            citations=citations,
                            usage=data.get("usage", {})
                        )
                    else:
                        raise Exception(f"API Error {resp.status_code}: {resp.text}")

                except Exception as e:
                    raise Exception(f"Perplexity API error: {e}")

    class Search:
        def __init__(self, client):
            self.client = client

        def create(self, query: List[str] | str, **kwargs) -> 'SearchResult':
            """Perform web search queries"""
            if isinstance(query, str):
                queries = [query]
            else:
                queries = query

            results = []
            for q in queries:
                # Use chat completion with search
                completion = self.client.chat.completions.create(
                    messages=[{"role": "user", "content": q}],
                    model="sonar",
                    **kwargs
                )

                # Extract citations as search results
                for cite in completion.citations:
                    results.append(SearchResultItem(
                        title=cite.title or q,
                        url=cite.url,
                        snippet=completion.choices[0].message.content[:200] if completion.choices else ""
                    ))

            return SearchResult(results=results, query=queries)


@dataclass
class SearchResultItem:
    title: str
    url: str
    snippet: str = ""


@dataclass
class SearchResult:
    results: List[SearchResultItem]
    query: List[str]


# =============================================================================
# TRADING-SPECIFIC FUNCTIONS
# =============================================================================

class TradingPerplexity(Perplexity):
    """Extended Perplexity client for trading analysis"""

    def analyze_coin(self, symbol: str, include_news: bool = True) -> Dict:
        """Analyze a cryptocurrency with real-time search"""

        prompt = f"""Analyze {symbol} cryptocurrency:
1. Current market sentiment (bullish/bearish/neutral)
2. Key support and resistance levels
3. Recent news or developments affecting price
4. Short-term outlook (24-48h)

Respond in JSON format:
{{"sentiment": "...", "support": [...], "resistance": [...], "news": [...], "outlook": "..."}}"""

        completion = self.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a crypto trading analyst. Respond only in JSON."},
                {"role": "user", "content": prompt}
            ],
            model="sonar-pro",
            web_search_options={
                "search_recency_filter": "day"
            }
        )

        try:
            content = completion.choices[0].message.content
            # Extract JSON from response
            if "{" in content:
                json_str = content[content.find("{"):content.rfind("}")+1]
                return json.loads(json_str)
        except:
            pass

        return {
            "sentiment": "unknown",
            "raw_response": completion.choices[0].message.content if completion.choices else "",
            "citations": [c.url for c in completion.citations]
        }

    def get_market_overview(self) -> Dict:
        """Get real-time crypto market overview"""

        prompt = """Give me a quick crypto market overview:
1. BTC trend and key levels
2. ETH trend and key levels
3. Top 3 trending altcoins today
4. Market sentiment (fear/greed index estimate)

Respond in JSON format."""

        completion = self.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a crypto market analyst. Be concise."},
                {"role": "user", "content": prompt}
            ],
            model="sonar-pro"
        )

        return {
            "analysis": completion.choices[0].message.content if completion.choices else "",
            "sources": [c.url for c in completion.citations]
        }

    def find_trading_opportunities(self, coins: List[str] = None) -> List[Dict]:
        """Find potential trading opportunities"""

        if coins is None:
            coins = ["BTC", "ETH", "SOL", "XRP", "DOGE"]

        prompt = f"""Analyze these cryptocurrencies for trading opportunities: {', '.join(coins)}

For each coin, identify:
- Current trend (up/down/sideways)
- Entry zone if bullish setup
- Stop loss level
- Target levels

Respond in JSON array format."""

        completion = self.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="sonar-pro",
            web_search_options={
                "search_recency_filter": "day"
            }
        )

        return {
            "opportunities": completion.choices[0].message.content if completion.choices else "",
            "citations": [c.url for c in completion.citations]
        }


# =============================================================================
# MAIN / TEST
# =============================================================================

def main():
    print("\n" + "="*60)
    print(" PERPLEXITY CLIENT - Test")
    print("="*60 + "\n")

    # Initialize client
    client = TradingPerplexity()

    # Test 1: Basic search
    print("[Test 1] Basic Search...")
    try:
        search = client.search.create(query="Bitcoin price today")
        print(f"  Results: {len(search.results)}")
        for r in search.results[:3]:
            print(f"  - {r.title}: {r.url}")
    except Exception as e:
        print(f"  Error: {e}")

    print()

    # Test 2: Market overview
    print("[Test 2] Market Overview...")
    try:
        overview = client.get_market_overview()
        print(f"  Analysis: {overview['analysis'][:200]}...")
        print(f"  Sources: {len(overview['sources'])}")
    except Exception as e:
        print(f"  Error: {e}")

    print()

    # Test 3: Coin analysis
    print("[Test 3] Analyze BTC...")
    try:
        analysis = client.analyze_coin("BTC")
        print(f"  Sentiment: {analysis.get('sentiment', 'N/A')}")
        print(f"  Data: {json.dumps(analysis, indent=2)[:300]}...")
    except Exception as e:
        print(f"  Error: {e}")

    print("\n[OK] Perplexity client ready!")


if __name__ == "__main__":
    main()
