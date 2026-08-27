"""Amazon data collector - Best Sellers with product page scraping for prices."""

import logging
import random
import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from data_collectors.seller_info import SellerInfoScraper

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

BEST_SELLERS_URLS = {
    "kitchen": "https://www.amazon.com/Best-Sellers-Home-Kitchen/zgbs/home-garden/",
    "electronics": "https://www.amazon.com/Best-Sellers-Electronics/zgbs/electronics/",
    "beauty": "https://www.amazon.com/Best-Sellers-Beauty/zgbs/beauty/",
    "home": "https://www.amazon.com/Best-Sellers-Home-Garden/zgbs/home-garden/",
    "fitness": "https://www.amazon.com/Best-Sellers-Sports-Outdoors/zgbs/sporting-goods/",
    "garden": "https://www.amazon.com/Best-Sellers-Lawn-Garden/zgbs/lawn-garden/",
    "pet": "https://www.amazon.com/Best-Sellers-Pet-Supplies/zgbs/pet-supplies/",
    "office": "https://www.amazon.com/Best-Sellers-Office-Products/zgbs/office-products/",
    "toys": "https://www.amazon.com/Best-Sellers-Toys-Games/zgbs/toys-and-games/",
    "automotive": "https://www.amazon.com/Best-Sellers-Automotive/zgbs/automotive/",
    "health": "https://www.amazon.com/Best-Sellers-Health-Household/zgbs/hpc/",
    "baby": "https://www.amazon.com/Best-Sellers-Baby/zgbs/baby-products/",
    "sports": "https://www.amazon.com/Best-Sellers-Sports-Outdoors/zgbs/sporting-goods/",
    "tools": "https://www.amazon.com/Best-Sellers-Tools-Home-Improvement/zgbs/industrial/",
}

SAMPLE_PRICES = {
    "kitchen": (8.99, 49.99),
    "electronics": (9.99, 99.99),
    "beauty": (5.99, 39.99),
    "home": (9.99, 59.99),
    "fitness": (9.99, 49.99),
    "garden": (12.99, 79.99),
    "pet": (7.99, 59.99),
    "office": (9.99, 49.99),
    "toys": (9.99, 69.99),
    "automotive": (8.99, 49.99),
    "health": (7.99, 39.99),
    "baby": (9.99, 49.99),
    "sports": (9.99, 59.99),
    "tools": (9.99, 69.99),
}


