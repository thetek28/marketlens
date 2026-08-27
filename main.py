"""
Amazon Product Idea Generator AI - Main Entry Point

Discovers high-potential product ideas for Amazon sellers by analyzing
trends, competition, and profitability across multiple data sources.
"""

import argparse
import os
import sys
from pathlib import Path

from analyzers import (
    DataValidator,
    HiddenGemsFinder,
    KeywordClustering,
    MarketingAnalyzer,
    ProductValidator,
    ProfitabilityEstimator,
    SeasonalityDetector,
)
from data_collectors import AmazonCollector, GoogleTrendsCollector, SocialMediaCollector
from utils.config import Config
from utils.exports import export_all_to_word, export_to_excel
from utils.helpers import save_results, setup_logging
from utils.listing_template import generate_listing_template


def parse_args():
    parser = argparse.ArgumentParser(
        description="Amazon Product Idea Generator AI"
    )
    parser.add_argument(
        "-c", "--categories",
        nargs="+",
        help="Product categories to analyze (e.g., 'kitchen electronics')"
    )
    parser.add_argument(
        "-k", "--keywords",
        nargs="+",
        help="Seed keywords to expand"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory for results (default: from config or ./output)"
    )
    parser.add_argument(
        "--min-profit-margin",
        type=float,
        default=None,
        help="Minimum profit margin %% (default: from config.yaml or 30)"
    )
    parser.add_argument(
        "--max-competition",
        type=int,
        default=None,
        help="Max number of competing listings (default: from config.yaml or 50)"
    )
    parser.add_argument(
        "--ungated-only",
        action="store_true",
        help="Only show ungated categories (no approval required)"
    )
    parser.add_argument(
        "--excel",
        action="store_true",
        help="Export results to Excel spreadsheet"
    )
    parser.add_argument(
        "--word",
        action="store_true",
        help="Export each product to individual Word documents"
    )
    return parser.parse_args()


def collect_data(config, categories, keywords):
    """Gather data from enabled sources."""
    raw_data = {"trends": [], "amazon": [], "social": []}
    sources = config.get("data_sources", {})

    if sources.get("google_trends", True):
        print("\n[1/4] Collecting trend data...")
        try:
            collector = GoogleTrendsCollector(config)
            raw_data["trends"] = collector.collect(categories, keywords)
            print(f"  -> {len(raw_data['trends'])} trend records")
        except Exception as e:
            print(f"  -> Google Trends failed: {e}")
    else:
        print("\n[1/4] Google Trends disabled, skipping.")

    if sources.get("amazon", True):
        print("[2/4] Collecting Amazon data...")
        try:
            collector = AmazonCollector(config)
            raw_data["amazon"] = collector.collect(categories, keywords)
            print(f"  -> {len(raw_data['amazon'])} Amazon products")
        except Exception as e:
            print(f"  -> Amazon collection failed: {e}")
    else:
        print("[2/4] Amazon disabled, skipping.")

    if sources.get("social_media", True):
        print("[3/4] Collecting social media data...")
        try:
            collector = SocialMediaCollector(config)
            raw_data["social"] = collector.collect(categories, keywords)
            print(f"  -> {len(raw_data['social'])} social records")
        except Exception as e:
            print(f"  -> Social media collection failed: {e}")
    else:
        print("[3/4] Social media disabled, skipping.")

    return raw_data


def analyze_data(raw_data, config):
    """Run analysis modules on collected data."""
    print("\n[4a] Running keyword clustering...")
    clustering = KeywordClustering(config)
    clusters = clustering.fit(raw_data)

    print("[4b] Detecting seasonality patterns...")
    seasonality = SeasonalityDetector(config)
    seasonal_analysis = seasonality.analyze(raw_data)

    print("[4c] Estimating profitability...")
    profitability = ProfitabilityEstimator(config)
    profit_estimates = profitability.estimate(raw_data)

    print("[4e] Finding hidden gems...")
    gems_finder = HiddenGemsFinder(config)
    hidden_gems = gems_finder.find(raw_data, {
        "clusters": clusters,
        "seasonality": seasonal_analysis,
        "profitability": profit_estimates,
    })
    print(f"  -> {len(hidden_gems)} hidden gems found")

    return {
        "clusters": clusters,
        "seasonality": seasonal_analysis,
        "profitability": profit_estimates,
        "hidden_gems": hidden_gems,
    }


