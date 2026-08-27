"""Marketing problems and solutions analyzer for product ideas."""

from typing import Any, Dict, List, Optional

MARKETING_STRATEGIES = {
    "social_media": {
        "name": "Social Media Marketing",
        "platforms": ["Instagram", "TikTok", "Pinterest", "YouTube"],
        "cost": "Low-Medium",
        "time_to_results": "1-3 months",
    },
    "ppc": {
        "name": "Amazon PPC Ads",
        "platforms": ["Sponsored Products", "Sponsored Brands", "Sponsored Display"],
        "cost": "Medium-High",
        "time_to_results": "1-2 weeks",
    },
    "influencer": {
        "name": "Influencer Marketing",
        "platforms": ["Micro-influencers", "Macro-influencers", "Affiliates"],
        "cost": "Medium",
        "time_to_results": "2-4 weeks",
    },
    "seo": {
        "name": "Amazon SEO",
        "platforms": ["Title optimization", "Backend keywords", "A+ Content"],
        "cost": "Low",
        "time_to_results": "1-3 months",
    },
    "email": {
        "name": "Email Marketing",
        "platforms": ["Follow-up sequences", "Newsletter", "Promotions"],
        "cost": "Low",
        "time_to_results": "1-2 months",
    },
    "content": {
        "name": "Content Marketing",
        "platforms": ["Blog posts", "Videos", "How-to guides"],
        "cost": "Low-Medium",
        "time_to_results": "2-4 months",
    },
}


