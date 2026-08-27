"""
Multi-Marketplace Product Collector
Collects products from Walmart, eBay, and Shopify.
"""
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger("marketlens.marketplace")


class WalmartCollector:
    """Collect products from Walmart."""
    BASE_URL = "https://www.walmart.com/search"

    def __init__(self, config=None):
        self.config = config or {}
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def collect(self, categories: list, keywords: list, max_results: int = 30) -> List[Dict[str, Any]]:
        products = []
        queries = []
        for cat in categories[:3]:
            for kw in keywords[:3]:
                queries.append(f"{kw} {cat}")
        for kw in keywords[:3]:
            queries.append(kw)

        for query in queries[:5]:
            try:
                resp = self.session.get(self.BASE_URL, params={"q": query, "sort": "best_match"}, timeout=15)
                if resp.status_code != 200:
                    continue
                items = self._parse_search(resp.text)
                for item in items[:max_results]:
                    item["source"] = "walmart"
                    item["search_query"] = query
                    products.append(item)
                time.sleep(1.5)
            except Exception as e:
                logger.warning(f"Walmart collect failed for '{query}': {e}")

        return products[:max_results]

    def _parse_search(self, html: str) -> list:
        products = []
        try:
            import json
            match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html)
            if match:
                data = json.loads(match.group(1))
                search_results = data.get("props", {}).get("pageProps", {}).get("initialData", {}).get("searchResult", {}).get("itemStacks", [{}])[0].get("items", [])
                for item in search_results:
                    if not item or item.get("__typename") != "Product":
                        continue
                    products.append({
                        "name": item.get("name", ""),
                        "asin": str(item.get("usItemId", "")),
                        "brand_name": item.get("brand", ""),
                        "amazon_price": float(item.get("priceInfo", {}).get("currentPrice", {}).get("price", 0)),
                        "rating": float(item.get("rating", 0)),
                        "review_count": int(item.get("numberOfReviews", 0)),
                        "category": item.get("category", ""),
                        "brand": item.get("brand", ""),
                        "image": item.get("image", ""),
                        "url": f"https://www.walmart.com/ip/{item.get('usItemId', '')}",
                        "in_stock": item.get("availabilityStatus") == "IN_STOCK",
                    })
        except Exception as e:
            logger.debug(f"Walmart parse failed: {e}")
        return products


