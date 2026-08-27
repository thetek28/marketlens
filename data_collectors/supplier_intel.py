"""MarketLens Supplier Intelligence - Contact info, pricing, and matching."""

import random
from typing import Any, Dict, List, Optional


class SupplierDatabase:
    """Pre-built database of realistic suppliers with contacts and pricing."""

    SUPPLIERS = [
        {
            "name": "Shenzhen TechParts Co.",
            "company_name": "Shenzhen TechParts Technology Co., Ltd.",
            "location": "Shenzhen, Guangdong",
            "country": "China",
            "website": "https://www.techparts.cn",
            "contact_person": "Li Wei",
            "contact_email": "sales@techparts.cn",
            "contact_phone": "+86 755 8888 9999",
            "contact_whatsapp": "+86 138 0000 1234",
            "contact_wechat": "techparts_sales",
            "business_type": "Manufacturer",
            "year_established": 2012,
            "employee_count": "200-500",
            "rating": 4.7,
            "certifications": "ISO 9001, CE, FCC, RoHS",
            "payment_terms": "T/T 30% deposit, 70% before shipping",
            "shipping_methods": "DHL, FedEx, Sea Freight",
            "specialties": "electronics, gadgets, smart home",
        },
        {
            "name": "Yiwu HomeGoods Ltd.",
            "company_name": "Yiwu HomeGoods Trading Co., Ltd.",
            "location": "Yiwu, Zhejiang",
            "country": "China",
            "website": "https://www.yiwuhomegoods.com",
            "contact_person": "Zhang Mei",
            "contact_email": "info@yiwuhomegoods.com",
            "contact_phone": "+86 579 8555 6666",
            "contact_whatsapp": "+86 139 8888 5678",
            "contact_wechat": "yiwu_home",
            "business_type": "Trading Company",
            "year_established": 2008,
            "employee_count": "50-100",
            "rating": 4.5,
            "certifications": "ISO 9001, BSCI",
            "payment_terms": "T/T, PayPal, Trade Assurance",
            "shipping_methods": "Sea Freight, Air Freight, DHL",
            "specialties": "kitchen, home, garden, organization",
        },
        {
            "name": "Dongguan PackPro",
            "company_name": "Dongguan PackPro Packaging Co., Ltd.",
            "location": "Dongguan, Guangdong",
            "country": "China",
            "website": "https://www.packpro.cn",
            "contact_person": "Chen Jun",
            "contact_email": "sales@packpro.cn",
            "contact_phone": "+86 769 2222 3333",
            "contact_whatsapp": "+86 137 6666 7890",
            "business_type": "Manufacturer",
            "year_established": 2015,
            "employee_count": "100-200",
            "rating": 4.6,
            "certifications": "ISO 9001, FSC, BRC",
            "payment_terms": "T/T 50% deposit",
            "shipping_methods": "Sea Freight, Express",
            "specialties": "packaging, boxes, displays",
        },
        {
            "name": "Ningbo FitnessPro",
            "company_name": "Ningbo FitnessPro Sports Co., Ltd.",
            "location": "Ningbo, Zhejiang",
            "country": "China",
            "website": "https://www.fitnesspro.cn",
            "contact_person": "Wang Fang",
            "contact_email": "export@fitnesspro.cn",
            "contact_phone": "+86 574 8888 7777",
            "contact_whatsapp": "+86 136 5555 4321",
            "contact_wechat": "fitnesspro_export",
            "business_type": "Manufacturer",
            "year_established": 2010,
            "employee_count": "300-500",
            "rating": 4.8,
            "certifications": "ISO 9001, CE, SGS",
            "payment_terms": "T/T 30/70, L/C",
            "shipping_methods": "Sea Freight, Air, FBA Direct",
            "specialties": "fitness, sports, yoga, gym equipment",
        },
        {
            "name": "Guangzhou BeautySupply",
            "company_name": "Guangzhou BeautySupply Co., Ltd.",
            "location": "Guangzhou, Guangdong",
            "country": "China",
            "website": "https://www.gzbeautysupply.com",
            "contact_person": "Huang Li",
            "contact_email": "orders@gzbeautysupply.com",
            "contact_phone": "+86 20 3333 4444",
            "contact_whatsapp": "+86 135 7777 8888",
            "contact_wechat": "beautysupply_gz",
            "business_type": "Manufacturer",
            "year_established": 2014,
            "employee_count": "100-200",
            "rating": 4.4,
            "certifications": "ISO 22716, GMP, FDA registered",
            "payment_terms": "T/T, PayPal, Alibaba Trade Assurance",
            "shipping_methods": "DHL, FedEx, Sea Freight",
            "specialties": "beauty, skincare, cosmetics, personal care",
        },
        {
            "name": "Shantou ToyWorld",
            "company_name": "Shantou ToyWorld Manufacturing Co., Ltd.",
            "location": "Shantou, Guangdong",
            "country": "China",
            "website": "https://www.toyworld.cn",
            "contact_person": "Xu Ming",
            "contact_email": "sales@toyworld.cn",
            "contact_phone": "+86 754 8888 5555",
            "contact_whatsapp": "+86 133 4444 5555",
            "business_type": "Manufacturer",
            "year_established": 2005,
            "employee_count": "500-1000",
            "rating": 4.6,
            "certifications": "ISO 9001, CE, EN71, ASTM",
            "payment_terms": "T/T 30/70",
            "shipping_methods": "Sea Freight, FBA Direct",
            "specialties": "toys, games, kids products",
        },
        {
            "name": "Xiamen PetSupply",
            "company_name": "Xiamen PetSupply Trading Co., Ltd.",
            "location": "Xiamen, Fujian",
            "country": "China",
            "website": "https://www.xmpetsupply.com",
            "contact_person": "Lin Hua",
            "contact_email": "info@xmpetsupply.com",
            "contact_phone": "+86 592 6666 7777",
            "contact_whatsapp": "+86 138 9999 0000",
            "business_type": "Trading Company",
            "year_established": 2016,
            "employee_count": "50-100",
            "rating": 4.3,
            "certifications": "ISO 9001, BSCI",
            "payment_terms": "T/T, PayPal",
            "shipping_methods": "DHL, Sea Freight",
            "specialties": "pet supplies, accessories, toys",
        },
        {
            "name": "Nanjing OfficePlus",
            "company_name": "Nanjing OfficePlus Supplies Co., Ltd.",
            "location": "Nanjing, Jiangsu",
            "country": "China",
            "website": "https://www.officeplus.cn",
            "contact_person": "Sun Lei",
            "contact_email": "sales@officeplus.cn",
            "contact_phone": "+86 25 8888 3333",
            "contact_whatsapp": "+86 139 3333 4444",
            "business_type": "Manufacturer",
            "year_established": 2011,
            "employee_count": "200-300",
            "rating": 4.5,
            "certifications": "ISO 9001, ISO 14001",
            "payment_terms": "T/T 30/70",
            "shipping_methods": "Sea Freight, Express",
            "specialties": "office supplies, organizers, stationery",
        },
        {
            "name": "Changzhou AutoGear",
            "company_name": "Changzhou AutoGear Accessories Co., Ltd.",
            "location": "Changzhou, Jiangsu",
            "country": "China",
            "website": "https://www.autogear.cn",
            "contact_person": "Zhou Yang",
            "contact_email": "export@autogear.cn",
            "contact_phone": "+86 519 7777 8888",
            "contact_whatsapp": "+86 137 2222 3333",
            "business_type": "Manufacturer",
            "year_established": 2013,
            "employee_count": "100-200",
            "rating": 4.4,
            "certifications": "ISO 9001, TS16949, CE",
            "payment_terms": "T/T, L/C",
            "shipping_methods": "Sea Freight, Air Freight",
            "specialties": "automotive accessories, car parts",
        },
        {
            "name": "Putian HealthPlus",
            "company_name": "Putian HealthPlus Medical Co., Ltd.",
            "location": "Putian, Fujian",
            "country": "China",
            "website": "https://www.healthplus.cn",
            "contact_person": "Chen Wei",
            "contact_email": "sales@healthplus.cn",
            "contact_phone": "+86 594 5555 6666",
            "contact_whatsapp": "+86 136 8888 9999",
            "business_type": "Manufacturer",
            "year_established": 2009,
            "employee_count": "300-500",
            "rating": 4.7,
            "certifications": "ISO 13485, CE, FDA, GMP",
            "payment_terms": "T/T 30/70, L/C",
            "shipping_methods": "DHL, Sea Freight, FBA",
            "specialties": "health, wellness, medical devices, supplements",
        },
        {
            "name": "Taizhou GardenPro",
            "company_name": "Taizhou GardenPro Tools Co., Ltd.",
            "location": "Taizhou, Zhejiang",
            "country": "China",
            "website": "https://www.gardenpro.cn",
            "contact_person": "Zheng Bo",
            "contact_email": "info@gardenpro.cn",
            "contact_phone": "+86 576 4444 5555",
            "contact_whatsapp": "+86 135 6666 7777",
            "business_type": "Manufacturer",
            "year_established": 2007,
            "employee_count": "200-400",
            "rating": 4.5,
            "certifications": "ISO 9001, CE, GS",
            "payment_terms": "T/T 30/70",
            "shipping_methods": "Sea Freight, FBA Direct",
            "specialties": "garden tools, outdoor, lawn care",
        },
        {
            "name": "Wenzhou BabyCare",
            "company_name": "Wenzhou BabyCare Products Co., Ltd.",
            "location": "Wenzhou, Zhejiang",
            "country": "China",
            "website": "https://www.babycare.cn",
            "contact_person": "Xie Yan",
            "contact_email": "sales@babycare.cn",
            "contact_phone": "+86 577 8888 2222",
            "contact_whatsapp": "+86 139 1111 2222",
            "business_type": "Manufacturer",
            "year_established": 2013,
            "employee_count": "100-200",
            "rating": 4.6,
            "certifications": "ISO 9001, EN 14350, BPA free",
            "payment_terms": "T/T, PayPal",
            "shipping_methods": "DHL, Sea Freight",
            "specialties": "baby products, feeding, safety",
        },
    ]

    CATEGORY_SUPPLIER_MAP = {
        "kitchen": [1, 2],
        "electronics": [0, 1],
        "beauty": [4],
        "home": [1, 2],
        "fitness": [3],
        "garden": [10],
        "pet": [6],
        "office": [7],
        "toys": [5],
        "automotive": [8],
        "health": [9],
        "baby": [11],
        "sports": [3],
        "tools": [10],
    }

    @classmethod
    def get_suppliers_for_category(cls, category: str, all_suppliers: Optional[List[Dict]] = None) -> List[Dict]:
        """Get suppliers for a category. Uses DB suppliers if provided, else pre-built."""
        if all_suppliers:
            cat_lower = category.lower()
            matches = []
            for s in all_suppliers:
                specialties = s.get("specialties", "").lower()
                name = s.get("name", "").lower()
                company = s.get("company_name", "").lower()
                business = s.get("business_type", "").lower()
                if (cat_lower in specialties or cat_lower in name
                        or cat_lower in company or cat_lower in business):
                    matches.append(s)
            if matches:
                return matches
            return all_suppliers[:3]
        indices = cls.CATEGORY_SUPPLIER_MAP.get(category.lower(), [1, 2])
        return [cls.SUPPLIERS[i].copy() for i in indices if i < len(cls.SUPPLIERS)]

    @classmethod
    def get_all_suppliers(cls) -> List[Dict]:
        return [s.copy() for s in cls.SUPPLIERS]


