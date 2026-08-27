"""Shared constants, themes, and FBA fee tables for MarketLens GUI."""

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.dirname(sys.executable))
else:
    BASE_DIR = str(Path(__file__).parent.parent)

CTK_BOLD = ("Segoe UI", 13, "bold")
MONO_FONT = ("Consolas", 12)

THEME = {
    "bg": "#070b14",
    "bg_dark": "#070b14",
    "bg_mid": "#0d1525",
    "bg_card": "#111d32",
    "card_bg": "#111d32",
    "bg_hover": "#162240",
    "surface": "#111d32",
    "surface_hover": "#1a2d4a",
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "accent_dim": "#1e3a5f",
    "success": "#10b981",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "error": "#ef4444",
    "info": "#06b6d4",
    "text": "#f1f5f9",
    "text_dim": "#94a3b8",
    "text_muted": "#4b5563",
    "border": "#162240",
    "gold": "#fbbf24",
    "silver": "#9ca3af",
    "bronze": "#cd7f32",
    "tier_critical": "#ef4444",
    "tier_high": "#f97316",
    "tier_medium": "#3b82f6",
    "tier_low": "#6b7280",
    "tier_minimal": "#4b5563",
    "font": ("Segoe UI", 11),
    "font_bold": ("Segoe UI", 11, "bold"),
    "font_small": ("Segoe UI", 10),
    "font_title": ("Segoe UI", 18, "bold"),
    "font_subtitle": ("Segoe UI", 10),
    "corner_radius": 8,
    "card_radius": 10,
    "btn_primary": {"fg_color": "#3b82f6", "hover_color": "#2563eb", "font": ("Segoe UI", 11, "bold"), "corner_radius": 6},
    "btn_small": {"fg_color": "#111d32", "hover_color": "#162240", "font": ("Segoe UI", 10), "corner_radius": 6},
    "btn_danger": {"fg_color": "#ef4444", "hover_color": "#dc2626", "font": ("Segoe UI", 10, "bold"), "corner_radius": 6},
    "btn_success": {"fg_color": "#10b981", "hover_color": "#059669", "font": ("Segoe UI", 10, "bold"), "corner_radius": 6},
    "btn_outline": {"fg_color": "transparent", "hover_color": "#162240", "border_color": "#3b82f6", "font": ("Segoe UI", 10, "bold"), "corner_radius": 6},
}

DEFAULT_CATEGORIES = [
    "kitchen", "electronics", "beauty", "home", "fitness",
    "garden", "pet", "office", "toys", "automotive",
    "health", "fashion", "baby", "sports", "tools",
]

CYCLE_INTERVAL_MINUTES = 5

# Single source of truth for Amazon FBA fees
AMAZON_FBA_FEES = {
    "small_standard": {"referral_pct": 0.15, "fulfillment": 3.22, "storage_per_unit": 0.75},
    "large_standard": {"referral_pct": 0.15, "fulfillment": 5.40, "storage_per_unit": 1.10},
    "oversize": {"referral_pct": 0.15, "fulfillment": 8.26, "storage_per_unit": 2.40},
    "small_oversize": {"referral_pct": 0.15, "fulfillment": 8.26, "storage_per_unit": 2.40},
    "large_oversize": {"referral_pct": 0.15, "fulfillment": 9.73, "storage_per_unit": 3.20},
    "special_oversize": {"referral_pct": 0.15, "fulfillment": 13.75, "storage_per_unit": 4.50},
}

AMAZON_REFERRAL_FEES = {
    "default": 0.15,
    "automotive": 0.12,
    "beauty": 0.15,
    "books": 0.15,
    "clothing": 0.17,
    "electronics": 0.08,
    "furniture": 0.15,
    "grocery": 0.15,
    "health": 0.15,
    "jewelry": 0.20,
    "luggage": 0.15,
    "mobile_electronics": 0.15,
    "office": 0.15,
    "outdoors": 0.15,
    "pet_supplies": 0.15,
    "shoes": 0.15,
    "sports": 0.15,
    "tools": 0.15,
    "toys": 0.15,
    "video_games": 0.15,
}

CATEGORY_COLUMNS = [
    ("Rank", 35), ("Product", 150), ("Brand", 80), ("Category", 60), ("Price", 50),
    ("Rating", 40), ("Reviews", 55), ("Margin", 40), ("AI", 35),
    ("Seller", 70), ("Fulfill", 40), ("Sales", 50), ("Light", 40),
    ("Tier", 45), ("Gating", 55), ("Link", 35),
]
