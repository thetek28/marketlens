"""AI-powered analysis using OpenAI/Claude APIs for better accuracy."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class AIAnalyzer:
    """Uses AI APIs to enhance product analysis accuracy."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = {}
        self.config = config
        self.openai_key = os.getenv("OPENAI_API_KEY", config.get("openai_api_key", ""))
        self.claude_key = os.getenv("ANTHROPIC_API_KEY", config.get("anthropic_api_key", ""))
        self.provider = config.get("ai_provider", "openai")
        self.license_mgr = None

    def set_license_manager(self, license_mgr):
        self.license_mgr = license_mgr

    def analyze_products(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enhance product analysis with AI insights."""
        if not products:
            return products

        enhanced = []
        for product in products:
            try:
                ai_insights = self._get_ai_insights(product)
                product.update(ai_insights)
            except Exception as e:
                logger.debug(f"AI analysis failed for product: {e}")
                product["ai_score"] = product.get("score", 0.5)
                product["ai_recommendation"] = "Manual review recommended"
                product["ai_confidence"] = 0.5
            enhanced.append(product)

        return enhanced

    def _get_ai_insights(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI insights for a single product."""
        prompt = self._build_analysis_prompt(product)

        if self.openai_key and HAS_OPENAI:
            return self._query_openai(prompt)
        elif self.claude_key and HAS_ANTHROPIC:
            return self._query_claude(prompt)
        else:
            return self._fallback_analysis(product)

    def _build_analysis_prompt(self, product: Dict[str, Any]) -> str:
        """Build enhanced analysis prompt for AI."""
        seller = product.get("seller_info", {})
        return """You are an expert Amazon product analyst. Analyze this product for FBA viability:

PRODUCT DATA:
- Name: {name}
- Category: {category}
- Price: £{price:.2f}
- Rating: {rating}/5 ({review_count} reviews)
- BSR: #{bsr}
- Seller: {seller} ({fulfillment})
- Monthly Sales Est: {sales}/mo

MARKET CONTEXT:
- Category average margin: 25-35%
- Sweet spot price: £15-£35
- Ideal review count: 100-10,000
- FBA advantage products score higher

Respond with JSON:
{{
  "ai_score": 0.0-1.0 (viability score),
  "ai_recommendation": "one-line verdict",
  "ai_confidence": 0.0-1.0,
  "market_demand": "high/medium/low",
  "competition_level": "high/medium/low",
  "suggested_action": "buy_now/research_more/skip",
  "price_analysis": "brief positioning analysis",
  "niche_opportunity": "high/medium/low",
  "improvement_areas": ["area1", "area2", "area3"],
  "risk_factors": ["risk1", "risk2"],
  "estimated_monthly_revenue": "estimated £ range"
}}

JSON only. No explanation.""".format(
            name=product.get("name", "Unknown"),
            category=product.get("category", "Unknown"),
            price=product.get("amazon_price", 0),
            rating=product.get("rating", 0),
            review_count=product.get("review_count", 0),
            bsr=product.get("seller_info", {}).get("bsr", "N/A"),
            seller=seller.get("seller_name", "Unknown"),
            fulfillment="FBA" if seller.get("is_fba") else "FBM",
            sales=seller.get("monthly_sales_est", "N/A"),
        )

    def _query_openai(self, prompt: str) -> Dict[str, Any]:
        """Query OpenAI API."""
        if not HAS_OPENAI or not self.openai_key:
            return self._fallback_analysis({})

        try:
            client = openai.OpenAI(api_key=self.openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an Amazon product analyst. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3,
            )

            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            return json.loads(content)
        except Exception as e:
            logger.debug(f"OpenAI query failed: {e}")
            return self._fallback_analysis({})

    def _query_claude(self, prompt: str) -> Dict[str, Any]:
        """Query Claude API."""
        if not HAS_ANTHROPIC or not self.claude_key:
            return self._fallback_analysis({})

        try:
            client = anthropic.Anthropic(api_key=self.claude_key)
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=300,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )

            content = response.content[0].text.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            return json.loads(content)
        except Exception as e:
            logger.debug(f"Claude query failed: {e}")
            return self._fallback_analysis({})

    def _fallback_analysis(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based fallback when AI APIs are unavailable."""
        price = product.get("amazon_price", product.get("price", 0))
        rating = product.get("rating", 0)
        reviews = product.get("review_count", 0)

        score = 0.5

        if 10 <= price <= 35:
            score += 0.15
        elif price > 50:
            score -= 0.1

        if rating >= 4.3:
            score += 0.1
        elif rating < 3.5:
            score -= 0.15

        if reviews > 10000:
            score += 0.1
        elif reviews < 100:
            score += 0.05

        if reviews > 50000:
            score -= 0.1

        score = max(0.1, min(1.0, score))

        if score >= 0.7:
            recommendation = "Strong product opportunity - research further"
            action = "research_more"
        elif score >= 0.5:
            recommendation = "Moderate opportunity - monitor trends"
            action = "research_more"
        else:
            recommendation = "Low opportunity - consider skipping"
            action = "skip"

        return {
            "ai_score": round(score, 2),
            "ai_recommendation": recommendation,
            "ai_confidence": 0.6,
            "market_demand": "medium",
            "competition_level": "medium",
            "suggested_action": action,
            "price_analysis": "Price is within typical range for category",
            "improvement_areas": ["Review competitor listings", "Check supplier pricing"],
        }

    def generate_summary(self, products: List[Dict[str, Any]]) -> str:
        """Generate AI summary of product analysis."""
        if not products:
            return "No products to analyze."

        top_products = sorted(products, key=lambda x: x.get("ai_score", x.get("score", 0)), reverse=True)[:5]

        summary = "Top Opportunities:\n\n"
        for i, p in enumerate(top_products, 1):
            summary += "{}. {} - Score: {:.0%}\n".format(
                i, p.get("name", "Unknown"), p.get("ai_score", p.get("score", 0)))
            summary += "   Price: £{:.2f} | Margin: {:.0f}% | {}\n\n".format(
                p.get("amazon_price", p.get("price", 0)),
                p.get("estimated_margin_pct", 0),
                p.get("ai_recommendation", ""),
            )

        return summary

    def optimize_listing(self, product_data: dict) -> dict:
        """AI-powered listing optimization."""
        prompt = """You are an Amazon listing optimization expert. Given this product, generate an optimized listing.

Product: {name}
Category: {category}
Current Price: £{price}
Current Bullets: {bullets}
Current Description: {description}

Return JSON with:
- "optimized_title" (max 200 chars, keyword-rich)
- "optimized_bullets" (5 bullets, each max 500 chars, benefit-focused)
- "optimized_description" (max 2000 chars, persuasive)
- "backend_keywords" (max 250 chars, relevant search terms)
- "seo_score" (0-100 estimate)
- "improvements" (list of what was changed and why)""".format(
            name=product_data.get("name", "")[:200],
            category=product_data.get("category", ""),
            price=product_data.get("amazon_price", product_data.get("price", 0)),
            bullets=" | ".join(product_data.get("bullets", [""])),
            description=product_data.get("description", "")[:500],
        )
        result = self._call_ai(prompt, max_tokens=1500)
        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                pass
        return self._fallback_listing_optimize(product_data)

    def analyze_review_sentiment(self, product_name: str, category: str,
                                  review_highlights: Optional[list] = None) -> dict:
        """AI-powered review sentiment analysis."""
        reviews_text = ""
        if review_highlights:
            reviews_text = "\n".join(["- " + r for r in review_highlights[:20]])
        else:
            reviews_text = "(No individual reviews available — analyze based on product type and common patterns)"

        prompt = f"""You are an Amazon review analyst. Analyze customer sentiment for this product.

Product: {product_name}
Category: {category}
Reviews/Highlights: {reviews_text}

Return JSON with:
- "total_reviews" (number)
- "positive_pct" (0-100)
- "negative_pct" (0-100)
- "neutral_pct" (0-100)
- "top_complaints" (list of top 5 complaints customers have)
- "top_praises" (list of top 5 things customers love)
- "recurring_issues" (list of problems that come up repeatedly)
- "improvement_ideas" (list of 5 product improvements based on reviews)
- "summary" (2-3 sentence executive summary)"""
        result = self._call_ai(prompt, max_tokens=1200)
        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                pass
        return self._fallback_sentiment(product_name, category)

    def generate_supplier_quote(self, product_data: dict, supplier_data: dict) -> dict:
        """AI-generated supplier inquiry email."""
        prompt = """You are an experienced Amazon FBA sourcing agent. Generate a professional supplier inquiry email.

Product: {product}
Category: {category}
Target Price: £{target_price}
Supplier: {supplier}
Supplier Location: {location}
MOQ: {moq}

Generate:
- "subject" (email subject line)
- "body" (professional inquiry email, 200-400 words, asking about pricing, MOQ, samples, lead times, customization, certifications)
- "follow_up" (short follow-up message for 3 days later)
- "key_questions" (list of 5 important questions to ask the supplier)""".format(
            product=product_data.get("name", "")[:200],
            category=product_data.get("category", ""),
            target_price=product_data.get("amazon_price", 0) * 0.25,
            supplier=supplier_data.get("company", supplier_data.get("name", "")),
            location=supplier_data.get("location", supplier_data.get("country", "")),
            moq=supplier_data.get("moq", "Negotiable"),
        )
        result = self._call_ai(prompt, max_tokens=1000)
        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                pass
        return self._fallback_quote(product_data, supplier_data)

    def _call_ai(self, prompt: str, max_tokens: int = 500) -> Optional[str]:
        """Unified AI call — tries OpenAI then Claude."""
        import concurrent.futures

        if self.openai_key:
            def _openai_call():
                import openai
                client = openai.OpenAI(api_key=self.openai_key)
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an Amazon business expert. Respond only with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=max_tokens, temperature=0.3,
                )
                return resp.choices[0].message.content.strip()
            ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                result = ex.submit(_openai_call).result(timeout=30)
                self._record_ai_usage()
                return result
            except Exception as e:
                logger.debug("OpenAI call failed: %s", e)
            finally:
                ex.shutdown(wait=False)

        if self.claude_key:
            def _claude_call():
                import anthropic
                client = anthropic.Anthropic(api_key=self.claude_key)
                resp = client.messages.create(
                    model="claude-3-haiku-20240307", max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                return resp.content[0].text.strip()
            ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                result = ex.submit(_claude_call).result(timeout=30)
                self._record_ai_usage()
                return result
            except Exception as e:
                logger.debug("Claude call failed: %s", e)
            finally:
                ex.shutdown(wait=False)

        return None

    def _record_ai_usage(self):
        if self.license_mgr:
            self.license_mgr.record_usage("ai_calls")

    def _fallback_listing_optimize(self, p: dict) -> dict:
        name = p.get("name", p.get("title", "Product"))
        return {
            "optimized_title": f"{name} - Premium Quality | Fast Shipping | Great Value",
            "optimized_bullets": [
                "PREMIUM QUALITY: Made with high-grade materials for lasting durability",
                "VERSATILE DESIGN: Perfect for everyday use, home, office, or gifting",
                "EASY TO USE: Simple setup with no complicated instructions needed",
                "GREAT VALUE: Compare to similar products at twice the price",
                "SATISFACTION GUARANTEED: 30-day money-back guarantee for peace of mind",
            ],
            "optimized_description": f"Discover the {name} — designed for quality and built to last. Perfect for anyone looking for reliability and value.",
            "backend_keywords": f"{name.lower()}, best seller, top rated, new arrival, premium quality",
            "seo_score": 65,
            "improvements": ["Added benefit-focused language", "Improved keyword density", "Structured for mobile reading"],
        }

    def _fallback_sentiment(self, name: str, category: str) -> dict:
        return {
            "total_reviews": 0, "positive_pct": 70, "negative_pct": 15, "neutral_pct": 15,
            "top_complaints": ["Quality could be better", "Packaging issues", "Sizing discrepancies"],
            "top_praises": ["Good value for money", "Fast shipping", "As described"],
            "recurring_issues": ["Durability concerns", "Color variations"],
            "improvement_ideas": ["Improve material quality", "Better packaging", "More color options"],
            "summary": f"General sentiment for {category} products is mixed-positive.",
        }

    def _fallback_quote(self, p: dict, s: dict) -> dict:
        name = p.get("name", "Product")
        company = s.get("company", s.get("name", "Supplier"))
        return {
            "subject": f"Inquiry: {name} — Wholesale Pricing & MOQ",
            "body": f"Dear {company} team,\n\nWe are interested in sourcing {name} for Amazon FBA distribution.\n\nCould you please provide:\n1. Best FOB price for 500/1000/3000 units\n2. Sample availability and cost\n3. Lead time for bulk orders\n4. Customization options (logo, packaging)\n5. Relevant certifications (FDA, CE, etc.)\n\nLooking forward to your reply.\n\nBest regards",
            "follow_up": f"Hi {company}, just following up on our inquiry. Could you share the pricing details?",
            "key_questions": ["What is the MOQ?", "Do you offer samples?", "What certifications do you have?", "Can you do custom branding?", "What are your payment terms?"],
        }

    def analyze_seasonality(self, product_name: str, category: str,
                             price_history: Optional[list] = None) -> dict:
        """AI-powered seasonality analysis."""
        history_text = ""
        if price_history:
            history_text = "\n".join([f"- £{h.get('price', 0):.2f} on {h.get('recorded_at', '')[:10]}" for h in price_history[:20]])
        else:
            history_text = "(No price history available — estimate based on category patterns)"

        prompt = f"""You are an Amazon seasonality expert. Analyze seasonal demand patterns for this product.

Product: {product_name}
Category: {category}
Price History: {history_text}

Return JSON with:
- "monthly_demand" (dict month 1-12 -> demand level: "very_high", "high", "medium", "low", "very_low")
- "peak_months" (list of month numbers 1-12 when demand peaks)
- "low_months" (list of month numbers 1-12 when demand is lowest)
- "season_pattern" (one of: "steady", "summer_peak", "winter_peak", "holiday_peak", "back_to_school", "spring_peak", "volatile")
- "revenue_impact" (% change from average during peak vs low)
- "strategy" (2-3 sentence recommended inventory/pricing strategy)
- "events" (list of events that drive demand, e.g. "Christmas", "Prime Day", "Back to School")"""
        result = self._call_ai(prompt, max_tokens=1000)
        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                pass
        return self._fallback_seasonality(category)

    def analyze_competitors(self, product_name: str, category: str,
                             competitors: Optional[list] = None) -> dict:
        """AI-powered competitor analysis."""
        try:
            comp_text = ""
            if competitors:
                comp_text = "\n".join([f"- {c.get('name', '')}: £{c.get('price', 0):.2f}, {c.get('rating', 0)}★, {c.get('reviews', 0)} reviews" for c in competitors[:10]])
            else:
                comp_text = "(No competitor data — estimate based on category averages)"

            prompt = f"""You are an Amazon competitor analyst. Analyze the competitive landscape for this product.

Product: {product_name}
Category: {category}
Competitors: {comp_text}

Return JSON with:
- "competition_level" ("low", "medium", "high", "very_high")
- "market_saturation" (0-100 score)
- "top_competitor_weaknesses" (list of 5 weaknesses in competitor products)
- "differentiation_opportunities" (list of 5 ways to stand out)
- "pricing_strategy" ("premium", "competitive", "budget", "penetration")
- "recommended_price_range" ({{"min": X, "max": Y}})
- "barriers_to_entry" (list of barriers)
- "market_share_estimate" (estimated % of market captured by top 3)"""
            result = self._call_ai(prompt, max_tokens=1000)
            if result:
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("analyze_competitors failed: %s", e)
        return self._fallback_competitors(category)

    def _fallback_seasonality(self, category: str) -> dict:
        return {
            "monthly_demand": {str(i): "medium" for i in range(1, 13)},
            "peak_months": [11, 12],
            "low_months": [1, 2],
            "season_pattern": "holiday_peak",
            "revenue_impact": "+40% during peak, -20% during low",
            "strategy": "Build inventory 2 months before Q4 peak. Run promotions during slow months.",
            "events": ["Black Friday", "Cyber Monday", "Christmas"],
        }

    def _fallback_competitors(self, category: str) -> dict:
        return {
            "competition_level": "medium",
            "market_saturation": 50,
            "top_competitor_weaknesses": ["Poor packaging", "Weak descriptions", "Low images", "No A+ content", "Slow shipping"],
            "differentiation_opportunities": ["Better packaging", "Bundle offers", "Superior description", "A+ content", "Prime shipping"],
            "pricing_strategy": "competitive",
            "recommended_price_range": {"min": 15, "max": 35},
            "barriers_to_entry": ["Supplier relationships", "Brand recognition", "PPC costs"],
            "market_share_estimate": "Top 3 hold ~35% of market",
        }
