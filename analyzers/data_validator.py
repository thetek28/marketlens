"""Data validation and accuracy improvement module."""

import re
from collections import Counter
from statistics import mean, stdev
from typing import Any, Dict, List, Optional, Tuple


class DataValidator:
    """Validates and improves data accuracy through multiple checks."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = {}
        self.min_confidence = config.get("min_confidence", 0.5)
        self.outlier_threshold = config.get("outlier_threshold", 2.0)
        self.min_data_points = config.get("min_data_points", 3)

    def validate_all(
        self,
        ideas: List[Dict[str, Any]],
        raw_data: Dict[str, List],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Validate all data and return improved ideas with accuracy report."""
        validated = []
        report: Dict[str, Any] = {
            "total_input": len(ideas),
            "total_output": 0,
            "removed": 0,
            "improved": 0,
            "avg_confidence": 0,
            "issues_found": [],
        }

        cross_referenced = self._cross_reference(ideas, raw_data)
        deduplicated = self._deduplicate(cross_referenced)
        outlier_filtered = self._detect_outliers(deduplicated)
        quality_checked = self._quality_checks(outlier_filtered)
        confidence_scored = self._add_confidence_scores(quality_checked, raw_data)

        for idea in confidence_scored:
            if idea.get("confidence", 0) >= self.min_confidence:
                validated.append(idea)
            else:
                report["removed"] += 1
                report["issues_found"].append({
                    "name": idea.get("name", "Unknown"),
                    "reason": f"Low confidence: {idea.get('confidence', 0):.2f}",
                })

        report["total_output"] = len(validated)
        report["improved"] = sum(1 for i in validated if i.get("improved", False))

        if validated:
            report["avg_confidence"] = mean([i.get("confidence", 0) for i in validated])

        validated.sort(key=lambda x: x.get("confidence", 0) * x.get("score", 0), reverse=True)

        return validated, report

    def _cross_reference(self, ideas: List[Dict], raw_data: Dict) -> List[Dict]:
        """Cross-reference ideas with raw data sources for accuracy."""
        amazon_data = {p.get("asin", ""): p for p in raw_data.get("amazon", []) if p.get("asin")}
        trends_data = {t.get("term", "").lower(): t for t in raw_data.get("trends", [])}
        social_data = {s.get("term", "").lower(): s for s in raw_data.get("social", [])}

        for idea in ideas:
            asin = idea.get("asin", "")
            name_lower = idea.get("name", "").lower()

            sources_found = []
            verification_score: float = 0

            if asin and asin in amazon_data:
                amazon_product = amazon_data[asin]
                sources_found.append("amazon")

                if amazon_product.get("price", 0) > 0:
                    idea["verified_price"] = amazon_product["price"]
                    verification_score += 0.4

                if amazon_product.get("review_count", 0) > 0:
                    idea["verified_reviews"] = amazon_product["review_count"]
                    verification_score += 0.3

                if amazon_product.get("rating", 0) > 0:
                    idea["verified_rating"] = amazon_product["rating"]
                    verification_score += 0.2

            for term, trend in trends_data.items():
                if term in name_lower or any(w in name_lower for w in term.split()):
                    sources_found.append("trends")
                    idea["trend_verification"] = trend.get("interest", 0)
                    verification_score += 0.05
                    break

            for term, social in social_data.items():
                if term in name_lower or any(w in name_lower for w in term.split()):
                    sources_found.append("social")
                    idea["social_verification"] = social.get("mentions", 0)
                    verification_score += 0.05
                    break

            idea["sources_verified"] = sources_found
            idea["verification_score"] = min(verification_score, 1.0)

        return ideas

    def _deduplicate(self, ideas: List[Dict]) -> List[Dict]:
        """Remove duplicate products, keeping the one with more data."""
        seen: Dict[str, dict] = {}
        deduplicated: List[dict] = []

        for idea in ideas:
            key = self._get_dedup_key(idea)

            if key in seen:
                existing = seen[key]
                if self._has_more_data(idea, existing):
                    deduplicated = [d if d != existing else idea for d in deduplicated]
                    seen[key] = idea
            else:
                seen[key] = idea
                deduplicated.append(idea)

        return deduplicated

    def _get_dedup_key(self, idea: Dict) -> str:
        """Generate deduplication key."""
        asin = idea.get("asin", "")
        if asin:
            return f"asin_{asin}"

        name = idea.get("name", "").lower().strip()
        name = re.sub(r'[^\w\s]', '', name)
        name = ' '.join(name.split())
        return f"name_{name[:50]}"

    def _has_more_data(self, idea1: Dict, idea2: Dict) -> bool:
        """Check which idea has more complete data."""
        fields = ["price", "rating", "review_count", "category", "url", "image"]
        score1 = sum(1 for f in fields if idea1.get(f))
        score2 = sum(1 for f in fields if idea2.get(f))
        return score1 > score2

    def _detect_outliers(self, ideas: List[Dict]) -> List[Dict]:
        """Detect and handle outlier data points."""
        if len(ideas) < self.min_data_points:
            return ideas

        prices = [i.get("amazon_price", 0) or i.get("price", 0) for i in ideas if i.get("amazon_price") or i.get("price")]
        reviews = [i.get("review_count", 0) for i in ideas]
        margins = [i.get("estimated_margin_pct", 0) for i in ideas]

        filtered = []
        for idea in ideas:
            is_outlier = False

            price = idea.get("amazon_price", 0) or idea.get("price", 0)
            if price > 0 and prices:
                if self._is_outlier(price, prices):
                    idea["price_outlier"] = True
                    is_outlier = True

            review_count = idea.get("review_count", 0)
            if review_count > 0 and reviews:
                if self._is_outlier(review_count, reviews):
                    idea["review_outlier"] = True

            margin = idea.get("estimated_margin_pct", 0)
            if margin > 0 and margins:
                if self._is_outlier(margin, margins):
                    idea["margin_outlier"] = True

            idea["is_outlier"] = is_outlier
            filtered.append(idea)

        return filtered

    def _is_outlier(self, value: float, values: List[float]) -> bool:
        """Check if value is a statistical outlier."""
        if len(values) < 3:
            return False

        avg = mean(values)
        std = stdev(values) if len(values) > 1 else 0

        if std == 0:
            return False

        z_score = abs((value - avg) / std)
        return z_score > self.outlier_threshold

    def _quality_checks(self, ideas: List[Dict]) -> List[Dict]:
        """Run data quality checks on each idea."""
        for idea in ideas:
            issues = []

            name = idea.get("name", "")
            if len(name) < 5:
                issues.append("Name too short")
            if len(name) > 200:
                issues.append("Name too long")

            price = idea.get("amazon_price", 0) or idea.get("price", 0)
            if price < 0:
                issues.append("Negative price")
                idea["amazon_price"] = abs(price)
            elif price > 10000:
                issues.append("Price unusually high")
            elif price == 0:
                issues.append("Missing price")

            rating = idea.get("rating", 0)
            if rating < 0 or rating > 5:
                issues.append("Invalid rating")

            reviews = idea.get("review_count", 0)
            if reviews < 0:
                issues.append("Negative review count")
                idea["review_count"] = abs(reviews)

            margin = idea.get("estimated_margin_pct", 0)
            if margin < 0:
                issues.append("Negative margin")
            elif margin > 100:
                issues.append("Margin > 100%")

            asin = idea.get("asin", "")
            if asin and not re.match(r'^B0[A-Z0-9]{8}$', asin):
                issues.append("Invalid ASIN format")

            idea["quality_issues"] = issues
            idea["quality_score"] = 1.0 - (len(issues) * 0.1)

        return ideas

    def _add_confidence_scores(self, ideas: List[Dict], raw_data: Dict) -> List[Dict]:
        """Add confidence scores based on data quality and verification."""
        for idea in ideas:
            confidence = 0.0

            confidence += idea.get("verification_score", 0) * 0.3

            confidence += idea.get("quality_score", 0.5) * 0.2

            if idea.get("asin"):
                confidence += 0.1

            if idea.get("price") or idea.get("amazon_price"):
                confidence += 0.1

            if idea.get("review_count", 0) > 10:
                confidence += 0.1

            if idea.get("rating", 0) > 0:
                confidence += 0.05

            if idea.get("category"):
                confidence += 0.05

            sources = idea.get("sources_verified", [])
            confidence += len(sources) * 0.05

            if not idea.get("is_outlier", False):
                confidence += 0.05

            idea["confidence"] = min(confidence, 1.0)
            idea["confidence_level"] = self._get_confidence_level(confidence)

        return ideas

    def _get_confidence_level(self, confidence: float) -> str:
        """Get confidence level label."""
        if confidence >= 0.8:
            return "HIGH"
        elif confidence >= 0.6:
            return "MEDIUM"
        elif confidence >= 0.4:
            return "LOW"
        else:
            return "VERY LOW"

    def validate_price(self, price: float, category: str = "") -> Tuple[bool, str]:
        """Validate a price value."""
        if price < 0:
            return False, "Negative price"
        if price == 0:
            return False, "Zero price"
        if price > 10000:
            return False, "Price too high"

        category_ranges = {
            "electronics": (5, 5000),
            "kitchen": (2, 1000),
            "clothing": (5, 500),
            "beauty": (3, 200),
            "home": (2, 2000),
            "toys": (5, 500),
            "default": (1, 5000),
        }

        min_price, max_price = category_ranges.get(category.lower(), category_ranges["default"])
        if price < min_price:
            return False, f"Price below typical range for {category}"
        if price > max_price:
            return False, f"Price above typical range for {category}"

        return True, "Valid"

    def validate_rating(self, rating: float) -> Tuple[bool, str]:
        """Validate a rating value."""
        if rating < 0:
            return False, "Negative rating"
        if rating > 5:
            return False, "Rating exceeds 5"
        return True, "Valid"

    def validate_review_count(self, count: int) -> Tuple[bool, str]:
        """Validate review count."""
        if count < 0:
            return False, "Negative review count"
        if count > 1000000:
            return False, "Review count unusually high"
        return True, "Valid"

    def validate_asin(self, asin: str) -> Tuple[bool, str]:
        """Validate Amazon ASIN format."""
        if not asin:
            return False, "Empty ASIN"
        if not re.match(r'^B0[A-Z0-9]{8}$', asin):
            return False, "Invalid ASIN format (expected B0XXXXXXXX)"
        return True, "Valid"

    def get_accuracy_report(self, ideas: List[Dict]) -> Dict[str, Any]:
        """Generate accuracy report for a list of ideas."""
        if not ideas:
            return {"total": 0}

        confidences = [i.get("confidence", 0) for i in ideas]
        qualities = [i.get("quality_score", 0) for i in ideas]
        verifications = [i.get("verification_score", 0) for i in ideas]

        high_conf = sum(1 for c in confidences if c >= 0.8)
        med_conf = sum(1 for c in confidences if 0.6 <= c < 0.8)
        low_conf = sum(1 for c in confidences if c < 0.6)

        all_issues = []
        for idea in ideas:
            for issue in idea.get("quality_issues", []):
                all_issues.append(issue)

        issue_counts = dict(Counter(all_issues))

        return {
            "total": len(ideas),
            "avg_confidence": round(mean(confidences), 3),
            "avg_quality": round(mean(qualities), 3),
            "avg_verification": round(mean(verifications), 3),
            "confidence_distribution": {
                "high": high_conf,
                "medium": med_conf,
                "low": low_conf,
            },
            "top_issues": issue_counts,
            "outliers": sum(1 for i in ideas if i.get("is_outlier")),
        }
