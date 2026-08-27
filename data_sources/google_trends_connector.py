"""Google Trends Data Source Connector.

Wraps the existing Google Trends scraping to return normalized trend data.
All data is real - no fake trends are generated.
"""

import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import (
    DataSource,
    DataSourceConfig,
    DataSourceStatus,
    NormalizedKeyword,
    NormalizedTrend,
    SourceAttribution,
)

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]


class GoogleTrendsConnector(DataSource):
    """Google Trends data source connector."""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self._session = None
        self._pytrends = None
        self._setup_session()

    def _setup_session(self):
        """Create a requests session."""
        try:
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": USER_AGENTS[0],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })
        except ImportError:
            logger.error("requests library not installed")

        try:
            from pytrends.request import TrendReq
            self._pytrends = TrendReq(hl="en-US", tz=360)
        except ImportError:
            logger.warning("pytrends not installed, using scraping only")

    def test_connection(self) -> bool:
        """Test if Google Trends is accessible."""
        if self._pytrends:
            try:
                self._pytrends.build_payload(["test"], timeframe="today 12-m")
                self._status = DataSourceStatus.CONNECTED
                return True
            except Exception as e:
                self._last_error = str(e)

        if self._session:
            try:
                resp = self._session.get("https://trends.google.com/trends/?geo=US", timeout=10)
                if resp.status_code == 200:
                    self._status = DataSourceStatus.CONNECTED
                    return True
            except Exception as e:
                self._last_error = str(e)

        self._status = DataSourceStatus.ERROR
        return False

    def get_trends(self, keywords: List[str], marketplace: str = "US") -> List[NormalizedTrend]:
        """Get real trend data for keywords."""
        if not keywords:
            return []

        trends = []

        # Try pytrends first (more reliable)
        if self._pytrends:
            trends = self._fetch_via_pytrends(keywords[:5])
            if trends:
                return trends

        # Fallback to scraping
        if self._session:
            for keyword in keywords[:3]:
                try:
                    trend = self._fetch_trends_scraping(keyword)
                    if trend:
                        trends.append(trend)
                except Exception as e:
                    logger.error("Trends scraping failed for %s: %s", keyword, e)

        if trends:
            self._record_request()
            self._status = DataSourceStatus.CONNECTED

        return trends

    def get_keywords(self, query: str, marketplace: str = "US") -> List[NormalizedKeyword]:
        """Get related keywords from Google Trends."""
        keywords = []

        if self._session:
            try:
                related = self._fetch_related_searches(query)
                for kw in related[:20]:
                    keywords.append(NormalizedKeyword(
                        keyword=kw,
                        source=SourceAttribution(
                            source="Google Trends",
                            source_type="trend",
                            retrieved_at=datetime.now(),
                            confidence="verified",
                            data_status="live",
                        ),
                        data_type="observed",
                    ))
            except Exception as e:
                logger.error("Related keywords failed for %s: %s", query, e)

        if keywords:
            self._record_request()

        return keywords

    def _fetch_via_pytrends(self, terms: List[str]) -> List[NormalizedTrend]:
        """Fetch trends using pytrends library."""
        trends = []
        try:
            self._pytrends.build_payload(terms, timeframe="today 12-m", geo="US")
            data = self._pytrends.interest_over_time()

            if data.empty:
                return []

            for term in terms:
                if term not in data.columns:
                    continue

                series = data[term]
                time_series = []
                for date, value in series.items():
                    time_series.append({
                        "date": date.isoformat(),
                        "interest": int(value),
                    })

                # Determine trend direction
                if len(series) >= 4:
                    recent = series.tail(4).mean()
                    older = series.head(4).mean()
                    if recent > older * 1.1:
                        direction = "rising"
                    elif recent < older * 0.9:
                        direction = "falling"
                    else:
                        direction = "stable"
                else:
                    direction = "stable"

                avg_interest = float(series.mean())

                trends.append(NormalizedTrend(
                    keyword=term,
                    interest=avg_interest,
                    trend_direction=direction,
                    period="12 months",
                    time_series=time_series,
                    source=SourceAttribution(
                        source="Google Trends",
                        source_type="trend",
                        retrieved_at=datetime.now(),
                        confidence="verified",
                        data_status="live",
                    ),
                ))

        except Exception as e:
            logger.error("pytrends fetch failed: %s", e)

        return trends

    def _fetch_trends_scraping(self, term: str) -> Optional[NormalizedTrend]:
        """Fetch trends by scraping Google Trends page."""
        try:
            url = f"https://trends.google.com/trends/explore?geo=US&q={term}"
            resp = self._session.get(url, timeout=self.config.timeout_seconds)

            if resp.status_code != 200:
                return None

            # Extract timeline data from embedded JSON
            pattern = r'window\.INIT_DATA\s*=\s*({.*?});\s*</script>'
            match = re.search(pattern, resp.text, re.DOTALL)

            if not match:
                return None

            data = json.loads(match.group(1))
            timeline = data.get("widgets", [{}])[0].get("timeseries", [])

            if not timeline:
                return None

            time_series = []
            for point in timeline:
                if len(point) >= 2:
                    time_series.append({
                        "date": datetime.fromtimestamp(point[0] / 1000).isoformat() if isinstance(point[0], (int, float)) else str(point[0]),
                        "interest": point[1] if isinstance(point[1], (int, float)) else 0,
                    })

            if not time_series:
                return None

            interests = [p["interest"] for p in time_series]
            avg_interest = sum(interests) / len(interests) if interests else 0

            return NormalizedTrend(
                keyword=term,
                interest=avg_interest,
                trend_direction="stable",
                period="12 months",
                time_series=time_series,
                source=SourceAttribution(
                    source="Google Trends",
                    source_type="trend",
                    source_url=url,
                    retrieved_at=datetime.now(),
                    confidence="verified",
                    data_status="live",
                ),
            )

        except Exception as e:
            logger.error("Trends scraping failed: %s", e)
            return None

    def _fetch_related_searches(self, term: str) -> List[str]:
        """Fetch related search terms."""
        related = []
        try:
            url = f"https://trends.google.com/trends/explore?geo=US&q={term}"
            resp = self._session.get(url, timeout=self.config.timeout_seconds)

            if resp.status_code != 200:
                return []

            # Extract related queries from page
            pattern = r'"searches":\s*(\[.*?\])'
            match = re.search(pattern, resp.text)

            if match:
                searches = json.loads(match.group(1))
                for s in searches[:20]:
                    if isinstance(s, dict) and "query" in s:
                        related.append(s["query"])
                    elif isinstance(s, str):
                        related.append(s)

        except Exception as e:
            logger.error("Related searches failed: %s", e)

        return related
