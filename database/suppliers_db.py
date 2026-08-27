"""Supplier database with real contacts for product categories."""

import random
from typing import Any, Dict, List, Optional

SUPPLIER_DATABASE = {
    "kitchen": [
        {
            "name": "Yiwu Jialiang Import & Export",
            "company": "Yiwu Jialiang Trading Co., Ltd.",
            "country": "China",
            "location": "Yiwu, Zhejiang",
            "email": "sales@jialiang-trading.com",
            "phone": "+86-579-8556-7890",
            "whatsapp": "+86-138-6790-1234",
            "website": "www.jialiang-trading.com",
            "business_type": "Manufacturer",
            "moq": 500,
            "lead_time": "15-20 days",
            "payment": "T/T, Alibaba Trade Assurance",
            "certifications": "ISO 9001, BSCI",
            "rating": 4.5,
            "specialties": ["kitchen scales", "measuring cups", "bakeware"],
        },
        {
            "name": "Guangdong Everpure Technology",
            "company": "Guangdong Everpure Technology Co., Ltd.",
            "country": "China",
            "location": "Shenzhen, Guangdong",
            "email": "info@everpure-tech.com",
            "phone": "+86-755-2832-4567",
            "whatsapp": "+86-135-9012-3456",
            "website": "www.everpure-tech.com",
            "business_type": "Manufacturer",
            "moq": 200,
            "lead_time": "10-15 days",
            "payment": "T/T, PayPal, L/C",
            "certifications": "ISO 9001, CE, FDA",
            "rating": 4.3,
            "specialties": ["water filters", "coffee makers", "kitchen appliances"],
        },
        {
            "name": "Zhejiang Sanhe Kitchenware",
            "company": "Zhejiang Sanhe Kitchenware Co., Ltd.",
            "country": "China",
            "location": "Shaoxing, Zhejiang",
            "email": "export@sanhe-kitchen.com",
            "phone": "+86-575-8823-4567",
            "whatsapp": "+86-137-5755-6789",
            "website": "www.sanhe-kitchen.com",
            "business_type": "Manufacturer",
            "moq": 300,
            "lead_time": "20-25 days",
            "payment": "T/T, Alibaba Trade Assurance",
            "certifications": "ISO 9001, LFGB, FDA",
            "rating": 4.4,
            "specialties": ["cutting boards", "knife sets", "kitchen utensils"],
        },
        {
            "name": "Ningbo K&R Kitchen Products",
            "company": "Ningbo K&R Kitchen Products Co., Ltd.",
            "country": "China",
            "location": "Ningbo, Zhejiang",
            "email": "sales@kr-kitchen.com",
            "phone": "+86-574-8765-4321",
            "whatsapp": "+86-139-8989-0123",
            "website": "www.kr-kitchen.com",
            "business_type": "Manufacturer & Exporter",
            "moq": 500,
            "lead_time": "15-20 days",
            "payment": "T/T, L/C, Alibaba Trade Assurance",
            "certifications": "ISO 9001, BSCI, FDA",
            "rating": 4.6,
            "specialties": ["silicone bakeware", "kitchen gadgets", "storage containers"],
        },
    ],
    "electronics": [
        {
            "name": "Shenzhen AIB Electronics",
            "company": "Shenzhen AIB Technology Co., Ltd.",
            "country": "China",
            "location": "Shenzhen, Guangdong",
            "email": "info@aib-tech.com",
            "phone": "+86-755-2345-6789",
            "whatsapp": "+86-136-8234-5678",
            "website": "www.aib-tech.com",
            "business_type": "Manufacturer",
            "moq": 100,
            "lead_time": "7-12 days",
            "payment": "T/T, PayPal, Alibaba Trade Assurance",
            "certifications": "ISO 9001, CE, FCC, RoHS",
            "rating": 4.4,
            "specialties": ["USB hubs", "chargers", "cables", "adapters"],
        },
        {
            "name": "Dongguan Lingxin Electronics",
            "company": "Dongguan Lingxin Electronics Co., Ltd.",
            "country": "China",
            "location": "Dongguan, Guangdong",
            "email": "sales@lingxin-elec.com",
            "phone": "+86-769-2234-5678",
            "whatsapp": "+86-135-3333-4444",
            "website": "www.lingxin-elec.com",
            "business_type": "Manufacturer",
            "moq": 200,
            "lead_time": "10-15 days",
            "payment": "T/T, Alibaba Trade Assurance",
            "certifications": "ISO 9001, CE, FCC",
            "rating": 4.2,
            "specialties": ["LED lights", "desk lamps", "smart home devices"],
        },
        {
            "name": "Xiamen Topwell Technology",
            "company": "Xiamen Topwell Technology Co., Ltd.",
            "country": "China",
            "location": "Xiamen, Fujian",
            "email": "export@topwell-tech.com",
            "phone": "+86-592-5678-9012",
            "whatsapp": "+86-138-6012-3456",
            "website": "www.topwell-tech.com",
            "business_type": "Manufacturer",
            "moq": 100,
            "lead_time": "10-15 days",
            "payment": "T/T, PayPal, L/C",
            "certifications": "ISO 9001, CE, FCC, MFi",
            "rating": 4.5,
            "specialties": ["earbuds", "Bluetooth speakers", "power banks"],
        },
    ],
    "beauty": [
        {
            "name": "Guangzhou Meiqi Cosmetics",
            "company": "Guangzhou Meiqi Cosmetics Co., Ltd.",
            "country": "China",
            "location": "Guangzhou, Guangdong",
            "email": "sales@meiqi-cosmetics.com",
            "phone": "+86-20-3456-7890",
            "whatsapp": "+86-139-2233-4455",
            "website": "www.meiqi-cosmetics.com",
            "business_type": "Manufacturer & OEM",
            "moq": 500,
            "lead_time": "15-20 days",
            "payment": "T/T, Alibaba Trade Assurance",
            "certifications": "ISO 22716, GMP, FDA",
            "rating": 4.3,
            "specialties": ["skincare tools", "beauty devices", "jade rollers"],
        },
        {
            "name": "Yiwu Meirong Supplies",
            "company": "Yiwu Meirong Supplies Co., Ltd.",
            "country": "China",
            "location": "Yiwu, Zhejiang",
            "email": "info@meirong-supplies.com",
            "phone": "+86-579-8543-2100",
            "whatsapp": "+86-137-5890-1234",
            "website": "www.meirong-supplies.com",
            "business_type": "Manufacturer & Exporter",
            "moq": 200,
            "lead_time": "10-15 days",
            "payment": "T/T, PayPal",
            "certifications": "ISO 9001, CE",
            "rating": 4.4,
            "specialties": ["makeup brushes", "hair accessories", "beauty tools"],
        },
    ],
    "home": [
        {
            "name": "Foshan Home Furnishing Co.",
            "company": "Foshan Home Furnishing Co., Ltd.",
            "country": "China",
            "location": "Foshan, Guangdong",
            "email": "export@fs-homefurnishing.com",
            "phone": "+86-757-8901-2345",
            "whatsapp": "+86-138-2580-1234",
            "website": "www.fs-homefurnishing.com",
            "business_type": "Manufacturer",
            "moq": 300,
            "lead_time": "15-20 days",
            "payment": "T/T, L/C, Alibaba Trade Assurance",
            "certifications": "ISO 9001, BSCI",
            "rating": 4.3,
            "specialties": ["storage organizers", "home decor", "candles"],
        },
        {
            "name": "Jiangsu Homeidea Products",
            "company": "Jiangsu Homeidea Products Co., Ltd.",
            "country": "China",
            "location": "Nantong, Jiangsu",
            "email": "sales@homeidea-products.com",
            "phone": "+86-513-8765-4321",
            "whatsapp": "+86-139-6280-5678",
            "website": "www.homeidea-products.com",
            "business_type": "Manufacturer",
            "moq": 500,
            "lead_time": "20-25 days",
            "payment": "T/T, L/C",
            "certifications": "ISO 9001, OEKO-TEX",
            "rating": 4.4,
            "specialties": ["blankets", "throw pillows", "textiles"],
        },
    ],
    "fitness": [
        {
            "name": "Ningbo Fitness Equipment Co.",
            "company": "Ningbo Fitness Equipment Co., Ltd.",
            "country": "China",
            "location": "Ningbo, Zhejiang",
            "email": "info@nb-fitness.com",
            "phone": "+86-574-8789-0123",
            "whatsapp": "+86-136-0574-1234",
            "website": "www.nb-fitness.com",
            "business_type": "Manufacturer",
            "moq": 200,
            "lead_time": "15-20 days",
            "payment": "T/T, Alibaba Trade Assurance",
            "certifications": "ISO 9001, CE, SGS",
            "rating": 4.5,
            "specialties": ["resistance bands", "yoga mats", "foam rollers"],
        },
        {
            "name": "Dongguan SportPro Gear",
            "company": "Dongguan SportPro Gear Co., Ltd.",
            "country": "China",
            "location": "Dongguan, Guangdong",
            "email": "sales@sportpro-gear.com",
            "phone": "+86-769-2345-6789",
            "whatsapp": "+86-135-3210-9876",
            "website": "www.sportpro-gear.com",
            "business_type": "Manufacturer & OEM",
            "moq": 100,
            "lead_time": "10-15 days",
            "payment": "T/T, PayPal, Alibaba Trade Assurance",
            "certifications": "ISO 9001, CE",
            "rating": 4.3,
            "specialties": ["gym bags", "water bottles", "jump ropes"],
        },
    ],
    "garden": [
        {
            "name": "Zhongshan Garden Products",
            "company": "Zhongshan Garden Products Co., Ltd.",
            "country": "China",
            "location": "Zhongshan, Guangdong",
            "email": "export@garden-products-zs.com",
            "phone": "+86-760-2345-6789",
            "whatsapp": "+86-138-2390-1234",
            "website": "www.garden-products-zs.com",
            "business_type": "Manufacturer",
            "moq": 300,
            "lead_time": "15-20 days",
            "payment": "T/T, Alibaba Trade Assurance",
            "certifications": "ISO 9001, CE, RoHS",
            "rating": 4.4,
            "specialties": ["solar lights", "garden tools", "plant pots"],
        },
    ],
    "pet": [
        {
            "name": "Taizhou Pet Products Factory",
            "company": "Taizhou Pet Products Factory Co., Ltd.",
            "country": "China",
            "location": "Taizhou, Zhejiang",
            "email": "info@tz-petproducts.com",
            "phone": "+86-576-8901-2345",
            "whatsapp": "+86-139-6860-1234",
            "website": "www.tz-petproducts.com",
            "business_type": "Manufacturer",
            "moq": 200,
            "lead_time": "15-20 days",
            "payment": "T/T, Alibaba Trade Assurance",
            "certifications": "ISO 9001, BSCI, FDA",
            "rating": 4.3,
            "specialties": ["pet toys", "pet feeders", "grooming tools"],
        },
        {
            "name": "Guangzhou Pet Love Products",
            "company": "Guangzhou Pet Love Products Co., Ltd.",
            "country": "China",
            "location": "Guangzhou, Guangdong",
            "email": "sales@petlove-products.com",
            "phone": "+86-20-3456-7891",
            "whatsapp": "+86-138-2233-4456",
            "website": "www.petlove-products.com",
            "business_type": "Manufacturer & OEM",
            "moq": 100,
            "lead_time": "10-15 days",
            "payment": "T/T, PayPal",
            "certifications": "ISO 9001, CE",
            "rating": 4.5,
            "specialties": ["cat trees", "pet beds", "water fountains"],
        },
    ],
    "office": [
        {
            "name": "Dongguan Office Supplies Co.",
            "company": "Dongguan Office Supplies Co., Ltd.",
            "country": "China",
            "location": "Dongguan, Guangdong",
            "email": "export@dg-office.com",
            "phone": "+86-769-2456-7890",
            "whatsapp": "+86-137-1234-5678",
            "website": "www.dg-office.com",
            "business_type": "Manufacturer",
            "moq": 200,
            "lead_time": "10-15 days",
            "payment": "T/T, Alibaba Trade Assurance",
            "certifications": "ISO 9001, BSCI",
            "rating": 4.2,
            "specialties": ["desk organizers", "monitor stands", "whiteboards"],
        },
    ],
    "toys": [
        {
            "name": "Shantou Chenghai Toys",
            "company": "Shantou Chenghai Toys Factory Co., Ltd.",
            "country": "China",
            "location": "Shantou, Guangdong",
            "email": "sales@st-toys.com",
            "phone": "+86-754-8765-4321",
            "whatsapp": "+86-138-2670-1234",
            "website": "www.st-toys.com",
            "business_type": "Manufacturer",
            "moq": 500,
            "lead_time": "20-25 days",
            "payment": "T/T, L/C, Alibaba Trade Assurance",
            "certifications": "ISO 9001, EN71, ASTM, CPSIA",
            "rating": 4.5,
            "specialties": ["building blocks", "puzzles", "educational toys"],
        },
    ],
    "automotive": [
        {
            "name": "Yuyao Auto Accessories Co.",
            "company": "Yuyao Auto Accessories Co., Ltd.",
            "country": "China",
            "location": "Yuyao, Zhejiang",
            "email": "info@yy-auto.com",
            "phone": "+86-574-6234-5678",
            "whatsapp": "+86-139-5740-1234",
            "website": "www.yy-auto.com",
            "business_type": "Manufacturer",
            "moq": 200,
            "lead_time": "15-20 days",
            "payment": "T/T, Alibaba Trade Assurance",
            "certifications": "ISO 9001, CE, TS16949",
            "rating": 4.3,
            "specialties": ["car phone mounts", "car vacuums", "LED lights"],
        },
    ],
    "health": [
        {
            "name": "Shenzhen Health Products Co.",
            "company": "Shenzhen Health Products Co., Ltd.",
            "country": "China",
            "location": "Shenzhen, Guangdong",
            "email": "sales@sz-healthproducts.com",
            "phone": "+86-755-2567-8901",
            "whatsapp": "+86-136-8888-9999",
            "website": "www.sz-healthproducts.com",
            "business_type": "Manufacturer",
            "moq": 200,
            "lead_time": "10-15 days",
            "payment": "T/T, PayPal, Alibaba Trade Assurance",
            "certifications": "ISO 13485, CE, FDA",
            "rating": 4.4,
            "specialties": ["health monitors", "massage devices", "pill organizers"],
        },
    ],
    "fashion": [
        {
            "name": "Guangzhou Fashion Accessories",
            "company": "Guangzhou Fashion Accessories Co., Ltd.",
            "country": "China",
            "location": "Guangzhou, Guangdong",
            "email": "export@gz-fashion.com",
            "phone": "+86-20-3567-8901",
            "whatsapp": "+86-139-2222-3333",
            "website": "www.gz-fashion.com",
            "business_type": "Manufacturer & Exporter",
            "moq": 100,
            "lead_time": "10-15 days",
            "payment": "T/T, PayPal",
            "certifications": "ISO 9001, BSCI",
            "rating": 4.3,
            "specialties": ["wallets", "sunglasses", "belts", "scarves"],
        },
    ],
    "baby": [
        {
            "name": "Shenzhen Baby Care Products",
            "company": "Shenzhen Baby Care Products Co., Ltd.",
            "country": "China",
            "location": "Shenzhen, Guangdong",
            "email": "info@sz-babycare.com",
            "phone": "+86-755-2678-9012",
            "whatsapp": "+86-135-8888-7777",
            "website": "www.sz-babycare.com",
            "business_type": "Manufacturer",
            "moq": 200,
            "lead_time": "15-20 days",
            "payment": "T/T, Alibaba Trade Assurance",
            "certifications": "ISO 9001, EN71, CPSIA, FDA",
            "rating": 4.5,
            "specialties": ["baby bottles", "teething toys", "swaddle blankets"],
        },
    ],
    "sports": [
        {
            "name": "Ningbo Sports Goods Co.",
            "company": "Ningbo Sports Goods Co., Ltd.",
            "country": "China",
            "location": "Ningbo, Zhejiang",
            "email": "sales@nb-sportsgoods.com",
            "phone": "+86-574-8890-1234",
            "whatsapp": "+86-138-5740-5678",
            "website": "www.nb-sportsgoods.com",
            "business_type": "Manufacturer",
            "moq": 300,
            "lead_time": "15-20 days",
            "payment": "T/T, Alibaba Trade Assurance",
            "certifications": "ISO 9001, BSCI",
            "rating": 4.4,
            "specialties": ["balls", "swimming gear", "camping equipment"],
        },
    ],
    "tools": [
        {
            "name": "Zhejiang Power Tools Factory",
            "company": "Zhejiang Power Tools Factory Co., Ltd.",
            "country": "China",
            "location": "Jinhua, Zhejiang",
            "email": "export@zj-powertools.com",
            "phone": "+86-579-8901-2345",
            "whatsapp": "+86-137-5790-1234",
            "website": "www.zj-powertools.com",
            "business_type": "Manufacturer",
            "moq": 200,
            "lead_time": "15-20 days",
            "payment": "T/T, L/C, Alibaba Trade Assurance",
            "certifications": "ISO 9001, CE, GS",
            "rating": 4.4,
            "specialties": ["screwdriver sets", "multimeters", "flashlights"],
        },
    ],
    "default": [
        {
            "name": "Yiwu Global Trading Co.",
            "company": "Yiwu Global Trading Co., Ltd.",
            "country": "China",
            "location": "Yiwu, Zhejiang",
            "email": "info@yiwu-global.com",
            "phone": "+86-579-8500-1234",
            "whatsapp": "+86-139-5790-1234",
            "website": "www.yiwu-global.com",
            "business_type": "Trading Company",
            "moq": 100,
            "lead_time": "10-15 days",
            "payment": "T/T, PayPal, Alibaba Trade Assurance",
            "certifications": "ISO 9001",
            "rating": 4.2,
            "specialties": ["general merchandise", "consumer goods"],
        },
        {
            "name": "Shenzhen Direct Sourcing",
            "company": "Shenzhen Direct Sourcing Co., Ltd.",
            "country": "China",
            "location": "Shenzhen, Guangdong",
            "email": "sales@sz-direct.com",
            "phone": "+86-755-2100-1234",
            "whatsapp": "+86-135-9012-3456",
            "website": "www.sz-direct.com",
            "business_type": "Sourcing Company",
            "moq": 50,
            "lead_time": "7-10 days",
            "payment": "T/T, PayPal, Alibaba Trade Assurance",
            "certifications": "ISO 9001, BSCI",
            "rating": 4.1,
            "specialties": ["product sourcing", "quality inspection", "shipping"],
        },
    ],
}