class SupplierPricing:
    """Generate realistic supplier pricing for products."""

    COST_RATIOS = {
        "kitchen": (0.12, 0.25),
        "electronics": (0.15, 0.30),
        "beauty": (0.08, 0.18),
        "home": (0.10, 0.22),
        "fitness": (0.12, 0.25),
        "garden": (0.10, 0.20),
        "pet": (0.10, 0.20),
        "office": (0.08, 0.18),
        "toys": (0.08, 0.15),
        "automotive": (0.12, 0.25),
        "health": (0.10, 0.22),
        "baby": (0.10, 0.20),
        "sports": (0.12, 0.25),
        "tools": (0.12, 0.25),
    }

    @classmethod
    def generate_pricing(cls, product: Dict, supplier: Dict) -> Dict[str, Any]:
        category = product.get("category", "kitchen").lower()
        amazon_price = product.get("amazon_price", product.get("price", 30))
        low, high = cls.COST_RATIOS.get(category, (0.12, 0.25))

        supplier_cost = round(amazon_price * random.uniform(low, high), 2)
        moq = supplier.get("moq", random.choice([50, 100, 200, 500]))

        bulk_prices = {}
        for qty, discount in [(100, 0), (500, 0.05), (1000, 0.10), (5000, 0.15)]:
            bulk_prices[str(qty)] = round(supplier_cost * (1 - discount), 2)

        shipping_per_unit = round(random.uniform(0.50, 3.00), 2)
        customs_duty = round(supplier_cost * random.uniform(0.02, 0.08), 2)
        packaging_cost = round(random.uniform(0.30, 1.50), 2)
        total_landed = round(supplier_cost + shipping_per_unit + customs_duty + packaging_cost, 2)

        fba_fee = round(amazon_price * 0.15 + 3.22, 2)
        profit_per_unit = round(amazon_price - total_landed - fba_fee, 2)
        margin_pct = round((profit_per_unit / amazon_price) * 100, 1) if amazon_price > 0 else 0

        lead_times = [3, 5, 7, 10, 14, 21, 30]
        lead_time = random.choice(lead_times)

        return {
            "supplier_id": supplier.get("id", 0),
            "supplier_name": supplier.get("name", "Unknown"),
            "unit_cost": supplier_cost,
            "bulk_prices": bulk_prices,
            "moq": moq,
            "lead_time_days": lead_time,
            "shipping_cost_per_unit": shipping_per_unit,
            "customs_duty": customs_duty,
            "packaging_cost": packaging_cost,
            "total_landed_cost": total_landed,
            "amazon_price": amazon_price,
            "fba_fee": fba_fee,
            "profit_per_unit": profit_per_unit,
            "margin_percent": margin_pct,
            "payment_terms": supplier.get("payment_terms", "T/T 30/70"),
            "shipping_methods": supplier.get("shipping_methods", "Sea Freight"),
            "price_breakdown": {
                "supplier_cost": supplier_cost,
                "shipping": shipping_per_unit,
                "customs": customs_duty,
                "packaging": packaging_cost,
                "fba_fee": fba_fee,
                "total_cost": round(total_landed + fba_fee, 2),
                "profit": profit_per_unit,
            },
        }


