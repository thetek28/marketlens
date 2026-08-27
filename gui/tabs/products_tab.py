"""Products (Top 20) tab for MarketLens."""

import customtkinter as ctk

from gui.common import THEME
from gui.widgets import build_column_header, build_product_row


class ProductsTab:
    """Top 20 recommended products tab."""

    def __init__(self, tabview, app):
        self.tabview = tabview
        self.app = app
        self.top100_rows = []
        self._build()

    def _build(self):
        tab = self.tabview.tab("Products")
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 5))
        ctk.CTkLabel(
            top, text="Top 20 Recommended for Amazon",
            font=THEME["font_title"],
        ).pack(side="left")
        ctk.CTkLabel(
            top, text="Best products ranked by AI score, margin & rating",
            font=THEME["font_subtitle"], text_color=THEME["text_muted"],
        ).pack(side="left", padx=15)

        build_column_header(tab)

        self.top100_scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent",
                                                     scrollbar_button_color=THEME["border"])
        self.top100_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.refresh()

    def refresh(self):
        for r in self.top100_rows:
            r.destroy()
        self.top100_rows.clear()

        products = [p for p in self.app._get_top20() if not p.get("gated", False)]
        for i, p in enumerate(products, 1):
            row = build_product_row(self.top100_scroll, p, i, self.top100_scroll, self.app)

            # Add AI sentiment button
            def sentiment(pp=p): self.app._run_sentiment_analysis(pp)
            ctk.CTkButton(
                row, text="AI", width=35, height=24, fg_color="#7c3aed",
                hover_color="#6d28d9", font=ctk.CTkFont(size=9, weight="bold"),
                corner_radius=6, command=sentiment,
            ).pack(side="left", padx=2)
            self.top100_rows.append(row)
