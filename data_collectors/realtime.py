"""Real-time data collector with connection testing and live status."""

import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class ConnectionTester:
    """Tests internet connectivity and API availability."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def test_internet(self) -> Dict[str, Any]:
        """Test general internet connectivity."""
        test_urls = [
            ("Google", "https://www.google.com"),
            ("Cloudflare", "https://1.1.1.1"),
            ("Amazon", "https://www.amazon.com"),
        ]

        results: dict[str, Any] = {"connected": False, "latency_ms": 0, "tests": []}

        for name, url in test_urls:
            try:
                start = time.time()
                resp = self.session.get(url, timeout=5)
                latency = (time.time() - start) * 1000

                results["tests"].append({
                    "name": name,
                    "url": url,
                    "status": "OK" if resp.ok else "FAILED",
                    "latency_ms": round(latency, 2),
                    "status_code": resp.status_code,
                })

                if resp.ok:
                    results["connected"] = True
                    results["latency_ms"] = round(latency, 2)

            except Exception as e:
                results["tests"].append({
                    "name": name,
                    "url": url,
                    "status": "ERROR",
                    "error": str(e),
                })

        return results

    def test_google_trends(self) -> Dict[str, Any]:
        """Test Google Trends API connectivity."""
        try:
            from pytrends.request import TrendReq
            pytrends = TrendReq(hl="en-US", tz=360)
            pytrends.build_payload(["test"], timeframe="today 12-m")
            interest = pytrends.interest_over_time()

            return {
                "name": "Google Trends",
                "status": "OK",
                "available": not interest.empty,
            }
        except ImportError:
            return {
                "name": "Google Trends",
                "status": "ERROR",
                "error": "pytrends not installed",
            }
        except Exception as e:
            return {
                "name": "Google Trends",
                "status": "ERROR",
                "error": str(e),
            }

    def test_amazon(self) -> Dict[str, Any]:
        """Test Amazon scraping connectivity."""
        try:
            resp = self.session.get(
                "https://www.amazon.com/s?k=test",
                timeout=10,
            )
            return {
                "name": "Amazon",
                "status": "OK" if resp.ok else "FAILED",
                "status_code": resp.status_code,
                "available": "s-search-result" in resp.text,
            }
        except Exception as e:
            return {
                "name": "Amazon",
                "status": "ERROR",
                "error": str(e),
            }

    def test_all(self) -> Dict[str, Any]:
        """Test all connections."""
        results: Dict[str, Any] = {
            "internet": self.test_internet(),
            "google_trends": self.test_google_trends(),
            "amazon": self.test_amazon(),
            "timestamp": datetime.now().isoformat(),
        }

        all_ok = (
            results["internet"]["connected"] and
            results["google_trends"]["status"] == "OK" and
            results["amazon"]["status"] == "OK"
        )
        results["overall_status"] = "OK" if all_ok else "PARTIAL"

        return results


class RealtimeCollector:
    """Real-time data collector with live status updates."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = {}
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

        self._callbacks: List[Callable] = []
        self._status = "idle"
        self._progress: float = 0
        self._current_source = ""
        self._collected_data: Dict[str, List] = {
            "trends": [],
            "amazon": [],
            "social": [],
        }
        self._stop_event = threading.Event()

    def add_callback(self, callback: Callable):
        """Add status update callback."""
        self._callbacks.append(callback)

    def _update_status(self, status: str, source: str = "", progress: float = 0):
        """Update status and notify callbacks."""
        self._status = status
        self._current_source = source
        self._progress = progress

        for callback in self._callbacks:
            try:
                callback(status, source, progress)
            except Exception:
                pass

    @property
    def status(self) -> Dict[str, Any]:
        """Get current collection status."""
        return {
            "status": self._status,
            "source": self._current_source,
            "progress": self._progress,
            "collected": {
                "trends": len(self._collected_data["trends"]),
                "amazon": len(self._collected_data["amazon"]),
                "social": len(self._collected_data["social"]),
            },
        }

    def collect_realtime(
        self,
        categories: List[str],
        keywords: List[str],
        enable_trends: bool = True,
        enable_amazon: bool = True,
        enable_social: bool = True,
    ) -> Dict[str, List]:
        """Collect data in real-time with live status updates."""
        self._stop_event.clear()
        self._collected_data = {"trends": [], "amazon": [], "social": []}

        search_terms = keywords or categories or []
        if not search_terms:
            self._update_status("No search terms provided")
            return self._collected_data

        total_sources = sum([enable_trends, enable_amazon, enable_social])
        current_source = 0

        if enable_trends:
            self._update_status("collecting", "Google Trends", current_source / total_sources)
            try:
                self._collect_trends(search_terms)
            except Exception as e:
                logger.error(f"Google Trends error: {e}")
            current_source += 1

        if self._stop_event.is_set():
            self._update_status("stopped")
            return self._collected_data

        if enable_amazon:
            self._update_status("collecting", "Amazon", current_source / total_sources)
            try:
                self._collect_amazon(search_terms)
            except Exception as e:
                logger.error(f"Amazon error: {e}")
            current_source += 1

        if self._stop_event.is_set():
            self._update_status("stopped")
            return self._collected_data

        if enable_social:
            self._update_status("collecting", "Social Media", current_source / total_sources)
            try:
                self._collect_social(search_terms)
            except Exception as e:
                logger.error(f"Social Media error: {e}")
            current_source += 1

        self._update_status("complete", "", 1.0)
        return self._collected_data

    def _collect_trends(self, terms: List[str]):
        """Collect Google Trends data."""
        try:
            from pytrends.request import TrendReq
            pytrends = TrendReq(hl="en-US", tz=360)

            for i, term in enumerate(terms):
                if self._stop_event.is_set():
                    break

                try:
                    pytrends.build_payload([term], timeframe="today 12-m")
                    interest = pytrends.interest_over_time()

                    if not interest.empty:
                        interest = interest.reset_index()
                        for _, row in interest.iterrows():
                            self._collected_data["trends"].append({
                                "source": "google_trends",
                                "term": term,
                                "date": row["date"].isoformat(),
                                "interest": int(row.get(term, 0)),
                            })

                    related = pytrends.related_queries()
                    if term in related:
                        rising = related[term].get("rising", [])
                        if not rising.empty:
                            for _, row in rising.head(5).iterrows():
                                self._collected_data["trends"].append({
                                    "source": "google_trends_related",
                                    "term": term,
                                    "related_query": row.get("query", ""),
                                    "value": int(row.get("value", 0)),
                                })

                    self._update_status("collecting", f"Google Trends: {term}", (i + 1) / len(terms))
                    time.sleep(1)

                except Exception as e:
                    logger.debug(f"Trends failed for '{term}': {e}")

        except ImportError:
            logger.warning("pytrends not installed")

    def _collect_amazon(self, terms: List[str]):
        """Collect Amazon product data."""
        for i, term in enumerate(terms):
            if self._stop_event.is_set():
                break

            try:
                products = self._search_amazon(term)
                self._collected_data["amazon"].extend(products)

                self._update_status("collecting", f"Amazon: {term}", (i + 1) / len(terms))
                time.sleep(2)

            except Exception as e:
                logger.debug(f"Amazon failed for '{term}': {e}")

    def _search_amazon(self, query: str, max_pages: int = 2) -> List[Dict]:
        """Search Amazon for products."""
        from bs4 import BeautifulSoup
        products = []

        for page in range(1, max_pages + 1):
            if self._stop_event.is_set():
                break

            try:
                resp = self.session.get(
                    "https://www.amazon.com/s",
                    params={"k": str(query), "page": str(page)},
                    timeout=10,
                )

                if not resp.ok:
                    break

                soup = BeautifulSoup(resp.text, "lxml")

                for item in soup.select('[data-component-type="s-search-result"]'):
                    try:
                        product = {
                            "source": "amazon_search",
                            "query": query,
                            "asin": item.get("data-asin", ""),
                            "title": self._extract_title(item),
                            "brand_name": "",
                            "price": self._extract_price(item),
                            "rating": self._extract_rating(item),
                            "review_count": self._extract_reviews(item),
                            "url": self._extract_url(item),
                            "image": self._extract_image(item),
                        }
                        if product["asin"]:
                            products.append(product)
                    except Exception:
                        continue

                time.sleep(2)

            except Exception as e:
                logger.debug(f"Amazon page {page} failed: {e}")
                break

        return products

    def _extract_title(self, item) -> str:
        el = item.select_one("h2 a span")
        return el.text.strip() if el else ""

    def _extract_price(self, item) -> float:
        whole = item.select_one("span.a-price-whole")
        fraction = item.select_one("span.a-price-fraction")
        if whole:
            try:
                return float(whole.text.strip().replace(",", "") + "." + (fraction.text.strip() if fraction else "00"))
            except ValueError:
                pass
        return 0.0

    def _extract_rating(self, item) -> float:
        el = item.select_one("span.a-icon-alt")
        if el:
            try:
                return float(el.text.split()[0])
            except (ValueError, IndexError):
                pass
        return 0.0

    def _extract_reviews(self, item) -> int:
        el = item.select_one("span.a-size-base.s-underline-text")
        if not el:
            el = item.select_one(".s-underline-text")
        if el:
            try:
                return int(el.text.replace(",", "").replace(".", ""))
            except ValueError:
                pass
        return 0

    def _extract_url(self, item) -> str:
        el = item.select_one("h2 a")
        if el and el.get("href"):
            return "https://www.amazon.com" + el["href"]
        return ""

    def _extract_image(self, item) -> str:
        el = item.select_one("img.s-image")
        return el.get("src", "") if el else ""

    def _collect_social(self, terms: List[str]):
        """Collect social media data."""
        for i, term in enumerate(terms):
            if self._stop_event.is_set():
                break

            self._collect_social_web(term)
            self._update_status("collecting", f"Social: {term}", (i + 1) / len(terms))
            time.sleep(1)

    def _collect_social_web(self, term: str):
        """Collect social data via web scraping."""
        try:
            resp = self.session.get(
                f"https://www.reddit.com/search.json?q={term}&sort=hot&limit=10",
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.ok:
                data = resp.json()
                for post in data.get("data", {}).get("children", []):
                    post_data = post.get("data", {})
                    self._collected_data["social"].append({
                        "source": "reddit",
                        "term": term,
                        "title": post_data.get("title", "")[:200],
                        "score": post_data.get("score", 0),
                        "num_comments": post_data.get("num_comments", 0),
                        "url": post_data.get("url", ""),
                    })
        except Exception as e:
            logger.debug(f"Reddit failed for '{term}': {e}")

    def stop(self):
        """Stop collection."""
        self._stop_event.set()

    def clear(self):
        """Clear collected data."""
        self._collected_data = {"trends": [], "amazon": [], "social": []}
        self._status = "idle"
        self._progress = 0
