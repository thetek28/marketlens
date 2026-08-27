"""Social media data collector - Reddit, TikTok, Pinterest, Instagram (free scraping)."""

import json
import logging
import os
import random
import time
import warnings
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


class SocialMediaCollector:
    """Collects trend data from social media platforms using free scraping."""

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()

    def collect(self, categories: Optional[List[str]] = None, keywords: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Collect data from all social platforms."""
        search_terms = keywords or categories or []
        if not search_terms:
            return []

        results = []

        reddit_data = self._collect_reddit(search_terms)
        results.extend(reddit_data)
        time.sleep(random.uniform(1, 2))

        tiktok_data = self._collect_tiktok(search_terms)
        results.extend(tiktok_data)
        time.sleep(random.uniform(1, 2))

        pinterest_data = self._collect_pinterest(search_terms)
        results.extend(pinterest_data)
        time.sleep(random.uniform(1, 2))

        instagram_data = self._collect_instagram(search_terms)
        results.extend(instagram_data)

        return results

    def _collect_reddit(self, terms: List[str]) -> List[Dict[str, Any]]:
        """Collect Reddit data via old.reddit.com (more permissive)."""
        results = []
        self.session.headers.update({
            "User-Agent": "MarketLens/1.0 (research bot)",
            "Accept": "text/html,application/json",
        })

        for term in terms:
            try:
                resp = self.session.get(
                    "https://old.reddit.com/search.json",
                    params={"q": term, "sort": "relevance", "limit": "15", "t": "month"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for post in data.get("data", {}).get("children", []):
                        post_data = post.get("data", {})
                        if post_data.get("score", 0) > 5:
                            results.append({
                                "source": "reddit",
                                "term": term,
                                "title": post_data.get("title", "")[:200],
                                "score": post_data.get("score", 0),
                                "num_comments": post_data.get("num_comments", 0),
                                "subreddit": post_data.get("subreddit", ""),
                                "url": "https://reddit.com" + post_data.get("permalink", ""),
                            })
                else:
                    logger.debug(f"Reddit returned {resp.status_code}")
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.debug(f"Reddit failed for '{term}': {e}")

        if not results:
            results = self._collect_reddit_rss(terms)

        return results

    def _collect_reddit_rss(self, terms: List[str]) -> List[Dict[str, Any]]:
        """Fallback: collect Reddit data via RSS feeds."""
        results = []
        for term in terms:
            try:
                resp = self.session.get(
                    "https://www.reddit.com/search.rss",
                    params={"q": term, "sort": "relevance", "limit": "15"},
                    headers={"User-Agent": "MarketLens/1.0"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for entry in soup.find_all("entry"):
                        title = entry.find("title")
                        if title:
                            results.append({
                                "source": "reddit_rss",
                                "term": term,
                                "title": title.text[:200],
                                "score": 0,
                                "num_comments": 0,
                                "subreddit": "",
                            })
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.debug(f"Reddit RSS failed for '{term}': {e}")
        return results

    def _collect_tiktok(self, terms: List[str]) -> List[Dict[str, Any]]:
        """Collect TikTok data via web scraping (no API key needed)."""
        results = []
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml",
        })

        for term in terms:
            try:
                url = "https://www.tiktok.com/search?q={}".format(term.replace(" ", "+"))
                resp = self.session.get(url, timeout=10, allow_redirects=True)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    scripts = soup.find_all("script", {"id": "__UNIVERSAL_DATA_FOR_REHYDRATION__"})
                    if scripts and scripts[0].string:
                        try:
                            data = json.loads(scripts[0].string)
                            items = data.get("__DEFAULT_SCOPE__", {}).get("webapp.search", {}).get("data", [])
                            for item in items[:10]:
                                info = item.get("item", {}).get("itemInfo", {}).get("itemStruct", {})
                                if info:
                                    results.append({
                                        "source": "tiktok",
                                        "term": term,
                                        "title": info.get("desc", "")[:200],
                                        "views": info.get("stats", {}).get("playCount", 0),
                                        "likes": info.get("stats", {}).get("diggCount", 0),
                                        "shares": info.get("stats", {}).get("shareCount", 0),
                                        "author": info.get("author", {}).get("uniqueId", ""),
                                    })
                        except json.JSONDecodeError:
                            pass
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.debug(f"TikTok failed for '{term}': {e}")

        if not results:
            results = self._collect_tiktok_api(terms)

        return results

    def _collect_tiktok_api(self, terms: List[str]) -> List[Dict[str, Any]]:
        """Fallback: TikTok trending via public API."""
        results = []
        try:
            resp = self.session.get(
                "https://www.tiktok.com/api/search/general/full/",
                params={"keyword": terms[0] if terms else "trending", "search_id": "search"},
                headers={"User-Agent": random.choice(USER_AGENTS)},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", [])[:10]:
                    results.append({
                        "source": "tiktok",
                        "term": terms[0] if terms else "trending",
                        "title": item.get("title", "")[:200],
                        "views": item.get("play_count", 0),
                        "likes": item.get("digg_count", 0),
                    })
        except Exception as e:
            logger.debug(f"TikTok collection failed: {e}")
        return results

    def _collect_pinterest(self, terms: List[str]) -> List[Dict[str, Any]]:
        """Collect Pinterest data via web scraping (no API key needed)."""
        results = []
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml",
        })

        for term in terms:
            try:
                url = "https://www.pinterest.com/search/pins/?q={}".format(term.replace(" ", "%20"))
                resp = self.session.get(url, timeout=10, allow_redirects=True)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    scripts = soup.find_all("script", {"data-test-id": "search-page-data"})
                    if not scripts:
                        scripts = soup.find_all("script", type="application/json")
                    for script in scripts:
                        if not script.string:
                            continue
                        try:
                            data = json.loads(script.string)
                            if isinstance(data, dict):
                                results_data = data.get("resource_response", {}).get("data", {}).get("results", [])
                                for pin in results_data[:10]:
                                    results.append({
                                        "source": "pinterest",
                                        "term": term,
                                        "title": pin.get("title", "")[:200],
                                        "description": pin.get("description", "")[:200],
                                        "repin_count": pin.get("repin_count", 0),
                                        "like_count": pin.get("like_count", 0),
                                    })
                                break
                        except (json.JSONDecodeError, AttributeError):
                            continue
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.debug(f"Pinterest failed for '{term}': {e}")

        if not results:
            results = self._collect_pinterest_rss(terms)

        return results

    def _collect_pinterest_rss(self, terms: List[str]) -> List[Dict[str, Any]]:
        """Fallback: Pinterest trending via RSS."""
        results = []
        for term in terms:
            try:
                resp = self.session.get(
                    "https://www.pinterest.com/search/pins/rss/",
                    params={"q": term},
                    headers={"User-Agent": "MarketLens/1.0"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for item in soup.find_all("item")[:10]:
                        title = item.find("title")
                        if title:
                            results.append({
                                "source": "pinterest_rss",
                                "term": term,
                                "title": title.text[:200],
                                "repin_count": 0,
                            })
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.debug(f"Pinterest RSS failed for '{term}': {e}")
        return results

    def _collect_instagram(self, terms: List[str]) -> List[Dict[str, Any]]:
        """Collect Instagram data via web scraping (no API key needed)."""
        results = []
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml",
            "X-IG-App-ID": "936619743392459",
        })

        for term in terms:
            hashtag = term.replace(" ", "")
            try:
                resp = self.session.get(
                    f"https://www.instagram.com/explore/tags/{hashtag}/",
                    timeout=10,
                    allow_redirects=True,
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    scripts = soup.find_all("script", type="application/ld+json")
                    for script in scripts:
                        if not script.string:
                            continue
                        try:
                            data = json.loads(script.string)
                            if isinstance(data, dict) and "name" in data:
                                results.append({
                                    "source": "instagram",
                                    "term": term,
                                    "hashtag": hashtag,
                                    "title": data.get("name", ""),
                                    "description": data.get("description", "")[:200],
                                })
                        except json.JSONDecodeError:
                            continue

                    meta_desc = soup.find("meta", {"name": "description"})
                    if meta_desc:
                        content = str(meta_desc.get("content", ""))
                        if "posts" in content or "photos" in content:
                            results.append({
                                "source": "instagram",
                                "term": term,
                                "hashtag": hashtag,
                                "title": f"#{hashtag}",
                                "description": content[:200],
                            })
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.debug(f"Instagram failed for '{term}': {e}")

        if not results:
            results = self._collect_instagram_graph(terms)

        return results

    def _collect_instagram_graph(self, terms: List[str]) -> List[Dict[str, Any]]:
        """Fallback: Instagram via Graph API (requires token)."""
        results: List[Dict[str, Any]] = []
        access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        if not access_token:
            return results

        for term in terms:
            hashtag = term.replace(" ", "")
            try:
                resp = self.session.get(
                    "https://graph.instagram.com/ig_hashtag_search",
                    params={"user_id": "me", "q": hashtag, "access_token": access_token},
                    timeout=10,
                )
                if resp.ok:
                    data = resp.json()
                    for ht in data.get("data", [])[:3]:
                        media_resp = self.session.get(
                            "https://graph.instagram.com/{}/recent_media".format(ht["id"]),
                            params={"user_id": "me", "fields": "id,caption,like_count,comments_count",
                                    "access_token": access_token, "limit": 10},
                            timeout=10,
                        )
                        if media_resp.ok:
                            for post in media_resp.json().get("data", []):
                                results.append({
                                    "source": "instagram",
                                    "term": term,
                                    "hashtag": hashtag,
                                    "caption": post.get("caption", "")[:200],
                                    "likes": post.get("like_count", 0),
                                    "comments": post.get("comments_count", 0),
                                })
            except Exception as e:
                logger.debug(f"Instagram Graph failed for '{term}': {e}")
        return results
