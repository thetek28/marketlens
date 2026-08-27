"""Analysis service module for the Amazon Product AI pipeline.

Orchestrates the end-to-end product analysis pipeline, coordinating multiple
analyzers to evaluate profitability, validate product viability, assess
marketing potential, generate AI scores, compute consistency metrics, produce
demand forecasts, and match supplier sources. The service aggregates results
from each analysis stage and returns a ranked list of prioritized product
opportunities.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from analyzers import (
    ConsistencyAnalyzer,
    ForecastingEngine,
    MarketingAnalyzer,
    ProductValidator,
    ProfitabilityEstimator,
)
from analyzers.ai_analyzer import AIAnalyzer
from database.suppliers_db import match_suppliers_to_products

logger = logging.getLogger(__name__)


class AnalysisService:
    """Orchestrates the full product analysis pipeline.

    Chains together profitability estimation, product validation, marketing
    analysis, AI-powered scoring, 5-year consistency analysis, demand
    forecasting, and supplier sourcing into a single unified workflow. Each
    stage processes the output of the previous stage, progressively enriching
    the product data with actionable insights and ranking metrics.

    Attributes:
        config: Application configuration dictionary.
        ai_analyzer: AIAnalyzer instance used for product scoring.
    """

    def __init__(self, config: Dict[str, Any], ai_analyzer: Optional[AIAnalyzer] = None):
        self.config = config
        self.ai_analyzer = ai_analyzer or AIAnalyzer(config)

    def analyze(
        self,
        products: List[Dict[str, Any]],
        raw_data: Dict[str, List],
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Run full analysis pipeline on products.

        Executes the nine-stage analysis pipeline sequentially:
        profitability estimation, product validation, marketing analysis,
        AI scoring, consistency analysis, forecasting, supplier sourcing,
        priority ranking, and database supplier matching. Each stage is
        wrapped in error handling so that failures in one stage do not
        prevent subsequent stages from running.

        Args:
            products: Raw product data to analyze.
            raw_data: Raw data from collectors (amazon, trends, social).
            status_callback: Optional callback for status updates.

        Returns:
            Analyzed and ranked products, limited to the top 100 results.
        """
        if not products:
            return []

        def update_status(msg: str) -> None:
            if status_callback:
                status_callback(msg)
            logger.info(msg)

        ideas = list(products)

        # Step 1: Profitability estimation
        update_status("Estimating profitability...")
        try:
            ideas = ProfitabilityEstimator(self.config).estimate(raw_data)
            logger.info(f"Profitability: {len(ideas)} products")
        except Exception as e:
            logger.warning(f"Profitability failed: {e}")

        # Step 2: Product validation
        update_status("Validating products...")
        try:
            ideas = ProductValidator(self.config).validate(ideas, raw_data)
        except Exception as e:
            logger.warning(f"Validation failed: {e}")

        # Step 3: Marketing analysis
        update_status("Analyzing marketing potential...")
        try:
            ideas = MarketingAnalyzer(self.config).analyze(ideas)
        except Exception as e:
            logger.warning(f"Marketing analysis failed: {e}")

        # Step 4: AI scoring
        update_status("Running AI analysis...")
        try:
            ideas = self.ai_analyzer.analyze_products(ideas)
            scored = len([i for i in ideas if i.get("ai_score", 0) > 0])
            logger.info(f"AI analysis: {scored} products scored")
        except Exception as e:
            logger.warning(f"AI analysis failed: {e}")

        # Step 5: Consistency analysis
        update_status("Calculating 5-year consistency...")
        try:
            consistency = ConsistencyAnalyzer(self.config)
            ideas = consistency.analyze(ideas, raw_data)
        except Exception as e:
            logger.warning(f"Consistency analysis failed: {e}")

        # Step 6: Forecasting
        update_status("Building forecasts...")
        try:
            forecast = ForecastingEngine(self.config)
            ideas = forecast.forecast_products(ideas)
        except Exception as e:
            logger.warning(f"Forecasting failed: {e}")

        # Step 7: Supplier sourcing
        update_status("Sourcing suppliers...")
        ideas = self._source_suppliers(ideas, status_callback)

        # Step 8: Priority ranking
        for i, idea in enumerate(ideas):
            idea["priority_rank"] = i + 1
            idea["priority"] = calculate_priority(idea, i + 1)
            idea.setdefault("url", "https://amazon.com/dp/{}".format(idea.get("asin", "")))

        # Step 9: Database supplier matching
        try:
            ideas = match_suppliers_to_products(ideas, use_alibaba=False)
        except Exception as e:
            logger.debug(f"Supplier matching failed: {e}")

        return ideas[:100]

    def _source_suppliers(
        self,
        ideas: List[Dict[str, Any]],
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Source suppliers for each product idea.

        Attempts to retrieve supplier pricing data from Alibaba for each
        product. Falls back to a direct Alibaba search when cached pricing
        is unavailable. Updates each idea dict with supplier contact and
        location information when found.

        Args:
            ideas: List of product idea dictionaries to enrich.
            status_callback: Optional callback for status updates.

        Returns:
            The same list with supplier data appended to each idea.
        """
        try:
            from data_collectors.alibaba_scraper import AlibabaScraper, get_supplier_pricing

            scraper = AlibabaScraper()
            for idx, idea in enumerate(ideas):
                try:
                    supplier_data = get_supplier_pricing(idea)
                    if supplier_data:
                        idea.update(supplier_data)
                    else:
                        product_name = idea.get("name", idea.get("title", ""))
                        category = idea.get("category", "")
                        query = f"{product_name} {category}".strip()
                        suppliers = scraper.search_suppliers(query, max_results=1)
                        if suppliers:
                            supplier = suppliers[0]
                            idea["supplier_name"] = supplier.get("company", "Unknown")
                            idea["supplier_company"] = supplier.get("company", "")
                            idea["supplier_email"] = supplier.get("email", "")
                            idea["supplier_phone"] = supplier.get("phone", "")
                            idea["supplier_whatsapp"] = supplier.get("whatsapp", "")
                            idea["supplier_website"] = supplier.get("website", "")
                            idea["supplier_location"] = supplier.get("location", "")
                            idea["supplier_rating"] = supplier.get("rating", 4.3)
                            idea["supplier_price_source"] = supplier.get("source", "alibaba")
                except Exception as e:
                    logger.debug(f"Supplier sourcing failed for product: {e}")

                if status_callback and (idx + 1) % 10 == 0:
                    status_callback(f"Sourcing suppliers [{idx + 1}/{len(ideas)}]...")

            logger.info(f"Supplier sourcing completed for {len(ideas)} products")
        except Exception as e:
            logger.warning(f"Supplier sourcing failed: {e}")

        return ideas


def calculate_priority(idea: Dict[str, Any], rank: int) -> Dict[str, Any]:
    """Calculate priority tier and recommended action for a product idea.

    Assigns a priority tier (CRITICAL, HIGH, MEDIUM, LOW, MINIMAL) based on
    the product's rank position and its AI score combined with estimated
    margin percentage. Higher-ranked products and those with strong scores
    and margins receive higher priority tiers.

    Args:
        idea: Product idea dictionary containing ai_score and estimated_margin_pct.
        rank: The product's rank position (1-indexed) in the sorted list.

    Returns:
        Dictionary with 'rank', 'tier', and 'action' keys describing
        the assigned priority level and recommended next step.
    """
    score = idea.get("ai_score", 0)
    margin = idea.get("estimated_margin_pct", 0)

    if rank <= 10 or (score >= 0.8 and margin >= 40):
        tier = "CRITICAL"
    elif rank <= 25 or (score >= 0.7 and margin >= 35):
        tier = "HIGH"
    elif rank <= 50:
        tier = "MEDIUM"
    elif rank <= 75:
        tier = "LOW"
    else:
        tier = "MINIMAL"

    action = {
        "CRITICAL": "Source now",
        "HIGH": "Research",
        "MEDIUM": "Watchlist",
        "LOW": "Monitor",
        "MINIMAL": "Track",
    }.get(tier, "Track")

    return {"rank": rank, "tier": tier, "action": action}