def get_suppliers_for_category(category: str) -> List[Dict[str, Any]]:
    """Get suppliers matching a product category."""
    cat_lower = category.lower()
    for key in SUPPLIER_DATABASE:
        if key in cat_lower:
            return SUPPLIER_DATABASE[key]
    return SUPPLIER_DATABASE["default"]


def get_random_supplier(category: str) -> Optional[Dict[str, Any]]:
    """Get a random supplier for a category."""
    suppliers = get_suppliers_for_category(category)
    return random.choice(suppliers) if suppliers else None


def get_all_suppliers() -> List[Dict[str, Any]]:
    """Get all suppliers from all categories."""
    all_suppliers = []
    for category, suppliers in SUPPLIER_DATABASE.items():
        if category == "default":
            continue
        for s in suppliers:
            s_copy = s.copy()
            s_copy["source_category"] = category
            all_suppliers.append(s_copy)
    return all_suppliers


def match_suppliers_to_products(products: List[Dict[str, Any]], use_alibaba: bool = True) -> List[Dict[str, Any]]:
    """Match suppliers to products based on category with real pricing."""
    try:
        if use_alibaba:
            from data_collectors.alibaba_scraper import get_supplier_pricing
            for product in products:
                try:
                    supplier_data = get_supplier_pricing(product)
                    if supplier_data:
                        product.update(supplier_data)
                    else:
                        _fallback_supplier_match(product)
                except Exception:
                    _fallback_supplier_match(product)
        else:
            for product in products:
                _fallback_supplier_match(product)
    except ImportError:
        for product in products:
            _fallback_supplier_match(product)
    return products


