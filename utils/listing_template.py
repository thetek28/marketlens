"""Generates Amazon listing templates from validated product ideas."""

import hashlib
from typing import Any, Dict

from analyzers.seo import SEOAnalyzer


def generate_listing_template(idea: Dict[str, Any], include_seo: bool = True) -> Dict[str, Any]:
    """Generate a full Amazon listing template from a validated product idea.

    Returns a dict structured according to Amazon's product listing schema.
    Fields are pre-filled where possible from scraped data; others are left
    as empty strings for the seller to complete.
    """
    name = idea.get("name", "")
    asin = idea.get("asin", "")
    price = idea.get("amazon_price", 0)
    rating = idea.get("rating", 0)
    review_count = idea.get("review_count", 0)
    category = idea.get("category", "")
    url = idea.get("url", "")
    gated = idea.get("gated", False)
    gated_category = idea.get("gated_category", "")
    margin = idea.get("estimated_margin_pct", 0)
    supplier_cost = idea.get("estimated_supplier_cost", 0)
    fba_fees = idea.get("fba_fees", 0)

    existing_images = idea.get("images", [])
    if not existing_images and idea.get("image"):
        existing_images = [idea["image"]]

    sku = _generate_sku(name)

    seo_data = {}
    if include_seo:
        try:
            seo_analyzer = SEOAnalyzer()
            seo_data = seo_analyzer.optimize_listing(idea)
        except Exception:
            seo_data = {}

    optimized_title = seo_data.get("optimized_title", name)
    optimized_bullets = seo_data.get("optimized_bullets", ["", "", "", "", ""])
    search_terms = seo_data.get("search_terms", "")
    return {
        "product_identity": {
            "item_name": optimized_title,
            "product_type": category,
            "recommended_browse_nodes": "",
            "variations": "",
            "item_highlight": "",
            "brand_name": "",
            "external_product_id": asin,
        },
        "description": {
            "product_description": "",
            "bullet_points": optimized_bullets,
            "images": existing_images,
        },
        "seo": {
            "primary_keywords": seo_data.get("seo_analysis", {}).get("primary_keywords", []),
            "long_tail_keywords": seo_data.get("seo_analysis", {}).get("long_tail_keywords", []),
            "backend_keywords": seo_data.get("seo_analysis", {}).get("backend_keywords", []),
            "search_terms": search_terms,
            "seo_score": seo_data.get("seo_analysis", {}).get("seo_score", {}),
            "optimization_tips": seo_data.get("seo_analysis", {}).get("optimization_tips", []),
        },
        "product_details": {
            "model_number": "",
            "manufacturer": "",
            "special_features": "",
            "style": "",
            "material": "",
            "number_of_items": "1",
            "colour": "",
            "colour_map": "",
            "size": "",
            "item_depth": "",
            "finish_type": "",
            "unit_count": "1",
            "unit_count_type": "Count",
            "is_fragile": "",
            "item_dimensions_w_x_h": "",
            "item_height": "",
            "item_height_unit": "inches",
            "item_width": "",
            "item_width_unit": "inches",
            "number_of_packs": "",
            "is_green_purchasing_law_compliant": "",
        },
        "offer": {
            "sku": sku,
            "quantity": "1",
            "your_price": f"{price:.2f}" if price else "",
            "item_condition": "New",
            "list_price_with_tax": f"{price:.2f}" if price else "",
            "fulfilment_channel": "FBA",
        },
        "package_dimensions": {
            "package_length": "",
            "package_length_unit": "inches",
            "package_width": "",
            "package_width_unit": "inches",
            "package_height": "",
            "package_height_unit": "inches",
        },
        "safety_and_compliance": {
            "country_region_of_origin": "",
            "dangerous_goods_regulations": "",
        },
        "_metadata": {
            "asin_reference": asin,
            "source_url": url,
            "reference_image": existing_images[0] if existing_images else "",
            "market_rating": rating,
            "market_reviews": review_count,
            "estimated_margin_pct": margin,
            "estimated_supplier_cost": supplier_cost,
            "estimated_fba_fees": fba_fees,
            "is_gated": gated,
            "gated_category": gated_category,
            "score": idea.get("score", 0),
            "tier": idea.get("tier", "unknown"),
            "generated_from": "amazon-product-ai",
        },
    }


def _generate_sku(name: str) -> str:
    """Generate a short SKU from the product name."""
    if not name:
        return ""
    hash_part = hashlib.md5(name.encode()).hexdigest()[:8].upper()
    words = name.split()[:3]
    prefix = "".join(w[0].upper() for w in words if w)
    return f"{prefix}-{hash_part}"


def listing_template_to_text(template: Dict[str, Any]) -> str:
    """Convert a listing template to a readable text format."""
    lines = []

    lines.append("=" * 60)
    lines.append("AMAZON LISTING TEMPLATE")
    lines.append("=" * 60)

    meta = template.get("_metadata", {})
    lines.append("\nMarket Reference:")
    lines.append(f"  ASIN: {meta.get('asin_reference', 'N/A')}")
    lines.append(f"  Source URL: {meta.get('source_url', 'N/A')}")
    lines.append(f"  Market Rating: {meta.get('market_rating', 0)} ({meta.get('market_reviews', 0)} reviews)")
    lines.append(f"  Score: {meta.get('score', 0):.2f} | Tier: {meta.get('tier', 'unknown')}")
    lines.append(f"  Estimated Margin: {meta.get('estimated_margin_pct', 0):.0f}%")
    if meta.get("is_gated"):
        lines.append(f"  GATED: {meta.get('gated_category', 'Unknown')}")

    for section_key, section_label in [
        ("product_identity", "PRODUCT IDENTITY"),
        ("description", "DESCRIPTION"),
        ("product_details", "PRODUCT DETAILS"),
        ("offer", "OFFER"),
        ("package_dimensions", "PACKAGE DIMENSIONS"),
        ("safety_and_compliance", "SAFETY AND COMPLIANCE"),
    ]:
        section = template.get(section_key, {})
        if not section:
            continue
        lines.append(f"\n{'─' * 60}")
        lines.append(f"{section_label}")
        lines.append(f"{'─' * 60}")
        for field, value in section.items():
            if isinstance(value, list):
                if value:
                    lines.append(f"  {field}:")
                    for item in value:
                        lines.append(f"    - {item if item else '(empty)'}")
            elif value:
                lines.append(f"  {field}: {value}")
            else:
                lines.append(f"  {field}: (to be filled)")

    return "\n".join(lines)