def validate_ideas(analysis, raw_data, config):
    """Validate and rank product ideas using profitability data and ProductValidator."""
    print("\n[4d] Validating product ideas...")

    profitability_ideas = analysis.get("profitability", [])
    if not profitability_ideas:
        return []

    seasonal_terms = set()
    for p in analysis.get("seasonality", {}).get("seasonal_products", []):
        seasonal_terms.add(p.get("term", "").lower())

    for idea in profitability_ideas:
        name_lower = idea.get("name", "").lower()
        idea["trend_score"] = 1.0 if any(t in name_lower for t in seasonal_terms) else 0.3

    validator = ProductValidator(config)
    validated = validator.validate(profitability_ideas, raw_data)

    for idea in validated:
        margin = idea.get("estimated_margin_pct", 0)
        trend = idea.get("trend_score", 0)
        review_count = idea.get("review_count", 0)
        competition = min(review_count / 1000, 1.0)
        idea["score"] = round(
            trend * 0.3 + (1 - competition) * 0.3 + min(margin / 50, 1) * 0.4,
            3,
        )

    validated.sort(key=lambda x: x.get("score", 0), reverse=True)

    for idea in validated:
        idea["listing_template"] = generate_listing_template(idea)

    print("[4f] Analyzing marketing strategies...")
    marketing = MarketingAnalyzer(config)
    validated = marketing.analyze(validated)
    print(f"  -> Marketing analysis complete for {len(validated)} ideas")

    print("[4g] Validating data accuracy...")
    data_validator = DataValidator(config)
    validated, accuracy_report = data_validator.validate_all(validated, raw_data)
    print(f"  -> Accuracy report: {accuracy_report['avg_confidence']:.1%} confidence")
    print(f"  -> Removed {accuracy_report['removed']} low-confidence items")

    print("[4h] Calculating priority rankings...")
    for i, idea in enumerate(validated):
        idea["priority_rank"] = i + 1
        idea["priority"] = _calculate_priority(idea, i + 1)

    validated = validated[:100]
    print(f"  -> Top {len(validated)} products selected by priority")

    return validated


def _calculate_priority(idea, rank):
    """Calculate priority level based on score, rank, and other factors."""
    score = idea.get("score", 0)
    margin = idea.get("estimated_margin_pct", 0)
    review_count = idea.get("review_count", 0)
    gated = idea.get("gated", False)
    marketing_score = idea.get("marketing", {}).get("marketing_score", 0.5)

    if rank <= 10:
        tier = "CRITICAL"
        color = "red"
    elif rank <= 25:
        tier = "HIGH"
        color = "orange"
    elif rank <= 50:
        tier = "MEDIUM"
        color = "yellow"
    elif rank <= 75:
        tier = "LOW"
        color = "blue"
    else:
        tier = "MINIMAL"
        color = "gray"

    if score >= 0.8 and margin >= 40 and not gated:
        tier = "CRITICAL"
        color = "red"
    elif score >= 0.7 and margin >= 35:
        tier = "HIGH"
        color = "orange"

    reasons = []
    if score >= 0.8:
        reasons.append("Excellent score")
    if margin >= 40:
        reasons.append("High margin")
    if review_count < 100:
        reasons.append("Low competition")
    if not gated:
        reasons.append("Ungated category")
    if marketing_score >= 0.7:
        reasons.append("Strong marketing potential")

    return {
        "rank": rank,
        "tier": tier,
        "color": color,
        "reasons": reasons[:3],
        "action": _get_action(tier, idea),
    }


def _get_action(tier, idea):
    """Get recommended action based on priority tier."""
    if tier == "CRITICAL":
        return "Start sourcing immediately - high profit, low competition"
    elif tier == "HIGH":
        return "Begin product research and supplier outreach"
    elif tier == "MEDIUM":
        return "Add to watchlist, monitor trends for 2-4 weeks"
    elif tier == "LOW":
        return "Keep on radar, revisit in 1-2 months"
    else:
        return "Low priority - monitor only"


