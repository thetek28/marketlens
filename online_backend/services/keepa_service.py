"""Amazon UK Product Scraper - Improved version.

Scrapes Amazon.co.uk search results for real product data.
Features:
    - Session-based requests with cookies
    - Automatic retry on blocks (503)
    - Rich data extraction (price, rating, reviews, BSR, seller)
    - Robust price parsing
    - Request delays to avoid blocks
"""
import logging
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# Request delay range (seconds) to avoid blocks
MIN_DELAY = 1.0
MAX_DELAY = 3.0

# Maximum retries on 503
MAX_RETRIES = 3

HEADERS_POOL = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    },
]

# Category detection keywords
CATEGORY_KEYWORDS = {
    "Electronics": ["bluetooth", "wireless", "headphone", "earbuds", "earphone", "speaker", "charger", "cable", "usb", "led", "smart", "wifi", "camera", "drone", "keyboard", "mouse", "monitor", "laptop", "tablet", "phone", "power bank", "adapter", "hub", "switch", "router", "antenna", "microphone", "headset", "gaming"],
    "Kitchen": ["kettle", "toaster", "blender", "coffee", "mug", "pan", "pot", "knife", "cutting", "baking", "air fryer", "food", "cooking", "dish", "spatula", "oven", "microwave", "juicer", "mixer", "grinder", "teapot", "flask", "bottle", "container"],
    "Home & Garden": ["lamp", "light", "curtain", "rug", "pillow", "plant", "garden", "outdoor", "door", "window", "bed", "bath", "towel", "furniture", "shelf", "storage", "decoration", "clock", "mirror", "vase", "mat", "blanket", "cushion"],
    "Sports & Outdoors": ["yoga", "gym", "fitness", "running", "cycling", "camping", "hiking", "football", "basketball", "swimming", "sport", "exercise", "workout", "dumbbell", "resistance", "band", "mat", "ball", "racket", "bat"],
    "Beauty": ["makeup", "skincare", "cream", "serum", "shampoo", "brush", "beauty", "cosmetic", "face", "hair", "nail", "lip", "eye", "moisturiser", "sunscreen", "lotion", "perfume", "cologne"],
    "Toys & Games": ["toy", "game", "puzzle", "lego", "doll", "action figure", "board game", "kids", "children", "building", "blocks", "remote control", "plush", "stuffed"],
    "Pet Supplies": ["dog", "cat", "pet", "bird", "fish", "hamster", "pet food", "collar", "leash", "toy", "treat", "litter", "aquarium", "cage"],
    "Baby Products": ["baby", "infant", "stroller", "cot", "nappy", "bottle", "pacifier", "pram", "car seat", "highchair", "monitor", "steriliser"],
    "Fashion": ["shirt", "dress", "jacket", "shoes", "socks", "hat", "bag", "watch", "jewellery", "ring", "necklace", "bracelet", "sunglasses", "wallet", "belt"],
    "Automotive": ["car", "motorcycle", "tyre", "tool", "dashboard", "seat cover", "windscreen", "mirror", "cleaning", "oil", "filter", "bulb", "LED"],
    "Health": ["vitamin", "supplement", "health", "medical", "first aid", "thermometer", "scale", "massager", "pain relief", "bandage", "inhaler"],
    "Office": ["pen", "pencil", "paper", "notebook", "stapler", "tape", "folder", "organiser", "desk", "chair", "printer", "ink", "toner"],
}


def search_products(query: str, page: int = 1, sort: str = "") -> dict:
    """Search Amazon.co.uk and scrape product results.

    Sort options:
        - "" (empty) = relevance
        - "review-count-rank" = most reviewed
        - "price-asc-rank" = price low to high
        - "price-desc-rank" = price high to low
        - "exact-aware-popularity-rank" = best sellers
        - "popularity-rank" = featured
    """
    session = requests.Session()
    headers = random.choice(HEADERS_POOL).copy()

    # Set initial cookies that Amazon expects
    session.cookies.set("session-id", f"262-{random.randint(1000000,9999999)}-{random.randint(1000000,9999999)}", domain=".amazon.co.uk")
    session.cookies.set("session-token", f"placeholder{random.randint(10000000,99999999)}", domain=".amazon.co.uk")
    session.cookies.set("i18n-prefs", "GBP", domain=".amazon.co.uk")

    url = f"https://www.amazon.co.uk/s?k={quote_plus(query)}&page={page}"
    if sort:
        url += f"&s={sort}"

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            # Add delay between requests
            if attempt > 0:
                delay = MIN_DELAY + random.random() * (MAX_DELAY - MIN_DELAY)
                time.sleep(delay)

            resp = session.get(url, headers=headers, timeout=25)

            if resp.status_code == 503:
                logger.warning(f"Amazon 503 on attempt {attempt+1}, retrying...")
                last_error = "Amazon blocked the request (503)"
                continue

            if resp.status_code == 404:
                return {"products": [], "total_results": 0, "page": page}

            if resp.status_code == 500:
                last_error = "Amazon server error (500)"
                continue

            resp.raise_for_status()

            # Check if we got a CAPTCHA page
            if "captcha" in resp.text.lower() or "robot" in resp.text.lower():
                logger.warning(f"Amazon CAPTCHA detected on attempt {attempt+1}")
                last_error = "Amazon detected automated access"
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            products = _parse_search_results(soup)

            # Estimate total results
            total = _extract_total_results(soup)

            return {
                "products": products,
                "total_results": total or len(products),
                "page": page,
                "query": query,
            }

        except requests.RequestException as e:
            last_error = str(e)
            logger.error(f"Amazon scrape error (attempt {attempt+1}): {e}")
            continue

    raise ValueError(f"Failed after {MAX_RETRIES} attempts: {last_error}")


