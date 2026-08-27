"""Tools tab - Compare, Analytics, Batch, Notes, Team, Report for MarketLens."""

import json
import os
from datetime import datetime

import customtkinter as ctk

from gui.common import CTK_BOLD, MONO_FONT, THEME


class ToolsTab:
    """Tools tab with Compare, Analytics, Batch, Notes, Team, and Report sub-tabs."""

    def __init__(self, tabview, app):
        self.tabview = tabview
        self.app = app
        self._build()

    def _build(self):
        tab = self.tabview.tab("Tools")

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 5))
        ctk.CTkLabel(
            top, text="Tools - Compare, Analytics, Batch & Notes",
            font=THEME["font_title"],
        ).pack(side="left")
        ctk.CTkLabel(
            top, text="Compare products side by side, run batch analysis, take notes",
            font=THEME["font_subtitle"], text_color=THEME["text_muted"],
        ).pack(side="left", padx=15)

        tools_tabview = ctk.CTkTabview(
            tab, fg_color=THEME["bg_dark"],
            segmented_button_fg_color=THEME["bg_mid"],
            segmented_button_selected_color=THEME["accent"],
        )
        tools_tabview.pack(fill="both", expand=True, padx=4, pady=4)

        tools_tabview.add("Compare")
        tools_tabview.add("Analytics")
        tools_tabview.add("Batch")
        tools_tabview.add("Notes")
        tools_tabview.add("Team")
        tools_tabview.add("Report")

        self._build_compare_tool(tools_tabview.tab("Compare"))
        self._build_analytics_tool(tools_tabview.tab("Analytics"))
        self._build_batch_tool(tools_tabview.tab("Batch"))
        self._build_notes_tool(tools_tabview.tab("Notes"))
        self._build_team_tool(tools_tabview.tab("Team"))
        self._build_report_tool(tools_tabview.tab("Report"))

        if self.app.ideas:
            self.app.after(200, self._refresh_analytics)

    # ─── Compare ──────────────────────────────────────────────────

    def _build_compare_tool(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=8)

        toolbar = ctk.CTkFrame(f, fg_color=THEME["surface"])
        toolbar.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            toolbar, text="Select products (min 2):",
            font=ctk.CTkFont(size=11),
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            toolbar, text="Compare", command=self._run_comparison, width=80, height=28,
            fg_color=THEME["accent"], font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(side="right", padx=8, pady=4)
        ctk.CTkButton(
            toolbar, text="All", width=40, height=28,
            fg_color="transparent", border_color=THEME["accent"], border_width=1,
            font=ctk.CTkFont(size=10), corner_radius=4,
            command=self._select_all_compare,
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            toolbar, text="None", width=40, height=28,
            fg_color="transparent", border_color=THEME["text_dim"], border_width=1,
            font=ctk.CTkFont(size=10), corner_radius=4,
            command=self._deselect_all_compare,
        ).pack(side="right", padx=2)
        self.compare_sel_count = ctk.CTkLabel(
            toolbar, text="0 selected",
            font=ctk.CTkFont(size=10), text_color=THEME["text_dim"],
        )
        self.compare_sel_count.pack(side="right", padx=4)

        content = ctk.CTkFrame(f, fg_color="transparent")
        content.pack(fill="both", expand=True)

        left = ctk.CTkFrame(content, fg_color=THEME["surface"], corner_radius=8)
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))

        self.compare_search = ctk.CTkEntry(
            left, placeholder_text="Search...", height=28,
            font=ctk.CTkFont(size=10),
        )
        self.compare_search.pack(fill="x", padx=8, pady=(8, 4))
        self.compare_search.bind("<KeyRelease>", self._filter_compare_list)

        scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        self.compare_checkboxes = []
        self.compare_items_frame = scroll
        self._populate_compare_list()

        right = ctk.CTkFrame(content, fg_color=THEME["surface"], corner_radius=8)
        right.pack(side="right", fill="both", expand=True, padx=(4, 0))

        self.compare_result = ctk.CTkTextbox(
            right, fg_color=THEME["bg"], font=MONO_FONT, wrap="word",
        )
        self.compare_result.pack(fill="both", expand=True, padx=4, pady=4)

    def _populate_compare_list(self, filter_text=""):
        for w in self.compare_items_frame.winfo_children():
            w.destroy()
        self.compare_checkboxes = []
        top20 = self.app._get_top20()
        filtered = (
            [p for p in top20 if filter_text.lower() in p.get("name", p.get("title", "")).lower()]
            if filter_text else top20
        )
        self.compare_vars = []
        for p in filtered:
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(
                self.compare_items_frame,
                text=p.get("name", p.get("title", ""))[:45],
                variable=var, font=ctk.CTkFont(size=9), text_color=THEME["text"],
                fg_color=THEME["accent"], command=self._update_compare_count,
            )
            cb.pack(anchor="w", padx=4, pady=1)
            self.compare_checkboxes.append((var, p))
            self.compare_vars.append(var)

    def _filter_compare_list(self, event=None):
        self._populate_compare_list(self.compare_search.get().strip())

    def _select_all_compare(self):
        for var, _ in self.compare_checkboxes:
            var.set(True)
        self._update_compare_count()

    def _deselect_all_compare(self):
        for var, _ in self.compare_checkboxes:
            var.set(False)
        self._update_compare_count()

    def _update_compare_count(self):
        count = sum(1 for var, _ in self.compare_checkboxes if var.get())
        self.compare_sel_count.configure(text=f"{count} selected")

    def _run_comparison(self):
        selected = [p for var, p in self.compare_checkboxes if var.get()]
        if len(selected) < 2:
            self.compare_result.delete("1.0", "end")
            self.compare_result.insert("end", "Select at least 2 products.")
            return

        from analyzers.advanced_analytics import ProductComparator
        comp = ProductComparator().compare(selected)
        self.compare_result.delete("1.0", "end")
        self.compare_result.insert("end", "PRODUCT COMPARISON\n" + "=" * 45 + "\n\n")
        metrics = comp.get("metrics", {})
        self.compare_result.insert(
            "end",
            "Avg Price: £{:.2f} | Rating: {:.1f} | Margin: {:.0f}%\n\n".format(
                metrics.get("avg_price", 0), metrics.get("avg_rating", 0),
                metrics.get("avg_margin", 0),
            ),
        )
        for i, p in enumerate(comp.get("products", []), 1):
            rank = "WINNER" if i == 1 else f"#{i}"
            self.compare_result.insert("end", "{}: {}\n".format(rank, p["name"]))
            self.compare_result.insert(
                "end",
                "  £{:.2f} | {:.1f} rating | {:,} reviews\n".format(
                    p["price"], p["rating"], p["reviews"],
                ),
            )
            self.compare_result.insert(
                "end",
                "  Margin: {:.0f}% | AI: {:.0%} | Score: {}/100\n\n".format(
                    p["margin"], p["ai_score"], p["composite_score"],
                ),
            )

    # ─── Analytics ────────────────────────────────────────────────

    def _build_analytics_tool(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=8)

        toolbar = ctk.CTkFrame(f, fg_color=THEME["surface"])
        toolbar.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            toolbar, text="Refresh", command=self._refresh_analytics, width=80, height=28,
            fg_color=THEME["accent"], font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(side="left", padx=8, pady=4)
        self.analytics_status = ctk.CTkLabel(
            toolbar, text="", font=ctk.CTkFont(size=10), text_color=THEME["text_dim"],
        )
        self.analytics_status.pack(side="left", padx=8)

        content = ctk.CTkFrame(f, fg_color="transparent")
        content.pack(fill="both", expand=True)

        left = ctk.CTkFrame(content, fg_color=THEME["surface"], corner_radius=8)
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))
        ctk.CTkLabel(
            left, text="Category Rankings", font=CTK_BOLD, text_color=THEME["accent"],
        ).pack(anchor="w", padx=8, pady=4)
        self.analytics_categories = ctk.CTkTextbox(
            left, fg_color=THEME["bg"], font=MONO_FONT, wrap="word",
        )
        self.analytics_categories.pack(fill="both", expand=True, padx=4, pady=4)

        right = ctk.CTkFrame(content, fg_color=THEME["surface"], corner_radius=8)
        right.pack(side="right", fill="both", expand=True, padx=(4, 0))
        ctk.CTkLabel(
            right, text="Market Gaps", font=CTK_BOLD, text_color=THEME["success"],
        ).pack(anchor="w", padx=8, pady=4)
        self.analytics_gaps = ctk.CTkTextbox(
            right, fg_color=THEME["bg"], font=MONO_FONT, wrap="word",
        )
        self.analytics_gaps.pack(fill="both", expand=True, padx=4, pady=4)

    def _refresh_analytics(self):
        self.analytics_status.configure(text="Analyzing...", text_color=THEME["warning"])
        self.app.update_idletasks()
        try:
            products = self.app._get_top20()
            if not products:
                self.analytics_status.configure(text="No products", text_color=THEME["error"])
                return
            from analyzers.advanced_analytics import CategoryAnalyzer, TrendAnalyzer
            cat_analysis = CategoryAnalyzer().analyze(products)
            trend_analysis = TrendAnalyzer().analyze(products)

            self.analytics_categories.delete("1.0", "end")
            self.analytics_categories.insert("end", "CATEGORIES (Top 20)\n")
            self.analytics_categories.insert("end", "-" * 35 + "\n\n")
            for i, cat in enumerate(cat_analysis.get("category_rankings", []), 1):
                self.analytics_categories.insert(
                    "end", "#{} {} | {} products\n".format(i, cat["name"], cat["product_count"]),
                )
                self.analytics_categories.insert(
                    "end",
                    "  Price: £{:.2f} | Margin: {:.0f}% | AI: {:.0%}\n".format(
                        cat["avg_price"], cat["avg_margin"], cat["avg_ai_score"],
                    ),
                )
                self.analytics_categories.insert("end", "  Status: {}\n\n".format(cat["opportunity"]))

            self.analytics_gaps.delete("1.0", "end")
            self.analytics_gaps.insert("end", "PRICE SWEET SPOT\n" + "-" * 35 + "\n")
            sweet = trend_analysis.get("price_trends", {}).get("sweet_spot", {})
            if sweet.get("bracket"):
                self.analytics_gaps.insert(
                    "end", "Best: {} (margin: {:.0f}%)\n\n".format(
                        sweet["bracket"].replace("_", " "), sweet.get("avg_margin", 0),
                    ),
                )

            gaps = trend_analysis.get("market_gaps", [])
            if gaps:
                self.analytics_gaps.insert("end", "IDENTIFIED GAPS\n" + "-" * 35 + "\n")
                for gap in gaps[:8]:
                    self.analytics_gaps.insert(
                        "end", "[{}] {} - {}\n".format(
                            gap["opportunity"], gap["category"], gap["type"],
                        ),
                    )

            self.analytics_status.configure(
                text="Done - Top 20 products", text_color=THEME["success"],
            )
        except Exception as e:
            self.analytics_status.configure(
                text=f"Error: {str(e)[:30]}", text_color=THEME["error"],
            )

    # ─── Batch ────────────────────────────────────────────────────

    def _build_batch_tool(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=8)

        ctk.CTkLabel(
            f, text="Enter ASINs (one per line or comma-separated):",
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", pady=(0, 4))
        self.batch_asin_input = ctk.CTkTextbox(
            f, height=80, fg_color=THEME["surface"], font=MONO_FONT,
        )
        self.batch_asin_input.pack(fill="x", pady=(0, 8))
        self.batch_asin_input.insert("1.0", "B0DFFQ9W2S,B0DFWR8QBQ,B0DFV9G6QB,B088FQ3CNF,B0C6MR6NPR")

        btn_frame = ctk.CTkFrame(f, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            btn_frame, text="Lookup", command=self._batch_lookup, width=80, height=28,
            fg_color=THEME["accent"], font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(side="left", padx=4)
        self.batch_status = ctk.CTkLabel(
            btn_frame, text="", font=ctk.CTkFont(size=10), text_color=THEME["text_dim"],
        )
        self.batch_status.pack(side="left", padx=8)

        self.batch_result = ctk.CTkTextbox(
            f, fg_color=THEME["surface"], font=MONO_FONT, wrap="word",
        )
        self.batch_result.pack(fill="both", expand=True)

    def _batch_lookup(self):
        raw = self.batch_asin_input.get("1.0", "end").strip()
        if not raw:
            return
        asins = set()
        for part in raw.replace("\n", ",").split(","):
            asin = part.strip().upper()
            if len(asin) >= 8 and asin.startswith("B"):
                asins.add(asin)
        asins = list(asins)
        if not asins:
            self.batch_status.configure(text="No valid ASINs", text_color=THEME["error"])
            return

        self.batch_status.configure(
            text=f"Looking up {len(asins)}...", text_color=THEME["warning"],
        )
        self.batch_result.delete("1.0", "end")
        self.app.update_idletasks()

        existing = {
            p.get("asin"): p for p in self.app._get_all_products() if p.get("asin")
        }
        found = sum(1 for a in asins if a in existing)
        new = [a for a in asins if a not in existing]

        self.batch_result.insert("end", f"BATCH LOOKUP: {len(asins)} ASINs\n")
        self.batch_result.insert("end", "=" * 40 + "\n\n")
        for asin in asins:
            if asin in existing:
                p = existing[asin]
                self.batch_result.insert(
                    "end", "[FOUND] {} - {}\n".format(asin, p.get("name", p.get("title", ""))[:40]),
                )
                self.batch_result.insert(
                    "end",
                    "  £{:.2f} | Margin: {:.0f}% | AI: {:.0%}\n\n".format(
                        p.get("amazon_price", p.get("price", 0)),
                        p.get("estimated_margin_pct", 0),
                        p.get("ai_score", 0),
                    ),
                )
            else:
                self.batch_result.insert("end", f"[NEW] {asin} - opportunity\n\n")
        self.batch_result.insert(
            "end", f"\nResults: {found} found, {len(new)} new",
        )
        self.batch_status.configure(
            text=f"Done: {found} found, {len(new)} new", text_color=THEME["success"],
        )

    # ─── Notes ────────────────────────────────────────────────────

    def _build_notes_tool(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=8)

        content = ctk.CTkFrame(f, fg_color="transparent")
        content.pack(fill="both", expand=True)

        left = ctk.CTkFrame(content, fg_color=THEME["surface"], corner_radius=8)
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))

        self.notes_search = ctk.CTkEntry(
            left, placeholder_text="Search...", height=28, font=ctk.CTkFont(size=10),
        )
        self.notes_search.pack(fill="x", padx=8, pady=(8, 4))
        self.notes_search.bind("<KeyRelease>", self._filter_notes_list)

        self.notes_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.notes_scroll.pack(fill="both", expand=True, padx=4, pady=4)
        self.notes_list_items = []
        self.notes_file = os.path.join(self.app.data_dir, "product_notes.json")
        self.notes_data = self._load_notes_data()
        self.notes_selected_asin = None
        self._populate_notes_list()

        right = ctk.CTkFrame(content, fg_color=THEME["surface"], corner_radius=8)
        right.pack(side="right", fill="both", expand=True, padx=(4, 0))

        self.notes_product_label = ctk.CTkLabel(
            right, text="Select a product",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["accent"],
        )
        self.notes_product_label.pack(anchor="w", padx=8, pady=4)

        tags_frame = ctk.CTkFrame(right, fg_color="transparent")
        tags_frame.pack(fill="x", padx=8, pady=(0, 4))
        ctk.CTkLabel(tags_frame, text="Tags:", font=ctk.CTkFont(size=9)).pack(side="left")
        for tag in ["HOT", "WATCH", "BUY", "PASS"]:
            ctk.CTkButton(
                tags_frame, text=tag, width=45, height=22,
                font=ctk.CTkFont(size=8, weight="bold"),
                fg_color=THEME["accent"] if tag == "HOT" else THEME["surface_hover"],
                command=lambda t=tag: self._add_tag_to_note(t),
            ).pack(side="left", padx=2)

        self.notes_text = ctk.CTkTextbox(
            right, fg_color=THEME["bg"], font=MONO_FONT, wrap="word",
        )
        self.notes_text.pack(fill="both", expand=True, padx=4, pady=4)

        ctk.CTkButton(
            right, text="Save Notes", command=self._save_notes, width=100, height=28,
            fg_color=THEME["accent"], font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(pady=(4, 8))

    def _load_notes_data(self):
        try:
            if os.path.exists(self.notes_file):
                with open(self.notes_file, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _populate_notes_list(self, filter_text=""):
        for w in self.notes_scroll.winfo_children():
            w.destroy()
        self.notes_list_items = []
        top20 = self.app._get_top20()
        filtered = (
            [p for p in top20 if filter_text.lower() in p.get("name", p.get("title", "")).lower()]
            if filter_text else top20
        )
        for p in filtered:
            asin = p.get("asin", "N/A")
            name = p.get("name", p.get("title", "N/A"))[:40]
            has_notes = "*" if asin in self.notes_data and self.notes_data[asin].get("text") else ""
            btn = ctk.CTkButton(
                self.notes_scroll, text=f"{name}{has_notes}", anchor="w",
                fg_color="transparent", hover_color=THEME["surface_hover"],
                font=ctk.CTkFont(size=10), height=24,
                command=lambda a=asin, n=name: self._select_note_product(a, n),
            )
            btn.pack(fill="x", padx=4, pady=1)

    def _filter_notes_list(self, event=None):
        self._populate_notes_list(self.notes_search.get().strip())

    def _select_note_product(self, asin, name):
        self.notes_selected_asin = asin
        self.notes_product_label.configure(text=f"{name} ({asin})")
        existing = self.notes_data.get(asin, {})
        self.notes_text.delete("1.0", "end")
        tags = existing.get("tags", [])
        text = existing.get("text", "")
        if tags:
            self.notes_text.insert("1.0", "Tags: {}\n\n{}".format(", ".join(tags), text))
        elif text:
            self.notes_text.insert("1.0", text)

    def _add_tag_to_note(self, tag):
        current = self.notes_text.get("1.0", "end").strip()
        if current.startswith("Tags:"):
            lines = current.split("\n")
            existing_tags = [t.strip() for t in lines[0].replace("Tags:", "").split(",") if t.strip()]
            if tag not in existing_tags:
                lines[0] = lines[0] + ", " + tag
                self.notes_text.delete("1.0", "end")
                self.notes_text.insert("1.0", "\n".join(lines))
        else:
            self.notes_text.delete("1.0", "end")
            self.notes_text.insert("1.0", f"Tags: {tag}\n\n{current}")

    def _save_notes(self):
        if not self.notes_selected_asin:
            return
        text = self.notes_text.get("1.0", "end").strip()
        tags = []
        if text.startswith("Tags:"):
            tag_line = text.split("\n")[0].replace("Tags:", "").strip()
            tags = [t.strip() for t in tag_line.split(",") if t.strip()]
            text = "\n".join(text.split("\n")[1:]).strip()
        self.notes_data[self.notes_selected_asin] = {
            "tags": tags,
            "text": text,
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        os.makedirs(self.app.data_dir, exist_ok=True)
        with open(self.notes_file, "w") as f:
            json.dump(self.notes_data, f, indent=2)
        self._populate_notes_list(self.notes_search.get().strip())

    # ─── Team ─────────────────────────────────────────────────────

    def _build_team_tool(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=8)

        ctk.CTkLabel(
            f, text="Team Collaboration",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=THEME["accent"],
        ).pack(anchor="w", pady=(0, 8))

        sel_frame = ctk.CTkFrame(f, fg_color="transparent")
        sel_frame.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            sel_frame, text="Product:", font=ctk.CTkFont(size=11),
            text_color=THEME["text_dim"],
        ).pack(side="left", padx=5)
        self.team_product_var = ctk.StringVar(value="Select product...")
        self.team_product_menu = ctk.CTkOptionMenu(
            sel_frame, variable=self.team_product_var,
            values=["Select product..."], width=280,
            fg_color=THEME["bg_mid"], button_color=THEME["accent"],
        )
        self.team_product_menu.pack(side="left", padx=5)

        def _refresh_team_products():
            top20 = self.app._get_top20()
            names = [
                "{} ({})".format(p.get("name", "Unknown")[:50], p.get("asin", ""))
                for p in top20
            ]
            self.team_product_menu.configure(values=names if names else ["No products"])
            if names:
                self.team_product_var.set(names[0])

        ctk.CTkButton(
            sel_frame, text="Refresh", width=70, fg_color=THEME["info"],
            font=ctk.CTkFont(size=10), corner_radius=5,
            command=_refresh_team_products,
        ).pack(side="left", padx=5)
        _refresh_team_products()

        paned = ctk.CTkFrame(f, fg_color="transparent")
        paned.pack(fill="both", expand=True)

        comments_frame = ctk.CTkFrame(paned, fg_color=THEME["bg_card"], corner_radius=8)
        comments_frame.pack(side="left", fill="both", expand=True, padx=(0, 2))
        ctk.CTkLabel(
            comments_frame, text="Comments",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["accent"],
        ).pack(anchor="w", padx=10, pady=(8, 4))

        self.comments_scroll = ctk.CTkScrollableFrame(
            comments_frame, fg_color="transparent",
            scrollbar_button_color=THEME["border"],
        )
        self.comments_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        comment_entry_frame = ctk.CTkFrame(comments_frame, fg_color="transparent")
        comment_entry_frame.pack(fill="x", padx=8, pady=(0, 8))
        self.comment_entry = ctk.CTkEntry(
            comment_entry_frame, placeholder_text="Add a comment...",
            height=30, font=ctk.CTkFont(size=10),
            border_color=THEME["border"], fg_color=THEME["bg_mid"],
        )
        self.comment_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.comment_entry.bind("<Return>", lambda e: self._add_comment())

        ctk.CTkButton(
            comment_entry_frame, text="Post", width=60, fg_color=THEME["accent"],
            font=ctk.CTkFont(size=10, weight="bold"), corner_radius=5,
            command=self._add_comment,
        ).pack(side="right")

        tasks_frame = ctk.CTkFrame(paned, fg_color=THEME["bg_card"], corner_radius=8)
        tasks_frame.pack(side="left", fill="both", expand=True, padx=(2, 0))
        ctk.CTkLabel(
            tasks_frame, text="Tasks",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["warning"],
        ).pack(anchor="w", padx=10, pady=(8, 4))

        self.tasks_scroll = ctk.CTkScrollableFrame(
            tasks_frame, fg_color="transparent",
            scrollbar_button_color=THEME["border"],
        )
        self.tasks_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        task_entry_frame = ctk.CTkFrame(tasks_frame, fg_color="transparent")
        task_entry_frame.pack(fill="x", padx=8, pady=(0, 8))
        self.task_entry = ctk.CTkEntry(
            task_entry_frame, placeholder_text="Add a task...",
            height=30, font=ctk.CTkFont(size=10),
            border_color=THEME["border"], fg_color=THEME["bg_mid"],
        )
        self.task_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.task_entry.bind("<Return>", lambda e: self._add_task())

        ctk.CTkButton(
            task_entry_frame, text="Add", width=60, fg_color=THEME["warning"],
            text_color="#000", font=ctk.CTkFont(size=10, weight="bold"), corner_radius=5,
            command=self._add_task,
        ).pack(side="right")

        self._load_team_data()

    def _get_team_product_asin(self):
        val = self.team_product_var.get()
        if "(" in val and ")" in val:
            return val.split("(")[-1].rstrip(")")
        top20 = self.app._get_top20()
        return top20[0].get("asin") if top20 else None

    def _add_comment(self):
        asin = self._get_team_product_asin()
        text = self.comment_entry.get().strip()
        if not text or not asin:
            return
        if self.app.db:
            self.app.db.add_comment(asin, "You", text)
        self.comment_entry.delete(0, "end")
        self._load_comments(asin)

    def _add_task(self):
        asin = self._get_team_product_asin()
        text = self.task_entry.get().strip()
        if not text or not asin:
            return
        product_name = ""
        for p in self.app._get_top20():
            if p.get("asin") == asin:
                product_name = p.get("name", p.get("title", ""))
                break
        if self.app.db:
            self.app.db.add_task(asin, product_name, text)
        self.task_entry.delete(0, "end")
        self._load_tasks(asin)

    def _load_team_data(self):
        asin = self._get_team_product_asin()
        if asin:
            self._load_comments(asin)
            self._load_tasks(asin)

    def _load_comments(self, asin):
        for w in self.comments_scroll.winfo_children():
            w.destroy()
        if not self.app.db:
            ctk.CTkLabel(
                self.comments_scroll, text="No database",
                text_color=THEME["text_muted"],
            ).pack(pady=5)
            return
        comments = self.app.db.get_comments(asin)
        if not comments:
            ctk.CTkLabel(
                self.comments_scroll, text="No comments yet",
                text_color=THEME["text_muted"],
            ).pack(pady=5)
            return
        for c in comments:
            row = ctk.CTkFrame(self.comments_scroll, fg_color=THEME["bg_mid"], corner_radius=6)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row, text="{}:".format(c.get("author", "Unknown")),
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=THEME["accent"],
            ).pack(anchor="w", padx=8, pady=(4, 0))
            ctk.CTkLabel(
                row, text=c.get("comment", ""),
                font=ctk.CTkFont(size=10),
                text_color=THEME["text"], wraplength=250, justify="left",
            ).pack(anchor="w", padx=8, pady=(0, 4))

    def _load_tasks(self, asin):
        for w in self.tasks_scroll.winfo_children():
            w.destroy()
        if not self.app.db:
            ctk.CTkLabel(
                self.tasks_scroll, text="No database",
                text_color=THEME["text_muted"],
            ).pack(pady=5)
            return
        tasks = self.app.db.get_tasks(asin)
        if not tasks:
            ctk.CTkLabel(
                self.tasks_scroll, text="No tasks yet",
                text_color=THEME["text_muted"],
            ).pack(pady=5)
            return
        for t in tasks:
            row = ctk.CTkFrame(self.tasks_scroll, fg_color=THEME["bg_mid"], corner_radius=6)
            row.pack(fill="x", pady=2)
            done = t.get("status") == "done"
            status = "\u2705" if done else "\u2b1c"
            task_label = ctk.CTkLabel(
                row, text="{} {}".format(status, t.get("task", "")),
                font=ctk.CTkFont(size=10),
                text_color=THEME["text_muted"] if done else THEME["text"],
                wraplength=250, justify="left",
            )
            task_label.pack(side="left", padx=8, pady=4)

            def _toggle_task(task_id=t.get("id"), current=t.get("status")):
                new_status = "open" if current == "done" else "done"
                if self.app.db:
                    self.app.db.update_task_status(task_id, new_status)
                self._load_tasks(asin)

            ctk.CTkButton(
                row, text="Toggle", width=50, fg_color=THEME["surface"],
                font=ctk.CTkFont(size=9), corner_radius=4,
                command=_toggle_task,
            ).pack(side="right", padx=4, pady=4)

    # ─── Report ───────────────────────────────────────────────────

    def _build_report_tool(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=8)

        ctk.CTkLabel(
            f, text="Custom Report Builder",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=THEME["accent"],
        ).pack(anchor="w", pady=(0, 8))

        sections_frame = ctk.CTkFrame(f, fg_color=THEME["bg_card"], corner_radius=8)
        sections_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(
            sections_frame, text="Report Sections:",
            font=ctk.CTkFont(size=10, weight="bold"), text_color=THEME["text_dim"],
        ).pack(anchor="w", padx=10, pady=(8, 4))

        self.report_checks = {}
        sections = [
            ("exec_summary", "Executive Summary"),
            ("top_products", "Top 20 Products"),
            ("profit_analysis", "Profit Analysis"),
            ("keyword_analysis", "Keyword Analysis"),
            ("supplier_info", "Supplier Information"),
            ("sentiment", "Review Sentiment"),
            ("seasonality", "Seasonality Data"),
            ("competitors", "Competitor Analysis"),
            ("pricing", "Price History"),
            ("charts", "Charts Summary"),
        ]
        checks_frame = ctk.CTkFrame(sections_frame, fg_color="transparent")
        checks_frame.pack(fill="x", padx=10, pady=(0, 8))
        for i, (key, label) in enumerate(sections):
            var = ctk.BooleanVar(value=True)
            self.report_checks[key] = var
            ctk.CTkCheckBox(
                checks_frame, text=label, variable=var,
                font=ctk.CTkFont(size=10), fg_color=THEME["accent"],
            ).grid(row=i // 3, column=i % 3, padx=8, pady=2, sticky="w")

        opts_frame = ctk.CTkFrame(f, fg_color=THEME["bg_card"], corner_radius=8)
        opts_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(
            opts_frame, text="Report Options:",
            font=ctk.CTkFont(size=10, weight="bold"), text_color=THEME["text_dim"],
        ).pack(anchor="w", padx=10, pady=(8, 4))

        opt_row = ctk.CTkFrame(opts_frame, fg_color="transparent")
        opt_row.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(
            opt_row, text="Company Name:", font=ctk.CTkFont(size=10),
            text_color=THEME["text_dim"],
        ).pack(side="left")
        self.report_company = ctk.CTkEntry(
            opt_row, width=200, placeholder_text="Your Company",
            fg_color=THEME["bg_mid"], border_color=THEME["border"],
        )
        self.report_company.pack(side="left", padx=8)
        self.report_company.insert(0, "MarketLens Analysis")

        btn_frame = ctk.CTkFrame(f, fg_color="transparent")
        btn_frame.pack(fill="x", pady=8)
        ctk.CTkButton(
            btn_frame, text="Generate Report", width=150, height=32,
            fg_color=THEME["accent"], font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=6, command=self._generate_custom_report,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            btn_frame, text="Preview", width=100, height=32,
            fg_color=THEME["bg_card"], font=ctk.CTkFont(size=11),
            corner_radius=6, command=self._preview_report,
        ).pack(side="left", padx=5)

        self.report_output = ctk.CTkTextbox(
            f, font=ctk.CTkFont(family="Consolas", size=10),
            fg_color=THEME["bg_card"],
        )
        self.report_output.pack(fill="both", expand=True, pady=5)

    def _preview_report(self):
        top20 = self.app._get_top20()
        if not top20:
            from tkinter import messagebox
            messagebox.showwarning("Warning", "Run analysis first.")
            return

        company = self.report_company.get() or "MarketLens Analysis"
        sections = {k: v.get() for k, v in self.report_checks.items()}

        self.report_output.delete("1.0", "end")
        self.report_output.insert("1.0", "{}\n".format("=" * 60))
        self.report_output.insert("1.0", f"  {company}\n")
        self.report_output.insert("1.0", "  Product Research Report\n")
        self.report_output.insert("1.0", "  Generated: {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M")))
        self.report_output.insert("1.0", "{}\n\n".format("=" * 60))

        if sections.get("exec_summary"):
            self.report_output.insert("end", "EXECUTIVE SUMMARY\n" + "-" * 40 + "\n")
            self.report_output.insert("end", f"Total Products Analyzed: {len(self.app.ideas)}\n")
            green = sum(1 for p in top20 if p.get("traffic_light") == "GREEN")
            self.report_output.insert(
                "end", f"Top 20 Products: {len(top20)} ({green} Green-light)\n",
            )
            avg_score = sum(p.get("ai_score", 0) for p in top20) / max(len(top20), 1)
            self.report_output.insert("end", f"Average AI Score: {avg_score:.0%}\n")
            avg_margin = sum(p.get("estimated_margin_pct", 0) for p in top20) / max(len(top20), 1)
            self.report_output.insert("end", f"Average Margin: {avg_margin:.0f}%\n\n")

        if sections.get("top_products"):
            self.report_output.insert("end", "TOP 20 PRODUCTS\n" + "-" * 40 + "\n")
            for i, p in enumerate(top20, 1):
                self.report_output.insert(
                    "end",
                    "{:2d}. {:35s} £{:>7.2f}  {:>5s}  {}\n".format(
                        i, p.get("name", "")[:35], p.get("amazon_price", 0),
                        "{:.0%}".format(p.get("ai_score", 0)), p.get("traffic_light", ""),
                    ),
                )
            self.report_output.insert("end", "\n")

        if sections.get("profit_analysis"):
            self.report_output.insert("end", "PROFIT ANALYSIS\n" + "-" * 40 + "\n")
            for p in top20:
                self.report_output.insert(
                    "end",
                    "  {:30s} Margin: {:.0f}%\n".format(
                        p.get("name", "")[:30], p.get("estimated_margin_pct", 0),
                    ),
                )
            self.report_output.insert("end", "\n")

        if sections.get("supplier_info"):
            self.report_output.insert("end", "SUPPLIER INFORMATION\n" + "-" * 40 + "\n")
            for p in top20:
                supplier = p.get("supplier_name", "N/A")
                cost = p.get("supplier_price", p.get("estimated_supplier_cost", 0))
                self.report_output.insert(
                    "end",
                    "  {:30s} Supplier: {:20s} Cost: £{:.2f}\n".format(
                        p.get("name", "")[:30], supplier[:20], cost,
                    ),
                )
            self.report_output.insert("end", "\n")

        if sections.get("keyword_analysis"):
            self.report_output.insert("end", "KEYWORD ANALYSIS\n" + "-" * 40 + "\n")
            keywords = getattr(self.app, 'keywords', [])
            for kw in keywords[:10]:
                matches = [p for p in top20 if kw.lower() in p.get("name", p.get("title", "")).lower()]
                self.report_output.insert("end", f"  {kw:20s} -> {len(matches)} products\n")
            self.report_output.insert("end", "\n")

        if sections.get("sentiment"):
            self.report_output.insert("end", "REVIEW SENTIMENT\n" + "-" * 40 + "\n")
            sentiments = getattr(self.app.db, 'get_all_sentiments', lambda: {})()
            if sentiments:
                for asin, data in list(sentiments.items())[:10]:
                    overall = data.get("overall_sentiment", "N/A") if isinstance(data, dict) else "N/A"
                    self.report_output.insert("end", f"  {asin:15s} {overall}\n")
            else:
                self.report_output.insert("end", "  No sentiment data available. Run sentiment analysis first.\n")
            self.report_output.insert("end", "\n")

        if sections.get("seasonality"):
            self.report_output.insert("end", "SEASONALITY DATA\n" + "-" * 40 + "\n")
            seasonality = getattr(self.app.db, 'get_all_seasonality', lambda: {})()
            if seasonality:
                for asin, data in list(seasonality.items())[:10]:
                    pattern = data.get("season_pattern", "N/A") if isinstance(data, dict) else "N/A"
                    peak = data.get("peak_month", "?") if isinstance(data, dict) else "?"
                    self.report_output.insert("end", f"  {asin:15s} {pattern:12s} Peak: month {peak}\n")
            else:
                self.report_output.insert("end", "  No seasonality data. Run AI Seasonality analysis.\n")
            self.report_output.insert("end", "\n")

        if sections.get("competitors"):
            self.report_output.insert("end", "COMPETITOR ANALYSIS\n" + "-" * 40 + "\n")
            competitors = getattr(self.app.db, 'get_all_competitors', lambda: {})()
            if competitors:
                for asin, data in list(competitors.items())[:10]:
                    level = data.get("competition_level", "N/A") if isinstance(data, dict) else "N/A"
                    saturation = data.get("market_saturation", 0) if isinstance(data, dict) else 0
                    self.report_output.insert("end", f"  {asin:15s} {level:12s} Saturation: {saturation}/100\n")
            else:
                self.report_output.insert("end", "  No competitor data. Run AI Competitors analysis.\n")
            self.report_output.insert("end", "\n")

        if sections.get("pricing"):
            self.report_output.insert("end", "PRICE HISTORY\n" + "-" * 40 + "\n")
            for p in top20[:10]:
                asin = p.get("asin", "")
                price = p.get("amazon_price", p.get("price", 0))
                self.report_output.insert("end", f"  {asin:15s} £{price:.2f}  ({p.get('name', '')[:25]})\n")
            self.report_output.insert("end", "\n")

        if sections.get("charts"):
            self.report_output.insert("end", "CHARTS SUMMARY\n" + "-" * 40 + "\n")
            charts = getattr(self.app, 'charts', {})
            if charts:
                for name, path in charts.items():
                    self.report_output.insert("end", f"  {name:25s} {os.path.basename(path)}\n")
            else:
                self.report_output.insert("end", "  No charts generated. Go to Charts tab.\n")
            self.report_output.insert("end", "\n")

        self.report_output.insert(
            "end", "\n{}\nReport generated by MarketLens\n".format("=" * 60),
        )

    def _generate_custom_report(self):
        self._preview_report()
        self.app.status_label.configure(
            text="Report generated \u2014 use Export for PDF", text_color=THEME["success"],
        )