def main():
    args = parse_args()
    setup_logging()
    config = Config()

    if args.min_profit_margin is not None:
        config._config["min_profit_margin"] = args.min_profit_margin
    if args.max_competition is not None:
        config._config["max_competition"] = args.max_competition

    if not args.categories and not args.keywords:
        print("Error: Provide at least one category or keyword.")
        sys.exit(1)

    raw_data = collect_data(config, args.categories, args.keywords)
    total_records = len(raw_data["trends"]) + len(raw_data["amazon"]) + len(raw_data["social"])
    if total_records == 0:
        print("\nNo data collected. Check your internet connection and try again.")
        sys.exit(1)

    analysis = analyze_data(raw_data, config)
    ideas = validate_ideas(analysis, raw_data, config)
    hidden_gems = analysis.get("hidden_gems", [])

    if args.ungated_only or config.get("ungated_only", False):
        before = len(ideas)
        ideas = [i for i in ideas if not i.get("gated", False)]
        hidden_gems = [g for g in hidden_gems if not g.get("gated", False)]
        print(f"\nFiltered to {len(ideas)} ungated ideas (removed {before - len(ideas)} gated).")

    print("[4g] Analyzing marketing for hidden gems...")
    marketing = MarketingAnalyzer(config)
    hidden_gems = marketing.analyze(hidden_gems)
    print(f"  -> Marketing analysis complete for {len(hidden_gems)} hidden gems")

    output_path = Path(args.output) if args.output else Path(config.get("output_dir", os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")))
    output_path.mkdir(parents=True, exist_ok=True)
    save_results(ideas, output_path / "product_ideas.json")
    save_results(hidden_gems, output_path / "hidden_gems.json")

    marketing_ideas = [{"name": i.get("name"), "marketing": i.get("marketing")} for i in ideas if i.get("marketing")]
    marketing_gems = [{"name": g.get("name"), "marketing": g.get("marketing")} for g in hidden_gems if g.get("marketing")]
    save_results({"ideas": marketing_ideas, "hidden_gems": marketing_gems}, output_path / "marketing_analysis.json")

    if args.excel and ideas:
        print("\n[Export] Generating Excel spreadsheet...")
        try:
            excel_path = export_to_excel(ideas, str(output_path))
            print(f"  -> Excel saved: {excel_path}")
        except Exception as e:
            print(f"  -> Excel export failed: {e}")

    if args.word and ideas:
        print("\n[Export] Generating Word documents...")
        try:
            word_paths = export_all_to_word(ideas, str(output_path / "word_docs"))
            print(f"  -> {len(word_paths)} Word documents saved to {output_path}/word_docs/")
        except Exception as e:
            print(f"  -> Word export failed: {e}")

    print(f"\nFound {len(ideas)} product ideas + {len(hidden_gems)} hidden gems")
    print(f"Results saved to {output_path}/")

    if ideas:
        gated_count = sum(1 for i in ideas if i.get("gated"))
        ungated_count = len(ideas) - gated_count
        print(f"\n  Product Ideas: {len(ideas)} (Gated: {gated_count} | Ungated: {ungated_count})")

        critical = [i for i in ideas if i.get("priority", {}).get("tier") == "CRITICAL"]
        high = [i for i in ideas if i.get("priority", {}).get("tier") == "HIGH"]
        medium = [i for i in ideas if i.get("priority", {}).get("tier") == "MEDIUM"]
        low = [i for i in ideas if i.get("priority", {}).get("tier") == "LOW"]
        minimal = [i for i in ideas if i.get("priority", {}).get("tier") == "MINIMAL"]

        print("\n  Priority Breakdown:")
        print(f"    CRITICAL: {len(critical)} | HIGH: {len(high)} | MEDIUM: {len(medium)} | LOW: {len(low)} | MINIMAL: {len(minimal)}")

        print("\n  Top 20 products by priority:")
        for i, idea in enumerate(ideas[:20], 1):
            margin = idea.get("estimated_margin_pct", 0)
            access = "Gated" if idea.get("gated") else "Ungated"
            gated_info = f" [{idea.get('gated_category', '')}]" if idea.get("gated") else ""
            image = idea.get("image", "")
            marketing = idea.get("marketing", {})
            marketing_summary = marketing.get("summary", "")
            priority = idea.get("priority", {})
            priority_tier = priority.get("tier", "unknown")
            priority_rank = priority.get("rank", i)
            priority_action = priority.get("action", "")
            listing = idea.get("listing_template", {})
            seo = listing.get("seo", {})
            seo_score = seo.get("seo_score", {}).get("percentage", 0)

            print(f"\n    #{priority_rank} [{priority_tier}] {idea.get('name', 'Unknown')}")
            print(f"       Score: {idea['score']:.2f} | Margin: {margin:.0f}% | SEO: {seo_score:.0f}% | {access}{gated_info}")
            if image:
                print(f"       Image: {image}")
            if marketing_summary:
                print(f"       Marketing: {marketing_summary}")
            print(f"       Action: {priority_action}")

            if seo.get("primary_keywords"):
                print(f"       Keywords: {', '.join(seo['primary_keywords'][:5])}")

            offer = listing.get("offer", {})
            details = listing.get("product_details", {})
            print(f"       SKU: {offer.get('sku', 'N/A')} | Price: £{offer.get('your_price', '0')} | Condition: {offer.get('item_condition', 'New')}")
            print(f"       Material: {details.get('material', '(to be filled)')} | Colour: {details.get('colour', '(to be filled)')} | Size: {details.get('size', '(to be filled)')}")

        if len(ideas) > 20:
            print(f"\n    ... and {len(ideas) - 20} more products (see full list in output files)")

        listings_path = output_path / "listing_templates.json"
        listings_data = [i.get("listing_template", {}) for i in ideas]
        save_results(listings_data, listings_path)
        print(f"\n  Listing templates saved to {listings_path}/")

    if hidden_gems:
        print(f"\n  Hidden Gems: {len(hidden_gems)} (untapped opportunities)")
        print("\n  Top 5 hidden gems:")
        for i, gem in enumerate(hidden_gems[:5], 1):
            score = gem.get("potential_score", 0)
            reasons = ", ".join(gem.get("reasons", [])[:3])
            gem_type = "Emerging Niche" if gem.get("type") == "emerging_niche" else "Hidden Gem"
            price = gem.get("amazon_price", 0)
            price_str = f"£{price:.2f}" if price else "No listings yet"
            image = gem.get("image", "")
            marketing = gem.get("marketing", {})
            marketing_summary = marketing.get("summary", "")
            print(f"    {i}. {gem.get('name', 'Unknown')}")
            print(f"       Potential: {score:.2f} | Price: {price_str} | Reviews: {gem.get('review_count', 0)} | {gem_type}")
            print(f"       Why: {reasons}")
            if image:
                print(f"       Image: {image}")
            if marketing_summary:
                print(f"       Marketing: {marketing_summary}")


if __name__ == "__main__":
    main()
