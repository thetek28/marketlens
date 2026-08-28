"""Opportunity Scoring Engine.

Deterministic, evidence-based scoring for product opportunity.
AI explains the score — it does NOT invent it.

Scoring Model: v2.4
"""

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SCORING_VERSION = "v2.4"

# ─── Default Weights ─────────────────────────────────────────

DEFAULT_WEIGHTS = {
    "demand": 0.20,
    "competition": 0.20,
    "profitability": 0.20,
    "trend": 0.10,
    "market_gap": 0.10,
    "review_opportunity": 0.05,
    "price_stability": 0.05,
    "supplier_potential": 0.05,
    "risk": 0.05,
}

# ─── Confidence Thresholds ───────────────────────────────────

CONFIDENCE_THRESHOLDS = {
    "high": 0.80,    # >= 80% of inputs available
    "medium": 0.50,  # >= 50% of inputs available
    "low": 0.0,      # < 50%
}

# ─── Recommendation Levels ───────────────────────────────────

RECOMMENDATION_LEVELS = [
    (90, "Exceptional Opportunity", "green"),
    (80, "Strong Opportunity", "green"),
    (70, "Promising", "blue"),
    (60, "Moderate", "yellow"),
    (40, "Weak", "orange"),
    (0, "High Concern", "red"),
]


def get_recommendation(score: float) -> Tuple[str, str]:
    """Get recommendation label and color for a score."""
    for threshold, label, color in RECOMMENDATION_LEVELS:
        if score >= threshold:
            return label, color
    return "High Concern", "red"


def get_confidence_level(input_completeness: float) -> str:
    """Determine confidence based on input completeness ratio."""
    if input_completeness >= CONFIDENCE_THRESHOLDS["high"]:
        return "high"
    elif input_completeness >= CONFIDENCE_THRESHOLDS["medium"]:
        return "medium"
    return "low"


# ─── Score Components ─────────────────────────────────────────