def _extract_total_results(soup: BeautifulSoup) -> int:
    """Extract total result count from the page."""
    total = 0

    # Method 1: Result info bar
    result_info = soup.select_one('[data-component-type="s-result-info-bar"]')
    if result_info:
        text = result_info.get_text()
        match = re.search(r"([\d,]+)\s+results?", text)
        if match:
            total = int(match.group(1).replace(",", ""))

    # Method 2: Alternative result count element
    if not total:
        count_el = soup.select_one(".rush-component[data-component-type='s-result-info-bar'] span")
        if count_el:
            match = re.search(r"([\d,]+)", count_el.get_text())
            if match:
                total = int(match.group(1).replace(",", ""))

    return total


def _parse_search_results(soup: BeautifulSoup) -> list:
    """Parse Amazon search results page into structured product data."""
    products = []
    items = soup.select('[data-asin]:not([data-asin=""])')

    for item in items:
        try:
            asin = item.get("data-asin", "").strip()
            if not asin or len(asin) < 5:
                continue

            # Title - try multiple selectors
            name = ""
            title_el = item.select_one("h2 a span, h2 span, h2.a-text-normal")
            if title_el:
                name = title_el.get_text(strip=True)
            if not name:
                continue

            # URL
            product_url = ""
            link_el = item.select_one("h2 a")
            if link_el and link_el.get("href"):
                href = link_el["href"]
                if href.startswith("/"):
                    product_url = f"https://www.amazon.co.uk{href}"
                elif href.startswith("http"):
                    product_url = href

            # Price - robust parsing
            price = _extract_price(item)

            # Rating
            rating = _extract_rating(item)

            # Review count
            reviews = _extract_reviews(item)

            # Image
            image_url = ""
            img_el = item.select_one("img.s-image")
            if img_el:
                image_url = img_el.get("src", "") or img_el.get("data-src", "")

            # Brand
            brand = _extract_brand(item)

            # Badges
            is_amazons_choice = bool(item.select_one('[aria-label*="Amazon\'s Choice"], [data-component-type="sp-sponsored-result"] ~ .a-row .a-badge-text'))
            is_best_seller = bool(item.select_one('[aria-label*="Best Seller"], .a-badge-text:contains("Best Seller")'))
            is_sponsored = bool(item.select_one('[data-component-type="sp-sponsored-result"], .puis-label-popover-default'))

            # Availability
            availability = ""
            avail_el = item.select_one('.a-row.a-size-base .a-color-price, .a-color-success')
            if avail_el:
                availability = avail_el.get_text(strip=True)

            # Category
            category = _guess_category(name, brand)

            # Margin estimate
            margin = 0.0
            supplier_cost = 0.0
            if price > 0:
                # Amazon UK referral fee (varies by category, ~15% average)
                referral_fee = price * 0.15
                # FBA fees (estimate based on price)
                if price < 10:
                    fba_fee = 2.50
                elif price < 25:
                    fba_fee = 3.50
                elif price < 50:
                    fba_fee = 4.50
                else:
                    fba_fee = 5.50
                # Estimated supplier cost (20% of price for generic products)
                supplier_cost = price * 0.20
                # Total costs
                total_cost = supplier_cost + referral_fee + fba_fee
                margin = ((price - total_cost) / price) * 100

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
                "is_sponsored": is_sponsored,
                "availability": availability,
                "estimated_margin_pct": round(max(0, margin), 1),
                "estimated_supplier_cost": round(supplier_cost, 2),
            })
        except Exception as e:
            logger.debug(f"Failed to parse item: {e}")
            continue

    return products


