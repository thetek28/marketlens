import csv
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk

from gui.common import THEME


class ListingTab:
    def __init__(self, tabview, app):
        self.tabview = tabview
        self.app = app
        self.listing_fields = {}
        self._combo_defaults = {}
        self._products_cache = []
        self.listing_output = ""
        self._build()

    def _build(self):
        tab = self.tabview.tab("Listing")
        container = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        top_frame = ctk.CTkFrame(container, fg_color="transparent")
        top_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(top_frame, text="Product:", font=THEME["font"],
                     text_color=THEME["text"]).pack(side="left", padx=(0, 5))
        self.product_selector = ctk.CTkOptionMenu(
            top_frame, values=["(select a product)"],
            command=self._on_listing_product_select, width=350)
        self.product_selector.pack(side="left", padx=(0, 10))
        ctk.CTkButton(top_frame, text="Refresh", width=80,
                      command=self.refresh_selector,
                      **THEME["btn_small"]).pack(side="left")
        self.seo_label = ctk.CTkLabel(top_frame, text="SEO Score: --",
                                       font=THEME["font"], text_color="#FFD700")
        self.seo_label.pack(side="right", padx=10)
        self.refresh_selector()

        def section_header(parent, text, r):
            lbl = ctk.CTkLabel(parent, text=text, font=THEME["font_bold"],
                               text_color=THEME["accent"], anchor="w")
            lbl.grid(column=0, row=r, columnspan=12, sticky="w", padx=8, pady=(6, 2))

        def add_field(parent, label, attr, default, r, col=0, width=250):
            lbl = ctk.CTkLabel(parent, text=label, font=THEME["font"],
                               text_color=THEME["text"], anchor="e")
            lbl.grid(column=col, row=r, padx=5, pady=2, sticky="e")
            entry = ctk.CTkEntry(parent, placeholder_text=default, width=width)
            entry.grid(column=col + 1, row=r, padx=5, pady=2, sticky="w")
            entry.insert(0, default)
            self.listing_fields[attr] = entry
            return entry

        def add_combo(parent, label, attr, values, default, r, col=0, width=160):
            lbl = ctk.CTkLabel(parent, text=label, font=THEME["font"],
                               text_color=THEME["text"], anchor="e")
            lbl.grid(column=col, row=r, padx=5, pady=2, sticky="e")
            combo = ctk.CTkOptionMenu(parent, values=values, width=width)
            combo.set(default)
            combo.grid(column=col + 1, row=r, padx=5, pady=2, sticky="w")
            self.listing_fields[attr] = combo
            self._combo_defaults[attr] = default
            return combo

        def add_textbox(parent, label, attr, default, r, height=60):
            parent.grid_columnconfigure(1, weight=1)
            lbl = ctk.CTkLabel(parent, text=label, font=THEME["font"],
                               text_color=THEME["text"], anchor="e")
            lbl.grid(column=0, row=r, padx=5, pady=2, sticky="e")
            tb = ctk.CTkTextbox(parent, width=500, height=height)
            tb.grid(column=1, row=r, padx=5, pady=3, sticky="w")
            if default:
                tb.insert("1.0", default)
            self.listing_fields[attr] = tb
            return tb

        def add_radio(parent, label, attr, options, default, r, col=0):
            lbl = ctk.CTkLabel(parent, text=label, font=THEME["font"],
                               text_color=THEME["text"], anchor="e")
            lbl.grid(column=col, row=r, padx=5, pady=2, sticky="e")
            var = ctk.StringVar(value=default)
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.grid(column=col + 1, row=r, padx=5, pady=2, sticky="w")
            for opt in options:
                ctk.CTkRadioButton(frame, text=opt, variable=var, value=opt,
                                    font=THEME["font"],
                                    text_color=THEME["text"]).pack(side="left", padx=5)
            self.listing_fields[attr] = var
            return var

        # Section A
        sec_a = ctk.CTkFrame(container, fg_color=THEME["card_bg"], corner_radius=8)
        sec_a.pack(fill="x", pady=5)
        sec_a.columnconfigure(1, weight=1)
        section_header(sec_a, "A. PRODUCT IDENTITY", 0)
        add_field(sec_a, "Item Name:", "item_name", "", 1, 0)
        add_field(sec_a, "Product Type:", "product_type", "", 1, 4)
        add_field(sec_a, "Browse Nodes:", "browse_nodes", "", 2, 0)
        add_field(sec_a, "Variations:", "variations", "", 2, 4)
        add_field(sec_a, "Item Highlight:", "item_highlight", "", 3, 0)
        add_field(sec_a, "Brand Name:", "brand_name", "", 3, 4)
        add_field(sec_a, "External Product ID:", "external_product_id", "", 4, 0)

        # Section B
        sec_b = ctk.CTkFrame(container, fg_color=THEME["card_bg"], corner_radius=8)
        sec_b.pack(fill="x", pady=5)
        sec_b.columnconfigure(1, weight=1)
        section_header(sec_b, "B. DESCRIPTION & MEDIA", 0)
        add_textbox(sec_b, "Product Description:", "product_description", "", 1, 80)
        for i in range(1, 6):
            add_textbox(sec_b, f"Bullet {i}:", f"bullet_{i}", "", i + 1, 50)
        add_field(sec_b, "Main Image URL:", "main_image", "", 7, 0)
        add_field(sec_b, "Other Images (CSV):", "other_images", "", 7, 4)

        # Section C
        sec_c = ctk.CTkFrame(container, fg_color=THEME["card_bg"], corner_radius=8)
        sec_c.pack(fill="x", pady=5)
        sec_c.columnconfigure(1, weight=1)
        section_header(sec_c, "C. PRODUCT DETAILS", 0)
        row = 1
        add_field(sec_c, "Model Number:", "model_number", "", row, 0)
        add_field(sec_c, "Manufacturer:", "manufacturer", "", row, 4)
        row += 1
        add_field(sec_c, "Special Features:", "special_features", "", row, 0)
        add_field(sec_c, "Style:", "style", "", row, 4)
        row += 1
        add_field(sec_c, "Material:", "material", "", row, 0)
        add_field(sec_c, "Number of Items:", "number_of_items", "", row, 4)
        row += 1
        add_field(sec_c, "Colour:", "colour", "", row, 0)
        add_field(sec_c, "Colour Map:", "colour_map", "", row, 4)
        row += 1
        add_field(sec_c, "Size:", "size", "", row, 0)
        add_field(sec_c, "Fits Hole Size:", "fits_hole_size", "", row, 4)
        row += 1
        add_field(sec_c, "Fits Hole Size (Decimal):", "fits_hole_size_decimal", "", row, 0)
        add_combo(sec_c, "Hole Size Unit:", "fits_hole_size_unit",
                  ["inches", "mm", "cm"], "inches", row, 4)
        row += 1
        add_field(sec_c, "Item Depth:", "item_depth", "", row, 0)
        add_field(sec_c, "Finish Type:", "finish_type", "", row, 4)
        row += 1
        add_field(sec_c, "Unit Count:", "unit_count", "", row, 0)
        add_combo(sec_c, "Unit Count Type:", "unit_count_type",
                  ["Count", "Fl Oz", "Pounds", "Ounce"], "Count", row, 4)
        row += 1
        add_radio(sec_c, "Is Fragile:", "is_fragile", ["Yes", "No"], "No", row, 0)
        row += 1
        add_field(sec_c, "Groove Depth:", "compatible_groove_depth", "", row, 0)
        add_combo(sec_c, "Depth Unit:", "groove_depth_unit",
                  ["inches", "mm"], "inches", row, 4)
        row += 1
        add_field(sec_c, "Groove Diameter:", "compatible_groove_diameter", "", row, 0)
        add_combo(sec_c, "Diameter Unit:", "groove_diameter_unit",
                  ["inches", "mm"], "inches", row, 4)
        row += 1
        add_field(sec_c, "Dimensions (W x H):", "item_dimensions_wh", "", row, 0)
        add_field(sec_c, "Item Height:", "item_height", "", row, 4)
        row += 1
        add_combo(sec_c, "Height Unit:", "item_height_unit",
                  ["inches", "mm", "cm"], "inches", row, 0)
        add_field(sec_c, "Item Width:", "item_width", "", row, 4)
        row += 1
        add_combo(sec_c, "Width Unit:", "item_width_unit",
                  ["inches", "mm", "cm"], "inches", row, 0)
        add_field(sec_c, "Number of Packs:", "number_of_packs", "", row, 4)
        row += 1
        add_radio(sec_c, "Green Purchasing:", "green_purchasing",
                  ["Yes", "No"], "No", row, 0)

        # Section D
        sec_d = ctk.CTkFrame(container, fg_color=THEME["card_bg"], corner_radius=8)
        sec_d.pack(fill="x", pady=5)
        sec_d.columnconfigure(1, weight=1)
        section_header(sec_d, "D. OFFER", 0)
        add_field(sec_d, "SKU:", "sku", "", 1, 0)
        add_field(sec_d, "Quantity:", "quantity", "1", 1, 4)
        add_field(sec_d, "Your Price:", "your_price", "", 2, 0)
        add_combo(sec_d, "Item Condition:", "item_condition",
                  ["New", "Used - Like New", "Used - Good", "Refurbished"],
                  "New", 2, 4)
        add_field(sec_d, "List Price (Tax Incl.):", "list_price_tax", "", 3, 0)
        add_combo(sec_d, "Fulfillment:", "fulfillment_channel",
                  ["FBA", "FBM", "Both"], "FBA", 3, 4)
        ctk.CTkLabel(sec_d, text="Package Dimensions", font=THEME["font_bold"],
                     text_color=THEME["accent"], anchor="w").grid(
            column=0, row=4, columnspan=12, sticky="w", padx=8, pady=(6, 2))
        add_field(sec_d, "Pkg Length:", "package_length", "", 5, 0)
        add_combo(sec_d, "Pkg Len Unit:", "package_length_unit",
                  ["inches", "cm"], "inches", 5, 4)
        add_field(sec_d, "Pkg Width:", "package_width", "", 6, 0)
        add_combo(sec_d, "Pkg Wid Unit:", "package_width_unit",
                  ["inches", "cm"], "inches", 6, 4)
        add_field(sec_d, "Pkg Height:", "package_height", "", 7, 0)
        add_combo(sec_d, "Pkg Hgt Unit:", "package_height_unit",
                  ["inches", "cm"], "inches", 7, 4)
        add_field(sec_d, "Pkg Weight:", "package_weight", "", 8, 0)

        # Section E
        sec_e = ctk.CTkFrame(container, fg_color=THEME["card_bg"], corner_radius=8)
        sec_e.pack(fill="x", pady=5)
        sec_e.columnconfigure(1, weight=1)
        section_header(sec_e, "E. SAFETY & COMPLIANCE", 0)
        add_field(sec_e, "Country of Origin:", "country_of_origin", "", 1, 0)
        add_combo(sec_e, "Dangerous Goods:", "dangerous_goods",
                  ["No", "Yes"], "No", 1, 4)

        # Output
        out_frame = ctk.CTkFrame(container, fg_color=THEME["card_bg"], corner_radius=8)
        out_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(out_frame, text="Generated Listing Output",
                      font=THEME["font_bold"],
                      text_color=THEME["accent"]).pack(anchor="w", padx=10, pady=(5, 0))
        self.output_box = ctk.CTkTextbox(out_frame, height=200, width=800)
        self.output_box.pack(fill="x", padx=10, pady=5)

        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)
        ctk.CTkButton(btn_frame, text="GENERATE LISTING",
                       command=self._generate_listing,
                       **THEME["btn_primary"]).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="AI OPTIMIZE",
                       command=self._ai_optimize_listing,
                       **THEME["btn_primary"]).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="COPY LISTING",
                       command=self._copy_listing,
                       **THEME["btn_small"]).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="EXPORT CSV",
                       command=self._export_listing,
                       **THEME["btn_small"]).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="CLEAR ALL",
                       command=self._clear_listing_form,
                       **THEME["btn_small"]).pack(side="left", padx=5)

    def refresh_selector(self):
        self._products_cache = self.app._get_top20()
        names = [p.get("name", p.get("title", "Unknown")) for p in self._products_cache]
        if not names:
            names = ["(no products)"]
        self.product_selector.configure(values=names)
        self.product_selector.set(names[0])

    def _on_listing_product_select(self, selection):
        for p in self._products_cache:
            if p.get("name", p.get("title")) == selection:
                self._auto_fill_listing(p)
                return

    def _auto_fill_listing(self, p):
        seller = p.get("seller_info", {})
        name = p.get("name", p.get("title", ""))
        category = p.get("category", "")

        bullets = self._generate_bullets_from_product(name, category, seller)
        description = self._generate_description_from_product(name, category, seller)

        mapping = {
            "item_name": name,
            "product_type": category,
            "browse_nodes": category,
            "variations": "",
            "item_highlight": seller.get("brand", ""),
            "brand_name": seller.get("brand", ""),
            "external_product_id": p.get("asin", ""),
            "product_description": description,
            "bullet_1": bullets[0] if len(bullets) > 0 else "",
            "bullet_2": bullets[1] if len(bullets) > 1 else "",
            "bullet_3": bullets[2] if len(bullets) > 2 else "",
            "bullet_4": bullets[3] if len(bullets) > 3 else "",
            "bullet_5": bullets[4] if len(bullets) > 4 else "",
            "main_image": p.get("image", ""),
            "other_images": "",
            "model_number": seller.get("manufacturer", ""),
            "manufacturer": seller.get("manufacturer", ""),
            "special_features": seller.get("brand", ""),
            "style": "",
            "material": "",
            "number_of_items": "1",
            "colour": "",
            "colour_map": "",
            "size": "",
            "fits_hole_size": "",
            "fits_hole_size_decimal": "",
            "item_depth": "",
            "finish_type": "",
            "unit_count": "1",
            "compatible_groove_depth": "",
            "compatible_groove_diameter": "",
            "item_dimensions_wh": seller.get("dimensions", ""),
            "item_height": "",
            "item_width": "",
            "number_of_packs": "1",
            "sku": p.get("asin", ""),
            "quantity": "1",
            "your_price": f"£{p.get('amazon_price', 0):.2f}",
            "list_price_tax": f"£{p.get('amazon_price', 0):.2f}",
            "package_length": "",
            "package_width": "",
            "package_height": "",
            "package_weight": seller.get("product_weight", ""),
            "country_of_origin": "",
        }
        combo_map = {
            "fits_hole_size_unit": "inches",
            "unit_count_type": "Count",
            "groove_depth_unit": "inches",
            "groove_diameter_unit": "inches",
            "item_height_unit": "inches",
            "item_width_unit": "inches",
            "item_condition": "New",
            "fulfillment_channel": "FBA" if seller.get("is_fba") else "FBM",
            "package_length_unit": "inches",
            "package_width_unit": "inches",
            "package_height_unit": "inches",
            "dangerous_goods": "No",
        }
        radio_map = {
            "is_fragile": "No",
            "green_purchasing": "No",
        }

        for attr, val in mapping.items():
            w = self.listing_fields.get(attr)
            if w is None:
                continue
            val = str(val) if val is not None else ""
            if isinstance(w, ctk.CTkTextbox):
                w.delete("1.0", "end")
                if val:
                    w.insert("1.0", val)
            else:
                w.delete(0, "end")
                if val:
                    w.insert(0, val)

        for attr, val in combo_map.items():
            w = self.listing_fields.get(attr)
            if w is not None:
                w.set(str(val) if val else "inches")

        for attr, val in radio_map.items():
            w = self.listing_fields.get(attr)
            if w is not None:
                w.set(str(val) if val else "No")

    def _generate_listing(self):
        parts = []
        name = self._get_field_val("item_name")
        if name:
            parts.append(f"Title: {name}")

        desc = self._get_field_val("product_description")
        if desc:
            parts.append(f"\nDescription:\n{desc}")

        for i in range(1, 6):
            b = self._get_field_val(f"bullet_{i}")
            if b:
                parts.append(f"\nBullet {i}: {b}")

        detail_fields = [
            ("product_type", "Product Type"), ("browse_nodes", "Browse Nodes"),
            ("variations", "Variations"), ("item_highlight", "Highlight"),
            ("brand_name", "Brand"), ("external_product_id", "Product ID"),
            ("model_number", "Model"), ("manufacturer", "Manufacturer"),
            ("special_features", "Features"), ("style", "Style"),
            ("material", "Material"), ("number_of_items", "Items"),
            ("colour", "Colour"), ("colour_map", "Colour Map"),
            ("size", "Size"), ("fits_hole_size", "Hole Size"),
            ("item_depth", "Depth"), ("finish_type", "Finish"),
            ("unit_count", "Unit Count"), ("sku", "SKU"),
            ("quantity", "Qty"), ("your_price", "Price"),
            ("list_price_tax", "List Price"), ("country_of_origin", "Origin"),
            ("package_length", "Pkg Length"), ("package_width", "Pkg Width"),
            ("package_height", "Pkg Height"), ("package_weight", "Pkg Weight"),
        ]
        detail_lines = []
        for field, label in detail_fields:
            val = self._get_field_val(field)
            if val:
                detail_lines.append(f"{label}: {val}")
        if detail_lines:
            parts.append("\n\nDetails:")
            parts.extend(detail_lines)

        for field, label in [
            ("item_condition", "Condition"), ("fulfillment_channel", "Fulfillment"),
            ("is_fragile", "Fragile"), ("green_purchasing", "Green Purchasing"),
        ]:
            val = self._get_field_val(field)
            if val:
                parts.append(f"{label}: {val}")

        output = "\n".join(parts)
        self.output_box.delete("1.0", "end")
        self.output_box.insert("1.0", output)
        self.listing_output = output

        score = self._calculate_seo_score(
            self._get_field_val("item_name"),
            "\n".join(self._get_field_val(f"bullet_{i}") for i in range(1, 6) if self._get_field_val(f"bullet_{i}")),
            self._get_field_val("special_features")
        )
        self.seo_label.configure(text=f"SEO Score: {score}/100")

    def _clear_listing_form(self):
        for attr, w in self.listing_fields.items():
            if isinstance(w, ctk.CTkTextbox):
                w.delete("1.0", "end")
            elif isinstance(w, ctk.CTkOptionMenu):
                w.set(self._combo_defaults.get(attr, "inches"))
            elif isinstance(w, ctk.StringVar):
                w.set("No")
            else:
                w.delete(0, "end")
        self.output_box.delete("1.0", "end")
        self.listing_output = None
        self.seo_label.configure(text="SEO Score: --")

    def _export_listing(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Listing"
        )
        if not path:
            return
        listing = self.output_box.get("1.0", "end").strip()
        if not listing:
            messagebox.showwarning("Warning", "Generate a listing first.")
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Field", "Value"])
            for line in listing.split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    writer.writerow([key.strip(), val.strip()])
                elif line.strip():
                    writer.writerow(["", line.strip()])

    def _copy_listing(self):
        listing = self.output_box.get("1.0", "end").strip()
        if listing:
            self.tabview.clipboard_clear()
            self.tabview.clipboard_append(listing)

    def _ai_optimize_listing(self):
        name = self._get_field_val("item_name")
        if not name:
            self.output_box.insert("end", "\n\n[AI] No product name to optimize.")
            return
        self.output_box.insert("end", "\n\n[AI] Optimizing listing...")
        bullets = [self._get_field_val(f"bullet_{i}") for i in range(1, 6)
                   if self._get_field_val(f"bullet_{i}")]
        product_data = {
            "name": name,
            "category": self._get_field_val("product_type"),
            "amazon_price": 0,
            "bullets": bullets,
            "description": self._get_field_val("product_description"),
        }
        threading.Thread(
            target=self._run_ai_optimize,
            args=(product_data,),
            daemon=True
        ).start()

    def _run_ai_optimize(self, product_data):
        try:
            result = self.app.ai_analyzer.optimize_listing(product_data)
        except Exception as e:
            result = {"error": str(e)}
        self.tabview.after(0, self._apply_ai_listing, result)

    def _apply_ai_listing(self, result):
        if isinstance(result, dict) and "error" in result:
            self.output_box.insert("end", f"\n[AI Error] {result['error']}")
            return
        if isinstance(result, dict):
            if "optimized_title" in result:
                self._set_field_val("item_name", result["optimized_title"])
            bullets = result.get("optimized_bullets", result.get("bullets", []))
            if isinstance(bullets, list):
                for i, b in enumerate(bullets[:5], 1):
                    self._set_field_val(f"bullet_{i}", b)
            desc = result.get("optimized_description", result.get("description", ""))
            if desc:
                self._set_field_val("product_description", desc)
            if "backend_keywords" in result:
                self._set_field_val("special_features", result["backend_keywords"])
            self.output_box.insert("end", "\n[AI] Listing optimized successfully.")
        else:
            self.output_box.insert("end", f"\n[AI] Result: {result}")

    def _generate_bullets_from_product(self, name, category, seller):
        brand = seller.get("brand", "")
        brand_str = f" by {brand}" if brand else ""
        cat_str = f" {category.lower()}" if category else ""

        bullets = [
            f"Premium quality {name.lower()} designed for durability and performance.",
            f"Ideal for{cat_str} applications. Easy to install and maintain.",
        ]
        if brand:
            bullets.append(f"Trusted brand: {brand}. Manufactured to the highest standards.")
        else:
            bullets.append("Made from high-grade materials ensuring long-lasting reliability.")

        weight = seller.get("product_weight", "")
        dims = seller.get("dimensions", "")
        if weight or dims:
            spec_parts = []
            if weight:
                spec_parts.append(f"weight: {weight}")
            if dims:
                spec_parts.append(f"dimensions: {dims}")
            bullets.append(f"Product specifications: {', '.join(spec_parts)}. Compact and well-designed.")
        else:
            bullets.append("Compact and well-designed for everyday use.")

        bullets.append("Customer satisfaction guaranteed. 100% quality assurance on every unit.")
        return bullets[:5]

    def _generate_description_from_product(self, name, category, seller):
        brand = seller.get("brand", "")
        cat_str = category.lower() if category else "professional"
        brand_str = f" from {brand}" if brand else ""

        desc = (
            f"Discover the {name}{brand_str} - a top-tier solution engineered for "
            f"{cat_str} use. "
        )
        if brand:
            desc += f"Crafted by {brand}, this product delivers unmatched "
        else:
            desc += "Crafted from premium materials, this product delivers unmatched "
        desc += "reliability and performance. "

        weight = seller.get("product_weight", "")
        dims = seller.get("dimensions", "")
        if weight or dims:
            desc += "Key specifications include "
            spec_parts = []
            if weight:
                spec_parts.append(f"weight of {weight}")
            if dims:
                spec_parts.append(f"dimensions of {dims}")
            desc += ", ".join(spec_parts) + ". "

        desc += (
            f"Whether for everyday use or specialized applications, the {name} "
            f"exceeds expectations. Backed by our quality guarantee."
        )
        return desc

    def _optimize_title(self, name, keywords):
        parts = []
        if keywords:
            parts.append(keywords.split(",")[0].strip())
        parts.append(name)
        title = " - ".join(parts) if len(parts) > 1 else name
        if len(title) > 200:
            title = title[:197] + "..."
        return title

    def _generate_bullets(self, name, keywords, category):
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        bullets = [
            f"Premium quality {name.lower()} designed for durability and performance.",
            f"Ideal for {category.lower() if category else 'various applications'}. Easy to install and maintain.",
            "Made from high-grade materials ensuring long-lasting reliability.",
            f"Features: {', '.join(kw_list[:3]) if kw_list else 'versatile design'}. Meets industry standards.",
            "Customer satisfaction guaranteed. 100% quality assurance on every unit."
        ]
        return bullets[:5]

    def _generate_description(self, name, keywords, category):
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        kw_str = ", ".join(kw_list[:5]) if kw_list else "versatile product"
        desc = (
            f"Discover the {name} - a top-tier solution engineered for "
            f"{category.lower() if category else 'professional'} use. "
            f"Crafted from premium materials, this product delivers unmatched "
            f"reliability and performance. Key features include {kw_str}. "
            f"Whether for everyday use or specialized applications, the {name} "
            f"exceeds expectations. Backed by our quality guarantee."
        )
        return desc

    def _generate_backend_keywords(self, keywords, category):
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        if category:
            kw_list.append(category)
        unique = list(dict.fromkeys(kw_list))
        return ", ".join(unique[:200]) if unique else ""

    def _calculate_seo_score(self, title, bullets, keywords):
        score = 0
        if not title:
            return 0
        if 50 <= len(title) <= 200:
            score += 30
        elif 20 <= len(title) < 50:
            score += 15
        else:
            score += 5
        if keywords and keywords.split(",")[0].strip().lower() in title.lower():
            score += 15
        bullet_list = [b.strip() for b in bullets.split("\n") if b.strip()]
        if len(bullet_list) >= 5:
            score += 25
        elif len(bullet_list) >= 3:
            score += 15
        elif len(bullet_list) >= 1:
            score += 5
        kw_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        if kw_list:
            bullet_text = bullets.lower()
            matches = sum(1 for k in kw_list if k in bullet_text)
            if matches >= 3:
                score += 15
            elif matches >= 1:
                score += 8
        if any(w.isupper() for w in title.split()):
            score += 5
        if any(word in title.lower() for word in ["best", "top", "premium", "professional"]):
            score += 10
        return min(score, 100)

    def _get_field_val(self, key):
        w = self.listing_fields.get(key)
        if w is None:
            return ""
        if isinstance(w, ctk.CTkTextbox):
            return w.get("1.0", "end").strip()
        if isinstance(w, ctk.CTkOptionMenu):
            return w.get()
        if isinstance(w, ctk.StringVar):
            return w.get()
        return w.get().strip()

    def _set_field_val(self, key, val):
        w = self.listing_fields.get(key)
        if w is None:
            return
        val = str(val) if val is not None else ""
        if isinstance(w, ctk.CTkTextbox):
            w.delete("1.0", "end")
            if val:
                w.insert("1.0", val)
        elif isinstance(w, ctk.CTkOptionMenu) or isinstance(w, ctk.StringVar):
            w.set(val)
        else:
            w.delete(0, "end")
            if val:
                w.insert(0, val)