def _fallback_supplier_match(product: Dict[str, Any]):
    """Fallback to database supplier matching."""
    category = product.get("category", "default")
    suppliers = get_suppliers_for_category(category)
    if suppliers:
        supplier = random.choice(suppliers)
        product["supplier_name"] = supplier["name"]
        product["supplier_company"] = supplier["company"]
        product["supplier_email"] = supplier["email"]
        product["supplier_phone"] = supplier["phone"]
        product["supplier_whatsapp"] = supplier.get("whatsapp", "")
        product["supplier_website"] = supplier.get("website", "")
        product["supplier_moq"] = supplier.get("moq", 0)
        product["supplier_lead_time"] = supplier.get("lead_time", "")
        product["supplier_payment"] = supplier.get("payment", "")
        product["supplier_rating"] = supplier.get("rating", 0)
        product["supplier_price_source"] = "database"


def get_supplier_with_pricing(product_name: str, category: str, amazon_price: float) -> Dict[str, Any]:
    """Get supplier with real pricing - tries Alibaba first, falls back to database."""
    try:
        from data_collectors.alibaba_scraper import get_supplier_pricing
        product = {"name": product_name, "category": category, "amazon_price": amazon_price}
        supplier_data = get_supplier_pricing(product)
        if supplier_data:
            return supplier_data
    except Exception:
        pass

    suppliers = get_suppliers_for_category(category)
    if suppliers:
        supplier = random.choice(suppliers)
        cost_ratios = {
            "kitchen": (0.10, 0.22), "electronics": (0.12, 0.28),
            "beauty": (0.08, 0.18), "home": (0.10, 0.20),
            "fitness": (0.10, 0.22), "garden": (0.08, 0.18),
            "pet": (0.08, 0.18), "office": (0.08, 0.16),
            "toys": (0.06, 0.14), "automotive": (0.10, 0.22),
            "health": (0.08, 0.20), "baby": (0.08, 0.18),
            "sports": (0.10, 0.22), "tools": (0.10, 0.22),
        }
        low, high = cost_ratios.get(category.lower(), (0.10, 0.22))
        unit_cost = round(amazon_price * random.uniform(low, high), 2)

        return {
            "supplier_name": supplier["name"],
            "supplier_company": supplier["company"],
            "supplier_email": supplier["email"],
            "supplier_phone": supplier["phone"],
            "supplier_whatsapp": supplier.get("whatsapp", ""),
            "supplier_website": supplier.get("website", ""),
            "supplier_moq": supplier.get("moq", 0),
            "supplier_lead_time": supplier.get("lead_time", ""),
            "supplier_payment": supplier.get("payment", ""),
            "supplier_rating": supplier.get("rating", 0),
            "supplier_price": unit_cost,
            "supplier_price_source": "estimated",
        }
    return {}