def _extract_price(item) -> float:
    """Extract price from a product card with robust parsing."""
    price = 0.0

    # Method 1: Standard price display
    price_el = item.select_one(".a-price:not([data-a-strike]) .a-offscreen")
    if price_el:
        price_text = price_el.get_text(strip=True)
        price = _parse_price_text(price_text)
        if price > 0:
            return price

    # Method 2: Price whole + fraction
    price_whole = item.select_one(".a-price:not([data-a-strike]) .a-price-whole")
    price_fraction = item.select_one(".a-price:not([data-a-strike]) .a-price-fraction")
    if price_whole:
        whole = price_whole.get_text(strip=True).replace(",", "").rstrip(".")
        fraction = price_fraction.get_text(strip=True) if price_fraction else "00"
        try:
            price = float(f"{whole}.{fraction}")
            if price > 0:
                return price
        except (ValueError, TypeError):
            pass

    # Method 3: Any price element
    any_price = item.select_one(".a-price .a-offscreen")
    if any_price:
        price = _parse_price_text(any_price.get_text(strip=True))
        if price > 0:
            return price

    # Method 4: Regex on full card text
    card_text = item.get_text()
    match = re.search(r"£(\d+(?:\.\d{2})?)", card_text)
    if match:
        try:
            price = float(match.group(1))
        except ValueError:
            pass

    return price


def _parse_price_text(text: str) -> float:
    """Parse a price string like '£29.99' or '29.99' into a float."""
    if not text:
        return 0.0
    # Remove currency symbols and whitespace
    cleaned = re.sub(r"[£$€\s]", "", text)
    # Remove thousands separators
    cleaned = cleaned.replace(",", "")
    # Try to parse
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _extract_rating(item) -> float:
    """Extract star rating from a product card."""
    # Method 1: aria-label on star element
    rating_el = item.select_one('[aria-label*="out of 5 stars"], [aria-label*="out of"]')
    if rating_el:
        label = rating_el.get("aria-label", "")
        match = re.search(r"([\d.]+)\s+out of", label)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

    # Method 2: Text content of rating span
    rating_span = item.select_one(".a-icon-alt")
    if rating_span:
        text = rating_span.get_text(strip=True)
        match = re.search(r"([\d.]+)\s+out of", text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

    return 0.0


def _extract_reviews(item) -> int:
    """Extract review count from a product card."""
    # Method 1: aria-label with stars + sibling span
    star_el = item.select_one('[aria-label*="stars"]')
    if star_el:
        # Look for the review count in the next sibling
        sibling = star_el.find_next_sibling("span")
        if sibling:
            text = sibling.get_text(strip=True).replace(",", "").replace(".", "")
            match = re.search(r"([\d]+)", text)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    pass

    # Method 2: Link to reviews with count
    review_link = item.select_one('a[href*="customerReviews"] span, a[href*="reviews"] span')
    if review_link:
        text = review_link.get_text(strip=True).replace(",", "")
        match = re.search(r"([\d]+)", text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass

    # Method 3: s-underline-text class
    count_el = item.select_one(".a-size-base.s-underline-text")
    if count_el:
        text = count_el.get_text(strip=True).replace(",", "")
        match = re.search(r"([\d]+)", text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass

    return 0


def _extract_brand(item) -> str:
    """Extract brand from a product card."""
    # Method 1: Specific brand class
    brand_el = item.select_one(".a-size-base-plus.a-color-base, .a-row.a-size-base > span.a-size-base-plus")
    if brand_el:
        return brand_el.get_text(strip=True)

    # Method 2: Sponsored brand line
    brand_el = item.select_one(".a-color-secondary .a-size-base-plus")
    if brand_el:
        return brand_el.get_text(strip=True)

    # Method 3: Extract from title (first word often is brand)
    title_el = item.select_one("h2 a span")
    if title_el:
        title = title_el.get_text(strip=True)
        # Common brand patterns
        parts = title.split()
        if parts and len(parts[0]) > 2 and parts[0][0].isupper():
            # Check if it looks like a brand (not a common word)
            skip_words = {"new", "pro", "max", "plus", "mini", "usb", "led", "hd", "4k", "8k"}
            if parts[0].lower() not in skip_words:
                return parts[0]

    return ""


def _guess_category(name: str, brand: str) -> str:
    """Guess product category from name keywords."""
    name_lower = name.lower()
    for cat, words in CATEGORY_KEYWORDS.items():
        if any(w in name_lower for w in words):
            return cat
    return "General"