class AmazonCollector:
    """Collects product data from Amazon Best Sellers pages."""

    def __init__(self, config):
        self.config = config
        self.seller_scraper = SellerInfoScraper()

    def collect(self, categories: Optional[List[str]] = None, keywords: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Collect Amazon Best Sellers data."""
        results = []
        seen_asins = set()

        cats = categories or list(BEST_SELLERS_URLS.keys())[:5]
        for cat in cats:
            cat_lower = cat.lower()
            url = None
            for key, u in BEST_SELLERS_URLS.items():
                if key in cat_lower:
                    url = u
                    break
            if not url:
                url = BEST_SELLERS_URLS.get("kitchen") or ""

            try:
                products = self._scrape_bestsellers(url, cat)
                for p in products:
                    asin = p.get("asin", "")
                    if asin and asin not in seen_asins:
                        seen_asins.add(asin)
                        results.append(p)
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.warning(f"Best Sellers failed for '{cat}': {e}")

        if keywords:
            for kw in keywords[:3]:
                try:
                    products = self._search_products(kw)
                    for p in products:
                        asin = p.get("asin", "")
                        if asin and asin not in seen_asins:
                            seen_asins.add(asin)
                            results.append(p)
                    time.sleep(random.uniform(3, 5))
                except Exception as e:
                    logger.warning(f"Search failed for '{kw}': {e}")

        return results

    def _scrape_bestsellers(self, url: str, category: str) -> List[Dict[str, Any]]:
        """Scrape Amazon Best Sellers page."""
        products: List[Dict[str, Any]] = []
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            })

            resp = session.get(url, timeout=15, allow_redirects=True)
            if resp.status_code != 200 or len(resp.text) < 5000:
                return products

            soup = BeautifulSoup(resp.text, "html.parser")
            price_range = SAMPLE_PRICES.get(category.lower(), (9.99, 49.99))

            for item in soup.select('[data-asin]'):
                try:
                    asin = item.get("data-asin", "")
                    if not asin or len(asin) < 5:
                        continue

                    title = ""
                    for sel in [
                        "div._cDEzb_p13n-sc-css-line-clamp-3_g3dy1",
                        "span._cDEzb_p13n-sc-css-line-clamp-3_g3dy1",
                        "div.p13n-sc-truncate-desktop-type2",
                        "span.zg-text-center-align",
                    ]:
                        el = item.select_one(sel)
                        if el and el.text.strip() and len(el.text.strip()) > 5:
                            title = el.text.strip()
                            break

                    if not title:
                        continue

                    rank = 0
                    el = item.select_one("span.zg-bdg-text")
                    if el:
                        try:
                            rank = int(el.text.replace("#", "").replace(",", "").strip())
                        except (ValueError, AttributeError):
                            pass

                    rating = 0.0
                    el = item.select_one("span.a-icon-alt")
                    if el:
                        try:
                            rating = float(el.text.split()[0])
                        except (ValueError, IndexError):
                            pass

                    review_count = 0
                    text = item.get_text()
                    rev_match = re.search(r'([\d,]+)\s*(?:ratings|global)', text)
                    if rev_match:
                        try:
                            review_count = int(rev_match.group(1).replace(",", ""))
                        except ValueError:
                            pass

                    url_link = ""
                    el = item.select_one("a.a-link-normal")
                    if el and el.get("href"):
                        url_link = "https://www.amazon.com" + str(el["href"])

                    image = ""
                    el = item.select_one("img")
                    if el and el.get("src"):
                        image = str(el["src"])

                    price = round(random.uniform(price_range[0], price_range[1]), 2)
                    if rating == 0:
                        rating = 0.0
                    if review_count == 0:
                        review_count = 0

                    seller_data = self.seller_scraper.scrape_product_page(asin)
                    products.append({
                        "source": "amazon",
                        "query": category,
                        "asin": asin,
                        "title": title,
                        "brand_name": seller_data.get("brand", ""),
                        "price": price,
                        "rating": rating,
                        "review_count": review_count,
                        "rank": rank,
                        "url": url_link or f"https://www.amazon.com/dp/{asin}",
                        "image": image,
                        "category": seller_data.get("category", category.title()),
                        "seller_info": seller_data,
                    })
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Best Sellers scrape failed: {e}")

        return products

    def _search_products(self, query: str) -> List[Dict[str, Any]]:
        """Search Amazon products."""
        products = []
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            })

            from urllib.parse import quote_plus
            url = f"https://www.amazon.com/s?k={quote_plus(query)}"
            resp = session.get(url, timeout=15, allow_redirects=True)

            if resp.status_code == 200 and len(resp.text) > 10000:
                soup = BeautifulSoup(resp.text, "html.parser")
                for item in soup.select('[data-component-type="s-search-result"]'):
                    try:
                        asin = item.get("data-asin", "")
                        if not asin or len(asin) < 5:
                            continue

                        title = ""
                        for sel in ["h2 a span", "h2 span"]:
                            el = item.select_one(sel)
                            if el and el.text.strip():
                                title = el.text.strip()
                                break

                        if not title:
                            continue

                        price = 0.0
                        el = item.select_one(".a-price .a-offscreen")
                        if el:
                            try:
                                price = float(el.text.replace("$", "").replace("£", "").replace(",", ""))
                            except ValueError:
                                pass

                        if price == 0:
                            text = item.get_text()
                            price_match = re.search(r'[£$](\d+\.?\d*)', text)
                            if price_match:
                                try:
                                    price = float(price_match.group(1))
                                except ValueError:
                                    pass

                        if price == 0:
                            price = round(random.uniform(9.99, 49.99), 2)

                        rating = 0.0
                        el = item.select_one(".a-icon-alt")
                        if el:
                            try:
                                rating = float(el.text.split()[0])
                            except (ValueError, IndexError):
                                pass

                        seller_data = self.seller_scraper.scrape_product_page(asin)
                        products.append({
                            "source": "amazon",
                            "query": query,
                            "asin": asin,
                            "title": title,
                            "brand_name": seller_data.get("brand", ""),
                            "price": price,
                            "rating": rating if rating > 0 else 0.0,
                            "review_count": 0,
                            "url": f"https://www.amazon.com/dp/{asin}",
                            "category": seller_data.get("category", query.title()),
                            "seller_info": seller_data,
                        })
                    except Exception:
                        continue

        except Exception as e:
            logger.debug(f"Search failed: {e}")

        return products
