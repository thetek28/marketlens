"""Alibaba.com supplier search scraper.

Scrapes Alibaba.com search results for supplier and product data.
Uses rotating user agents and request delays to avoid blocks.
"""
import logging
import re
import random
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

HEADERS_POOL = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    },
]


def search_suppliers(query: str, page: int = 1) -> dict:
    """Search Alibaba.com for suppliers matching a query.

    Returns dict with:
        - suppliers: list of supplier/product dicts
        - total_results: estimated total
        - page: current page
    """
    headers = random.choice(HEADERS_POOL).copy()

    # Try the main search URL
    url = f"https://www.alibaba.com/trade/search?SearchText={quote_plus(query)}&page={page}"

    try:
        resp = requests.get(url, headers=headers, timeout=25, allow_redirects=True)
        if resp.status_code == 503:
            raise ValueError("Alibaba blocked the request. Try again in a moment.")
        if resp.status_code == 404:
            return {"suppliers": [], "total_results": 0, "page": page}
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Alibaba scrape error: {e}")
        raise ValueError(f"Failed to fetch from Alibaba: {str(e)}")

    soup = BeautifulSoup(resp.text, "html.parser")
    suppliers = _parse_search_results(soup, resp.text)

    # Estimate total
    total = 0
    total_el = soup.select_one(".total-count, .search-results-count, [class*='result'] [class*='count']")
    if total_el:
        match = re.search(r"([\d,]+)", total_el.get_text())
        if match:
            total = int(match.group(1).replace(",", ""))
    # Try to find total in JSON-LD or script tags
    if not total:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and "numberOfItems" in data:
                    total = data["numberOfItems"]
                    break
            except:
                pass

    return {
        "suppliers": suppliers,
        "total_results": total or len(suppliers),
        "page": page,
        "query": query,
    }


def _parse_search_results(soup: BeautifulSoup, raw_html: str) -> list:
    """Parse Alibaba search results page into structured supplier data."""
    suppliers = []

    # Strategy 1: Look for product cards in the HTML
    # Alibaba uses various class patterns for product cards
    cards = soup.select(
        '[class*="organic-list"] [class*="card"], '
        '[class*="search-result"] [class*="card"], '
        '[class*="product-list"] [class*="item"], '
        '[class*="J-offer-wrapper"], '
        '[data-content="productItem"], '
        '.organic-list .fy23-search-card, '
        '.list-no-v2-outter'
    )

    # Strategy 2: If no cards found, try broader selectors
    if not cards:
        cards = soup.select('[class*="offer"], [class*="product-item"], [class*="search-card"]')

    # Strategy 3: Parse from embedded JSON data in script tags
    if not cards:
        suppliers = _parse_from_scripts(raw_html)
        if suppliers:
            return suppliers

    for card in cards:
        try:
            supplier = _extract_supplier_from_card(card)
            if supplier and supplier.get("name"):
                suppliers.append(supplier)
        except Exception as e:
            logger.debug(f"Failed to parse card: {e}")
            continue

    return suppliers


