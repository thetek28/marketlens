"""Product Intelligence Service.

Responsible for:
- AI explanation of scores (AI explains, doesn't invent)
- Market analysis from structured data
- Recommendation generation
- Score component descriptions

Separation: Scoring is deterministic. AI provides natural language interpretation.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def get_score_label(value: float) -> str:
    """Convert a 0-100 score to a human-readable label."""
    if value >= 80:
        return "High"
    elif value >= 60:
        return "Medium"
    elif value >= 40:
        return "Low"
    return "Very Low"


def get_demand_label(value: float) -> str:
    if value >= 80: return "Very High"
    if value >= 65: return "High"
    if value >= 45: return "Moderate"
    if value >= 25: return "Low"
    return "Very Low"


def get_competition_label(value: float) -> str:
    """For competition score: high score = LOW competition (good)."""
    if value >= 80: return "Low (Favorable)"
    if value >= 60: return "Moderate"
    if value >= 40: return "High"
    return "Very High (Challenging)"


def get_profitability_label(value: float) -> str:
    if value >= 80: return "Strong"
    if value >= 60: return "Moderate"
    if value >= 40: return "Thin"
    return "Weak"


def get_trend_label(value: float) -> str:
    if value >= 70: return "Rising"
    if value >= 45: return "Stable"
    return "Declining"


class ProductIntelligenceService:
    """Generates AI-powered explanations of product opportunity scores.

    The scoring engine produces deterministic numbers.
    This service translates those numbers into actionable insights.
    """

    def __init__(self, db=None, ai_analyzer=None):
        self.db = db
        self.ai_analyzer = ai_analyzer

    def generate_explanation(self, product: dict, score_breakdown: dict) -> dict:
        """Generate a human-readable explanation of the score.

        Uses structured rules for consistency. Optional AI enhancement
        for richer language when available.
        """
        explanation = {
            "summary": "",
            "positive_factors": [],
            "negative_factors": [],
            "data_notes": [],
            "recommendation": "",
        }

        opportunity = product.get("opportunity_score", 0)
        confidence = product.get("opportunity_confidence", "low")
        data_quality = product.get("data_quality_score", 0)

        # Extract component scores
        demand = score_breakdown.get("demand", 50)
        competition = score_breakdown.get("competition", 50)
        profitability = score_breakdown.get("profitability", 50)
        trend = score_breakdown.get("trend", 50)
        market_gap = score_breakdown.get("market_gap", 50)
        risk = score_breakdown.get("risk", 50)
        price_stability = score_breakdown.get("price_stability", 50)
        review_opp = score_breakdown.get("review_opportunity", 50)

        # ─── Summary ────────────────────────────────────────────
        from .scoring_engine import get_recommendation
        rec_label, _ = get_recommendation(opportunity)

        if confidence == "low":
            explanation["summary"] = (
                f"Opportunity Score: {opportunity:.0f}/100 ({rec_label}). "
                f"Confidence is LOW — important data is missing. "
                f"Score should be validated with additional research."
            )
        elif confidence == "medium":
            explanation["summary"] = (
                f"Opportunity Score: {opportunity:.0f}/100 ({rec_label}). "
                f"Some data gaps exist. Results are moderately reliable."
            )
        else:
            explanation["summary"] = (
                f"Opportunity Score: {opportunity:.0f}/100 ({rec_label}). "
                f"High confidence based on available market data."
            )

        # ─── Positive Factors ────────────────────────────────────
        if demand >= 65:
            explanation["positive_factors"].append(
                f"Strong demand signal — {get_demand_label(demand).lower()} review activity "
                f"relative to category benchmarks."
            )
        elif demand >= 50:
            explanation["positive_factors"].append(
                f"Moderate demand — review activity is average for this category."
            )

        if profitability >= 70:
            detail = score_breakdown.get("profitability_detail", {})
            margin = detail.get("estimated_margin_pct")
            if margin:
                explanation["positive_factors"].append(
                    f"Healthy estimated margin (~{margin:.0f}%) suggests good profitability potential."
                )
            else:
                explanation["positive_factors"].append(
                    "Profitability metrics are favorable."
                )

        if competition >= 70:
            explanation["positive_factors"].append(
                f"Low competition — market is not saturated."
            )

        if trend >= 65:
            explanation["positive_factors"].append(
                "Positive market trend — interest is growing."
            )

        if market_gap >= 65:
            complaints = score_breakdown.get("market_gap_detail", {}).get("complaint_count", 0)
            if complaints > 0:
                explanation["positive_factors"].append(
                    f"Identified {complaints} customer complaint themes — "
                    f"potential differentiation opportunities exist."
                )
            else:
                explanation["positive_factors"].append(
                    "Market gap analysis indicates unmet customer needs."
                )

        if risk >= 65:
            explanation["positive_factors"].append(
                "Low overall risk profile across multiple dimensions."
            )

        if price_stability >= 70:
            explanation["positive_factors"].append(
                "Price has been stable — predictable market conditions."
            )

        # ─── Negative Factors ────────────────────────────────────
        if demand < 40:
            explanation["negative_factors"].append(
                f"Weak demand signal — {get_demand_label(demand).lower()} review activity."
            )

        if competition < 40:
            explanation["negative_factors"].append(
                "Highly competitive market — significant barriers to entry."
            )

        if profitability < 40:
            detail = score_breakdown.get("profitability_detail", {})
            if detail.get("incomplete"):
                explanation["negative_factors"].append(
                    "Profitability could not be fully calculated — supplier cost data is missing."
                )
            else:
                margin = detail.get("estimated_margin_pct", 0)
                explanation["negative_factors"].append(
                    f"Estimated margin is thin (~{margin:.0f}%) — pricing pressure likely."
                )

        if trend < 35:
            explanation["negative_factors"].append(
                "Market trend is declining — demand may be shrinking."
            )

        if risk < 35:
            explanation["negative_factors"].append(
                "Elevated risk profile — multiple risk factors detected."
            )

        if price_stability < 40:
            explanation["negative_factors"].append(
                "Price has been volatile — may indicate unstable market conditions."
            )

        # ─── Data Notes ──────────────────────────────────────────
        missing = product.get("score_breakdown", {}).get("missing_inputs", [])
        if isinstance(missing, list) and missing:
            explanation["data_notes"].append(
                f"Missing data: {', '.join(missing)}. Score confidence is reduced."
            )

        if data_quality < 50:
            explanation["data_notes"].append(
                f"Data quality is {data_quality:.0f}/100 — many fields are incomplete."
            )

        if confidence == "low":
            explanation["data_notes"].append(
                "Low confidence — this score should not be used as the sole decision basis."
            )

        # ─── Recommendation ──────────────────────────────────────
        if opportunity >= 80 and confidence in ("high", "medium"):
            explanation["recommendation"] = (
                "This product shows strong opportunity. Consider deeper analysis "
                "including supplier sourcing, sample ordering, and competition study."
            )
        elif opportunity >= 60:
            explanation["recommendation"] = (
                "Promising opportunity worth monitoring. Gather additional data "
                "on supplier costs and competition before committing."
            )
        elif opportunity >= 40:
            explanation["recommendation"] = (
                "Moderate opportunity with notable risks. Additional validation recommended."
            )
        else:
            explanation["recommendation"] = (
                "Significant concerns detected. Proceed with caution or consider "
                "alternative products."
            )

        # ─── Try AI Enhancement (optional) ──────────────────────
        if self.ai_analyzer and confidence != "low":
            try:
                ai_enhanced = self._ai_enhance_explanation(product, score_breakdown, explanation)
                if ai_enhanced:
                    explanation["ai_enhanced"] = True
                    # Merge AI suggestions but keep our structure
                    if "summary" in ai_enhanced:
                        explanation["summary"] = ai_enhanced["summary"]
                    if "ai_insights" in ai_enhanced:
                        explanation["ai_insights"] = ai_enhanced["ai_insights"]
            except Exception as e:
                logger.debug("AI enhancement failed (using rule-based): %s", e)

        return explanation

    def _ai_enhance_explanation(self, product: dict, score_breakdown: dict, base_explanation: dict) -> Optional[dict]:
        """Use AI to enhance the explanation with richer language.

        The AI receives the STRUCTURED score breakdown and must work within
        the evidence we provide. It cannot override verified numbers.
        """
        if not self.ai_analyzer:
            return None

        prompt = f"""You are a product market analyst. Given the following structured scoring data,
