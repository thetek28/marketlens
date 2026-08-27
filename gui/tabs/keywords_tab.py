"""Keywords (SEO) tab for MarketLens."""

import random
import threading

import customtkinter as ctk

from gui.common import THEME


class KeywordsTab:
    """SEO keywords and product solutions tab."""

    def __init__(self, tabview, app):
        self.tabview = tabview
        self.app = app
        self.kw_rows = []
        self._kw_products_map = {}
        self._kw_ready = False
        self._build()

    def _build(self):
        tab = self.tabview.tab("Keywords")
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 5))
        ctk.CTkLabel(
            top, text="SEO Keywords & Product Solutions",
            font=THEME["font_title"],
        ).pack(side="left")
        ctk.CTkLabel(
            top, text="Amazon-optimized keywords + problems each product solves",
            font=THEME["font_subtitle"], text_color=THEME["text_muted"],
        ).pack(side="left", padx=15)

        ctrl = ctk.CTkFrame(tab, fg_color=THEME["bg_card"], corner_radius=THEME["corner_radius"])
        ctrl.pack(fill="x", padx=12, pady=5)
        ctk.CTkLabel(ctrl, text="Select Product:", font=ctk.CTkFont(size=10),
                     text_color=THEME["text_dim"]).pack(side="left", padx=(10, 3))
        self.kw_product_sel = ctk.CTkComboBox(ctrl, values=["All Products"], width=350,
                                               fg_color=THEME["bg_mid"], border_color=THEME["border"],
                                               command=self._on_kw_product_select)
        self.kw_product_sel.pack(side="left", padx=5)
        self.kw_product_sel.set("All Products")
        ctk.CTkButton(ctrl, text="GENERATE SEO", width=110, height=30, fg_color=THEME["accent"],
                      font=ctk.CTkFont(size=11, weight="bold"), corner_radius=6,
                      command=self._run_keyword_analysis).pack(side="left", padx=(15, 5))
        ctk.CTkButton(ctrl, text="COPY ALL", width=80, height=30, fg_color=THEME["success"],
                      font=ctk.CTkFont(size=10, weight="bold"), corner_radius=6,
                      command=self._copy_keywords).pack(side="left", padx=5)
        self.kw_count = ctk.CTkLabel(ctrl, text="", font=ctk.CTkFont(size=10, weight="bold"),
                                     text_color=THEME["accent"])
        self.kw_count.pack(side="right", padx=10)

        self.kw_scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent",
                                                scrollbar_button_color=THEME["border"])
        self.kw_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self._kw_ready = True
        self.refresh_selector()

    def refresh_selector(self):
        if not self._kw_ready:
            return
        top20 = self.app._get_top20()
        names = ["All Products"] + [
            "{} ({})".format(p.get("name", p.get("title", "Unknown"))[:40], p.get("asin", ""))
            for p in top20
        ]
        self.kw_product_sel.configure(values=names)
        self._kw_products_map = {
            names[i + 1]: p for i, p in enumerate(top20)
        } if len(names) > 1 else {}

    def _on_kw_product_select(self, selection):
        if not self._kw_ready:
            return
        self._run_keyword_analysis()

    def _copy_keywords(self):
        text_parts = []
        for w in self.kw_scroll.winfo_children():
            if isinstance(w, ctk.CTkFrame):
                labels = w.winfo_children()
                row_text = " ".join(lbl.cget("text") for lbl in labels if hasattr(lbl, "cget"))
                if row_text.strip():
                    text_parts.append(row_text.strip())
        if text_parts:
            self.app.clipboard_clear()
            self.app.clipboard_append("\n".join(text_parts))

    def _run_keyword_analysis(self):
        for r in self.kw_rows:
            r.destroy()
        self.kw_rows.clear()

        selection = self.kw_product_sel.get()
        if selection == "All Products":
            products = self.app._get_top20()
        else:
            products = [self._kw_products_map.get(selection)] if self._kw_products_map.get(selection) else []
            if not products:
                products = self.app._get_analyzed_products() if self.app.ideas else []

        if not products:
            lbl = ctk.CTkLabel(
                self.kw_scroll, text="No products analyzed yet. Run analysis first.",
                font=ctk.CTkFont(size=12), text_color=THEME["text_muted"],
            )
            lbl.pack(pady=20)
            self.kw_rows.append(lbl)
            return

        loading = ctk.CTkLabel(
            self.kw_scroll, text="Generating SEO keywords...",
            font=ctk.CTkFont(size=12), text_color=THEME["warning"],
        )
        loading.pack(pady=20)
        self.kw_rows.append(loading)
        self.kw_count.configure(text="Processing...")

        def worker():
            results = []
            for p in products:
                try:
                    results.append(self._generate_product_seo_data(p))
                except Exception:
                    pass
            self.app.after(0, lambda: self._display_kw_results(results, len(products)))

        threading.Thread(target=worker, daemon=True).start()

    def _generate_product_seo_data(self, product):
        name = product.get("name", product.get("title", "Product"))
        category = product.get("category", "general")
        asin = product.get("asin", "")
        price = product.get("amazon_price", 0)
        rating = product.get("rating", 0)
        reviews = product.get("review_count", 0)

        title_words = [
            w.lower().strip(",-./()[]{}:;\"'!@#$%^&*+=<>?|\\~`")
            for w in name.split() if len(w) >= 3
        ]
        brand = product.get("seller_info", {}).get("brand", "")
        if brand and brand.lower() not in [w.lower() for w in title_words]:
            title_words.insert(0, brand.lower())

        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "it", "as", "be", "was", "are",
            "this", "that", "not", "no", "so", "if", "up", "out", "do", "has",
            "its", "can", "will", "all", "one", "two", "new", "set", "pk", "pack",
        }
        core_keywords = list(dict.fromkeys([w for w in title_words if w not in stopwords]))[:15]

        long_tail = []
        for kw in core_keywords[:5]:
            modifiers = ["best", "premium", "professional", "high quality", "durable",
                         "portable", "lightweight", "easy to use", "versatile"]
            for mod in random.sample(modifiers, min(3, len(modifiers))):
                long_tail.append(f"{mod} {kw}")
            for qual in ["for home", "for office", "professional grade", "top rated"]:
                long_tail.append(f"{kw} {qual}")

        backend = list(dict.fromkeys(core_keywords + long_tail[:20]))[:250]
        search_terms = list(dict.fromkeys(core_keywords[:10] + long_tail[:10]))[:50]
        problems = self._generate_problems_solutions(name, category, core_keywords)

        return {
            "name": name, "asin": asin, "price": price, "rating": rating,
            "reviews": reviews, "core_keywords": core_keywords, "long_tail": long_tail,
            "backend": backend, "search_terms": search_terms, "problems": problems,
        }

    def _display_kw_results(self, results, total):
        for r in self.kw_rows:
            r.destroy()
        self.kw_rows.clear()

        for data in results:
            self._render_kw_card(data)

        self.kw_count.configure(text=f"{total} products analyzed")

    def _render_kw_card(self, data):
        from gui.widgets import make_copyable

        name = data["name"]
        asin = data["asin"]
        price = data["price"]
        rating = data["rating"]
        reviews = data["reviews"]
        core_keywords = data["core_keywords"]
        long_tail = data["long_tail"]
        backend = data["backend"]
        search_terms = data["search_terms"]
        problems = data["problems"]

        hdr = ctk.CTkFrame(self.kw_scroll, fg_color=THEME["accent"], corner_radius=6, height=32)
        hdr.pack(fill="x", padx=4, pady=(10, 2))
        hdr.pack_propagate(False)
        hdr_lbl = ctk.CTkLabel(
            hdr, text=f"  {name[:55]} ({asin}) - £{price:.2f} | {rating:.1f} stars | {reviews:,} reviews",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#fff",
        )
        hdr_lbl.pack(side="left", padx=8)
        make_copyable(hdr_lbl, name, self.app)

        seo_frame = ctk.CTkFrame(self.kw_scroll, fg_color=THEME["bg_card"], corner_radius=8)
        seo_frame.pack(fill="x", padx=4, pady=2)
        seo_inner = ctk.CTkFrame(seo_frame, fg_color="transparent")
        seo_inner.pack(fill="x", padx=8, pady=6)

        ctk.CTkLabel(seo_inner, text="CORE KEYWORDS:", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=THEME["accent"]).pack(anchor="w")
        kw_lbl = ctk.CTkLabel(seo_inner, text=", ".join(core_keywords[:12]),
                     font=ctk.CTkFont(size=9), text_color=THEME["text"], wraplength=700, justify="left")
        kw_lbl.pack(anchor="w", pady=(0, 4))
        make_copyable(kw_lbl, ", ".join(core_keywords[:12]), self.app)

        ctk.CTkLabel(seo_inner, text="LONG-TAIL KEYWORDS:", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=THEME["success"]).pack(anchor="w")
        for i in range(0, min(12, len(long_tail)), 3):
            chunk = ", ".join(long_tail[i:i + 3])
            chunk_lbl = ctk.CTkLabel(seo_inner, text=chunk, font=ctk.CTkFont(size=9),
                         text_color=THEME["text"], wraplength=700, justify="left")
            chunk_lbl.pack(anchor="w")
            make_copyable(chunk_lbl, chunk, self.app)

        backend_full = ", ".join(backend)
        ctk.CTkLabel(seo_inner, text=f"BACKEND SEARCH TERMS ({len(backend_full)} chars):",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=THEME["warning"]).pack(anchor="w", pady=(4, 0))
        backend_text = backend_full[:499]
        be_lbl = ctk.CTkLabel(seo_inner, text=backend_text, font=ctk.CTkFont(size=9),
                     text_color=THEME["text"], wraplength=700, justify="left")
        be_lbl.pack(anchor="w", pady=(0, 4))
        make_copyable(be_lbl, backend_text, self.app)

        ctk.CTkLabel(seo_inner, text="SEARCH TERMS (Amazon A9):", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=THEME["info"]).pack(anchor="w")
        st_text = ", ".join(search_terms)
        st_lbl = ctk.CTkLabel(seo_inner, text=st_text, font=ctk.CTkFont(size=9),
                     text_color=THEME["text"], wraplength=700, justify="left")
        st_lbl.pack(anchor="w")
        make_copyable(st_lbl, st_text, self.app)

        prob_frame = ctk.CTkFrame(self.kw_scroll, fg_color=THEME["bg_card"], corner_radius=8)
        prob_frame.pack(fill="x", padx=4, pady=2)
        prob_inner = ctk.CTkFrame(prob_frame, fg_color="transparent")
        prob_inner.pack(fill="x", padx=8, pady=6)

        ctk.CTkLabel(prob_inner, text="PROBLEMS THIS PRODUCT SOLVES:", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=THEME["danger"]).pack(anchor="w", pady=(0, 4))

        for i, item in enumerate(problems, 1):
            prob_row = ctk.CTkFrame(prob_inner, fg_color="transparent")
            prob_row.pack(fill="x", pady=1)
            prob_lbl = ctk.CTkLabel(prob_row, text="{}. {}".format(i, item["problem"]),
                         font=ctk.CTkFont(size=9, weight="bold"),
                         text_color=THEME["warning"], width=350, anchor="w")
            prob_lbl.pack(side="left")
            sol_lbl = ctk.CTkLabel(prob_row, text="  -> {}".format(item["solution"]),
                         font=ctk.CTkFont(size=9),
                         text_color=THEME["success"], anchor="w")
            sol_lbl.pack(side="left")
            make_copyable(prob_lbl, item["problem"], self.app)
            make_copyable(sol_lbl, item["solution"], self.app)

        self.kw_rows.append(seo_frame)
        self.kw_rows.append(prob_frame)

    def _generate_problems_solutions(self, name, category, keywords):
        cat = category.lower() if category else ""

        problem_templates = {
            "kitchen": [
                ("Messy countertops cluttering your space", "Organize utensils and gadgets in one compact holder"),
                ("Time-consuming food preparation", "Speed up chopping, slicing, and dicing with multi-function design"),
                ("Inconsistent cooking results", "Precision-engineered for even heat distribution every time"),
                ("Difficult to clean after use", "Dishwasher-safe and non-stick surface for effortless cleanup"),
                ("Storage space running low", "Collapsible and stackable design saves cabinet space"),
                ("Bland meals lacking flavor", "Enhance taste with professional-grade tools and techniques"),
                ("Dangerous knife handling risks", "Safety guard and ergonomic grip prevent accidental cuts"),
                ("Cheap utensils breaking quickly", "Heavy-duty stainless steel construction built to last"),
                ("Measuring inaccurately ruining recipes", "Precision measurements with clear markings for accuracy"),
                ("Kids helping in the kitchen safely", "Child-safe design with rounded edges and non-slip base"),
                ("Outdoor cooking limitations", "Portable design perfect for camping and backyard BBQ"),
                ("Health-conscious cooking needs", "Oil-free cooking options for healthier meals"),
            ],
            "electronics": [
                ("Slow charging wasting valuable time", "Fast-charge technology powers up 3x faster than standard"),
                ("Tangled cables creating desk clutter", "Wireless design eliminates cord mess entirely"),
                ("Poor sound quality on calls", "Built-in noise cancellation for crystal-clear conversations"),
                ("Devices dying mid-day", "Extended battery life lasts up to 24 hours on single charge"),
                ("Compatibility issues with multiple devices", "Universal connectivity works with all major brands"),
                ("Fragile electronics breaking easily", "Military-grade shock absorption protects from drops"),
                ("Overheating during extended use", "Advanced cooling system prevents thermal throttling"),
                ("Small buttons hard to use with gloves", "Oversized controls for easy operation in any condition"),
                ("No waterproof protection for outdoor use", "IPX7 waterproof rating handles rain and splashes"),
                ("Low storage for apps and files", "Expandable memory slot supports up to 1TB additional"),
                ("Poor connectivity in large spaces", "Extended range antenna covers up to 3000 sq ft"),
                ("Difficult setup process", "One-tap pairing gets you connected in under 30 seconds"),
            ],
            "beauty": [
                ("Uneven makeup application", "Precision bristles distribute product evenly across skin"),
                ("Expensive salon visits adding up", "Professional results at home save hundreds yearly"),
                ("Skin irritation from cheap products", "Hypoallergenic materials safe for sensitive skin types"),
                ("Makeup not lasting through the day", "Long-wear formula stays put for 12+ hours"),
                ("Difficulty contouring and blending", "Ergonomic design allows seamless blending technique"),
                ("Travel-friendly makeup storage needed", "Compact carry case keeps everything organized on-the-go"),
                ("Wrinkles and fine lines showing", "Micro-roller stimulates collagen production naturally"),
                ("Dull complexion lacking radiance", "Jade rolling boosts circulation for natural glow"),
                ("Dark circles under eyes persisting", "Cooling massage reduces puffiness and dark circles"),
                ("Acne and blemishes recurring", "Deep cleansing removes impurities from pores"),
                ("Makeup brushes shedding fibers", "Premium synthetic bristles maintain shape wash after wash"),
                ("Cross-contamination from dirty tools", "Antimicrobial coating prevents bacteria buildup"),
            ],
            "home": [
                ("Cluttered rooms looking messy", "Stylish storage solutions keep spaces organized"),
                ("Allergies triggered by dust", "HEPA-grade filters capture 99.9% of airborne particles"),
                ("Dark rooms feeling unwelcoming", "Ambient lighting creates warm inviting atmosphere"),
                ("Unpleasant odors lingering", "Natural essential oil diffusion eliminates unwanted smells"),
                ("Cords and cables everywhere", "Cable management system keeps wires neat and hidden"),
                ("Windows letting in drafts", "Insulated design blocks cold air and reduces energy bills"),
                ("Pet hair covering furniture", "Lint roller and brush combo removes pet hair easily"),
                ("Small spaces feeling cramped", "Multi-functional furniture maximizes available space"),
                ("Home feeling dated and boring", "Modern accent pieces refresh any room instantly"),
                ("Candles burning unevenly", "Centered wick design ensures full melt pool every time"),
                ("Guests noticing musty smells", "Activated charcoal absorbers neutralize odors naturally"),
                ("No organization in bathroom", "Stackable containers maximize vanity counter space"),
            ],
            "fitness": [
                ("Joint pain during workouts", "Low-impact resistance bands reduce stress on joints"),
                ("Gym membership too expensive", "Full-body workout system costs less than one month membership"),
                ("No time to drive to gym", "Compact home gym fits in any room for instant workouts"),
                ("Boring repetitive exercise routines", "15 different resistance levels create endless combinations"),
                ("Poor flexibility causing injuries", "Progressive stretching program improves range of motion"),
                ("Recovery taking too long", "Foam rolling accelerates muscle recovery by 50%"),
                ("Warming up properly before lifting", "Dynamic bands activate muscles safely before heavy sets"),
                ("Rehabilitation after injury slow", "Gradual resistance progression supports physical therapy"),
                ("Home workouts lacking intensity", "Heavy bands simulate real gym equipment resistance"),
                ("Travel disrupting fitness routine", "Lightweight portable bands work anywhere in the world"),
                ("Losing motivation to exercise", "Visual progress tracking keeps you accountable daily"),
                ("Plateau in strength gains", "Progressive overload system breaks through plateaus"),
            ],
        }

        generic_problems = [
            ("Poor product quality causing frustration", "Premium materials ensure reliable long-term performance"),
            ("Overpaying for basic functionality", "Competitive pricing delivers exceptional value for money"),
            ("Complicated setup and installation", "Tool-free assembly gets you running in minutes"),
            ("Products not matching online descriptions", "Verified reviews and accurate images show exactly what you get"),
            ("Warranty claims being denied", "Lifetime warranty covers defects and provides peace of mind"),
            ("Customer service unresponsive", "24/7 support team resolves issues within 24 hours"),
            ("Shipping damage due to poor packaging", "Double-boxed protection ensures safe delivery every time"),
            ("Sizing issues when ordering online", "Universal fit design accommodates 95% of users comfortably"),
            ("Products fading or deteriorating quickly", "UV-resistant and fade-proof materials maintain appearance"),
            ("Not environmentally friendly", "Eco-friendly materials and recyclable packaging reduce waste"),
            ("Difficult to store when not in use", "Compact foldable design minimizes storage footprint"),
            ("Children safety concerns", "CPSC-certified safety standards protect your family"),
        ]

        problems = problem_templates.get(cat, generic_problems)
        selected = random.sample(problems, min(12, len(problems)))

        if len(selected) < 12:
            remaining = [p for p in generic_problems if p not in selected]
            selected.extend(random.sample(remaining, min(12 - len(selected), len(remaining))))

        return [{"problem": p, "solution": s} for p, s in selected[:12]]
