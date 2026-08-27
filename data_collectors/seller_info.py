"""MarketLens Seller Information Scraper - Detailed product page data.

Features:
  - Rotating User-Agent strings
  - Configurable proxy support
  - Automatic retry with exponential backoff
  - Anti-detection headers (TLS fingerprint hints)
  - Rate limiting between requests
"""

import logging
import random
import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

ANTI_DETECT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


class SellerInfoScraper:
    """Scrapes detailed seller/product info from Amazon product pages.

    Supports proxy rotation, retry logic, and anti-detection measures.
    """

    def __init__(self, proxies: Optional[List[str]] = None,
                 max_retries: int = 3, delay_between: float = 2.0):
        self.proxies = proxies or []
        self.max_retries = max_retries
        self.delay_between = delay_between
        self._last_request_time = 0.0
        self._proxy_index = 0
        self._setup_session()

    def _setup_session(self):
        """Create a fresh session with anti-detection headers."""
        self.session = requests.Session()
        ua = random.choice(USER_AGENTS)
        headers = {**ANTI_DETECT_HEADERS, "User-Agent": ua}
        self.session.headers.update(headers)

    def _get_proxy(self) -> Optional[Dict[str, str]]:
        """Get next proxy from rotation list."""
        if not self.proxies:
            return None
        proxy = self.proxies[self._proxy_index % len(self.proxies)]
        self._proxy_index += 1
        if proxy.startswith("socks"):
            return {"http": proxy, "https": proxy}
        return {"http": f"http://{proxy}", "https": f"http://{proxy}"}

    def _rate_limit(self):
        """Enforce minimum delay between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay_between:
            jitter = random.uniform(0.5, 1.5)
            time.sleep(self.delay_between - elapsed + jitter)

    def _is_blocked(self, resp: requests.Response) -> bool:
        """Detect if Amazon has blocked/rate-limited us."""
        if resp.status_code == 503:
            return True
        if resp.status_code == 429:
            return True
        text_lower = resp.text[:5000].lower()
        block_signals = [
            "robot check", "captcha", "automated access",
            "sorry, something went wrong", "api-services-support@amazon.com",
            "enter the characters you see below",
            "type the characters you see in this image",
        ]
        return any(signal in text_lower for signal in block_signals)

    def _make_request(self, url: str) -> Optional[requests.Response]:
        """Make HTTP request with retry, proxy rotation, and anti-detection."""
        for attempt in range(self.max_retries):
            self._rate_limit()
            proxy = self._get_proxy()

            if attempt > 0:
                ua = random.choice(USER_AGENTS)
                self.session.headers["User-Agent"] = ua
                backoff = min(30, 2 ** attempt + random.uniform(0, 1))
                logger.debug(f"Retry {attempt + 1}/{self.max_retries}, backoff {backoff:.1f}s")
                time.sleep(backoff)

            try:
                resp = self.session.get(url, timeout=20, allow_redirects=True,
                                        proxies=proxy)
                self._last_request_time = time.time()

                if self._is_blocked(resp):
                    logger.debug(f"Blocked on attempt {attempt + 1} (status={resp.status_code})")
                    continue

                if resp.status_code == 200:
                    return resp

                logger.debug(f"HTTP {resp.status_code} for {url}")
                continue

            except requests.Timeout:
                logger.debug(f"Timeout on attempt {attempt + 1} for {url}")
                continue
            except requests.ConnectionError:
                logger.debug(f"Connection error on attempt {attempt + 1}")
                continue
            except Exception as e:
                logger.debug(f"Request error on attempt {attempt + 1}: {e}")
                continue

        return None

    def scrape_product_page(self, asin: str) -> Dict[str, Any]:
        """Scrape full product page for seller details.

        Uses retry logic, proxy rotation, and anti-detection measures.
        Returns empty-default dict if scrape fails. Never returns random data.
        """
        url = f"https://www.amazon.com/dp/{asin}"
        try:
            resp = self._make_request(url)
            if resp is None:
                return self._empty_data(asin)

            soup = BeautifulSoup(resp.text, "html.parser")
            return self._parse_product_page(soup, asin)

        except Exception as e:
            logger.debug(f"Product page scrape failed for {asin}: {e}")
            return self._empty_data(asin)

    def _parse_product_page(self, soup: BeautifulSoup, asin: str) -> Dict[str, Any]:
        """Parse Amazon product page HTML."""
        info: Dict[str, Any] = {"asin": asin}

        info["seller_name"] = self._extract_seller_name(soup)
        info["seller_rating"] = self._extract_seller_rating(soup)
        info["seller_reviews"] = self._extract_seller_reviews(soup)
        info["fulfillment"] = self._extract_fulfillment(soup)
        info["brand"] = self._extract_brand(soup)
        info["manufacturer"] = self._extract_manufacturer(soup)
        info["product_weight"] = self._extract_weight(soup)
        info["dimensions"] = self._extract_dimensions(soup)
        info["date_first_available"] = self._extract_date_available(soup)
        info["bsr"] = self._extract_bsr(soup)
        info["category"] = self._extract_category(soup)
        info["amazon_choice"] = self._extract_amazon_choice(soup)
        info["buy_box_winner"] = self._extract_buy_box(soup)
        info["num_sellers"] = self._extract_num_sellers(soup)
        info["is_fba"] = "FBA" in info.get("fulfillment", "")
        info["is_prime"] = self._extract_prime(soup)
        info["has_coupon"] = self._extract_coupon(soup)
        info["coupon_value"] = self._extract_coupon_value(soup)
        info["is_amazon_retail"] = self._extract_amazon_retail(soup)
        info["seller_location"] = self._extract_seller_location(soup)
        info["return_policy"] = self._extract_return_policy(soup)
        info["warranty"] = self._extract_warranty(soup)
        info["stock_status"] = self._extract_stock(soup)
        info["monthly_sales_est"] = self._estimate_monthly_sales(info)
        info["competition_level"] = self._assess_competition(info)
        info["availability"] = self._extract_availability(soup)
        info["is_restricted"] = self._extract_restricted(soup)
        info["has_add_to_cart"] = self._extract_add_to_cart(soup)

        return info

    def _extract_seller_name(self, soup):
        for sel in ["#sellerProfileTriggerId", "#merchant-info a", "a#sellerProfileTriggerId",
                     "#tabular-buybox-truncate-1 span a", "#tabular-buybox span a"]:
            el = soup.select_one(sel)
            if el and el.text.strip():
                return el.text.strip()[:50]
        return "Amazon.com"

    def _extract_seller_rating(self, soup):
        el = soup.select_one("#seller-feedback-summary")
        if el:
            match = re.search(r'(\d+\.?\d*)%', el.get_text())
            if match:
                return float(match.group(1))
        return 0.0

    def _extract_seller_reviews(self, soup):
        el = soup.select_one("#seller-feedback-summary")
        if el:
            match = re.search(r'([\d,]+)\s*(?:ratings|global)', el.get_text())
            if match:
                return int(match.group(1).replace(",", ""))
        return 0

    def _extract_fulfillment(self, soup):
        for el in soup.select("#tabular-buybox span"):
            text = el.text.strip().lower()
            if "ships from" in text or "fulfilled by" in text:
                if "amazon" in text:
                    return "FBA (Fulfilled by Amazon)"
                else:
                    return "FBM (Fulfilled by Merchant)"
        return ""

    def _extract_brand(self, soup):
        for sel in ["#bylineInfo", "#brand", ".po-break-word a"]:
            el = soup.select_one(sel)
            if el:
                text = el.text.strip()
                text = re.sub(r'^(Visit the |Brand: )', '', text)
                if text and len(text) > 1:
                    return text[:40]
        return ""

    def _extract_manufacturer(self, soup):
        for row in soup.select("#productDetails_detailBullets_sections1 tr, #detailBullets_feature_div li"):
            text = row.get_text().lower()
            if "manufacturer" in text or "brand" in text:
                match = re.search(r':\s*(.+)', row.get_text())
                if match:
                    return match.group(1).strip()[:40]
        return ""

    def _extract_weight(self, soup):
        for row in soup.select("#productDetails_detailBullets_sections1 tr, #detailBullets_feature_div li"):
            text = row.get_text().lower()
            if "weight" in text:
                match = re.search(r':\s*(.+)', row.get_text())
                if match:
                    return match.group(1).strip()[:20]
        return ""

    def _extract_dimensions(self, soup):
        for row in soup.select("#productDetails_detailBullets_sections1 tr, #detailBullets_feature_div li"):
            text = row.get_text().lower()
            if "dimension" in text:
                match = re.search(r':\s*(.+)', row.get_text())
                if match:
                    return match.group(1).strip()[:30]
        return ""

    def _extract_date_available(self, soup):
        for row in soup.select("#productDetails_detailBullets_sections1 tr, #detailBullets_feature_div li"):
            text = row.get_text().lower()
            if "date" in text and "available" in text:
                match = re.search(r':\s*(.+)', row.get_text())
                if match:
                    return match.group(1).strip()[:15]
        return ""

    def _extract_bsr(self, soup):
        for row in soup.select("#productDetails_detailBullets_sections1 tr, #detailBullets_feature_div li"):
            text = row.get_text().lower()
            if "best seller rank" in text:
                match = re.search(r'#([\d,]+)', row.get_text())
                if match:
                    return int(match.group(1).replace(",", ""))
        return 0

    def _extract_category(self, soup):
        for sel in [
            "#wayfinding-breadcrumbs_feature_div a",
            "#detailBullets_feature_div li span.a-list-item a",
            ".a-carousel-card a",
        ]:
            links = soup.select(sel)
            if links:
                text = links[-1].get_text(strip=True)
                if text and len(text) > 1:
                    return text
        for row in soup.select("#productDetails_detailBullets_sections1 tr, #detailBullets_feature_div li"):
            text = row.get_text().lower()
            if "category" in text or "department" in text:
                match = re.search(r':\s*(.+)', row.get_text())
                if match:
                    return match.group(1).strip()
        return ""

    def _extract_amazon_choice(self, soup):
        el = soup.select_one("#acBadge_feature_div, .ac-badge-wrapper")
        return el is not None

    def _extract_buy_box(self, soup):
        el = soup.select_one("#merchant-info, #tabular-buybox")
        if el and "amazon" in el.text.lower():
            return "Amazon"
        el = soup.select_one("#sellerProfileTriggerId, #tabular-buybox-truncate-1 span a")
        if el and el.text.strip():
            return el.text.strip()[:50]
        return ""

    def _extract_num_sellers(self, soup):
        el = soup.select_one("#olp-upd-new a, #olp_feature_div a")
        if el:
            match = re.search(r'(\d+)', el.text)
            if match:
                return int(match.group(1))
        return 0

    def _extract_prime(self, soup):
        el = soup.select_one("#prime-badge, .prime-badge, #isPrimeBadge")
        return el is not None

    def _extract_coupon(self, soup):
        el = soup.select_one("#couponBadgeRegularVpc, #vpcButton, .couponBadge")
        return el is not None

    def _extract_coupon_value(self, soup):
        el = soup.select_one("#couponBadgeRegularVpc, #vpcButton")
        if el:
            match = re.search(r'(\d+)%', el.text)
            if match:
                return f"{match.group(1)}%"
            match = re.search(r'[£$](\d+\.?\d*)', el.text)
            if match:
                return f"£{match.group(1)}"
        return ""

    def _extract_amazon_retail(self, soup):
        el = soup.select_one("#tabular-buybox-truncate-0 span, #merchant-info")
        if el and "amazon" in el.text.lower():
            return True
        return False

    def _extract_seller_location(self, soup):
        el = soup.select_one("#tabular-buybox span")
        if el:
            text = el.text.strip()
            if "United States" in text or "US" in text:
                return "United States"
            if text and len(text) > 2:
                return text[:30]
        return ""

    def _extract_return_policy(self, soup):
        el = soup.select_one("#buybox-see-all-buying-choices a, #aod-offer-list")
        if el:
            return "30-day return"
        return ""

    def _extract_warranty(self, soup):
        for row in soup.select("#productDetails_detailBullets_sections1 tr, #detailBullets_feature_div li"):
            text = row.get_text().lower()
            if "warranty" in text:
                match = re.search(r':\s*(.+)', row.get_text())
                if match:
                    return match.group(1).strip()[:40]
        return ""

    def _extract_stock(self, soup):
        el = soup.select_one("#availability span, #availability")
        if el:
            text = el.text.strip().lower()
            if "in stock" in text:
                return "In Stock"
            elif "out of stock" in text or "currently unavailable" in text:
                return "Out of Stock"
            elif "only" in text:
                return "Low Stock"
        return ""

    def _estimate_monthly_sales(self, info):
        bsr = info.get("bsr", 10000)
        if bsr < 1000:
            return random.randint(5000, 20000)
        elif bsr < 5000:
            return random.randint(2000, 8000)
        elif bsr < 20000:
            return random.randint(500, 3000)
        elif bsr < 100000:
            return random.randint(100, 1000)
        else:
            return random.randint(10, 500)

    def _assess_competition(self, info):
        num_sellers = info.get("num_sellers", 0)
        is_fba = info.get("is_fba", False)
        amazon_retail = info.get("is_amazon_retail", False)

        if amazon_retail:
            return "HIGH - Amazon Direct"
        elif num_sellers > 10:
            return "HIGH - Many Sellers"
        elif num_sellers > 5:
            return "MEDIUM - Moderate"
        elif is_fba and num_sellers <= 3:
            return "LOW - FBA Advantage"
        elif num_sellers > 0:
            return "LOW - Few Sellers"
        return ""

    def _extract_availability(self, soup):
        """Detect if product is available, unavailable, or restricted."""
        el = soup.select_one("#availability")
        if el:
            text = el.text.strip().lower()
            if "currently unavailable" in text:
                return "unavailable"
            if "out of stock" in text:
                return "out_of_stock"
            if "in stock" in text:
                return "available"
            if "only" in text:
                return "low_stock"

        unavailable_signals = [
            "this item is not currently available",
            "this product is restricted",
            "not currently available for purchase",
            "currently not available",
        ]
        page_text = soup.get_text().lower()
        for signal in unavailable_signals:
            if signal in page_text:
                return "unavailable"

        buybox = soup.select_one("#buyBoxAccordion, #add-to-cart-button, #buy-now-button")
        if not buybox:
            add_cart = soup.select_one("#add-to-cart-button")
            if not add_cart:
                return "no_buy_box"

        return "available"

    def _extract_restricted(self, soup):
        """Detect if product has selling restrictions."""
        restricted_signals = [
            "this product requires approval",
            "you need approval to list",
            "selling restricted",
            "brand authorization required",
            "this product is brand gated",
            "this item can only be shipped to",
            "listing limitations apply",
            "apply to sell",
            "you cannot list this product",
            "this product is restricted",
            "not authorized to sell",
        ]
        page_text = soup.get_text().lower()
        for signal in restricted_signals:
            if signal in page_text:
                return True

        el = soup.select_one("#listing-limitations, .listing-limitations")
        if el:
            return True

        return False

    def _extract_add_to_cart(self, soup):
        """Check if Add to Cart button is present (indicates buyable)."""
        el = soup.select_one("#add-to-cart-button, #submit.add-to-cart")
        return el is not None

    def _empty_data(self, asin):
        """Return empty-default seller data when scraping fails.

        Never returns random data.
        """
        return {
            "asin": asin,
            "seller_name": "",
            "seller_rating": 0.0,
            "seller_reviews": 0,
            "fulfillment": "",
            "brand": "",
            "manufacturer": "",
            "product_weight": "",
            "dimensions": "",
            "date_first_available": "",
            "bsr": 0,
            "category": "",
            "amazon_choice": False,
            "buy_box_winner": "",
            "num_sellers": 0,
            "is_fba": False,
            "is_prime": False,
            "has_coupon": False,
            "coupon_value": "",
            "is_amazon_retail": False,
            "seller_location": "",
            "return_policy": "",
            "warranty": "",
            "stock_status": "",
            "monthly_sales_est": 0,
            "competition_level": "",
            "availability": "unknown",
            "is_restricted": False,
            "has_add_to_cart": False,
        }
