"""Profits (FBA Fee Calculator) tab for MarketLens."""

from tkinter import messagebox

import customtkinter as ctk

from gui.common import AMAZON_FBA_FEES, AMAZON_REFERRAL_FEES, THEME


class ProfitsTab:
    """FBA fee calculator and profit estimation tab."""

    def __init__(self, tabview, app):
        self.tabview = tabview
        self.app = app
        self._profit_products_map = {}
        self._build()

    def _build(self):
        tab = self.tabview.tab("Profits")

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 5))
        ctk.CTkLabel(
            top, text="Profits - FBA Fee Calculator",
            font=THEME["font_title"],
        ).pack(side="left")
        ctk.CTkLabel(
            top, text="Calculate profit per unit and estimate monthly revenue",
            font=THEME["font_subtitle"], text_color=THEME["text_muted"],
        ).pack(side="left", padx=15)

        sel_frame = ctk.CTkFrame(tab, fg_color=THEME["bg_card"], corner_radius=THEME["corner_radius"])
        sel_frame.pack(fill="x", padx=12, pady=5)
        ctk.CTkLabel(
            sel_frame, text="Select Product:", font=ctk.CTkFont(size=10),
            text_color=THEME["text_dim"],
        ).pack(side="left", padx=(10, 5), pady=6)
        self.profit_product_selector = ctk.CTkComboBox(
            sel_frame, values=["Manual Input"], width=350,
            fg_color=THEME["bg_mid"], border_color=THEME["border"],
            command=self._on_profit_product_select,
        )
        self.profit_product_selector.pack(side="left", padx=5, pady=6)
        self.profit_product_selector.set("Manual Input")

        ctk.CTkButton(
            sel_frame, text="Calculate", width=90, fg_color=THEME["accent"],
            font=ctk.CTkFont(size=11, weight="bold"), corner_radius=6,
            command=self._calculate_profits,
        ).pack(side="right", padx=10, pady=6)
        ctk.CTkButton(
            sel_frame, text="Calc All Products", width=110, fg_color=THEME["success"],
            font=ctk.CTkFont(size=10, weight="bold"), corner_radius=6,
            command=self._calculate_all_profits,
        ).pack(side="right", padx=5, pady=6)
        ctk.CTkButton(
            sel_frame, text="Track Price", width=90, fg_color="#7c3aed",
            hover_color="#6d28d9", font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=6, command=self._track_current_price,
        ).pack(side="right", padx=5, pady=6)
        ctk.CTkButton(
            sel_frame, text="Price History", width=90, fg_color=THEME["info"],
            font=ctk.CTkFont(size=10, weight="bold"), corner_radius=6,
            command=self._show_price_history,
        ).pack(side="right", padx=5, pady=6)
        ctk.CTkButton(
            sel_frame, text="Inventory", width=80, fg_color="#d97706",
            hover_color="#b45309", font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=6, command=self._show_inventory,
        ).pack(side="right", padx=5, pady=6)

        form = ctk.CTkFrame(tab, fg_color=THEME["bg_card"], corner_radius=8)
        form.pack(fill="x", padx=12, pady=5)

        fields = [
            ("Selling Price (£):", "profit_sell_price", "29.99"),
            ("Supplier Cost (£):", "profit_supplier_cost", "8.00"),
            ("Shipping to Amazon (£):", "profit_shipping", "2.50"),
            ("Product Weight (oz):", "profit_weight", "16"),
            ("Product Size:", "profit_size", "small_standard"),
            ("Category:", "profit_category", "default"),
            ("Monthly Units:", "profit_units", "500"),
            ("PPC Spend (%):", "profit_ppc", "15"),
            ("Refund Rate (%):", "profit_refund", "3"),
        ]

        for i, (label, attr, default) in enumerate(fields):
            row = i // 3
            col = (i % 3) * 2
            ctk.CTkLabel(
                form, text=label, font=ctk.CTkFont(size=10),
                text_color=THEME["text_dim"],
            ).grid(row=row, column=col, padx=6, pady=4, sticky="w")
            e = ctk.CTkEntry(
                form, width=90, fg_color=THEME["bg_mid"],
                border_color=THEME["border"],
            )
            e.grid(row=row, column=col + 1, padx=6, pady=4)
            e.insert(0, default)
            setattr(self, attr, e)

        self.profits_output = ctk.CTkTextbox(
            tab, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=THEME["bg_card"], text_color=THEME["text"],
        )
        self.profits_output.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.refresh_selector()

    def refresh_selector(self):
        top20 = self.app._get_top20()
        names = ["Manual Input"] + [
            "{} ({})".format(
                p.get("name", p.get("title", "Unknown"))[:40], p.get("asin", "")
            )
            for p in top20
        ]
        self.profit_product_selector.configure(values=names)
        self._profit_products_map = (
            {names[i + 1]: p for i, p in enumerate(top20)}
            if len(names) > 1
            else {}
        )

    def _on_profit_product_select(self, selection):
        if selection == "Manual Input":
            return
        product = self._profit_products_map.get(selection)
        if not product:
            return
        self.profit_sell_price.delete(0, "end")
        self.profit_sell_price.insert(
            0, str(round(product.get("amazon_price", product.get("price", 29.99)), 2))
        )
        self.profit_supplier_cost.delete(0, "end")
        self.profit_supplier_cost.insert(
            0, str(round(product.get("supplier_price", product.get("estimated_supplier_cost", 8.00)), 2))
        )
        monthly_sales = product.get("seller_info", {}).get("monthly_sales_est", 500)
        self.profit_units.delete(0, "end")
        self.profit_units.insert(0, str(monthly_sales))
        self.profit_category.delete(0, "end")
        self.profit_category.insert(0, product.get("category", "default").lower())

    def _calculate_profits(self):
        try:
            sell = float(self.profit_sell_price.get() or 0)
            supplier = float(self.profit_supplier_cost.get() or 0)
            shipping = float(self.profit_shipping.get() or 0)
            size = self.profit_size.get()
            category = self.profit_category.get()
            units = int(self.profit_units.get() or 500)
            ppc_pct = float(self.profit_ppc.get() or 15)
            refund_pct = float(self.profit_refund.get() or 3)

            fee_info = AMAZON_FBA_FEES.get(size, AMAZON_FBA_FEES["small_standard"])
            referral_pct = AMAZON_REFERRAL_FEES.get(category, AMAZON_REFERRAL_FEES["default"])

            referral_fee = sell * referral_pct
            fulfillment_fee = fee_info["fulfillment"]
            storage_fee = fee_info["storage_per_unit"]
            total_fba_fee = referral_fee + fulfillment_fee + storage_fee

            landed_cost = supplier + shipping
            ppc_cost = sell * (ppc_pct / 100)
            refund_cost = sell * (refund_pct / 100)

            total_cost = landed_cost + total_fba_fee + ppc_cost + refund_cost
            profit_per_unit = sell - total_cost
            margin_pct = (profit_per_unit / sell * 100) if sell > 0 else 0
            roi_pct = (profit_per_unit / landed_cost * 100) if landed_cost > 0 else 0

            monthly_revenue = sell * units
            monthly_profit = profit_per_unit * units
            monthly_fba_fees = total_fba_fee * units

            self.profits_output.delete("1.0", "end")
            self.profits_output.insert("end", "PROFIT ANALYSIS\n" + "=" * 50 + "\n\n")
            self.profits_output.insert("end", f"SELLING PRICE:              £{sell:.2f}\n\n")
            self.profits_output.insert("end", "COST BREAKDOWN:\n")
            self.profits_output.insert("end", f"  Supplier Cost:            £{supplier:.2f}\n")
            self.profits_output.insert("end", f"  Shipping to Amazon:       £{shipping:.2f}\n")
            self.profits_output.insert("end", f"  Landed Cost:              £{landed_cost:.2f}\n")
            self.profits_output.insert("end", "\nAMAZON FEES:\n")
            self.profits_output.insert(
                "end", f"  Referral Fee ({referral_pct * 100:.0f}%):      £{referral_fee:.2f}\n"
            )
            self.profits_output.insert("end", f"  Fulfillment Fee:          £{fulfillment_fee:.2f}\n")
            self.profits_output.insert("end", f"  Storage Fee:              £{storage_fee:.2f}\n")
            self.profits_output.insert("end", f"  Total FBA Fee:            £{total_fba_fee:.2f}\n")
            self.profits_output.insert("end", "\nMARKETING:\n")
            self.profits_output.insert(
                "end", f"  PPC Cost ({ppc_pct:.0f}%):           £{ppc_cost:.2f}\n"
            )
            self.profits_output.insert(
                "end", f"  Refund Cost ({refund_pct:.0f}%):        £{refund_cost:.2f}\n"
            )
            self.profits_output.insert("end", "\n" + "=" * 50 + "\n")
            self.profits_output.insert("end", f"TOTAL COST:                 £{total_cost:.2f}\n")
            self.profits_output.insert("end", f"PROFIT PER UNIT:            £{profit_per_unit:.2f}\n")
            self.profits_output.insert("end", f"MARGIN:                     {margin_pct:.1f}%\n")
            self.profits_output.insert("end", f"ROI:                        {roi_pct:.1f}%\n")
            self.profits_output.insert(
                "end", f"\nMONTHLY PROJECTIONS ({units} units):\n"
            )
            self.profits_output.insert("end", f"  Revenue:                  £{monthly_revenue:,.2f}\n")
            self.profits_output.insert("end", f"  Profit:                   £{monthly_profit:,.2f}\n")
            self.profits_output.insert("end", f"  Amazon Fees:              £{monthly_fba_fees:,.2f}\n")
            self.profits_output.insert(
                "end", f"\n  >>> PROFIT: £{profit_per_unit:.2f}/unit <<<\n"
            )
        except ValueError:
            pass

    def _calculate_all_profits(self):
        products = self.app._get_top20()
        if not products:
            self.profits_output.delete("1.0", "end")
            self.profits_output.insert("end", "No products to analyze. Run analysis first.\n")
            return

        self.profits_output.delete("1.0", "end")
        self.profits_output.insert("end", "PROFIT ESTIMATES - TOP 20 RECOMMENDED\n")
        self.profits_output.insert("end", "=" * 70 + "\n\n")
        self.profits_output.insert(
            "end",
            "{:<4} {:<25} {:<10} {:<10} {:<10} {:<10} {:<8}\n".format(
                "#", "Product", "Price", "Cost", "FBA Fee", "Profit", "Margin"
            ),
        )
        self.profits_output.insert("end", "-" * 70 + "\n")

        total_profit = 0
        total_revenue = 0
        profitable = 0

        for i, p in enumerate(products, 1):
            price = p.get("amazon_price", p.get("price", 0))
            supplier_cost = p.get("supplier_price", p.get("estimated_supplier_cost", price * 0.15))
            shipping = price * 0.03
            landed_cost = supplier_cost + shipping

            fee_info = AMAZON_FBA_FEES.get("small_standard", {})
            referral_fee = price * 0.15
            fulfillment_fee = fee_info.get("fulfillment", 3.22)
            storage_fee = fee_info.get("storage_per_unit", 0.75)
            total_fba = referral_fee + fulfillment_fee + storage_fee

            ppc = price * 0.15
            refund = price * 0.03
            total_cost = landed_cost + total_fba + ppc + refund
            profit = price - total_cost
            margin = (profit / price * 100) if price > 0 else 0

            monthly = p.get("seller_info", {}).get("monthly_sales_est", 300)
            monthly_profit = profit * monthly
            monthly_revenue = price * monthly

            total_profit += monthly_profit
            total_revenue += monthly_revenue
            if profit > 0:
                profitable += 1

            name = p.get("name", p.get("title", ""))[:25]
            color = THEME["success"] if profit > 0 else THEME["danger"]

            self.profits_output.insert(
                "end",
                "{:<4} {:<25} {:<10} {:<10} {:<10} {:<10} {:<8}\n".format(
                    i, name, f"£{price:.2f}", f"£{supplier_cost:.2f}",
                    f"£{total_fba:.2f}", f"£{profit:.2f}",
                    f"{margin:.0f}%",
                ),
            )

        self.profits_output.insert("end", "\n" + "=" * 70 + "\n")
        self.profits_output.insert("end", "\nSUMMARY\n")
        self.profits_output.insert(
            "end", f"Top 20 Products | Profitable: {profitable}\n"
        )
        self.profits_output.insert(
            "end", f"Total Monthly Revenue: £{total_revenue:,.2f}\n"
        )
        self.profits_output.insert(
            "end", f"Total Monthly Profit:  £{total_profit:,.2f}\n"
        )
        self.profits_output.insert(
            "end",
            f"Average Margin:        {(total_profit / total_revenue * 100) if total_revenue > 0 else 0:.1f}%\n",
        )

    def _track_current_price(self):
        sel = self.profit_product_selector.get()
        if sel == "Manual Input":
            messagebox.showwarning("Warning", "Select a product first.")
            return
        product = self._profit_products_map.get(sel)
        if not product:
            return
        asin = product.get("asin", "")
        name = product.get("name", product.get("title", ""))
        price = product.get("amazon_price", product.get("price", 0))
        rating = product.get("rating", 0)
        reviews = product.get("review_count", 0)
        self.app.db.record_price(asin, name, "amazon", price, rating=rating, review_count=reviews)
        self.app.status_label.configure(
            text=f"Price tracked: £{price:.2f} for {name[:30]}",
            text_color=THEME["success"],
        )

    def _show_price_history(self):
        sel = self.profit_product_selector.get()
        if sel == "Manual Input":
            messagebox.showwarning("Warning", "Select a product first.")
            return
        product = self._profit_products_map.get(sel)
        if not product:
            return
        asin = product.get("asin", "")
        name = product.get("name", product.get("title", ""))
        history = self.app.db.get_price_history(asin, limit=50)

        dialog = ctk.CTkToplevel(self.app)
        dialog.title(f"Price History — {name[:40]}")
        dialog.geometry("600x400")
        dialog.configure(fg_color=THEME["bg_dark"])
        dialog.transient(self.app)
        dialog.grab_set()
        try:
            dialog.after(50, dialog.lift)
            dialog.after(100, dialog.focus_force)
        except Exception:
            pass

        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(
            header, text=f"Price History: {name[:50]}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME["accent"],
        ).pack(side="left")
        ctk.CTkLabel(
            header, text=f"ASIN: {asin}",
            font=ctk.CTkFont(size=10),
            text_color=THEME["text_muted"],
        ).pack(side="left", padx=10)

        if not history:
            ctk.CTkLabel(
                dialog,
                text="No price history recorded yet.\nClick 'Track Price' to start recording.",
                font=ctk.CTkFont(size=12), text_color=THEME["text_muted"],
            ).pack(pady=40)
            return

        cols_frame = ctk.CTkFrame(dialog, fg_color=THEME["bg_card"], corner_radius=6)
        cols_frame.pack(fill="x", padx=12, pady=4)
        for col_name, w in [
            ("Date", 140), ("Price", 80), ("Rating", 60),
            ("Reviews", 70), ("Change", 70),
        ]:
            ctk.CTkLabel(
                cols_frame, text=col_name, width=w,
                font=ctk.CTkFont(size=9, weight="bold"),
                text_color=THEME["text_muted"],
            ).pack(side="left", padx=4, pady=4)

        scroll = ctk.CTkScrollableFrame(
            dialog, fg_color="transparent",
            scrollbar_button_color=THEME["border"],
        )
        scroll.pack(fill="both", expand=True, padx=12, pady=4)

        prev_price = None
        for rec in history[:30]:
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(
                row, text=rec["recorded_at"][:16], width=140,
                font=ctk.CTkFont(size=9),
                text_color=THEME["text_dim"],
            ).pack(side="left", padx=4)
            ctk.CTkLabel(
                row, text="£{:.2f}".format(rec["price"]), width=80,
                font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
                text_color=THEME["text"],
            ).pack(side="left", padx=4)
            ctk.CTkLabel(
                row, text="{:.1f}".format(rec.get("rating", 0)), width=60,
                font=ctk.CTkFont(size=9),
                text_color=THEME["warning"],
            ).pack(side="left", padx=4)
            ctk.CTkLabel(
                row, text="{:,}".format(rec.get("review_count", 0)), width=70,
                font=ctk.CTkFont(size=9),
                text_color=THEME["text_dim"],
            ).pack(side="left", padx=4)
            if prev_price and prev_price > 0:
                change = ((rec["price"] - prev_price) / prev_price) * 100
                color = THEME["success"] if change < 0 else THEME["danger"]
                ctk.CTkLabel(
                    row, text=f"{change:+.1f}%", width=70,
                    font=ctk.CTkFont(size=9),
                    text_color=color,
                ).pack(side="left", padx=4)
            prev_price = rec["price"]

    def _show_inventory(self):
        sel = self.profit_product_selector.get()
        if sel == "Manual Input":
            messagebox.showwarning("Warning", "Select a product first.")
            return
        product = self._profit_products_map.get(sel)
        if not product:
            return
        asin = product.get("asin", "")
        name = product.get("name", "Unknown")[:50]

        dialog = ctk.CTkToplevel(self.app)
        dialog.title(f"Inventory — {name[:40]}")
        dialog.geometry("520x480")
        dialog.configure(fg_color=THEME["bg_dark"])
        dialog.transient(self.app)
        dialog.grab_set()
        try:
            dialog.after(50, dialog.lift)
            dialog.after(100, dialog.focus_force)
        except Exception:
            pass

        header = ctk.CTkFrame(dialog, fg_color=THEME["bg_card"], corner_radius=8)
        header.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(
            header, text=f"Inventory Tracker: {name[:45]}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME["accent"],
        ).pack(padx=12, pady=8, anchor="w")

        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(fill="x", padx=12, pady=5)

        inv_fields = {}
        for row_idx, (label, field, default) in enumerate([
            ("Current Stock:", "current_stock", "0"),
            ("Reorder Point:", "reorder_point", "10"),
            ("FBA Status:", "fba_status", "Self-Fulfilled"),
            ("Monthly Sales:", "monthly_sales", "0"),
            ("Lead Time (days):", "lead_time", "14"),
            ("Unit Cost (£):", "unit_cost", "0.00"),
        ]):
            ctk.CTkLabel(
                form, text=label, font=ctk.CTkFont(size=11),
                text_color=THEME["text"], width=120, anchor="e",
            ).grid(row=row_idx, column=0, padx=5, pady=4, sticky="e")
            entry = ctk.CTkEntry(
                form, width=200, placeholder_text=default,
                border_color=THEME["border"], fg_color=THEME["bg_mid"],
            )
            entry.grid(row=row_idx, column=1, padx=5, pady=4, sticky="w")
            inv_fields[field] = entry

        existing_list = self.app.db.get_inventory(asin) if self.app.db else []
        existing_inv = existing_list[0] if existing_list else None
        if existing_inv:
            _FIELD_MAP = {"monthly_sales": "monthly_velocity", "lead_time": "days_of_stock"}
            for field, entry in inv_fields.items():
                db_key = _FIELD_MAP.get(field, field)
                val = existing_inv.get(db_key, "")
                if val and hasattr(entry, "delete") and hasattr(entry, "insert"):
                    entry.delete(0, "end")
                    entry.insert(0, str(val))

        status_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        status_frame.pack(fill="x", padx=12, pady=5)
        status_label = ctk.CTkLabel(
            status_frame, text="", font=ctk.CTkFont(size=10)
        )
        status_label.pack(side="left")

        def _safe_int(val, default=0):
            try:
                return int(val)
            except (TypeError, ValueError):
                return default

        def _safe_float(val, default=0.0):
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        def _save_inv():
            stock = _safe_int(inv_fields["current_stock"].get(), 0)
            reorder = _safe_int(inv_fields["reorder_point"].get(), 10)
            if stock <= reorder:
                status_label.configure(
                    text="Stock below reorder point!", text_color=THEME["warning"]
                )
            else:
                status_label.configure(text="Stock OK", text_color=THEME["success"])
            self.app.db.save_inventory(
                asin=asin,
                product_name=product.get("name", ""),
                data={
                    "current_stock": stock,
                    "reorder_point": reorder,
                    "fba_status": inv_fields["fba_status"].get(),
                    "monthly_velocity": _safe_int(inv_fields["monthly_sales"].get(), 0),
                    "days_of_stock": _safe_int(inv_fields["lead_time"].get(), 14),
                    "unit_cost": _safe_float(inv_fields["unit_cost"].get(), 0),
                },
            )
            self.app._update_status(f"Inventory saved for {name[:30]}")

        save_btn = ctk.CTkButton(
            dialog, text="Save Inventory", fg_color=THEME["success"],
            hover_color="#059669", font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=6, command=_save_inv,
        )
        save_btn.pack(pady=8)

        if existing_inv and existing_inv.get("current_stock", 0) <= existing_inv.get("reorder_point", 10):
            status_label.configure(
                text="Stock below reorder point! Consider reordering.",
                text_color=THEME["warning"],
            )
        elif existing_inv:
            status_label.configure(
                text="Last updated: {}".format(existing_inv.get("updated_at", "N/A")),
                text_color=THEME["text_muted"],
            )
