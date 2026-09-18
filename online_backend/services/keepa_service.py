"""Keepa API integration for Amazon product search.

Uses Keepa's search endpoint to discover real Amazon products.
Requires KEEPA_API_KEY environment variable.
"""
import os
import logging
import time
import requests

logger = logging.getLogger(__name__)

KEEPA_API_KEY = os.environ.get("KEEPA_API_KEY", "")
KEEPA_BASE = "https://api.keepa.com"
DOMAIN_UK = 3
DOMAIN_US = 1
DOMAIN_DE = 3

# Keepa price history tokens: -1=unavailable, 0=removed
PRICE_UNAVAILABLE = -1


def search_products(query: str, domain: int = DOMAIN_UK, category: str = "",
                    page: int = 1, sort: str = "REVIEW_COUNT") -> dict:
    """Search Amazon via Keepa API.

    Returns dict with:
        - products: list of product dicts
        - total_results: estimated total
        - page: current page
    """
    if not KEEPA_API_KEY:
        raise ValueError("KEEPA_API_KEY not configured. Sign up at keepa.com (free tier: 1 req/min), get your API key, and add KEEPA_API_KEY to your Render environment variables.")

    params = {
        "key": KEEPA_API_KEY,
        "type": "keyword",
        "query": query,
        "domain": domain,
        "page": page,
        "sort": sort,  # REVIEW_COUNT, PRICE, RATING, SALES_ESTIMATE
    }
    if category:
        params["category"] = category

    try:
        resp = requests.get(f"{KEEPA_BASE}/search", params=params, timeout=30)
        if resp.status_code == 429:
            raise ValueError("Keepa rate limit hit. Try again in 60 seconds.")
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error(f"Keepa API error: {e}")
        raise ValueError(f"Keepa API request failed: {str(e)}")

    products = []
    for item in data.get("products", []):
        # Parse current price (keepa stores prices in cents, x100)
        price_history = item.get("csv", [])
        current_price = _get_current_price(price_history)
        rating = item.get("rating") or 0
        review_count = item.get("reviewCount") or 0
        monthly_sales = item.get("monthlySold") or 0

        # Estimate margin (rough: assume 25% Amazon fee + £3 FBA)
        if current_price > 0:
            amazon_fee = current_price * 0.25
            fba_fee = 3 + current_price * 0.05
            estimated_cost = current_price * 0.20  # rough estimate
            margin = (current_price - estimated_cost - amazon_fee - fba_fee) / current_price * 100
        else:
            margin = 0

        image_url = item.get("img") or ""

        products.append({
            "asin": item.get("asin", ""),
            "name": item.get("title", ""),
            "brand": item.get("brand", ""),
            "category": _category_name(item.get("category", 0)),
            "amazon_price": round(current_price, 2) if current_price > 0 else 0,
            "rating": round(rating / 100, 1) if rating > 0 else 0,
            "review_count": review_count,
            "image_url": image_url,
            "product_url": f"https://www.amazon.co.uk/dp/{item.get('asin', '')}",
            "marketplace": "UK",
            "monthly_sales_estimate": monthly_sales,
            "estimated_margin_pct": round(margin, 1),
            "estimated_supplier_cost": round(current_price * 0.20, 2) if current_price > 0 else 0,
        })

    return {
        "products": products,
        "total_results": data.get("totalResults", len(products)),
        "page": page,
    }


def get_product_details(asin: str, domain: int = DOMAIN_UK) -> dict:
    """Get full product details from Keepa by ASIN."""
    if not KEEPA_API_KEY:
        raise ValueError("KEEPA_API_KEY not configured. Sign up at keepa.com (free tier: 1 req/min), get your API key, and add KEEPA_API_KEY to your Render environment variables.")

    params = {
        "key": KEEPA_API_KEY,
        "domain": domain,
        "asin": asin,
        "stats": "1",  # current stats
        "history": "0",  # no full history
    }

    try:
        resp = requests.get(f"{KEEPA_BASE}/product", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise ValueError(f"Keepa API request failed: {str(e)}")

    products = data.get("products", [])
    if not products:
        raise ValueError(f"Product {asin} not found on Keepa")

    item = products[0]
    price_history = item.get("csv", [])
    current_price = _get_current_price(price_history)
    rating = item.get("rating") or 0
    review_count = item.get("reviewCount") or 0

    if current_price > 0:
        amazon_fee = current_price * 0.25
        fba_fee = 3 + current_price * 0.05
        estimated_cost = current_price * 0.20
        margin = (current_price - estimated_cost - amazon_fee - fba_fee) / current_price * 100
    else:
        margin = 0

    return {
        "asin": item.get("asin", ""),
        "name": item.get("title", ""),
        "brand": item.get("brand", ""),
        "category": _category_name(item.get("category", 0)),
        "amazon_price": round(current_price, 2) if current_price > 0 else 0,
        "rating": round(rating / 100, 1) if rating > 0 else 0,
        "review_count": review_count,
        "image_url": item.get("img", ""),
        "product_url": f"https://www.amazon.co.uk/dp/{item.get('asin', '')}",
        "marketplace": "UK",
        "estimated_margin_pct": round(margin, 1),
        "estimated_supplier_cost": round(current_price * 0.20, 2) if current_price > 0 else 0,
    }


def _get_current_price(price_history: list) -> float:
    """Extract current price from Keepa CSV price history."""
    if not price_history:
        return 0.0
    # Keepa CSV: prices are in cents * 100, -1 = unavailable
    for entry in reversed(price_history):
        if entry > 0:
            return entry / 100.0
    return 0.0


# Keepa category ID to name mapping (common UK categories)
_KEEPA_CATEGORIES = {
    1: "Books", 2: "DVD", 3: "Music", 4: "Tools & DIY",
    5: "Toys & Games", 6: "Electronics", 7: "Video Games",
    8: "Software", 9: "Sports & Outdoors", 10: "Health & Beauty",
    11: "Garden & Outdoors", 12: "Grocery", 13: "Industrial & Scientific",
    14: "Jewellery", 15: "Kitchen", 16: "Lamps & Lighting",
    17: "Luggage & Bags", 18: "Mobile Phones & Accessories",
    19: "Fashion", 20: "Pet Supplies", 21: "Shoes",
    22: "Stationery & Office Supplies", 23: "Toys & Games",
    24: "Baby Products", 25: "Apparel", 26: "Automotive",
    27: "Baby", 28: "Home & Kitchen", 29: "Sports & Outdoors",
    30: "Baby", 31: "Beauty", 32: "Wireless",
    33: "Computers & Accessories", 34: "Home & Kitchen",
    35: "Patio, Lawn & Garden", 36: "Arts, Crafts & Sewing",
    37: "Automotive", 38: "Industrial & Scientific",
    39: "Office Products", 40: "Patio, Lawn & Garden",
    41: "Pet Supplies", 42: "Sports & Outdoors",
    43: "Tools & Home Improvement", 44: "Toys & Games",
    45: "Video Games", 46: "Baby Products",
}


def _category_name(cat_id: int) -> str:
    """Convert Keepa category ID to name."""
    return _KEEPA_CATEGORIES.get(cat_id, "General")
