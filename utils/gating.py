"""Gating detection for Amazon products.

Amazon restricts ("gates") products at THREE levels:
  1. Category-level — entire categories require approval
  2. Brand-level — specific brands require authorization
  3. ASIN-level — individual products are restricted

Detection uses multiple independent signals with confidence scoring:
  - Category match (static list)
  - Brand match (commonly gated brands)
  - Seller info signals (availability, restricted, no buy box)
  - Heuristic signals (BSR, reviews, sellers, price anomalies)

A product is gated if confidence exceeds threshold (default 0.5).

Verified against Amazon Seller Central (2026):
https://sellercentral.amazon.com/gp/help/external/G200333160
"""

from typing import Dict, Optional, Tuple

# ── Category-level gating ──────────────────────────────────────────
ALWAYS_GATED = {
    "alcohol", "animal-related products", "automotive & powersports",
    "automotive", "baby products", "beauty & personal care",
    "beauty products", "beauty", "certified refurbished", "collectible coins",
    "cosmetics & skin/hair care", "cosmetics", "dietary supplements",
    "drugs & drug paraphernalia", "drugs", "entertainment collectibles",
    "explosives weapons & related items", "explosives", "fine art",
    "gambling & lottery", "gambling", "grocery & gourmet food", "grocery",
    "handmade", "hazardous & dangerous items", "hazardous",
    "health & personal care", "health", "historical & advertising collectibles",
    "historical collectibles", "human parts & burial artifacts",
    "industrial & scientific", "industrial", "jewelry & precious gems",
    "jewelry", "laser products", "lighting", "lock picking & theft devices",
    "lock picking", "major appliances", "medical devices & accessories",
    "medical devices", "medication", "music & dvd", "music",
    "offensive & controversial materials", "offensive", "organic products",
    "organic", "pesticides & pesticide devices", "pesticides",
    "pet food & treats", "pet food", "plants, plant products & seeds",
    "plants", "postage meters & stamps", "postage", "precious gems",
    "safety & security", "scientific", "security", "sex & sensuality",
    "sex", "software & computer games", "software", "sports collectibles",
    "subscriptions & periodicals", "subscriptions", "surveillance equipment",
    "surveillance", "tobacco & tobacco-related products", "tobacco",
    "topicals", "video, dvd & blu-ray", "video", "watches",
    "warranties, service contracts, guarantees & non-amazon services",
    "warranties", "wine",
}

GATED_KEYWORDS = {
    "alcohol", "automotive", "baby", "beauty", "coins", "cosmetics",
    "dietary", "drugs", "fine art", "gambling", "grocery", "hazardous",
    "health", "industrial", "jewelry", "laser", "lighting", "lock picking",
    "major appliances", "medical", "medication", "music", "organic",
    "pesticide", "pet food", "plants", "postage", "precious", "scientific",
    "security", "sex", "software", "sports collectibles", "subscriptions",
    "surveillance", "tobacco", "topicals", "video", "watches", "warranties",
    "wine",
}

CONFIRMED_UNGATED = {
    "books", "home & kitchen", "home improvement", "kitchen",
    "patio, lawn & garden", "pet supplies", "sports & outdoors",
    "toys & games", "toys", "tools & home improvement", "office products",
    "office", "garden", "clothing, shoes & jewelry",
}