class EbayCollector:
    """Collect products from eBay."""
    FINDING_API = "https://svcs.ebay.com/services/search/FindingService/v1"

    def __init__(self, config=None):
        self.config = config or {}
        self.ebay_app_id = (self.config.get("ebay_app_id", "") or
                           __import__("os").environ.get("EBAY_APP_ID", ""))

    def collect(self, categories: list, keywords: list, max_results: int = 30) -> List[Dict[str, Any]]:
        products = []
        if not self.ebay_app_id:
            return self._fallback_collect(keywords, max_results)

        queries = list(set([f"{kw} {cat}" for cat in categories[:3] for kw in keywords[:3]] + keywords[:3]))
        for query in queries[:5]:
            try:
                params = {
                    "OPERATION-NAME": "findItemsByKeywords",
                    "SERVICE-VERSION": "1.0.0",
                    "SECURITY-APPNAME": self.ebay_app_id,
                    "RESPONSE-DATA-FORMAT": "JSON",
                    "REST-PAYLOAD": "",
                    "keywords": query,
                    "paginationInput.entriesPerPage": min(max_results, 20),
                    "sortOrder": "BestMatch",
                }
                resp = requests.get(self.FINDING_API, params=params, timeout=15)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                items = data.get("findItemsByKeywordsResponse", [{}])[0].get("searchResult", [{}])[0].get("item", [])
                for item in items:
                    title = item.get("title", [""])[0]
                    price_info = item.get("sellingStatus", [{}])[0]
                    current_price = float(price_info.get("currentPrice", [{}])[0].get("__value__", 0))
                    products.append({
                        "name": title,
                        "asin": item.get("itemId", [""])[0],
                        "brand_name": "",
                        "amazon_price": current_price,
                        "rating": 0,
                        "review_count": int(item.get("sellingStatus", [{}])[0].get("sellerInfo", [{}])[0].get("sellerUserName", "0") or 0),
                        "category": item.get("primaryCategory", [{}])[0].get("categoryName", ""),
                        "brand": "",
                        "image": item.get("galleryURL", [""])[0],
                        "url": item.get("viewItemURL", [""])[0],
                        "source": "ebay",
                        "search_query": query,
                    })
                time.sleep(1)
            except Exception as e:
                logger.warning(f"eBay collect failed for '{query}': {e}")

        return products[:max_results]

    def _fallback_collect(self, keywords: list, max_results: int = 30) -> List[Dict[str, Any]]:
        products = []
        for kw in keywords[:5]:
            try:
                resp = requests.get(
                    "https://www.ebay.com/sch/i.html",
                    params={"_nkw": kw, "_sop": "12", "_ipg": "25"},
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"},
                    timeout=15,
                )
                if resp.status_code != 200:
                    continue
                items = re.findall(r'class="s-item__link"[^>]*href="([^"]+)"[^>]*>.*?<span class="s-item__title"[^>]*>([^<]+)</span>.*?<span class="s-item__price"[^>]*>([^<]+)</span>', resp.text, re.DOTALL)
                for url, title, price_str in items[:10]:
                    price = float(re.sub(r"[^0-9.]", "", price_str) or 0)
                    products.append({
                        "name": title,
                        "asin": url.split("/itm/")[-1].split("?")[0] if "/itm/" in url else "",
                        "brand_name": "",
                        "amazon_price": price,
                        "rating": 0,
                        "review_count": 0,
                        "category": "",
                        "brand": "",
                        "image": "",
                        "url": url,
                        "source": "ebay",
                        "search_query": kw,
                    })
                time.sleep(1)
            except Exception as e:
                logger.warning(f"eBay fallback collect failed: {e}")
        return products[:max_results]


class ShopifyCollector:
    """Collect products from Shopify stores (public API)."""

    def __init__(self, config=None):
        self.config = config or {}
        self.stores = self.config.get("shopify_stores", [
            "https://allbirds.com/products.json",
            "https://www.gymshark.com/products.json",
        ])

    def collect(self, categories: Optional[List[Any]] = None, keywords: Optional[List[Any]] = None, max_results: int = 30) -> List[Dict[str, Any]]:
        products = []
        for store_url in self.stores:
            try:
                resp = requests.get(store_url, params={"limit": 25}, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0"
                })
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for item in data.get("products", [])[:max_results]:
                    variants = item.get("variants", [])
                    price = float(variants[0].get("price", 0)) if variants else 0
                    products.append({
                        "name": item.get("title", ""),
                        "asin": str(item.get("id", "")),
                        "brand_name": item.get("vendor", ""),
                        "amazon_price": price,
                        "rating": 0,
                        "review_count": 0,
                        "category": item.get("product_type", ""),
                        "brand": item.get("vendor", ""),
                        "image": item.get("image", {}).get("src", "") if item.get("image") else "",
                        "url": f"https://{store_url.split('//')[1].split('/products')[0]}/products/{item.get('handle', '')}",
                        "source": "shopify",
                    })
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Shopify collect failed for {store_url}: {e}")

        return products[:max_results]


def collect_from_marketplaces(config: Any = None, categories: Any = None, keywords: Any = None) -> List[Dict[str, Any]]:
    """Collect from all marketplaces."""
    all_products: List[Dict[str, Any]] = []
    collectors: List[Tuple[str, Any]] = [
        ("Walmart", WalmartCollector(config)),
        ("eBay", EbayCollector(config)),
        ("Shopify", ShopifyCollector(config)),
    ]
    cats = categories or ["general"]
    kws = keywords or ["trending"]

    for name, collector in collectors:
        try:
            products = collector.collect(cats, kws, max_results=15)
            all_products.extend(products)
            logger.info(f"{name}: {len(products)} products collected")
        except Exception as e:
            logger.warning(f"{name} collection failed: {e}")

    return all_products
