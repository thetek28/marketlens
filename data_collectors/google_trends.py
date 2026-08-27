"""Google Trends data collector - uses free scraping."""

import json
import logging
import random
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


class GoogleTrendsCollector:
    """Collects trend data from Google Trends."""

    def __init__(self, config):
        self.config = config

    def collect(self, categories: Optional[List[str]] = None, keywords: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Fetch trend data."""
        search_terms = keywords or categories or []
        if not search_terms:
            return []

        results = []
        for term in search_terms[:3]:
            try:
                trends = self._fetch_trends(term)
                results.extend(trends)
                time.sleep(random.uniform(3, 6))
            except Exception as e:
                logger.warning(f"Trends failed for '{term}': {e}")

        if not results:
            try:
                results = self._fetch_via_pytrends(search_terms)
            except Exception as e:
                logger.warning(f"pytrends fallback failed: {e}")

        return results

    def _fetch_trends(self, term: str) -> List[Dict[str, Any]]:
        """Fetch trends using Google Trends page scraping."""
        records = []
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            })

            url = "https://trends.google.com/trends/explore"
            params = {"q": term, "geo": "US", "date": "today 12-m"}
            resp = session.get(url, params=params, timeout=10)

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")

                for script in soup.find_all("script"):
                    text = script.string or ""
                    if "timelineData" in text or "interestOverTime" in text:
                        try:
                            json_start = text.find("JSON.parse('")
                            if json_start > -1:
                                json_str = text[json_start + 12:]
                                json_end = json_str.find("')")
                                if json_end > -1:
                                    json_str = json_str[:json_end]
                                    json_str = json_str.encode().decode('unicode_escape')
                                    data = json.loads(json_str)
                                    timeline = data.get("default", {}).get("timelineData", [])
                                    for point in timeline:
                                        records.append({
                                            "source": "google_trends",
                                            "term": term,
                                            "date": point.get("formattedTime", ""),
                                            "interest": point.get("value", [0])[0],
                                        })
                        except Exception as e:
                            logger.debug(f"Failed to parse timeline data: {e}")

            if not records:
                records = self._fetch_related_searches(term, session)

        except Exception as e:
            logger.debug(f"Trends scrape failed for '{term}': {e}")

        return records

    def _fetch_related_searches(self, term: str, session: requests.Session) -> List[Dict[str, Any]]:
        """Fetch related searches from Google."""
        records = []
        try:
            resp = session.get(
                "https://www.google.com/search",
                params={"q": term + " amazon best seller", "tbm": "shop"},
                timeout=10,
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for el in soup.select(".sh-dlr__list-result .tAxDx")[:10]:
                    title = el.text.strip()
                    if title:
                        records.append({
                            "source": "google_shopping",
                            "term": term,
                            "title": title[:200],
                        })
        except Exception as e:
            logger.debug(f"Failed to fetch related searches: {e}")
        return records

    def _fetch_via_pytrends(self, terms: List[str]) -> List[Dict[str, Any]]:
        """Fallback to pytrends library."""
        try:
            from pytrends.request import TrendReq
            client = TrendReq(hl="en-US", tz=360)
        except ImportError:
            return []

        results = []
        for term in terms[:2]:
            try:
                client.build_payload([term], cat=0, timeframe="today 12-m")
                interest = client.interest_over_time()
                if not interest.empty:
                    interest = interest.reset_index()
                    for _, row in interest.iterrows():
                        results.append({
                            "source": "google_trends",
                            "term": term,
                            "date": row["date"].isoformat(),
                            "interest": int(row.get(term, 0)),
                        })
                time.sleep(random.uniform(5, 10))
            except Exception as e:
                logger.debug(f"pytrends failed for '{term}': {e}")
                time.sleep(5)
        return results
