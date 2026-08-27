"""Research (Black Box) tab for MarketLens."""

import re
import threading
from tkinter import messagebox

import customtkinter as ctk

from gui.common import DEFAULT_CATEGORIES, THEME
from gui.widgets import build_column_header, build_product_row


class ResearchTab:
    """Black Box advanced product search tab."""

    def __init__(self, tabview, app):
        self.tabview = tabview
        self.app = app
        self.bb_rows = []
        self._build()

    def _build(self):
        tab = self.tabview.tab("Research")
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 5))
        ctk.CTkLabel(
            top, text="Black Box - Product Research",
            font=THEME["font_title"],
        ).pack(side="left")
        ctk.CTkLabel(
            top, text="Advanced filters to find winning products",
            font=THEME["font_subtitle"], text_color=THEME["text_muted"],
        ).pack(side="left", padx=15)

        asin_frame = ctk.CTkFrame(tab, fg_color=THEME["bg_card"], corner_radius=THEME["corner_radius"])
        asin_frame.pack(fill="x", padx=12, pady=(5, 5))

        asin_row = ctk.CTkFrame(asin_frame, fg_color="transparent")
        asin_row.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(asin_row, text="ASIN Lookup:",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=THEME["accent"]).pack(side="left", padx=(0, 8))
        self.asin_entry = ctk.CTkEntry(asin_row, width=160, placeholder_text="e.g. B0DFFQ9W2S",
                                       fg_color=THEME["bg_mid"], border_color=THEME["border"])
        self.asin_entry.pack(side="left", padx=5)
        self.asin_entry.bind("<Return>", lambda e: self._search_asin())

        self.asin_status = ctk.CTkLabel(asin_row, text="", font=ctk.CTkFont(size=10),
                                        text_color=THEME["text_muted"])
        self.asin_status.pack(side="left", padx=8)

        ctk.CTkButton(asin_row, text="FETCH", width=70, height=28, fg_color=THEME["accent"],
                      font=ctk.CTkFont(size=11, weight="bold"), corner_radius=6,
                      command=self._search_asin).pack(side="left", padx=5)

        filters = ctk.CTkFrame(tab, fg_color=THEME["bg_card"], corner_radius=THEME["corner_radius"])
        filters.pack(fill="x", padx=12, pady=5)

        row1 = ctk.CTkFrame(filters, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=(5, 3))
        ctk.CTkLabel(row1, text="Category:", font=ctk.CTkFont(size=10), text_color=THEME["text_dim"]).pack(side="left", padx=3)
        self.bb_category = ctk.CTkComboBox(row1, values=["All"] + DEFAULT_CATEGORIES, width=120,
                                            fg_color=THEME["bg_mid"], border_color=THEME["border"])
        self.bb_category.pack(side="left", padx=3)
        self.bb_category.set("All")

        ctk.CTkLabel(row1, text="Min Price:", font=ctk.CTkFont(size=10), text_color=THEME["text_dim"]).pack(side="left", padx=(10, 3))
        self.bb_min_price = ctk.CTkEntry(row1, width=70, fg_color=THEME["bg_mid"], border_color=THEME["border"])
        self.bb_min_price.pack(side="left", padx=3)
        self.bb_min_price.insert(0, "10")

        ctk.CTkLabel(row1, text="Max Price:", font=ctk.CTkFont(size=10), text_color=THEME["text_dim"]).pack(side="left", padx=(10, 3))
        self.bb_max_price = ctk.CTkEntry(row1, width=70, fg_color=THEME["bg_mid"], border_color=THEME["border"])
        self.bb_max_price.pack(side="left", padx=3)
        self.bb_max_price.insert(0, "50")

        ctk.CTkLabel(row1, text="Min Reviews:", font=ctk.CTkFont(size=10), text_color=THEME["text_dim"]).pack(side="left", padx=(10, 3))
        self.bb_min_reviews = ctk.CTkEntry(row1, width=70, fg_color=THEME["bg_mid"], border_color=THEME["border"])
        self.bb_min_reviews.pack(side="left", padx=3)
        self.bb_min_reviews.insert(0, "50")

        ctk.CTkLabel(row1, text="Max Reviews:", font=ctk.CTkFont(size=10), text_color=THEME["text_dim"]).pack(side="left", padx=(10, 3))
        self.bb_max_reviews = ctk.CTkEntry(row1, width=70, fg_color=THEME["bg_mid"], border_color=THEME["border"])
        self.bb_max_reviews.pack(side="left", padx=3)
        self.bb_max_reviews.insert(0, "500000")

        ctk.CTkLabel(row1, text="Min Rating:", font=ctk.CTkFont(size=10), text_color=THEME["text_dim"]).pack(side="left", padx=(10, 3))
        self.bb_min_rating = ctk.CTkEntry(row1, width=50, fg_color=THEME["bg_mid"], border_color=THEME["border"])
        self.bb_min_rating.pack(side="left", padx=3)
        self.bb_min_rating.insert(0, "3.5")

        row2 = ctk.CTkFrame(filters, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=(3, 8))
        ctk.CTkLabel(row2, text="Min Margin:", font=ctk.CTkFont(size=10), text_color=THEME["text_dim"]).pack(side="left", padx=3)
        self.bb_min_margin = ctk.CTkEntry(row2, width=60, fg_color=THEME["bg_mid"], border_color=THEME["border"])
        self.bb_min_margin.pack(side="left", padx=3)
        self.bb_min_margin.insert(0, "30")

        ctk.CTkLabel(row2, text="Min AI Score:", font=ctk.CTkFont(size=10), text_color=THEME["text_dim"]).pack(side="left", padx=(10, 3))
        self.bb_min_ai = ctk.CTkEntry(row2, width=60, fg_color=THEME["bg_mid"], border_color=THEME["border"])
        self.bb_min_ai.pack(side="left", padx=3)
        self.bb_min_ai.insert(0, "0.5")

        ctk.CTkLabel(row2, text="Traffic Light:", font=ctk.CTkFont(size=10), text_color=THEME["text_dim"]).pack(side="left", padx=(10, 3))
        self.bb_traffic = ctk.CTkComboBox(row2, values=["All", "GREEN", "YELLOW", "RED"], width=90,
                                           fg_color=THEME["bg_mid"], border_color=THEME["border"])
        self.bb_traffic.pack(side="left", padx=3)
        self.bb_traffic.set("All")

        ctk.CTkLabel(row2, text="Sort By:", font=ctk.CTkFont(size=10), text_color=THEME["text_dim"]).pack(side="left", padx=(10, 3))
        self.bb_sort = ctk.CTkComboBox(row2, values=["AI Score", "Margin", "Reviews", "Price", "Consistency"],
                                        width=110, fg_color=THEME["bg_mid"], border_color=THEME["border"])
        self.bb_sort.pack(side="left", padx=3)
        self.bb_sort.set("AI Score")

        ctk.CTkButton(row2, text="SEARCH", width=90, height=30, fg_color=THEME["accent"],
                      font=ctk.CTkFont(size=11, weight="bold"), corner_radius=6,
                      command=self._run_search).pack(side="left", padx=(15, 5))
        ctk.CTkButton(row2, text="RESET", width=60, height=30, fg_color=THEME["bg_mid"],
                      font=ctk.CTkFont(size=10), corner_radius=6,
                      command=self._reset).pack(side="left", padx=3)

        self.bb_count = ctk.CTkLabel(row2, text="0 results", font=ctk.CTkFont(size=11, weight="bold"),
                                      text_color=THEME["accent"])
        self.bb_count.pack(side="right", padx=10)

        build_column_header(tab)

        self.bb_scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent",
                                                 scrollbar_button_color=THEME["border"])
        self.bb_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.refresh()

    def _run_search(self):
        for r in self.bb_rows:
            r.destroy()
        self.bb_rows.clear()

        try:
            min_price = float(self.bb_min_price.get() or 0)
            max_price = float(self.bb_max_price.get() or 9999)
            min_reviews = int(self.bb_min_reviews.get() or 0)
            max_reviews = int(self.bb_max_reviews.get() or 999999)
            min_rating = float(self.bb_min_rating.get() or 0)
            min_margin = float(self.bb_min_margin.get() or 0)
            min_ai = float(self.bb_min_ai.get() or 0)
        except (ValueError, TypeError):
            messagebox.showwarning("Input Error", "Please enter valid numbers in filter fields.")
            return

        traffic = self.bb_traffic.get()
        category = self.bb_category.get()
        sort_by = self.bb_sort.get()

        filtered = []
        for p in self.app.ideas:
            if p.get("gated", False):
                continue
            price = p.get("amazon_price", p.get("price", 0))
            reviews = p.get("review_count", 0)
            rating = p.get("rating", 0)
            margin = p.get("estimated_margin_pct", 0)
            ai = p.get("ai_score", p.get("score", 0))
            tl = p.get("traffic_light", "RED")
            cat = p.get("category", "").lower()

            if price < min_price or price > max_price:
                continue
            if reviews < min_reviews or reviews > max_reviews:
                continue
            if rating < min_rating:
                continue
            if margin < min_margin:
                continue
            if ai < min_ai:
                continue
            if traffic != "All" and tl != traffic:
                continue
            if category != "All" and category.lower() not in cat:
                continue
            filtered.append(p)

        sort_keys = {
            "AI Score": lambda x: x.get("ai_score", 0),
            "Margin": lambda x: x.get("estimated_margin_pct", 0),
            "Reviews": lambda x: x.get("review_count", 0),
            "Price": lambda x: x.get("amazon_price", 0),
            "Consistency": lambda x: x.get("consistency_score", 0),
        }
        filtered.sort(key=sort_keys.get(sort_by, sort_keys["AI Score"]), reverse=True)

        for i, p in enumerate(filtered[:100], 1):
            row = build_product_row(self.bb_scroll, p, i, self.bb_scroll, self.app)
            self.bb_rows.append(row)

        self.bb_count.configure(text=f"{len(filtered)} results")

    def _reset(self):
        self.bb_min_price.delete(0, "end")
        self.bb_min_price.insert(0, "10")
        self.bb_max_price.delete(0, "end")
        self.bb_max_price.insert(0, "50")
        self.bb_min_reviews.delete(0, "end")
        self.bb_min_reviews.insert(0, "50")
        self.bb_max_reviews.delete(0, "end")
        self.bb_max_reviews.insert(0, "500000")
        self.bb_min_rating.delete(0, "end")
        self.bb_min_rating.insert(0, "3.5")
        self.bb_min_margin.delete(0, "end")
        self.bb_min_margin.insert(0, "30")
        self.bb_min_ai.delete(0, "end")
        self.bb_min_ai.insert(0, "0.5")
        self.bb_category.set("All")
        self.bb_traffic.set("All")
        self.bb_sort.set("AI Score")
        self._run_search()

    def _search_asin(self):
        raw = self.asin_entry.get().strip().upper()
        asin_match = re.search(r'B0[A-Z0-9]{8}', raw)
        asin = asin_match.group(0) if asin_match else raw

        if not asin or len(asin) < 5:
            self.asin_status.configure(text="Invalid ASIN", text_color=THEME["danger"])
            return

        for p in self.app.ideas:
            if p.get("asin") == asin:
                self.asin_status.configure(text=f"Already in list!", text_color=THEME["success"])
                return

        self.asin_status.configure(text="Fetching...", text_color=THEME["text_muted"])
        self.asin_entry.configure(state="disabled")

        def _fetch():
            try:
                from data_collectors.seller_info import SellerInfoScraper
                from bs4 import BeautifulSoup
                import requests

                scraper = SellerInfoScraper()
                seller_data = scraper.scrape_product_page(asin)

                title = ""
                price = 0.0
                try:
                    url = f"https://www.amazon.com/dp/{asin}"
                    resp = requests.get(url, timeout=15, allow_redirects=True,
                                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        el = soup.select_one("#productTitle")
                        if el:
                            title = el.get_text(strip=True)
                        price_el = soup.select_one(".a-price .a-offscreen")
                        if price_el:
                            price = float(price_el.get_text(strip=True).replace("£", "").replace("$", "").replace(",", ""))
                except Exception:
                    pass

                if not title:
                    title = seller_data.get("brand", "") + " Product"

                product = {
                    "source": "asin_search",
                    "query": "asin_lookup",
                    "asin": asin,
                    "title": title,
                    "brand_name": seller_data.get("brand", ""),
                    "price": price,
                    "rating": 0,
                    "review_count": seller_data.get("seller_reviews", 0),
                    "rank": seller_data.get("bsr", 0),
                    "url": f"https://www.amazon.com/dp/{asin}",
                    "image": "",
                    "category": seller_data.get("category", ""),
                    "seller_info": seller_data,
                }

                from utils.gating import mark_gating
                mark_gating(product)

                self.app.after(0, lambda: self._on_asin_result(asin, product))
            except Exception as e:
                self.app.after(0, lambda: self._on_asin_error(str(e)))

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_asin_result(self, asin, product):
        self.asin_entry.configure(state="normal")
        self.app.ideas.append(product)

        if hasattr(self.app, 'hidden_gems'):
            self.app.hidden_gems = [g for g in self.app.hidden_gems if g.get("asin") != asin]

        brand = product.get("brand_name", "Unknown")
        self.asin_status.configure(text=f"Found: {brand} ({asin})", text_color=THEME["success"])
        self.refresh()

    def _on_asin_error(self, msg):
        self.asin_entry.configure(state="normal")
        self.asin_status.configure(text=f"Error: {msg[:40]}", text_color=THEME["danger"])

    def refresh(self):
        for r in self.bb_rows:
            r.destroy()
        self.bb_rows.clear()

        products = [p for p in (self.app.ideas if self.app.ideas else []) if not p.get("gated", False)]
        self.bb_count.configure(text=f"{len(products)} products gathered")

        if not products:
            lbl = ctk.CTkLabel(
                self.bb_scroll, text="No products yet. Start analysis to gather products.",
                font=ctk.CTkFont(size=12), text_color=THEME["text_muted"],
            )
            lbl.pack(pady=20)
            self.bb_rows.append(lbl)
            return

        for i, p in enumerate(products, 1):
            row = build_product_row(self.bb_scroll, p, i, self.bb_scroll, self.app)
            self.bb_rows.append(row)
