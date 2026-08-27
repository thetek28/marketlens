"""Identifies hidden gem products with untapped market potential."""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class HiddenGemsFinder:
    """Finds products with low current presence but high potential if marketed well.

    A "hidden gem" is a product that:
    - Has low competition (few reviews/listings on Amazon)
    - Shows rising interest on Google Trends or social media
    - Has good profit margins
    - Exists in a niche that isn't oversaturated
    """

    def __init__(self, config):
        self.config = config
        self.min_margin = getattr(config, "min_profit_margin", 30.0)
        self.min_rising_score = 0.4
        self.max_existing_reviews = 200
        self.max_existing_listings = 10

    def find(self, raw_data: dict, analysis: dict) -> List[Dict[str, Any]]:
        """Find hidden gem products from collected data and analysis."""
        gems = []

        trending_terms = self._get_rising_terms(raw_data)
        amazon_products = self._get_amazon_products(raw_data)
        social_terms = self._get_social_signals(raw_data)

        cluster_niches = {}
        for cluster in analysis.get("clusters", {}).get("clusters", []):
            niche = cluster.get("niche", "")
            terms = cluster.get("terms", [])
            cluster_niches[niche] = terms

        for product in amazon_products:
            gem = self._evaluate_product(product, trending_terms, social_terms, cluster_niches)
            if gem:
                gems.append(gem)

        emerging = self._find_emerging_niches(trending_terms, social_terms, cluster_niches, amazon_products)
        gems.extend(emerging)

        gems.sort(key=lambda x: x.get("potential_score", 0), reverse=True)
        return gems

    def _get_rising_terms(self, raw_data: dict) -> Dict[str, float]:
        """Extract rising terms from Google Trends with their strength."""
        rising = {}
        for record in raw_data.get("trends", []):
            if not isinstance(record, dict):
                continue
            term = record.get("term", "")
            if record.get("source") == "google_trends_related":
                value = record.get("value", 0)
                if term and value > 50:
                    rising[term.lower()] = min(value / 100, 1.0)
            elif record.get("source") == "google_trends":
                interest = record.get("interest", 0)
                if term and interest > 0:
                    key = term.lower()
                    if key not in rising or interest > rising[key]:
                        rising[key] = min(interest / 100, 1.0)
        return rising

    def _get_amazon_products(self, raw_data: dict) -> List[Dict[str, Any]]:
        """Extract Amazon products."""
        products = []
        for record in raw_data.get("amazon", []):
            if isinstance(record, dict) and record.get("asin"):
                products.append(record)
        return products

    def _get_social_signals(self, raw_data: dict) -> Dict[str, float]:
        """Extract social media buzz signals."""
        signals: Dict[str, float] = {}
        for record in raw_data.get("social", []):
            if not isinstance(record, dict):
                continue
            term = record.get("term", "").lower()
            if not term:
                continue
            views = record.get("views", 0) or record.get("likes", 0) or record.get("repin_count", 0)
            if views > 0:
                score = min(views / 10000, 1.0)
                if term not in signals or score > signals[term]:
                    signals[term] = score
        return signals

    def _evaluate_product(
        self,
        product: Dict[str, Any],
        trending_terms: Dict[str, float],
        social_terms: Dict[str, float],
        cluster_niches: Dict[str, List[str]],
    ) -> Dict[str, Any] | None:
        """Evaluate if a single product is a hidden gem."""
        title = product.get("title", "").lower()
        review_count = product.get("review_count", 0)
        rating = product.get("rating", 0)
        price = product.get("price", 0)
        asin = product.get("asin", "")

        if not title or price <= 0:
            return None

        if review_count > self.max_existing_reviews:
            return None

        low_competition = 1.0 - min(review_count / self.max_existing_reviews, 1.0)

        trend_score = 0.0
        for term, strength in trending_terms.items():
            if term in title or any(w in title for w in term.split()):
                trend_score = max(trend_score, strength)

        social_score = 0.0
        for term, strength in social_terms.items():
            if term in title or any(w in title for w in term.split()):
                social_score = max(social_score, strength)

        niche_score = 0.0
        for _niche, terms in cluster_niches.items():
            for term in terms:
                if term.lower() in title:
                    niche_count = len(terms)
                    if niche_count < 20:
                        niche_score = max(niche_score, 1.0 - niche_count / 20)

        margin_score = self._estimate_margin_score(price)

        rating_bonus = 0.0
        if 3.5 <= rating <= 4.5:
            rating_bonus = 0.3
        elif rating > 4.5:
            rating_bonus = 0.15

        potential_score = (
            low_competition * 0.30
            + trend_score * 0.25
            + social_score * 0.15
            + niche_score * 0.10
            + margin_score * 0.15
            + rating_bonus * 0.05
        )

        if potential_score < 0.35:
            return None

        reasons = []
        if low_competition > 0.7:
            reasons.append("Very low competition")
        elif low_competition > 0.5:
            reasons.append("Low competition")
        if trend_score > 0.5:
            reasons.append("Rising Google Trends")
        elif trend_score > 0.2:
            reasons.append("Trending on Google")
        if social_score > 0.3:
            reasons.append("Social media buzz")
        if niche_score > 0.5:
            reasons.append("Underserved niche")
        if margin_score > 0.6:
            reasons.append("High margin potential")
        if 3.5 <= rating <= 4.5:
            reasons.append("Room for better product")

        return {
            "name": product.get("title", ""),
            "asin": asin,
            "amazon_price": price,
            "rating": rating,
            "review_count": review_count,
            "url": product.get("url", ""),
            "image": product.get("image", ""),
            "images": product.get("images", []),
            "category": product.get("query", product.get("category", "")),
            "potential_score": round(potential_score, 3),
            "low_competition": round(low_competition, 3),
            "trend_score": round(trend_score, 3),
            "social_score": round(social_score, 3),
            "niche_score": round(niche_score, 3),
            "margin_score": round(margin_score, 3),
            "reasons": reasons,
            "type": "hidden_gem",
        }

    def _find_emerging_niches(
        self,
        trending_terms: Dict[str, float],
        social_terms: Dict[str, float],
        cluster_niches: Dict[str, List[str]],
        amazon_products: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Find niches that are rising but not yet on Amazon."""
        gems: List[Dict[str, Any]] = []
        amazon_titles = [p.get("title", "").lower() for p in amazon_products]

        rising_on_amazon = set()
        for term in trending_terms:
            for title in amazon_titles:
                if term in title:
                    rising_on_amazon.add(term)
                    break

        for term, strength in trending_terms.items():
            if term in rising_on_amazon:
                continue
            if strength < 0.3:
                continue

            social_strength = social_terms.get(term, 0)
            combined = strength * 0.6 + social_strength * 0.4

            if combined < 0.35:
                continue

            gems.append({
                "name": f"[Emerging] {term.title()}",
                "asin": "",
                "amazon_price": 0,
                "rating": 0,
                "review_count": 0,
                "url": "",
                "category": term,
                "potential_score": round(combined, 3),
                "low_competition": 1.0,
                "trend_score": round(strength, 3),
                "social_score": round(social_strength, 3),
                "niche_score": 0.8,
                "margin_score": 0.5,
                "reasons": [
                    "Rising on Google but not yet on Amazon",
                    "First-mover opportunity",
                ],
                "type": "emerging_niche",
            })

        gems.sort(key=lambda x: float(x["potential_score"]), reverse=True)
        return gems[:10]

    def _estimate_margin_score(self, price: float) -> float:
        """Estimate margin potential from selling price."""
        if price < 10:
            return 0.3
        elif price < 25:
            return 0.6
        elif price < 50:
            return 0.8
        elif price < 75:
            return 0.7
        else:
            return 0.5