@dataclass
class ScoreInputs:
    """All inputs needed for scoring. Missing data = None, not 0."""
    # Product data
    price: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    category: str = ""
    marketplace: str = "US"

    # Supplier data
    supplier_cost: Optional[float] = None
    shipping_cost: Optional[float] = None

    # Market data
    competitor_count: Optional[int] = None
    avg_competitor_price: Optional[float] = None
    avg_competitor_rating: Optional[float] = None
    avg_competitor_reviews: Optional[int] = None
    top_seller_review_count: Optional[int] = None

    # Trend data
    price_trend_30d: Optional[float] = None  # % change
    review_velocity_30d: Optional[float] = None  # reviews/day
    search_trend: Optional[float] = None  # -1 to 1

    # Review sentiment
    negative_review_pct: Optional[float] = None
    top_complaints: List[str] = field(default_factory=list)

    # Category benchmarks (from category_benchmarks table)
    benchmark_avg_reviews: Optional[float] = None
    benchmark_avg_price: Optional[float] = None
    benchmark_avg_rating: Optional[float] = None
    benchmark_median_reviews: Optional[float] = None
    benchmark_p90_reviews: Optional[float] = None

    # Price history
    price_history: List[float] = field(default_factory=list)


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of how the score was calculated."""
    demand: float = 0.0
    competition: float = 0.0
    profitability: float = 0.0
    trend: float = 0.0
    market_gap: float = 0.0
    review_opportunity: float = 0.0
    price_stability: float = 0.0
    supplier_potential: float = 0.0
    risk: float = 0.0

    demand_raw: dict = field(default_factory=dict)
    competition_raw: dict = field(default_factory=dict)
    profitability_raw: dict = field(default_factory=dict)
    trend_raw: dict = field(default_factory=dict)
    market_gap_raw: dict = field(default_factory=dict)
    review_opportunity_raw: dict = field(default_factory=dict)
    price_stability_raw: dict = field(default_factory=dict)
    supplier_potential_raw: dict = field(default_factory=dict)
    risk_raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "demand": round(self.demand, 1),
            "competition": round(self.competition, 1),
            "profitability": round(self.profitability, 1),
            "trend": round(self.trend, 1),
            "market_gap": round(self.market_gap, 1),
            "review_opportunity": round(self.review_opportunity, 1),
            "price_stability": round(self.price_stability, 1),
            "supplier_potential": round(self.supplier_potential, 1),
            "risk": round(self.risk, 1),
            "demand_detail": self.demand_raw,
            "competition_detail": self.competition_raw,
            "profitability_detail": self.profitability_raw,
            "trend_detail": self.trend_raw,
            "market_gap_detail": self.market_gap_raw,
            "review_opportunity_detail": self.review_opportunity_raw,
            "price_stability_detail": self.price_stability_raw,
            "supplier_potential_detail": self.supplier_potential_raw,
            "risk_detail": self.risk_raw,
        }


@dataclass
class ScoreResult:
    """Final scoring result."""
    opportunity_score: float = 0.0
    recommendation: str = ""
    recommendation_color: str = ""
    confidence: str = "low"
    data_quality_score: float = 0.0
    breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    missing_inputs: List[str] = field(default_factory=list)
    available_inputs: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    scoring_version: str = SCORING_VERSION
    score_fingerprint: str = ""

    def to_dict(self) -> dict:
        return {
            "opportunity_score": round(self.opportunity_score, 1),
            "recommendation": self.recommendation,
            "recommendation_color": self.recommendation_color,
            "confidence": self.confidence,
            "data_quality_score": round(self.data_quality_score, 1),
            "score_breakdown": self.breakdown.to_dict(),
            "missing_inputs": self.missing_inputs,
            "available_inputs": self.available_inputs,
            "warnings": self.warnings,
            "scoring_version": self.scoring_version,
        }


# ─── Scoring Engine ──────────────────────────────────────────


class OpportunityScoringEngine:
    """Deterministic scoring engine for product opportunity."""

    def __init__(self, db=None):
        self.db = db
        self.weights = DEFAULT_WEIGHTS.copy()

    def _load_weights(self, version: str = SCORING_VERSION):
        """Load scoring weights from database if available."""
        if self.db:
            try:
                row = self.db._exec(
                    """SELECT demand_weight, competition_weight, profitability_weight,
                              trend_weight, market_gap_weight, review_opportunity_weight,
                              price_stability_weight, supplier_potential_weight, risk_weight
                       FROM scoring_weights WHERE scoring_version = %s AND is_active = TRUE
                       LIMIT 1""",
                    (version,), "one"
                )
                if row:
                    self.weights = {
                        "demand": row["demand_weight"],
                        "competition": row["competition_weight"],
                        "profitability": row["profitability_weight"],
                        "trend": row["trend_weight"],
                        "market_gap": row["market_gap_weight"],
                        "review_opportunity": row["review_opportunity_weight"],
                        "price_stability": row["price_stability_weight"],
                        "supplier_potential": row["supplier_potential_weight"],
                        "risk": row["risk_weight"],
                    }
            except Exception as e:
                logger.warning("Failed to load scoring weights: %s", e)

    def _get_category_benchmarks(self, category: str, marketplace: str = "US") -> dict:
        """Get category benchmarks for relative scoring."""
        if self.db and category:
            try:
                row = self.db._exec(
                    """SELECT avg_reviews, avg_price, avg_rating, avg_margin,
                              median_reviews, median_price, p90_reviews, p90_price
                       FROM category_benchmarks WHERE category = %s AND marketplace = %s""",
                    (category, marketplace), "one"
                )
                if row:
                    return dict(row)
            except Exception as e:
                logger.warning("Failed to load benchmarks for %s: %s", category, e)
        return {}

    def _normalize_to_0_100(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize a value to 0-100 scale."""
        if max_val <= min_val:
            return 50.0
        normalized = (value - min_val) / (max_val - min_val) * 100
        return max(0.0, min(100.0, normalized))

    def _score_demand(self, inputs: ScoreInputs, benchmarks: dict) -> Tuple[float, dict]:
        """Score demand based on review count, review velocity, and benchmarks."""
        detail = {}
        score = 50.0  # Default middle score

        if inputs.review_count is None:
            return 50.0, {"note": "review_count missing, defaulting to 50"}

        # Review count relative to benchmarks
        avg_reviews = benchmarks.get("avg_reviews") or benchmarks.get("benchmark_avg_reviews") or 1000
        median_reviews = benchmarks.get("median_reviews") or benchmarks.get("benchmark_median_reviews") or 500

        if inputs.review_count > 0:
            # How does this product compare to category average?
            relative_to_avg = inputs.review_count / max(avg_reviews, 1)
            relative_to_median = inputs.review_count / max(median_reviews, 1)

            # Score: 0 (way below average) to 100 (way above average)
            # Use log scale to prevent runaway scores for mega-products
            import math
            log_ratio = math.log10(max(relative_to_median, 0.01))
            score = self._normalize_to_0_100(log_ratio, -2, 3)  # -2 = 1% of median, 3 = 1000x median

            detail["review_count"] = inputs.review_count
            detail["category_avg_reviews"] = avg_reviews
            detail["relative_to_avg"] = round(relative_to_avg, 2)

        # Bonus for review velocity (reviews per day)
        if inputs.review_velocity_30d is not None:
            velocity_bonus = min(inputs.review_velocity_30d * 2, 20)  # Max +20
            score = min(100, score + velocity_bonus)
            detail["review_velocity_30d"] = inputs.review_velocity_30d
            detail["velocity_bonus"] = round(velocity_bonus, 1)

        # Penalty for too few reviews (less than 10)
        if inputs.review_count is not None and inputs.review_count < 10:
            score = max(10, score * 0.3)
            detail["low_review_penalty"] = True

        return min(100, max(0, score)), detail

    def _score_competition(self, inputs: ScoreInputs, benchmarks: dict) -> Tuple[float, dict]:
        """Score competition (lower competition = higher score).

        High competition DECREASES opportunity.
        """
        detail = {}
        score = 50.0

        if inputs.competitor_count is None and inputs.top_seller_review_count is None:
            return 50.0, {"note": "competition data missing, defaulting to 50"}

        # Fewer competitors = better opportunity
        if inputs.competitor_count is not None:
            if inputs.competitor_count <= 5:
                score = 85
            elif inputs.competitor_count <= 15:
                score = 70
            elif inputs.competitor_count <= 30:
                score = 50
            elif inputs.competitor_count <= 100:
                score = 30
            else:
                score = 15
            detail["competitor_count"] = inputs.competitor_count

        # Top seller dominance
        if inputs.top_seller_review_count is not None and inputs.review_count is not None:
            if inputs.review_count > 0:
                dominance = inputs.top_seller_review_count / max(inputs.review_count, 1)
                if dominance > 0.5:
                    score = max(10, score - 20)
                    detail["top_seller_dominant"] = True
                elif dominance > 0.3:
                    score = max(20, score - 10)
                    detail["top_seller_strong"] = True
                detail["top_seller_dominance"] = round(dominance, 2)

        # Average competitor rating (high avg rating = harder to compete)
        if inputs.avg_competitor_rating is not None:
            if inputs.avg_competitor_rating >= 4.5:
                score = max(10, score - 10)
                detail["high_competitor_rating"] = True
            elif inputs.avg_competitor_rating < 4.0:
                score = min(100, score + 10)
                detail["low_competitor_rating"] = True
            detail["avg_competitor_rating"] = inputs.avg_competitor_rating

        return min(100, max(0, score)), detail

    def _score_profitability(self, inputs: ScoreInputs) -> Tuple[float, dict]:
        """Score profitability based on margin calculation."""
        detail = {}
        score = 50.0

        if inputs.price is None or inputs.price <= 0:
            return 50.0, {"note": "price missing, defaulting to 50"}

        if inputs.supplier_cost is None:
            return 40.0, {"note": "supplier_cost missing — margin cannot be calculated", "incomplete": True}

        # Calculate estimated margin
        shipping = inputs.shipping_cost or 0
        # Amazon referral fee ~15%
        referral_fee = inputs.price * 0.15
        # FBA fee estimate (varies by size, rough estimate)
        fba_fee = 3.0 + (inputs.price * 0.05)

        total_cost = inputs.supplier_cost + shipping + referral_fee + fba_fee
        profit = inputs.price - total_cost
        margin = (profit / inputs.price * 100) if inputs.price > 0 else 0

        detail["selling_price"] = inputs.price
        detail["supplier_cost"] = inputs.supplier_cost
        detail["estimated_fees"] = round(referral_fee + fba_fee, 2)
        detail["estimated_profit"] = round(profit, 2)
        detail["estimated_margin_pct"] = round(margin, 1)

        # Score based on margin percentage
        if margin >= 40:
            score = 95
        elif margin >= 30:
            score = 85
        elif margin >= 20:
            score = 70
        elif margin >= 15:
            score = 55
        elif margin >= 10:
            score = 40
        elif margin >= 5:
            score = 25
        elif margin > 0:
            score = 15
        else:
            score = 5  # Negative margin

        # Bonus for absolute profit per unit
        if profit >= 15:
            score = min(100, score + 10)
        elif profit >= 8:
            score = min(100, score + 5)

        return min(100, max(0, score)), detail

    def _score_trend(self, inputs: ScoreInputs) -> Tuple[float, dict]:
        """Score trend based on price movement, review velocity, and search trend."""
        detail = {}
        score = 50.0

        signals = 0
        total_signal = 0

        # Price trend
        if inputs.price_trend_30d is not None:
            signals += 1
            # Falling price could mean competition or demand issues
            # Rising price could mean strong demand
            if inputs.price_trend_30d > 5:
                total_signal += 70  # Price rising — could be demand
            elif inputs.price_trend_30d > 0:
                total_signal += 60
            elif inputs.price_trend_30d > -5:
                total_signal += 45
            else:
                total_signal += 30  # Price dropping fast
            detail["price_trend_30d"] = f"{inputs.price_trend_30d:+.1f}%"

        # Review velocity
        if inputs.review_velocity_30d is not None:
            signals += 1
            if inputs.review_velocity_30d >= 10:
                total_signal += 85
            elif inputs.review_velocity_30d >= 3:
                total_signal += 70
            elif inputs.review_velocity_30d >= 1:
                total_signal += 55
            else:
                total_signal += 35
            detail["review_velocity_30d"] = inputs.review_velocity_30d

        # Search trend
        if inputs.search_trend is not None:
            signals += 1
            # search_trend is -1 (declining) to 1 (rising)
            total_signal += 50 + (inputs.search_trend * 40)
            detail["search_trend"] = inputs.search_trend

        if signals > 0:
            score = total_signal / signals
        else:
            return 50.0, {"note": "no trend data available"}

        return min(100, max(0, score)), detail

    def _score_market_gap(self, inputs: ScoreInputs) -> Tuple[float, dict]:
        """Score market gap based on complaints, rating gaps, and price gaps."""
        detail = {}
        score = 50.0

        signals = 0
        total_signal = 0

        # Negative review percentage (high = potential gap)
        if inputs.negative_review_pct is not None:
            signals += 1
            if inputs.negative_review_pct >= 30:
                total_signal += 80  # Lots of unhappy customers = opportunity
            elif inputs.negative_review_pct >= 20:
                total_signal += 65
            elif inputs.negative_review_pct >= 10:
                total_signal += 50
            else:
                total_signal += 35  # Low complaints = market is satisfied
            detail["negative_review_pct"] = inputs.negative_review_pct

        # Number of complaints
        if inputs.top_complaints:
            signals += 1
            complaint_count = len(inputs.top_complaints)
            if complaint_count >= 5:
                total_signal += 75
            elif complaint_count >= 3:
                total_signal += 60
            else:
                total_signal += 45
            detail["complaint_count"] = complaint_count

        # Average competitor rating (lower avg = more gaps)
        if inputs.avg_competitor_rating is not None:
            signals += 1
            if inputs.avg_competitor_rating < 4.0:
                total_signal += 75
            elif inputs.avg_competitor_rating < 4.3:
                total_signal += 60
            else:
                total_signal += 40
            detail["market_quality_gap"] = inputs.avg_competitor_rating < 4.0

        if signals > 0:
            score = total_signal / signals
        else:
            return 50.0, {"note": "insufficient market gap data"}

        return min(100, max(0, score)), detail

    def _score_review_opportunity(self, inputs: ScoreInputs) -> Tuple[float, dict]:
        """Score opportunity based on review complaints and improvement areas."""
        detail = {}
        score = 50.0

        if not inputs.top_complaints:
            return 50.0, {"note": "no complaint data available"}

        complaint_count = len(inputs.top_complaints)

        # More actionable complaints = more opportunity
        if complaint_count >= 5:
            score = 80
        elif complaint_count >= 3:
            score = 65
        elif complaint_count >= 1:
            score = 50
        else:
            score = 30

        detail["actionable_complaints"] = complaint_count
        detail["complaints"] = inputs.top_complaints[:5]

        return min(100, max(0, score)), detail

    def _score_price_stability(self, inputs: ScoreInputs) -> Tuple[float, dict]:
        """Score price stability (stable price = less risk)."""
        detail = {}
        score = 70.0  # Default moderately stable

        if not inputs.price_history or len(inputs.price_history) < 2:
            return 70.0, {"note": "insufficient price history"}

        prices = inputs.price_history
        avg_price = sum(prices) / len(prices)
        if avg_price == 0:
            return 50.0, {"note": "zero average price"}

        # Calculate coefficient of variation
        variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
        std_dev = variance ** 0.5
        cv = std_dev / avg_price

        detail["price_avg"] = round(avg_price, 2)
        detail["price_std_dev"] = round(std_dev, 2)
        detail["coefficient_of_variation"] = round(cv, 4)

        if cv < 0.02:
            score = 90  # Very stable
        elif cv < 0.05:
            score = 80
        elif cv < 0.10:
            score = 65
        elif cv < 0.20:
            score = 45
        else:
            score = 25  # Very volatile

        return min(100, max(0, score)), detail

    def _score_supplier_potential(self, inputs: ScoreInputs) -> Tuple[float, dict]:
        """Score supplier potential based on cost data availability."""
        detail = {}
        score = 50.0

        if inputs.supplier_cost is None:
            return 40.0, {"note": "supplier cost not available", "incomplete": True}

        if inputs.price is None or inputs.price <= 0:
            return 50.0, {"note": "selling price missing"}

        cost_ratio = inputs.supplier_cost / inputs.price
        detail["supplier_cost_ratio"] = round(cost_ratio, 3)

        if cost_ratio <= 0.15:
            score = 90
        elif cost_ratio <= 0.25:
            score = 75
        elif cost_ratio <= 0.35:
            score = 60
        elif cost_ratio <= 0.50:
            score = 40
        else:
            score = 20

        return min(100, max(0, score)), detail

    def _score_risk(self, inputs: ScoreInputs) -> Tuple[float, dict]:
        """Score risk (lower risk = higher score, inverted).

        Risk factors: high competition, price volatility, low rating,
                      few reviews, dominant seller, negative trend.
        """
        detail = {}
        risk_factors = 0
        total_risk = 0

        # Competition risk
        if inputs.competitor_count is not None:
            if inputs.competitor_count > 50:
                risk_factors += 1
                total_risk += 80
                detail["high_competition"] = True
            elif inputs.competitor_count > 20:
                risk_factors += 1
                total_risk += 50
            else:
                total_risk += 20

        # Rating risk
        if inputs.rating is not None:
            if inputs.rating < 3.5:
                risk_factors += 1
                total_risk += 70
                detail["low_rating"] = True
            elif inputs.rating < 4.0:
                risk_factors += 1
                total_risk += 40
            else:
                total_risk += 15

        # Review count risk (too few = unproven)
        if inputs.review_count is not None:
            if inputs.review_count < 10:
                risk_factors += 1
                total_risk += 60
                detail["very_few_reviews"] = True
            elif inputs.review_count < 50:
                risk_factors += 1
                total_risk += 35
            else:
                total_risk += 10

        # Price volatility risk
        if inputs.price_history and len(inputs.price_history) >= 3:
            avg = sum(inputs.price_history) / len(inputs.price_history)
            if avg > 0:
                variance = sum((p - avg) ** 2 for p in inputs.price_history) / len(inputs.price_history)
                cv = (variance ** 0.5) / avg
                if cv > 0.15:
                    risk_factors += 1
                    total_risk += 65
                    detail["price_volatile"] = True
                elif cv > 0.08:
                    risk_factors += 1
                    total_risk += 35

        # Trend risk
        if inputs.search_trend is not None and inputs.search_trend < -0.3:
            risk_factors += 1
            total_risk += 55
            detail["declining_trend"] = True

        if risk_factors > 0:
            avg_risk = total_risk / risk_factors
        else:
            avg_risk = 30  # Default low risk

        # INVERT: high risk = low score
        score = 100 - avg_risk

        detail["risk_factors_count"] = risk_factors
        detail["avg_risk_level"] = round(avg_risk, 1)

        return min(100, max(0, score)), detail

    def _compute_data_quality(self, inputs: ScoreInputs) -> float:
        """Compute data quality score (0-100) based on field completeness."""
        fields = {
            "price": inputs.price is not None and inputs.price > 0,
            "rating": inputs.rating is not None and inputs.rating > 0,
            "review_count": inputs.review_count is not None and inputs.review_count > 0,
            "category": bool(inputs.category),
            "brand": False,  # Not in ScoreInputs directly, check if available
            "supplier_cost": inputs.supplier_cost is not None,
            "competitor_count": inputs.competitor_count is not None,
            "price_history": len(inputs.price_history) >= 3,
            "review_velocity": inputs.review_velocity_30d is not None,
            "search_trend": inputs.search_trend is not None,
            "negative_reviews": inputs.negative_review_pct is not None,
        }
        filled = sum(1 for v in fields.values() if v)
        total = len(fields)
        return round((filled / total) * 100, 1) if total > 0 else 0.0

    def calculate_score(self, inputs: ScoreInputs, version: str = SCORING_VERSION) -> ScoreResult:
        """Calculate the opportunity score from structured inputs.

        This is the main scoring method. It:
        1. Loads configurable weights
        2. Gets category benchmarks
        3. Scores each component independently
        4. Combines with weights
        5. Validates for contradictions
        6. Computes confidence and data quality
        7. Returns full breakdown
        """
        self._load_weights(version)
        benchmarks = self._get_category_benchmarks(inputs.category, inputs.marketplace)
        breakdown = ScoreBreakdown()
        missing = []
        available = []

        # Score each component
        breakdown.demand, breakdown.demand_raw = self._score_demand(inputs, benchmarks)
        breakdown.competition, breakdown.competition_raw = self._score_competition(inputs, benchmarks)
        breakdown.profitability, breakdown.profitability_raw = self._score_profitability(inputs)
        breakdown.trend, breakdown.trend_raw = self._score_trend(inputs)
        breakdown.market_gap, breakdown.market_gap_raw = self._score_market_gap(inputs)
        breakdown.review_opportunity, breakdown.review_opportunity_raw = self._score_review_opportunity(inputs)
        breakdown.price_stability, breakdown.price_stability_raw = self._score_price_stability(inputs)
        breakdown.supplier_potential, breakdown.supplier_potential_raw = self._score_supplier_potential(inputs)
        breakdown.risk, breakdown.risk_raw = self._score_risk(inputs)

        # Track available/missing inputs
        input_checks = [
            ("price", inputs.price is not None),
            ("rating", inputs.rating is not None),
            ("review_count", inputs.review_count is not None),
            ("supplier_cost", inputs.supplier_cost is not None),
            ("competitor_count", inputs.competitor_count is not None),
            ("price_history", len(inputs.price_history) >= 3),
            ("review_velocity", inputs.review_velocity_30d is not None),
            ("search_trend", inputs.search_trend is not None),
            ("negative_reviews", inputs.negative_review_pct is not None),
            ("price_trend", inputs.price_trend_30d is not None),
        ]
        for name, is_available in input_checks:
            if is_available:
                available.append(name)
            else:
                missing.append(name)

        input_completeness = len(available) / len(input_checks) if input_checks else 0

        # Weighted score calculation
        weighted_score = (
            breakdown.demand * self.weights["demand"] +
            breakdown.competition * self.weights["competition"] +
            breakdown.profitability * self.weights["profitability"] +
            breakdown.trend * self.weights["trend"] +
            breakdown.market_gap * self.weights["market_gap"] +
            breakdown.review_opportunity * self.weights["review_opportunity"] +
            breakdown.price_stability * self.weights["price_stability"] +
            breakdown.supplier_potential * self.weights["supplier_potential"] +
            breakdown.risk * self.weights["risk"]
        )

        # Confidence from input completeness
        confidence = get_confidence_level(input_completeness)

        # Data quality
        data_quality = self._compute_data_quality(inputs)

        # Sanity check: contradictory scores
        warnings = []
        weighted_score = self._validate_score(weighted_score, breakdown, warnings)

        # Clamp to 0-100
        weighted_score = max(0.0, min(100.0, weighted_score))

        # Recommendation
        recommendation, rec_color = get_recommendation(weighted_score)

        # Fingerprint for cache invalidation
        from .identity_service import compute_score_fingerprint
        fingerprint = compute_score_fingerprint(
            inputs.price or 0, inputs.review_count or 0, inputs.rating or 0,
            supplier_cost=inputs.supplier_cost
        )

        return ScoreResult(
            opportunity_score=round(weighted_score, 1),
            recommendation=recommendation,
            recommendation_color=rec_color,
            confidence=confidence,
            data_quality_score=data_quality,
            breakdown=breakdown,
            missing_inputs=missing,
            available_inputs=available,
            warnings=warnings,
            scoring_version=version,
            score_fingerprint=fingerprint,
        )

    def _validate_score(self, score: float, breakdown: ScoreBreakdown, warnings: List[str]) -> float:
        """Validate score for contradictions and apply sanity checks."""
        adjusted = score

        # Contradiction: Very low demand + very low profitability should not yield high score
        if breakdown.demand < 20 and breakdown.profitability < 20:
            if adjusted > 60:
                warnings.append("Score capped: low demand + low profitability")
                adjusted = min(adjusted, 55)

        # Contradiction: Very high competition + declining trend
        if breakdown.competition < 20 and breakdown.trend < 25:
            if adjusted > 50:
                warnings.append("Score capped: high competition + declining trend")
                adjusted = min(adjusted, 45)

        # Contradiction: Negative margin should not yield high profitability score
        if breakdown.profitability < 15 and adjusted > 70:
            warnings.append("Score adjusted: negative margin detected")
            adjusted = min(adjusted, 50)

        return adjusted

    def recalculate_score(self, asin: str) -> Optional[ScoreResult]:
        """Recalculate score for a product in the database."""
        if not self.db:
            return None

        try:
            product = self.db._exec("SELECT * FROM products WHERE asin = %s", (asin,), "one")
            if not product:
                return None

            # Build inputs from product data
            inputs = ScoreInputs(
                price=product.get("amazon_price"),
                rating=product.get("rating"),
                review_count=product.get("review_count"),
                category=product.get("category", ""),
                marketplace=product.get("marketplace", "US"),
                supplier_cost=product.get("supplier_price") or product.get("full_data", {}).get("supplier_cost"),
            )

            # Get price history
            history = self.db._exec(
                "SELECT price FROM product_observations WHERE asin = %s AND price IS NOT NULL ORDER BY recorded_at DESC LIMIT 30",
                (asin,), "all"
            )
            if history:
                inputs.price_history = [h["price"] for h in history if h["price"]]

            # Calculate review velocity
            recent_obs = self.db._exec(
                """SELECT review_count, recorded_at FROM product_observations
                   WHERE asin = %s AND review_count IS NOT NULL
                   ORDER BY recorded_at DESC LIMIT 2""",
                (asin,), "all"
            )
            if recent_obs and len(recent_obs) >= 2:
                diff = (recent_obs[0]["review_count"] or 0) - (recent_obs[1]["review_count"] or 0)
                time_diff = (recent_obs[0]["recorded_at"] - recent_obs[1]["recorded_at"]).days or 1
                inputs.review_velocity_30d = diff / time_diff

            # Get sentiment data
            sentiment = self.db._exec(
                "SELECT negative_pct, top_complaints FROM review_sentiment WHERE asin = %s LIMIT 1",
                (asin,), "one"
            )
            if sentiment:
                inputs.negative_review_pct = sentiment.get("negative_pct")
                if sentiment.get("top_complaints"):
                    inputs.top_complaints = sentiment["top_complaints"] if isinstance(sentiment["top_complaints"], list) else []

            # Calculate score
            result = self.calculate_score(inputs)

            # Update product
            self.db._exec(
                """UPDATE products SET
                    opportunity_score = %s,
                    opportunity_confidence = %s,
                    data_quality_score = %s,
                    scoring_version = %s,
                    score_breakdown = %s,
                    score_fingerprint = %s,
                    updated_at = CURRENT_TIMESTAMP
                   WHERE asin = %s""",
                (result.opportunity_score, result.confidence, result.data_quality_score,
                 result.scoring_version, json.dumps(result.breakdown.to_dict()),
                 result.score_fingerprint, asin)
            )

            # Store in scoring history
            self.db._exec(
                """INSERT INTO scoring_history
                   (asin, scoring_version, opportunity_score, confidence, score_breakdown,
                    inputs_used, missing_inputs, data_quality_score)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (asin, result.scoring_version, result.opportunity_score, result.confidence,
                 json.dumps(result.breakdown.to_dict()),
                 json.dumps(result.available_inputs),
                 json.dumps(result.missing_inputs),
                 result.data_quality_score)
            )

            return result
        except Exception as e:
            logger.error("Failed to recalculate score for %s: %s", asin, e)
            return None

    def score_from_product_data(self, product: dict) -> ScoreResult:
        """Score a product from a product dict (for inline scoring without DB recalc)."""
        inputs = ScoreInputs(
            price=product.get("amazon_price"),
            rating=product.get("rating"),
            review_count=product.get("review_count"),
            category=product.get("category", ""),
            marketplace=product.get("marketplace", "US"),
            supplier_cost=product.get("supplier_price"),
        )

        # Try to extract additional data from full_data
        full_data = product.get("full_data", {})
        if isinstance(full_data, str):
            try:
                full_data = json.loads(full_data)
            except:
                full_data = {}

        if full_data:
            inputs.supplier_cost = inputs.supplier_cost or full_data.get("supplier_cost")
            inputs.competitor_count = full_data.get("competitor_count")
            inputs.avg_competitor_rating = full_data.get("avg_competitor_rating")
            inputs.top_seller_review_count = full_data.get("top_seller_review_count")
            inputs.negative_review_pct = full_data.get("negative_review_pct")
            inputs.top_complaints = full_data.get("top_complaints", [])

        # Use existing score_breakdown if available
        existing = product.get("score_breakdown", {})
        if existing and isinstance(existing, dict) and existing.get("demand"):
            # Already scored, just return the stored result
            return ScoreResult(
                opportunity_score=product.get("opportunity_score", 0),
                recommendation=product.get("traffic_light", ""),
                confidence=product.get("opportunity_confidence", "low"),
                data_quality_score=product.get("data_quality_score", 0),
                scoring_version=product.get("scoring_version", ""),
                score_fingerprint=product.get("score_fingerprint", ""),
            )

        return self.calculate_score(inputs)