class SupplierMatcher:
    """Match products to best suppliers."""

    def match_product(self, product: Dict, suppliers: Optional[List[Dict]] = None) -> Dict[str, Any]:
        category = product.get("category", "kitchen").lower()

        if suppliers:
            category_suppliers = SupplierDatabase.get_suppliers_for_category(category, suppliers)
        else:
            category_suppliers = SupplierDatabase.get_suppliers_for_category(category)

        if not category_suppliers:
            category_suppliers = suppliers[:3] if suppliers else []

        matches = []
        for supplier in category_suppliers:
            pricing = SupplierPricing.generate_pricing(product, supplier)
            match_score = self._score_match(product, supplier, pricing)
            matches.append({
                "supplier": supplier,
                "pricing": pricing,
                "match_score": match_score,
            })

        matches.sort(key=lambda x: float(str(x["match_score"])), reverse=True)

        return {
            "product_name": product.get("name", product.get("title", "Unknown")),
            "product_asin": product.get("asin", ""),
            "category": category,
            "amazon_price": product.get("amazon_price", product.get("price", 0)),
            "matches": matches,
            "best_match": matches[0] if matches else None,
            "recommendation": self._generate_recommendation(matches),
        }

    def _score_match(self, product: Dict, supplier: Dict, pricing: Dict) -> float:
        score = 0.0
        margin = pricing.get("margin_percent", 0)
        if margin >= 40:
            score += 30
        elif margin >= 30:
            score += 20
        elif margin >= 20:
            score += 10

        rating = supplier.get("rating", 0)
        score += min(rating / 5.0 * 15, 15)

        moq = pricing.get("moq", 500)
        if moq <= 100:
            score += 15
        elif moq <= 500:
            score += 10
        else:
            score += 5

        lead = pricing.get("lead_time_days", 14)
        if lead <= 7:
            score += 10
        elif lead <= 14:
            score += 7
        else:
            score += 3

        if supplier.get("certifications"):
            score += 5

        return round(min(score, 100), 1)

    def _generate_recommendation(self, matches: List[Dict]) -> str:
        if not matches:
            return "No matching suppliers found."

        best = matches[0]
        pricing = best["pricing"]
        supplier = best["supplier"]

        lines = []
        lines.append("RECOMMENDED: {}".format(supplier["name"]))
        lines.append("Supplier Cost: £{:.2f}".format(pricing["unit_cost"]))
        lines.append("MOQ: {} units".format(pricing["moq"]))
        lines.append("Lead Time: {} days".format(pricing["lead_time_days"]))
        lines.append("Estimated Margin: {:.0f}%".format(pricing["margin_percent"]))
        lines.append("Profit per Unit: £{:.2f}".format(pricing["profit_per_unit"]))
        lines.append("Contact: {}".format(supplier.get("contact_email", "")))
        return "\n".join(lines)
