"""Product validator - validates and filters product ideas."""

from typing import Any, Dict, List, Optional


class ProductValidator:
    """Validates and filters product ideas based on criteria."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = {}
        self.min_margin = config.get("min_profit_margin", 15)
        self.max_competition = config.get("max_competition", 500)
        self.min_demand = config.get("min_demand_score", 0.1)

    def validate(self, ideas: List[Dict[str, Any]], raw_data: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Validate and filter product ideas. Returns all products but flags validity."""
        validated = []
        for idea in ideas:
            if self._is_valid(idea):
                idea["validated"] = True
            else:
                idea["validated"] = False
            validated.append(idea)
        return validated

    def _is_valid(self, idea: Dict[str, Any]) -> bool:
        """Check if a single idea meets validation criteria."""
        margin = idea.get("estimated_margin_pct", 0)
        if margin < self.min_margin:
            return False

        review_count = idea.get("review_count", 0)
        if review_count > self.max_competition * 100:
            return False

        price = idea.get("amazon_price", 0) or idea.get("price", 0)
        if price <= 0:
            return False

        return True