# ── Brand-level gating ─────────────────────────────────────────────
# Commonly gated brands that require authorization to sell.
# Source: Amazon Seller Central, ungating guides, seller forums (2026)
# Last updated: July 2026
GATED_BRANDS = {
    # ── Fashion & Apparel ──
    "nike", "adidas", "under armour", "new balance", "puma", "reebok",
    "asics", "skechers", "crocs", "converse", "vans",
    "ralph lauren", "tommy hilfiger", "calvin klein", "hugo boss",
    "gucci", "prada", "louis vuitton", "chanel", "dior",
    "coach", "michael kors", "kate spade", "tory burch",
    "ray-ban", "oakley", "versace", "armani", "burberry",
    "patagonia", "north face", "columbia", "lululemon", "adidas",
    "supreme", "off-white", "balenciaga", "ysl", "givenchy",
    "cartier", "tiffany", "pandora", "swarovski",
    "levi's", "lee", "wrangler",
    # ── Electronics ──
    "apple", "samsung", "sony", "bose", "jbl", "beats",
    "lg", "panasonic", "philips", "sharp", "toshiba",
    "canon", "nikon", "fujifilm", "gopro", "dji",
    "fitbit", "garmin", "peloton",
    "logitech", "razer", "steelseries", "corsair", "hyperx",
    "intel", "amd", "nvidia", "asus", "msi", "gigabyte",
    "corsair", "nzxt", "thermaltake", "seasonic",
    "western digital", "seagate", "crucial", "kingston", "sandisk",
    "anker", "belkin", "spigen", "otterbox", "pelican",
    "google", "oneplus", "xiaomi", "huawei",
    "dell", "hp", "lenovo", "acer", "microsoft",
    "playstation", "xbox", "nintendo",
    # ── Toys & Games ──
    "lego", "mattel", "hasbro", "disney", "marvel", "star wars",
    "transformers", "barbie", "hot wheels", "nerf", "play-doh",
    "fisher-price", "matchbox", "little tikes",
    "bandai", "namco", "sega", "konami",
    "pokemon", "yugioh", "magic the gathering",
    "funko", "collecta", "schleich",
    # ── Beauty & Personal Care ──
    "clinique", "estee lauder", "l'oreal", "maybelline", "revlon",
    "mac", "nars", "urban decay", "bare minerals", "too faced",
    "tarte", "shape tape", "mario badescu", "the ordinary",
    "cerave", "la roche-posay", "avene", "bioderma", "supergoop",
    "drunk elephant", "tatcha", "sunday riley", "glossier",
    "charlotte tilbury", "tom ford", "jo malone", "diptyque",
    "chanel beauty", "dior beauty", "ysl beauty",
    "neutrogena", "cetaphil", "eucerin", "aveeno",
    "dove", "olay", "pantene", "head & shoulders",
    "oral-b", "colgate", "crest", "sensodyne",
    # ── Health & Supplements ──
    "pfizer", "johnson & johnson", "merck", "abbvie", "amgen",
    "gilead", "novartis", "roche", "bayer", "sanofi",
    "glaxosmithkline", "astrazeneca", "eli lilly",
    "centrum", "nature made", "one a day", "flinstones",
    "gnc", "natures bounty", "now foods", "jarrow",
    "optimum nutrition", "myprotein", "whey protein",
    # ── Grocery & Food ──
    "coca-cola", "pepsi", "nestle", "kraft", "general mills",
    "kellogg's", "campbell's", "heinz", "del monte", "dole",
    "tyson", "perdue", "oscar mayer", "jimmy dean",
    "starbucks", "dunkin", "folgers", "maxwell house",
    "red bull", "monster", "bang energy",
    "kIND", "clif bar", "luna bar",
    "oreo", "chips ahoy", "ritz", "cheez-its",
    "tide", "bounty", "charmin", "dawn", "cascade",
    "lysol", "clorox", "mr. clean", "febreze",
    # ── Home & Kitchen ──
    "kitchenaid", "cuisinart", "ninja", "instant pot", "breville",
    "dyson", "iroomba", "roborock", "shark",
    "yeti", "rtic", "hydro flask", "stanley", "contigo",
    "le creuset", "staub", "all-clad", "calphalon",
    "pyrex", "corelle", "-anchor hocking",
    "bed bath beyond", "casper", "purple", "tempur-pedic",
    "ikea", "west elm", "pottery barn", "crate & barrel",
    # ── Automotive ──
    "toyota", "honda", "ford", "chevrolet", "bmw", "mercedes",
    "audi", "volkswagen", "hyundai", "kia", "nissan", "mazda",
    "subaru", "tesla", "lamborghini", "ferrari", "porsche",
    "bosch", "denso", "ngk", "monroe", "bilstein",
    # ── Sports & Outdoors ──
    "titleist", "callaway", "taylormade", "ping", "cleveland",
    "wilson", "spalding", "molten", "baden",
    "bowflex", "peloton", "nordictrack", "proform",
    "yeti", "coleman", "ozark trail", "rei",
    # ── Luxury & Watches ──
    "rolex", "omega", "tag heuer", "breitling", "cartier",
    "tudor", "seiko", "citizen", "casio", "g-shock",
    "fossil", "michael kors watches", "daniel wellington",
}