def _extract_supplier_from_card(card) -> dict:
    """Extract supplier data from a product card element."""
    # Title / Product name
    title_el = card.select_one(
        '[class*="title"] a, '
        '[class*="name"] a, '
        'h2 a, h3 a, '
        '[class*="subject"]'
    )
    name = title_el.get_text(strip=True) if title_el else ""
    if not name:
        return {}

    # URL
    url = ""
    if title_el and title_el.get("href"):
        href = title_el["href"]
        if href.startswith("//"):
            url = f"https:{href}"
        elif href.startswith("/"):
            url = f"https://www.alibaba.com{href}"
        else:
            url = href

    # Price
    price = ""
    price_el = card.select_one('[class*="price"], [class*="Price"]')
    if price_el:
        price = price_el.get_text(strip=True)

    # MOQ (Minimum Order Quantity)
    moq = ""
    moq_el = card.select_one('[class*="min-order"], [class*="moq"], [class*="MOQ"]')
    if moq_el:
        moq = moq_el.get_text(strip=True)

    # Supplier name
    supplier_name = ""
    supplier_el = card.select_one(
        '[class*="company"], '
        '[class*="supplier"], '
        '[class*="seller"]'
    )
    if supplier_el:
        supplier_name = supplier_el.get_text(strip=True)

    # Supplier location
    location = ""
    location_el = card.select_one('[class*="location"], [class*="country"]')
    if location_el:
        location = location_el.get_text(strip=True)

    # Years in business
    years = ""
    years_el = card.select_one('[class*="year"], [class*="experience"]')
    if years_el:
        years = years_el.get_text(strip=True)

    # Verification badges
    is_gold = bool(card.select_one('[class*="gold"], [class*="Gold"]'))
    has_trade_assurance = bool(card.select_one('[class*="trade-assurance"], [class*="verified"]'))

    # Image
    img_el = card.select_one("img")
    image_url = ""
    if img_el:
        image_url = img_el.get("src", "") or img_el.get("data-src", "")
        if image_url and image_url.startswith("//"):
            image_url = f"https:{image_url}"

    return {
        "name": supplier_name or name[:60],
        "product_name": name,
        "url": url,
        "price_range": price,
        "moq": moq,
        "location": location,
        "years_in_business": years,
        "is_gold_supplier": is_gold,
        "has_trade_assurance": has_trade_assurance,
        "image_url": image_url,
        "source": "alibaba",
        "business_type": "Manufacturer",
        "rating": 0,
        "contact_email": "",
        "contact_phone": "",
        "notes": f"Found via Alibaba search. Price: {price}. MOQ: {moq}",
    }


def _parse_from_scripts(raw_html: str) -> list:
    """Try to extract supplier data from embedded JSON/script tags."""
    suppliers = []
    # Look for window.__INIT_DATA or similar embedded JSON
    patterns = [
        r'window\.__INIT_DATA__\s*=\s*({.*?});',
        r'window\.detailData\s*=\s*({.*?});',
        r'"offerList"\s*:\s*(\[.*?\])',
        r'"productList"\s*:\s*(\[.*?\])',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, raw_html, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                items = data if isinstance(data, list) else data.get("offerList", data.get("productList", []))
                if isinstance(items, list):
                    for item in items:
                        s = {
                            "name": item.get("company", {}).get("name", "") or item.get("supplierName", ""),
                            "product_name": item.get("subject", "") or item.get("title", ""),
                            "url": item.get("detailUrl", "") or item.get("productUrl", ""),
                            "price_range": item.get("price", "") or item.get("priceRange", ""),
                            "moq": item.get("minOrderQuantity", "") or item.get("moq", ""),
                            "location": item.get("company", {}).get("country", "") or item.get("location", ""),
                            "years_in_business": str(item.get("company", {}).get("yearIndex", "")),
                            "is_gold_supplier": item.get("company", {}).get("isGoldSupplier", False),
                            "has_trade_assurance": item.get("company", {}).get("hasTradeAssurance", False),
                            "image_url": item.get("image", "") or item.get("imageUrl", ""),
                            "source": "alibaba",
                            "business_type": "Manufacturer",
                            "rating": 0,
                            "contact_email": "",
                            "contact_phone": "",
                            "notes": f"Found via Alibaba search.",
                        }
                        if s.get("name") or s.get("product_name"):
                            suppliers.append(s)
            except (json.JSONDecodeError, TypeError):
                continue

    return suppliers


def get_supplier_details(supplier_url: str) -> dict:
    """Get detailed supplier information from their Alibaba page."""
    headers = random.choice(HEADERS_POOL).copy()

    try:
        resp = requests.get(supplier_url, headers=headers, timeout=20, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch supplier page: {str(e)}")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract what we can from the page
    name = ""
    name_el = soup.select_one('[class*="company-name"], [class*="companyName"], h1')
    if name_el:
        name = name_el.get_text(strip=True)

    location = ""
    location_el = soup.select_one('[class*="location"], [class*="address"]')
    if location_el:
        location = location_el.get_text(strip=True)

    return {
        "name": name,
        "location": location,
        "url": supplier_url,
        "source": "alibaba",
    }
