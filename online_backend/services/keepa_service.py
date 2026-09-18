"""Amazon UK Product Scraper - Direct web scraping (no API key needed).

Scrapes Amazon.co.uk search results for real product data.
Uses rotating user agents and request delays to avoid blocks.
"""
import logging
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

HEADERS_POOL = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    },
]


def search_products(query: str, page: int = 1, sort: str = "review-count-rank") -> dict:
    """Search Amazon.co.uk and scrape product results.

    Sort options:
        - review-count-rank (most reviewed, default)
        - price-asc-rank (price low to high)
        - price-desc-rank (price high to low)
        - exact-aware-popularity-rank (best sellers)
        - popularity-rank (featured)
    """
    headers = random.choice(HEADERS_POOL).copy()

    url = f"https://www.amazon.co.uk/s?k={quote_plus(query)}&page={page}"
    if sort:
        url += f"&s={sort}"

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 503:
            raise ValueError("Amazon blocked the request. Try again in a moment.")
        if resp.status_code == 404:
            return {"products": [], "total_results": 0, "page": page}
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Amazon scrape error: {e}")
        raise ValueError(f"Failed to fetch from Amazon: {str(e)}")

    soup = BeautifulSoup(resp.text, "html.parser")
    products = _parse_search_results(soup)

    # Estimate total results from header
    total = 0
    results_header = soup.select_one('[data-component-type="s-result-info-bar"] .a-section')
    if results_header:
        text = results_header.get_text()
        match = re.search(r"([\d,]+)\s+results?", text)
        if match:
            total = int(match.group(1).replace(",", ""))

    return {
        "products": products,
        "total_results": total or len(products),
        "page": page,
        "query": query,
    }


def _parse_search_results(soup: BeautifulSoup) -> list:
    """Parse Amazon search results page into structured product data."""
    products = []
    items = soup.select('[data-asin]:not([data-asin=""])')

    for item in items:
        try:
            asin = item.get("data-asin", "").strip()
            if not asin or len(asin) < 5:
                continue

            # Title
            title_el = item.select_one("h2 a span, h2 span")
            name = title_el.get_text(strip=True) if title_el else ""
            if not name:
                continue

            # URL
            link_el = item.select_one("h2 a")
            product_url = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                if href.startswith("/"):
                    product_url = f"https://www.amazon.co.uk{href}"
                else:
                    product_url = href

            # Price
            price = 0.0
            price_whole = item.select_one(".a-price-whole")
            price_fraction = item.select_one(".a-price-fraction")
            if price_whole:
                price_text = price_whole.get_text(strip=True).replace(",", "").replace(".", "")
                fraction_text = price_fraction.get_text(strip=True) if price_fraction else "00"
                try:
                    price = float(f"{price_text}.{fraction_text}")
                except (ValueError, TypeError):
                    pass

            # Rating
            rating = 0.0
            rating_el = item.select_one('[aria-label*="out of"]')
            if rating_el:
                rating_match = re.search(r"([\d.]+)\s+out of", rating_el.get("aria-label", ""))
                if rating_match:
                    rating = float(rating_match.group(1))

            # Review count
            reviews = 0
            review_el = item.select_one('[aria-label*="stars"] + span, .a-size-base.s-underline-text')
            if review_el:
                rev_text = review_el.get_text(strip=True).replace(",", "").replace(".", "")
                rev_match = re.search(r"([\d]+)", rev_text)
                if rev_match:
                    reviews = int(rev_match.group(1))

            # Image
            img_el = item.select_one("img.s-image")
            image_url = img_el.get("src", "") if img_el else ""

            # Brand
            brand = ""
            brand_el = item.select_one(".a-size-base-plus.a-color-base, .a-row.a-size-base > span")
            if brand_el:
                brand = brand_el.get_text(strip=True)

            # Amazon's Choice / Best Seller badges
            is_amazons_choice = bool(item.select_one('[aria-label*="Amazon\'s Choice"], .a-badge-text'))
            is_best_seller = bool(item.select_one('[aria-label*="Best Seller"], .a-badge-text'))

            # Category (from breadcrumb or result type)
            category = _guess_category(name, brand)

            # Margin estimate
            if price > 0:
                amazon_fee = price * 0.25
                fba_fee = 3 + price * 0.05
                estimated_cost = price * 0.20
                margin = (price - estimated_cost - amazon_fee - fba_fee) / price * 100
            else:
                margin = 0

            products.append({
                "asin": asin,
                "name": name,
                "brand": brand,
                "category": category,
                "amazon_price": round(price, 2),
                "rating": rating,
                "review_count": reviews,
                "image_url": image_url,
                "product_url": product_url,
                "marketplace": "UK",
                "is_amazons_choice": is_amazons_choice,
                "is_best_seller": is_best_seller,
                "estimated_margin_pct": round(margin, 1),
                "estimated_supplier_cost": round(price * 0.20, 2) if price > 0 else 0,
            })
        except Exception as e:
            logger.debug(f"Failed to parse item: {e}")
            continue

    return products


def _guess_category(name: str, brand: str) -> str:
    """Guess product category from name keywords."""
    name_lower = name.lower()
    keywords = {
        "Electronics": ["bluetooth", "wireless", "headphone", "earbuds", "speaker", "charger", "cable", "usb", "led", "smart", "wifi", "camera", "drone", "keyboard", "mouse", "monitor", "laptop", "tablet", "phone"],
        "Kitchen": ["kettle", "toaster", "blender", "coffee", "mug", "pan", "pot", "knife", "cutting", "baking", "air fryer", "food", "cooking", "dish"],
        "Home & Garden": ["lamp", "light", "curtain", "rug", "pillow", "plant", "garden", "outdoor", "door", "window", "bed", "bath", "towel"],
        "Sports & Outdoors": ["yoga", "gym", "fitness", "running", "cycling", "camping", "hiking", "football", "basketball", "swimming", "sport"],
        "Beauty": ["makeup", "skincare", "cream", "serum", "shampoo", "brush", "beauty", "cosmetic", "face", "hair"],
        "Toys & Games": ["toy", "game", "puzzle", "lego", "doll", "action figure", "board game", "kids", "children"],
        "Pet Supplies": ["dog", "cat", "pet", "bird", "fish", "hamster", "pet food", "collar", "leash"],
        "Baby Products": ["baby", "infant", "stroller", "cot", "nappy", "bottle", "pacifier"],
        "Fashion": ["shirt", "dress", "jacket", "shoes", "socks", "hat", "bag", "watch", "jewellery", "ring", "necklace"],
        "Automotive": ["car", "motorcycle", "tyre", "tool", "dashboard", "seat cover", "windscreen"],
        "Health": ["vitamin", "supplement", "health", "medical", "first aid", "thermometer", "scale", "massager"],
    }
    for cat, words in keywords.items():
        if any(w in name_lower for w in words):
            return cat
    return "General"