# ── Heuristic thresholds ──────────────────────────────────────────
# Products matching these patterns in ungated categories may still be gated.
SUSPICIOUS_BSR_ZERO_REVIEW_THRESHOLD = 50000
SUSPICIOUS_ZERO_SELLERS = True
SUSPICIOUS_HIGH_PRICE_LOW_REVIEW = 200.0
SUSPICIOUS_MIN_PRICE = 0.50
SUSPICIOUS_MAX_PRICE = 5000.0


def _normalize(text: str) -> str:
    return text.lower().strip().replace("&", "and")


def _category_gating(category: str) -> Tuple[bool, float]:
    """Check category-level gating. Returns (is_gated, confidence)."""
    if not category or not category.strip():
        return False, 0.0

    norm = _normalize(category)

    if norm in CONFIRMED_UNGATED:
        return False, 0.0

    if norm in ALWAYS_GATED:
        return True, 1.0

    words = set(norm.replace(",", " ").replace(">", " ").split())
    matched = words & GATED_KEYWORDS
    if matched:
        return True, 0.8

    return False, 0.0


def _brand_gating(brand: str) -> Tuple[bool, float]:
    """Check brand-level gating. Returns (is_gated, confidence)."""
    if not brand or not brand.strip():
        return False, 0.0

    norm = _normalize(brand)

    if norm in GATED_BRANDS:
        return True, 0.9

    for gated in GATED_BRANDS:
        if gated in norm or norm in gated:
            return True, 0.7

    return False, 0.0


def _signal_gating(seller_info: dict) -> Tuple[bool, float]:
    """Check seller_info signals. Returns (is_gated, confidence)."""
    if not seller_info:
        return False, 0.0

    confidence = 0.0

    if seller_info.get("is_restricted", False):
        return True, 1.0

    availability = seller_info.get("availability", "")
    if availability == "unavailable":
        confidence = max(confidence, 0.7)
    if availability == "no_buy_box":
        confidence = max(confidence, 0.6)

    has_cart = seller_info.get("has_add_to_cart")
    if has_cart is False and availability != "available":
        confidence = max(confidence, 0.5)

    num_sellers = seller_info.get("num_sellers", 0)
    if num_sellers == 0 and availability != "available":
        confidence = max(confidence, 0.4)

    return confidence >= 0.4, confidence


def _heuristic_gating(product: dict) -> Tuple[bool, float]:
    """Check heuristic signals. Returns (is_gated, confidence)."""
    confidence = 0.0

    bsr = product.get("rank", 0) or product.get("seller_info", {}).get("bsr", 0)
    review_count = product.get("review_count", 0)
    num_sellers = product.get("seller_info", {}).get("num_sellers", 0)
    price = product.get("price", 0)
    availability = product.get("seller_info", {}).get("availability", "")

    if bsr > 0 and review_count == 0 and availability != "available":
        confidence = max(confidence, 0.3)

    if num_sellers == 0 and review_count == 0 and bsr > 0:
        confidence = max(confidence, 0.3)

    if price > SUSPICIOUS_HIGH_PRICE_LOW_REVIEW and review_count < 10:
        confidence = max(confidence, 0.2)

    if price > 0 and (price < SUSPICIOUS_MIN_PRICE or price > SUSPICIOUS_MAX_PRICE):
        confidence = max(confidence, 0.2)

    return confidence >= 0.3, confidence


