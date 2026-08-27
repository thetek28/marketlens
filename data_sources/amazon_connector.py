"""Amazon Data Source Connector.

Wraps the existing Amazon scraping infrastructure but:
- Returns ONLY real scraped data
- Never generates fake prices
- Marks estimated values clearly
- Tracks source attribution and freshness
"""

import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import (
    DataSource,
    DataSourceConfig,
    DataSourceStatus,
    NormalizedProduct,
    SourceAttribution,
)

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
]

BEST_SELLERS_URLS = {
    "Kitchen": "https://www.amazon.com/Best-Sellers/zgbs/home-garden/",
    "Electronics": "https://www.amazon.com/Best-Sellers/zgbs/electronics/",
    "Beauty": "https://www.amazon.com/Best-Sellers/zgbs/beauty/",
    "Home & Kitchen": "https://www.amazon.com/Best-Sellers/zgbs/home-garden/",
    "Sports": "https://www.amazon.com/Best-Sellers/zgbs/sporting-goods/",
    "Health": "https://www.amazon.com/Best-Sellers/zgbs/hpc/",
    "Toys": "https://www.amazon.com/Best-Sellers/zgbs/toys-and-games/",
    "Office": "https://www.amazon.com/Best-Sellers/zgbs/office-products/",
    "Pet Supplies": "https://www.amazon.com/Best-Sellers/zgbs/pet-supplies/",
    "Garden": "https://www.amazon.com/Best-Sellers/zgbed-garden/",
}

MARKETPLACE_CONFIGS = {
    "US": {"domain": "www.amazon.com", "currency": "USD"},
    "UK": {"domain": "www.amazon.co.uk", "currency": "GBP"},
    "DE": {"domain": "www.amazon.de", "currency": "EUR"},
    "FR": {"domain": "www.amazon.fr", "currency": "EUR"},
    "CA": {"domain": "www.amazon.ca", "currency": "CAD"},
    "JP": {"domain": "www.amazon.co.jp", "currency": "JPY"},
    "IT": {"domain": "www.amazon.it", "currency": "EUR"},
    "ES": {"domain": "www.amazon.es", "currency": "EUR"},
    "AU": {"domain": "www.amazon.com.au", "currency": "AUD"},
}


