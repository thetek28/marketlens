"""SEO keyword analyzer for Amazon product listings."""

import re
from typing import Any, Dict, List, Optional

# Amazon search term limits
MAX_TITLE_LENGTH = 200
MAX_BULLET_LENGTH = 500
MAX_SEARCH_TERMS = 250
MAX_BACKEND_KEYWORDS = 5

# High-value modifier words for Amazon
CATEGORY_MODIFIERS = {
    "kitchen": ["premium", "professional", "stainless steel", "dishwasher safe", "BPA free", "eco-friendly"],
    "electronics": ["wireless", "bluetooth", "smart", "rechargeable", "portable", "waterproof"],
    "home": ["modern", "elegant", "durable", "lightweight", "foldable", "adjustable"],
    "beauty": ["organic", "natural", "cruelty-free", "paraben-free", "dermatologist tested", "hypoallergenic"],
    "fitness": ["anti-slip", "ergonomic", "heavy duty", "gym grade", "portable", "comfortable"],
    "toys": ["educational", "safe", "non-toxic", "age appropriate", "interactive", "STEM"],
    "pets": ["vet approved", "organic", "grain free", "all natural", "dental health", "premium"],
    "office": ["ergonomic", "space saving", "professional", "heavy duty", "adjustable", "modern"],
}

# Seasonal keywords
SEASONAL_KEYWORDS = {
    "spring": ["spring", "outdoor", "garden", "patio", "fresh", "bloom"],
    "summer": ["summer", "beach", "pool", "cooling", "outdoor", "travel"],
    "fall": ["fall", "autumn", "harvest", "cozy", "warm", "Thanksgiving"],
    "winter": ["winter", "holiday", "Christmas", "gift", "warm", "indoor"],
    "valentines": ["Valentine", "love", "gift", "romantic", "couples"],
    "mothers_day": ["Mother's Day", "mom", "gift", "spa", "relaxation"],
    "fathers_day": ["Father's Day", "dad", "gift", "tools", "gadget"],
    "back_to_school": ["school", "college", "dorm", "study", "office"],
}

# Word count helper
def count_words(text: str) -> int:
    return len(text.split())