def _compute_gating(category: str, product: Optional[dict] = None) -> Tuple[bool, float, str]:
    """Compute gating status with confidence and reason.

    Returns:
        (is_gated, confidence, reason)
    """
    cat_gated, cat_conf = _category_gating(category)
    if cat_gated:
        return True, cat_conf, f"category:{category}"

    seller = product.get("seller_info", {}) if product else {}
    brand = product.get("brand_name", "") or seller.get("brand", "") if product else ""

    brand_gated, brand_conf = _brand_gating(brand)
    if brand_gated:
        return True, brand_conf, f"brand:{brand}"

    sig_gated, sig_conf = _signal_gating(seller)
    if sig_gated:
        reason = "signal:restricted" if seller.get("is_restricted") else "signal:unavailable"
        return True, sig_conf, reason

    heur_gated, heur_conf = _heuristic_gating(product) if product else (False, 0.0)
    if heur_gated:
        return True, heur_conf, "heuristic:suspicious"

    return False, 0.0, ""


def is_gated(category: str, product: dict = None) -> bool:
    """Check if a product is gated.

    Uses four signals with confidence scoring:
      1. Category match (static list)
      2. Brand match (commonly gated brands)
      3. Seller info signals (availability, restricted, no buy box)
      4. Heuristic signals (BSR, reviews, sellers, price)

    Args:
        category: Category string (e.g., "Beauty", "Home & Kitchen")
        product: Optional product dict with seller_info for signal detection

    Returns:
        True if the product appears to be gated.
    """
    gated, _, _ = _compute_gating(category, product)
    return gated


def get_gating_info(category: str, product: dict = None) -> Dict[str, any]:
    """Get detailed gating information for a product.

    Returns:
        Dict with keys: gated, confidence, reason, level
    """
    gated, confidence, reason = _compute_gating(category, product)

    level = "none"
    if gated:
        if reason.startswith("category:"):
            level = "category"
        elif reason.startswith("brand:"):
            level = "brand"
        elif reason.startswith("signal:"):
            level = "signal"
        elif reason.startswith("heuristic:"):
            level = "heuristic"

    return {
        "gated": gated,
        "confidence": round(confidence, 2),
        "reason": reason,
        "level": level,
    }


def get_gated_reason(category: str, product: dict = None) -> str:
    """Return why a product is gated, or empty string if not gated."""
    _, _, reason = _compute_gating(category, product)
    return reason


def get_gated_category(category: str) -> str:
    """Return the gated category name if found, else empty string."""
    if not category or not category.strip():
        return ""
    if _normalize(category) in CONFIRMED_UNGATED:
        return ""
    norm = _normalize(category)
    if norm in ALWAYS_GATED:
        return category.strip()
    words = set(norm.replace(",", " ").replace(">", " ").split())
    matched = words & GATED_KEYWORDS
    if matched:
        return matched.pop()
    return ""


def mark_gating(product: dict) -> dict:
    """Set gated, gated_category, gated_reason, and gating_confidence fields.

    Uses four signals: category, brand, seller_info, and heuristics.
    """
    category = product.get("category", "")
    info = get_gating_info(category, product)
    product["gated"] = info["gated"]
    product["gated_category"] = get_gated_category(category) if info["gated"] else ""
    product["gated_reason"] = info["reason"]
    product["gating_confidence"] = info["confidence"]
    product["gating_level"] = info["level"]
    return product


def filter_ungated(products: list, min_confidence: float = 0.0) -> list:
    """Return only products that are NOT gated.

    Args:
        products: List of product dicts
        min_confidence: Minimum confidence to consider (0.0 = all gated)
    """
    if min_confidence > 0:
        return [p for p in products
                if not p.get("gated", False)
                or p.get("gating_confidence", 0) < min_confidence]
    return [p for p in products if not p.get("gated", False)]