class MarketingAnalyzer:
    """Analyzes marketing problems and provides actionable solutions."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = {}
        self.min_reviews = config.get("min_reviews", 10)
        self.high_competition_reviews = config.get("high_competition_reviews", 1000)
        self.ideal_margin_range = config.get("ideal_margin_range", [30, 60])

    def analyze(self, ideas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add marketing analysis to each product idea."""
        analyzed = []
        for idea in ideas:
            marketing = self._analyze_single(idea)
            idea["marketing"] = marketing
            analyzed.append(idea)
        return analyzed

    def _analyze_single(self, idea: Dict[str, Any]) -> Dict[str, Any]:
        """Generate marketing problems and solutions for a single idea."""
        problems = []
        solutions = []
        strategies = []

        review_count = idea.get("review_count", 0)
        rating = idea.get("rating", 0)
        price = idea.get("amazon_price", 0) or idea.get("price", 0)
        margin = idea.get("estimated_margin_pct", 0)
        tier = idea.get("tier", "unknown")
        category = idea.get("category", "")
        name = idea.get("name", "")

        if review_count < self.min_reviews:
            problems.append({
                "problem": "Low Social Proof",
                "severity": "high",
                "description": f"Only {review_count} reviews - customers may hesitate to buy",
            })
            solutions.append({
                "solution": "Review Generation Campaign",
                "priority": "high",
                "actions": [
                    "Use Amazon Vine program (if brand registered)",
                    "Insert follow-up cards in packaging requesting reviews",
                    "Use Request a Review button within 5-30 days of delivery",
                    "Run Giveaway promotions to boost initial reviews",
                ],
                "estimated_cost": "£200-500 for Vine enrollment",
                "timeline": "2-4 weeks for initial reviews",
            })

        if review_count > self.high_competition_reviews:
            problems.append({
                "problem": "High Competition",
                "severity": "high",
                "description": f"{review_count} reviews means established competitors with strong rankings",
            })
            solutions.append({
                "solution": "Differentiation Strategy",
                "priority": "high",
                "actions": [
                    "Create unique product bundles or kits",
                    "Add value with accessories or premium packaging",
                    "Target long-tail keywords competitors ignore",
                    "Create A+ Content with comparison charts",
                ],
                "estimated_cost": "£500-2000 for product differentiation",
                "timeline": "1-2 months for implementation",
            })

        if rating < 4.0 and review_count > 50:
            problems.append({
                "problem": "Poor Competitor Ratings",
                "severity": "medium",
                "description": f"Competitors have {rating} stars - opportunity to outperform",
            })
            solutions.append({
                "solution": "Quality Improvement Focus",
                "priority": "medium",
                "actions": [
                    "Analyze competitor 1-3 star reviews for pain points",
                    "Improve materials, packaging, or instructions",
                    "Highlight quality differences in listing",
                    "Offer superior customer service",
                ],
                "estimated_cost": "£100-500 for product improvements",
                "timeline": "1 month for product sourcing changes",
            })

        if price and price < 15:
            problems.append({
                "problem": "Low Price Point",
                "severity": "medium",
                "description": f"£{price:.2f} limits marketing budget and margins",
            })
            solutions.append({
                "solution": "Bundle or Premium Strategy",
                "priority": "medium",
                "actions": [
                    "Bundle with complementary products to increase price",
                    "Create multi-packs (2-pack, 3-pack, 6-pack)",
                    "Position as premium version with better materials",
                    "Focus on high-volume, low-ACoS keywords",
                ],
                "estimated_cost": "£200-800 for bundling setup",
                "timeline": "2-4 weeks",
            })

        if price and price > 100:
            problems.append({
                "problem": "High Price Barrier",
                "severity": "medium",
                "description": f"£{price:.2f} requires strong trust-building and social proof",
            })
            solutions.append({
                "solution": "Trust Building Campaign",
                "priority": "high",
                "actions": [
                    "Create detailed A+ Content with lifestyle images",
                    "Produce product demo videos",
                    "Partner with influencers for reviews",
                    "Offer money-back guarantee prominently",
                    "Build brand story through social media",
                ],
                "estimated_cost": "£1000-5000 for content creation",
                "timeline": "1-3 months",
            })

        if margin and (margin < self.ideal_margin_range[0] or margin > self.ideal_margin_range[1]):
            severity = "high" if margin < 20 else "low"
            problems.append({
                "problem": "Margin Concerns",
                "severity": severity,
                "description": f"Estimated {margin:.0f}% margin {'is too low for advertising' if margin < 20 else 'is high - may indicate low competition or unmet demand'}",
            })
            if margin < 20:
                solutions.append({
                    "solution": "Cost Optimization",
                    "priority": "high",
                    "actions": [
                        "Negotiate better pricing with suppliers",
                        "Optimize FBA shipping with better packaging",
                        "Increase price if market allows",
                        "Focus on organic traffic to reduce ad spend",
                    ],
                    "estimated_cost": "£0-200 for negotiation",
                    "timeline": "1-2 months",
                })

        if tier == "premium":
            problems.append({
                "problem": "Premium Tier Expectations",
                "severity": "medium",
                "description": "Premium products require higher quality standards and presentation",
            })
            solutions.append({
                "solution": "Premium Brand Experience",
                "priority": "medium",
                "actions": [
                    "Invest in professional product photography",
                    "Create luxury unboxing experience",
                    "Use premium packaging materials",
                    "Offer white-glove customer service",
                    "Build brand storytelling through A+ Content",
                ],
                "estimated_cost": "£500-3000 for branding",
                "timeline": "1-2 months",
            })

        if "seasonal" in category.lower() or "christmas" in name.lower() or "holiday" in name.lower():
            problems.append({
                "problem": "Seasonal Demand",
                "severity": "medium",
                "description": "Product has fluctuating demand throughout the year",
            })
            solutions.append({
                "solution": "Seasonal Marketing Calendar",
                "priority": "medium",
                "actions": [
                    "Start PPC campaigns 2-3 months before peak season",
                    "Build email list year-round for seasonal promotions",
                    "Create evergreen content that references seasonal use",
                    "Diversify into adjacent year-round products",
                    "Run lightning deals during peak periods",
                ],
                "estimated_cost": "£300-1000 for campaign setup",
                "timeline": "Ongoing seasonal planning",
            })

        strategies = self._recommend_strategies(idea)

        overall_score = self._calculate_marketing_score(problems, solutions, strategies)

        return {
            "problems": problems,
            "solutions": solutions,
            "recommended_strategies": strategies,
            "marketing_score": round(overall_score, 2),
            "summary": self._generate_summary(problems, solutions, strategies),
        }

    def _recommend_strategies(self, idea: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Recommend marketing strategies based on product characteristics."""
        strategies = []
        price = idea.get("amazon_price", 0) or idea.get("price", 0)
        review_count = idea.get("review_count", 0)
        tier = idea.get("tier", "unknown")

        strategies.append({
            **MARKETING_STRATEGIES["seo"],
            "priority": "high",
            "reason": "Foundation for all organic visibility",
        })

        if price and price > 25:
            strategies.append({
                **MARKETING_STRATEGIES["influencer"],
                "priority": "medium" if tier != "premium" else "high",
                "reason": "Higher price justifies influencer investment",
            })

        if review_count < 500:
            strategies.append({
                **MARKETING_STRATEGIES["social_media"],
                "priority": "high",
                "reason": "Build brand awareness and drive external traffic",
            })

        if review_count >= 100:
            strategies.append({
                **MARKETING_STRATEGIES["ppc"],
                "priority": "high",
                "reason": "Social proof established - PPC will convert well",
            })

        if tier == "premium":
            strategies.append({
                **MARKETING_STRATEGIES["content"],
                "priority": "medium",
                "reason": "Premium products benefit from educational content",
            })

        strategies.append({
            **MARKETING_STRATEGIES["email"],
            "priority": "low",
            "reason": "Build customer base for repeat purchases",
        })

        return strategies

    def _calculate_marketing_score(
        self,
        problems: List[Dict],
        solutions: List[Dict],
        strategies: List[Dict],
    ) -> float:
        """Calculate a marketing readiness score (0-1)."""
        score = 1.0

        severity_weights = {"high": 0.15, "medium": 0.08, "low": 0.03}
        for problem in problems:
            severity = problem.get("severity", "medium")
            score -= severity_weights.get(severity, 0.05)

        high_priority = sum(1 for s in solutions if s.get("priority") == "high")
        score -= high_priority * 0.05

        if len(strategies) >= 3:
            score += 0.1

        return max(0.0, min(1.0, score))

    def _generate_summary(
        self,
        problems: List[Dict],
        solutions: List[Dict],
        strategies: List[Dict],
    ) -> str:
        """Generate a human-readable summary."""
        if not problems:
            return "Product has strong marketing potential with minimal challenges."

        high_count = sum(1 for p in problems if p.get("severity") == "high")
        top_strategy = strategies[0]["name"] if strategies else "SEO"

        if high_count >= 2:
            return f"Requires significant marketing effort. Focus on {top_strategy} and address {high_count} critical issues first."
        elif high_count == 1:
            return f"One key challenge to address. Prioritize {top_strategy} for best results."
        else:
            return f"Good marketing potential. Recommended approach: {top_strategy}."