provide a brief (2-3 sentence) market insight. Do NOT invent numbers. Only interpret the data provided.

Product: {product.get('name', 'Unknown')}
Category: {product.get('category', 'Unknown')}
Price: ${product.get('amazon_price', 0):.2f}
Rating: {product.get('rating', 0)}/5
Reviews: {product.get('review_count', 0)}

Score Breakdown:
- Demand: {score_breakdown.get('demand', 'N/A')}/100
- Competition: {score_breakdown.get('competition', 'N/A')}/100 (higher = less competition)
- Profitability: {score_breakdown.get('profitability', 'N/A')}/100
- Trend: {score_breakdown.get('trend', 'N/A')}/100
- Market Gap: {score_breakdown.get('market_gap', 'N/A')}/100
- Risk: {score_breakdown.get('risk', 'N/A')}/100 (higher = less risk)

Provide your response as JSON with key "ai_insights" containing a string."""

        try:
            if hasattr(self.ai_analyzer, '_call_ai'):
                response = self.ai_analyzer._call_ai(prompt, max_tokens=150)
                if response:
                    import json as _json
                    parsed = _json.loads(response) if isinstance(response, str) else response
                    return parsed
        except Exception:
            pass

        return None

    def get_score_components_display(self, score_breakdown: dict) -> List[dict]:
        """Get formatted score components for UI display."""
        components = [
            {
                "key": "demand",
                "label": "Demand",
                "score": score_breakdown.get("demand", 0),
                "label_text": get_demand_label(score_breakdown.get("demand", 0)),
                "weight": "20%",
                "description": "Based on review count, review velocity, and category benchmarks.",
            },
            {
                "key": "competition",
                "label": "Competition",
                "score": score_breakdown.get("competition", 0),
                "label_text": get_competition_label(score_breakdown.get("competition", 0)),
                "weight": "20%",
                "description": "Based on competitor count, top seller dominance, and market concentration.",
            },
            {
                "key": "profitability",
                "label": "Profitability",
                "score": score_breakdown.get("profitability", 0),
                "label_text": get_profitability_label(score_breakdown.get("profitability", 0)),
                "weight": "20%",
                "description": "Based on estimated margin after fees and costs.",
            },
            {
                "key": "trend",
                "label": "Trend",
                "score": score_breakdown.get("trend", 0),
                "label_text": get_trend_label(score_breakdown.get("trend", 0)),
                "weight": "10%",
                "description": "Based on price movement, review velocity, and search trends.",
            },
            {
                "key": "market_gap",
                "label": "Market Gap",
                "score": score_breakdown.get("market_gap", 0),
                "label_text": get_score_label(score_breakdown.get("market_gap", 0)),
                "weight": "10%",
                "description": "Based on customer complaints, rating gaps, and unmet needs.",
            },
            {
                "key": "review_opportunity",
                "label": "Review Opportunity",
                "score": score_breakdown.get("review_opportunity", 0),
                "label_text": get_score_label(score_breakdown.get("review_opportunity", 0)),
                "weight": "5%",
                "description": "Based on identifiable improvement areas from customer reviews.",
            },
            {
                "key": "price_stability",
                "label": "Price Stability",
                "score": score_breakdown.get("price_stability", 0),
                "label_text": get_score_label(score_breakdown.get("price_stability", 0)),
                "weight": "5%",
                "description": "Based on price history volatility.",
            },
            {
                "key": "supplier_potential",
                "label": "Supplier Potential",
                "score": score_breakdown.get("supplier_potential", 0),
                "label_text": get_score_label(score_breakdown.get("supplier_potential", 0)),
                "weight": "5%",
                "description": "Based on supplier cost relative to selling price.",
            },
            {
                "key": "risk",
                "label": "Risk",
                "score": score_breakdown.get("risk", 0),
                "label_text": get_score_label(score_breakdown.get("risk", 0)),
                "weight": "5%",
                "description": "Based on competition risk, margin risk, trend risk, and data risk.",
            },
        ]
        return components

    def get_market_analysis(self, product: dict, score_breakdown: dict) -> dict:
        """Generate structured market analysis for a product."""
        analysis = {
            "market_position": "",
            "key_strengths": [],
            "key_weaknesses": [],
            "opportunities": [],
            "threats": [],
            "estimated_monthly_revenue": None,
            "data_gaps": [],
        }

        demand = score_breakdown.get("demand", 50)
        competition = score_breakdown.get("competition", 50)
        profitability = score_breakdown.get("profitability", 50)
        risk = score_breakdown.get("risk", 50)

        # Market position
        if demand >= 65 and competition >= 60:
            analysis["market_position"] = "Strong market position with good demand and manageable competition."
        elif demand >= 65 and competition < 40:
            analysis["market_position"] = "High demand but very competitive — differentiation is critical."
        elif demand < 40 and competition >= 60:
            analysis["market_position"] = "Low demand despite low competition — market may be too niche."
        else:
            analysis["market_position"] = "Mixed signals — further analysis recommended."

        # Strengths
        if demand >= 65:
            analysis["key_strengths"].append("Strong customer demand")
        if profitability >= 65:
            analysis["key_strengths"].append("Good profit margin potential")
        if competition >= 65:
            analysis["key_strengths"].append("Low competitive pressure")
        if risk >= 65:
            analysis["key_strengths"].append("Low overall risk")

        # Weaknesses
        if demand < 40:
            analysis["key_weaknesses"].append("Weak market demand")
        if profitability < 40:
            analysis["key_weaknesses"].append("Thin or unverifiable margins")
        if competition < 40:
            analysis["key_weaknesses"].append("Highly competitive market")
        if risk < 40:
            analysis["key_weaknesses"].append("Multiple risk factors identified")

        # Opportunities
        market_gap = score_breakdown.get("market_gap", 50)
        if market_gap >= 65:
            analysis["opportunities"].append("Customer complaints suggest differentiation potential")
        review_opp = score_breakdown.get("review_opportunity", 50)
        if review_opp >= 65:
            analysis["opportunities"].append("Review analysis reveals improvement areas")

        # Threats
        if competition < 30:
            analysis["threats"].append("Dominant competitors may be hard to displace")
        trend = score_breakdown.get("trend", 50)
        if trend < 30:
            analysis["threats"].append("Declining market trend")
        price_stab = score_breakdown.get("price_stability", 50)
        if price_stab < 30:
            analysis["threats"].append("Price volatility indicates market instability")

        # Revenue estimate (rough)
        price = product.get("amazon_price", 0)
        reviews = product.get("review_count", 0)
        if price and reviews:
            # Very rough: ~30-50 reviews/day for top products, much less for others
            # This is a placeholder — real estimate needs BSR data
            est_daily_reviews = max(reviews / 365, 0.1)
            # Rough conversion: 1 review ≈ 30-50 sales
            est_daily_sales = est_daily_reviews * 40
            est_monthly_revenue = price * est_daily_sales * 30
            analysis["estimated_monthly_revenue"] = round(est_monthly_revenue, 0)

        # Data gaps
        breakdown = score_breakdown
        for key in ["demand_detail", "profitability_detail", "competition_detail"]:
            detail = breakdown.get(key, {})
            if isinstance(detail, dict) and detail.get("incomplete"):
                field_name = key.replace("_detail", "")
                analysis["data_gaps"].append(field_name)

        return analysis

    def score_history_summary(self, asin: str) -> Optional[dict]:
        """Get score history and trend for a product."""
        if not self.db:
            return None

        try:
            history = self.db._exec(
                """SELECT opportunity_score, confidence, data_quality_score,
                          scoring_version, score_breakdown, calculated_at
                   FROM scoring_history WHERE asin = %s
                   ORDER BY calculated_at DESC LIMIT 10""",
                (asin,), "all"
            )
            if not history:
                return None

            scores = [h["opportunity_score"] for h in history if h["opportunity_score"]]
            if not scores:
                return None

            trend = "stable"
            if len(scores) >= 2:
                diff = scores[0] - scores[-1]
                if diff > 5:
                    trend = "improving"
                elif diff < -5:
                    trend = "declining"

            return {
                "current_score": scores[0],
                "previous_scores": scores[1:],
                "trend": trend,
                "score_range": {
                    "min": min(scores),
                    "max": max(scores),
                    "avg": round(sum(scores) / len(scores), 1),
                },
                "history_count": len(history),
                "latest_version": history[0].get("scoring_version", ""),
            }
        except Exception as e:
            logger.error("Failed to get score history for %s: %s", asin, e)
            return None