class AmazonConnector(DataSource):
    """Amazon data source connector using web scraping."""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self._session = None
        self._setup_session()

    def _setup_session(self):
        """Create a requests session with appropriate headers."""
        try:
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": USER_AGENTS[0],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            })
            self._status = DataSourceStatus.DISCONNECTED
        except ImportError:
            logger.error("requests library not installed")
            self._status = DataSourceStatus.ERROR

    def test_connection(self) -> bool:
        """Test if Amazon is accessible."""
        if not self._session:
            return False
        try:
            import requests
            resp = self._session.get("https://www.amazon.com", timeout=10)
            if resp.status_code == 200:
                self._status = DataSourceStatus.CONNECTED
                return True
            self._status = DataSourceStatus.ERROR
            self._last_error = f"HTTP {resp.status_code}"
            return False
        except Exception as e:
            self._status = DataSourceStatus.ERROR
            self._last_error = str(e)
            return False

    def search_products(self, query: str, marketplace: str = "US",
                        max_results: int = 20) -> List[NormalizedProduct]:
        """Search Amazon for products. Returns ONLY real scraped data."""
        if not self._session:
            return []

        if not self._check_rate_limit():
            return []

        mk_config = MARKETPLACE_CONFIGS.get(marketplace, MARKETPLACE_CONFIGS["US"])
        domain = mk_config["domain"]
        currency = mk_config["currency"]

        try:
            import requests
            from bs4 import BeautifulSoup

            url = f"https://{domain}/s"
            params = {"k": query, "ref": "nb_sb_noss"}
            resp = self._session.get(url, params=params, timeout=self.config.timeout_seconds)

            if resp.status_code == 429:
                self._set_rate_limit(60)
                return []

            if resp.status_code != 200:
                self._last_error = f"HTTP {resp.status_code}"
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []

            items = soup.select('[data-component-type="s-search-result"]')

            for item in items[:max_results]:
                try:
                    product = self._parse_search_result(item, domain, currency, marketplace)
                    if product and product.asin:
                        results.append(product)
                except Exception as e:
                    logger.debug("Failed to parse item: %s", e)
                    continue

            self._record_request()
            self._status = DataSourceStatus.CONNECTED
            return results

        except ImportError:
            logger.error("BeautifulSoup not installed")
            return []
        except Exception as e:
            self._record_error(str(e))
            return []

    def get_product(self, asin: str, marketplace: str = "US") -> Optional[NormalizedProduct]:
        """Get a single product by ASIN from Amazon."""
        if not self._session:
            return None

        mk_config = MARKETPLACE_CONFIGS.get(marketplace, MARKETPLACE_CONFIGS["US"])
        domain = mk_config["domain"]
        currency = mk_config["currency"]

        try:
            import requests
            from bs4 import BeautifulSoup

            url = f"https://{domain}/dp/{asin}"
            resp = self._session.get(url, timeout=self.config.timeout_seconds)

            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            product = self._parse_product_page(soup, asin, domain, currency, marketplace)

            if product:
                self._record_request()
                self._status = DataSourceStatus.CONNECTED

            return product

        except Exception as e:
            self._record_error(str(e))
            return None

    def _parse_search_result(self, item, domain: str, currency: str,
                             marketplace: str) -> Optional[NormalizedProduct]:
        """Parse a single Amazon search result item."""
        asin = item.get("data-asin", "")
        if not asin:
            return None

        # Title
        title_el = item.select_one("h2 a span, h2 span")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None

        # Price - ONLY from real scraping
        price = 0.0
        price_el = item.select_one(".a-price .a-offscreen")
        if price_el:
            price_text = price_el.get_text(strip=True)
            price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(",", ""))
            if price_match:
                try:
                    price = float(price_match.group())
                except ValueError:
                    price = 0.0

        # If no price found, skip (don't generate fake price)
        if price <= 0:
            return None

        # Rating
        rating = 0.0
        rating_el = item.select_one(".a-icon-alt")
        if rating_el:
            rating_match = re.search(r'(\d+\.?\d*)\s*out of', rating_el.get_text())
            if rating_match:
                try:
                    rating = float(rating_match.group(1))
                except ValueError:
                    pass

        # Reviews
        review_count = 0
        review_el = item.select_one('[aria-label*="stars"] + span, .a-size-base.s-underline-text')
        if review_el:
            review_match = re.search(r'([\d,]+)', review_el.get_text())
            if review_match:
                try:
                    review_count = int(review_match.group(1).replace(",", ""))
                except ValueError:
                    pass

        # URL
        url_el = item.select_one("h2 a")
        product_url = f"https://{domain}{url_el['href']}" if url_el and url_el.get("href") else ""

        # Image
        image_url = ""
        img_el = item.select_one("img.s-image")
        if img_el:
            image_url = img_el.get("src", "")

        return NormalizedProduct(
            asin=asin,
            title=title,
            marketplace=marketplace,
            price=price,
            currency=currency,
            rating=rating,
            review_count=review_count,
            product_url=product_url,
            image_url=image_url,
            source=SourceAttribution(
                source="Amazon",
                source_type="marketplace",
                source_url=product_url,
                retrieved_at=datetime.now(),
                marketplace=marketplace,
                confidence="verified",
                data_status="live",
            ),
        )

    def _parse_product_page(self, soup, asin: str, domain: str,
                            currency: str, marketplace: str) -> Optional[NormalizedProduct]:
        """Parse a full Amazon product page."""
        # Title
        title = ""
        title_el = soup.select_one("#productTitle")
        if title_el:
            title = title_el.get_text(strip=True)
        if not title:
            return None

        # Price
        price = 0.0
        price_el = soup.select_one(".a-price .a-offscreen, #priceblock_ourprice, #priceblock_dealprice")
        if price_el:
            price_text = price_el.get_text(strip=True)
            price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(",", ""))
            if price_match:
                try:
                    price = float(price_match.group())
                except ValueError:
                    pass

        # Brand
        brand = ""
        brand_el = soup.select_one("#bylineInfo, .a-row.a-size-base .a-link-normal")
        if brand_el:
            brand = brand_el.get_text(strip=True).replace("Visit the ", "").replace(" Store", "")

        # Rating
        rating = 0.0
        rating_el = soup.select_one("#acrPopover .a-icon-alt, #averageCustomerReviews .a-icon-alt")
        if rating_el:
            rating_match = re.search(r'(\d+\.?\d*)', rating_el.get_text())
            if rating_match:
                try:
                    rating = float(rating_match.group(1))
                except ValueError:
                    pass

        # Reviews
        review_count = 0
        review_el = soup.select_one("#acrCustomerReviewCount")
        if review_el:
            review_match = re.search(r'([\d,]+)', review_el.get_text())
            if review_match:
                try:
                    review_count = int(review_match.group(1).replace(",", ""))
                except ValueError:
                    pass

        # Category
        category = ""
        breadcrumbs = soup.select("#wayfinding-breadcrumbs_feature_div li a, #nav-subnav a")
        if breadcrumbs:
            category = breadcrumbs[-1].get_text(strip=True)

        # BSR
        sales_rank = 0
        bsr_el = soup.select_one("#productDetails_detailBullets_sections1 tr:contains('Best Sellers Rank') td, #detailBullets_feature_div li span")
        if bsr_el:
            bsr_match = re.search(r'#([\d,]+)', bsr_el.get_text())
            if bsr_match:
                try:
                    sales_rank = int(bsr_match.group(1).replace(",", ""))
                except ValueError:
                    pass

        # Image
        image_url = ""
        img_el = soup.select_one("#landingImage, #imgBlkFront")
        if img_el:
            image_url = img_el.get("data-old-hires") or img_el.get("src", "")

        product_url = f"https://{domain}/dp/{asin}"

        return NormalizedProduct(
            asin=asin,
            title=title,
            brand=brand,
            category=category,
            marketplace=marketplace,
            price=price,
            currency=currency,
            rating=rating,
            review_count=review_count,
            sales_rank=sales_rank,
            product_url=product_url,
            image_url=image_url,
            source=SourceAttribution(
                source="Amazon",
                source_type="marketplace",
                source_url=product_url,
                retrieved_at=datetime.now(),
                marketplace=marketplace,
                confidence="verified",
                data_status="live",
            ),
        )

    def _search_amazon(self, query: str, domain: str, max_pages: int = 1) -> List[Dict]:
        """Search Amazon and return raw results."""
        results = []
        try:
            import requests
            from bs4 import BeautifulSoup

            for page in range(1, max_pages + 1):
                url = f"https://{domain}/s"
                params = {"k": query, "page": str(page)}
                resp = self._session.get(url, params=params, timeout=self.config.timeout_seconds)

                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                items = soup.select('[data-component-type="s-search-result"]')

                for item in items:
                    asin = item.get("data-asin", "")
                    if not asin:
                        continue
                    results.append({"asin": asin, "raw": str(item)})

                time.sleep(1)  # Rate limiting

        except Exception as e:
            logger.error("Amazon search failed: %s", e)

        return results