class SEOAnalyzer:
    """Analyzes and optimizes product listings for Amazon SEO."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = {}
        self.target_audience = config.get("target_audience", "general")
        self.season = config.get("season", "")

    def analyze(self, idea: Dict[str, Any]) -> Dict[str, Any]:
        """Generate full SEO analysis and suggestions for a product."""
        name = idea.get("name", "")
        category = idea.get("category", "")
        keywords = self._extract_keywords(name, category)
        long_tail = self._generate_long_tail(name, category)
        backend = self._generate_backend_keywords(name, category, keywords)
        title_suggestions = self._optimize_title(name, category, keywords)
        bullet_points = self._generate_bullet_keywords(name, category)
        search_terms = self._generate_search_terms(name, category, keywords)

        seo_score = self._calculate_seo_score(
            title_suggestions, bullet_points, backend, search_terms
        )

        return {
            "primary_keywords": keywords[:10],
            "long_tail_keywords": long_tail,
            "backend_keywords": backend,
            "title_suggestions": title_suggestions,
            "bullet_keywords": bullet_points,
            "search_terms": search_terms,
            "seo_score": seo_score,
            "optimization_tips": self._get_optimization_tips(seo_score),
            "seasonal_keywords": self._get_seasonal_keywords(),
        }

    def _extract_keywords(self, name: str, category: str) -> List[str]:
        """Extract primary keywords from product name."""
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "it", "that", "this", "was", "are",
            "be", "has", "had", "have", "not", "all", "can", "her", "his",
            "they", "you", "we", "our", "its", "my", "me", "him", "she", "he",
        }

        words = re.findall(r'\b[a-zA-Z]{3,}\b', name.lower())
        keywords = [w for w in words if w not in stop_words]

        category_words = category.lower().split()
        keywords.extend([w for w in category_words if w not in stop_words])

        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        return unique_keywords

    def _generate_long_tail(self, name: str, category: str) -> List[str]:
        """Generate long-tail keyword suggestions."""
        base_words = name.lower().split()
        long_tail = []

        templates = [
            "{name} for {use}",
            "best {name} {year}",
            "{name} {category}",
            "{name} with {feature}",
            "premium {name}",
            "professional {name}",
            "{name} review",
            "{name} comparison",
            "top rated {name}",
            "{name} sale",
        ]

        uses = ["home", "kitchen", "office", "travel", "gym", "outdoor"]
        features = ["free shipping", "warranty", "guarantee", "fast delivery"]
        year = "2024"

        for template in templates:
            try:
                suggestion = template.format(
                    name=" ".join(base_words[:3]),
                    category=category,
                    use=uses[0],
                    feature=features[0],
                    year=year,
                )
                long_tail.append(suggestion)
            except (IndexError, KeyError):
                continue

        return long_tail[:15]

    def _generate_backend_keywords(self, name: str, category: str, primary: List[str]) -> List[str]:
        """Generate backend search term suggestions."""
        backend = []

        category_lower = category.lower()
        for cat, modifiers in CATEGORY_MODIFIERS.items():
            if cat in category_lower or any(w in category_lower for w in cat.split()):
                backend.extend(modifiers[:3])
                break

        name_words = name.lower().split()
        if len(name_words) > 1:
            for i in range(len(name_words)):
                for j in range(i + 2, min(i + 4, len(name_words) + 1)):
                    phrase = " ".join(name_words[i:j])
                    if phrase not in backend and len(phrase) > 3:
                        backend.append(phrase)

        synonyms = self._get_synonyms(name_words[0] if name_words else "")
        backend.extend(synonyms)

        seen = set()
        unique_backend = []
        for kw in backend:
            kw_lower = kw.lower()
            if kw_lower not in seen and len(kw_lower) > 2:
                seen.add(kw_lower)
                unique_backend.append(kw_lower)

        return unique_backend[:MAX_BACKEND_KEYWORDS * 10]

    def _get_synonyms(self, word: str) -> List[str]:
        """Get common synonyms for a word."""
        synonym_map = {
            "bag": ["purse", "tote", "satchel", "carrier", "case"],
            "holder": ["stand", "rack", "mount", "organizer", "dispenser"],
            "cover": ["protector", "case", "sleeve", "shield", "guard"],
            "set": ["kit", "bundle", "pack", "collection", "combo"],
            "tool": ["instrument", "device", "gadget", "implement", "utensil"],
            "mat": ["pad", "rug", "carpet", "runner", "cushion"],
            "lamp": ["light", "lighting", "lantern", "bulb", "fixture"],
            "scale": ["meter", "gauge", "balance", "measurer"],
            "bottle": ["flask", "container", "vessel", "canteen", "jug"],
            "cup": ["mug", "glass", "tumbler", "chalice", "stein"],
        }
        return synonym_map.get(word.lower(), [])

    def _optimize_title(self, name: str, category: str, keywords: List[str]) -> List[str]:
        """Generate optimized title suggestions."""
        suggestions = []

        base = " ".join(keywords[:4]).title()
        modifiers = CATEGORY_MODIFIERS.get(category.lower().split()[0] if category else "", ["Premium"])

        suggestion1 = f"{base} - {modifiers[0].title()}"
        if len(suggestion1) <= MAX_TITLE_LENGTH:
            suggestions.append(suggestion1)

        suggestion2 = f"{name} | {modifiers[0].title()} | {category.title()}"
        if len(suggestion2) <= MAX_TITLE_LENGTH:
            suggestions.append(suggestion2)

        suggestion3 = f"{' '.join(keywords[:5]).title()} for {category.title()}"
        if len(suggestion3) <= MAX_TITLE_LENGTH:
            suggestions.append(suggestion3)

        suggestion4 = f"{name} - Professional Grade {category.title()}"
        if len(suggestion4) <= MAX_TITLE_LENGTH:
            suggestions.append(suggestion4)

        return suggestions

    def _generate_bullet_keywords(self, name: str, category: str) -> List[Dict[str, Any]]:
        """Generate bullet point keyword suggestions."""
        bullets = []

        bullet_templates = [
            {
                "title": "PREMIUM QUALITY",
                "keywords": ["high quality", "durable", "long-lasting", "premium materials", "built to last"],
            },
            {
                "title": "EASY TO USE",
                "keywords": ["user-friendly", "simple setup", "easy to clean", "hassle-free", "convenient"],
            },
            {
                "title": "VERSATILE",
                "keywords": ["multi-purpose", "ideal for", "perfect for", "great for", "works with"],
            },
            {
                "title": "SATISFACTION GUARANTEED",
                "keywords": ["money back guarantee", "warranty", "customer support", "satisfaction guaranteed", "risk-free"],
            },
            {
                "title": "GREAT VALUE",
                "keywords": ["affordable", "best value", "cost-effective", "budget-friendly", "excellent value"],
            },
        ]

        for template in bullet_templates:
            bullet = {
                "heading": template["title"],
                "suggested_keywords": template["keywords"],
                "amazon_format": f"• {template['title']}: [Your description with keywords here]",
            }
            bullets.append(bullet)

        return bullets

    def _generate_search_terms(self, name: str, category: str, keywords: List[str]) -> str:
        """Generate Amazon search terms (max 250 bytes)."""
        terms = []

        terms.extend(keywords[:5])

        category_words = category.split()
        terms.extend([w.lower() for w in category_words])

        synonyms = []
        for kw in keywords[:3]:
            synonyms.extend(self._get_synonyms(kw)[:2])
        terms.extend(synonyms[:5])

        seen = set()
        unique_terms = []
        for term in terms:
            term_lower = term.lower()
            if term_lower not in seen and len(term_lower) > 2:
                seen.add(term_lower)
                unique_terms.append(term_lower)

        search_string = " ".join(unique_terms)

        while len(search_string.encode('utf-8')) > MAX_SEARCH_TERMS and unique_terms:
            unique_terms.pop()
            search_string = " ".join(unique_terms)

        return search_string

    def _calculate_seo_score(
        self,
        titles: List[str],
        bullets: List[Dict],
        backend: List[str],
        search_terms: str,
    ) -> Dict[str, Any]:
        """Calculate SEO score for the listing."""
        score = 0
        max_score = 100

        if titles:
            score += 20
            avg_title_len = sum(len(t) for t in titles) / len(titles)
            if 50 <= avg_title_len <= 150:
                score += 10

        if bullets:
            score += min(len(bullets) * 4, 20)

        if backend:
            score += min(len(backend) * 2, 20)

        if search_terms:
            term_len = len(search_terms.encode('utf-8'))
            if 100 <= term_len <= 250:
                score += 20
            elif term_len > 0:
                score += 10

        return {
            "score": min(score, max_score),
            "max_score": max_score,
            "percentage": round(min(score, max_score) / max_score * 100, 1),
        }

    def _get_optimization_tips(self, seo_score: Dict) -> List[str]:
        """Get optimization tips based on SEO score."""
        tips = []
        score = seo_score.get("score", 0)

        if score < 50:
            tips.append("Add more keywords to your title and bullet points")
            tips.append("Include backend search terms for better discoverability")

        if score < 70:
            tips.append("Use long-tail keywords to target specific searches")
            tips.append("Add product-specific modifiers (color, size, material)")

        tips.append("Include your brand name in the title")
        tips.append("Use all 5 bullet points with relevant keywords")
        tips.append("Add backend search terms (250 bytes max)")
        tips.append("Include seasonal keywords when applicable")
        tips.append("Use natural language that customers would search for")

        return tips

    def _get_seasonal_keywords(self) -> List[str]:
        """Get seasonal keyword suggestions."""
        seasonal = []
        for _season, keywords in SEASONAL_KEYWORDS.items():
            seasonal.extend(keywords[:3])
        return list(set(seasonal))

    def optimize_listing(self, idea: Dict[str, Any]) -> Dict[str, Any]:
        """Generate complete optimized listing content."""
        seo = self.analyze(idea)

        optimized_title = seo["title_suggestions"][0] if seo["title_suggestions"] else idea.get("name", "")

        bullets = []
        for bullet in seo["bullet_keywords"]:
            bullets.append(f"• {bullet['heading']}: [Add your description with {', '.join(bullet['suggested_keywords'][:3])}]")

        while len(bullets) < 5:
            bullets.append("• [Add more features and benefits]")

        return {
            "seo_analysis": seo,
            "optimized_title": optimized_title,
            "optimized_bullets": bullets[:5],
            "backend_search_terms": " ".join(seo["backend_keywords"][:10]),
            "search_terms": seo["search_terms"],
        }
