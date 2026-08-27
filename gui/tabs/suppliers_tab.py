"""Suppliers tab for MarketLens."""

import threading
import webbrowser
from tkinter import filedialog, messagebox

import customtkinter as ctk

from gui.common import THEME
from gui.widgets import make_copyable


class SuppliersTab:
    """Supplier database management and AI quote generation tab."""

    def __init__(self, tabview, app):
        self.tabview = tabview
        self.app = app
        self.supplier_cards = []
        self._build()

    # ── Build ──────────────────────────────────────────────────────

    def _build(self):
        tab = self.tabview.tab("Suppliers")

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 5))
        ctk.CTkLabel(
            top, text="Supplier Database",
            font=THEME["font_title"],
        ).pack(side="left")
        ctk.CTkLabel(
            top, text="Find and manage suppliers for your products",
            font=THEME["font_subtitle"], text_color=THEME["text_muted"],
        ).pack(side="left", padx=15)

        btn = ctk.CTkFrame(tab, fg_color="transparent")
        btn.pack(fill="x", padx=10, pady=3)
        ctk.CTkButton(
            btn, text="Add Supplier", width=100, corner_radius=6,
            fg_color=THEME["accent"],
            command=self._add_supplier,
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            btn, text="Load Pre-Built", width=100, corner_radius=6,
            fg_color=THEME["info"],
            command=self._load_prebuilt_suppliers,
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            btn, text="Import CSV", width=80, corner_radius=6,
            fg_color=THEME["bg_card"],
            command=self._import_suppliers,
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            btn, text="Export CSV", width=80, corner_radius=6,
            fg_color=THEME["bg_card"],
            command=self._export_suppliers,
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            btn, text="Match Products", width=100, corner_radius=6,
            fg_color=THEME["success"],
            command=self._match_products_to_suppliers,
        ).pack(side="left", padx=3)

        self.suppliers_scroll = ctk.CTkScrollableFrame(
            tab, fg_color="transparent",
            scrollbar_button_color=THEME["border"],
        )
        self.suppliers_scroll.pack(fill="both", expand=True, padx=8, pady=5)

        self.refresh()

    # ── Add Supplier Dialog ────────────────────────────────────────

    def _add_supplier(self):
        dialog = ctk.CTkToplevel(self.app)
        dialog.title("Add Supplier")
        dialog.geometry("550x720")
        dialog.configure(fg_color=THEME["bg_dark"])
        dialog.transient(self.app)
        dialog.grab_set()

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        entries = {}
        sections = [
            ("COMPANY INFO", [
                "name", "company_name", "business_type",
                "year_established", "employee_count",
            ]),
            ("LOCATION", ["location", "country", "website"]),
            ("CONTACT", [
                "contact_person", "contact_email", "contact_phone",
                "contact_whatsapp", "contact_wechat",
            ]),
            ("TERMS", [
                "moq", "lead_time_days", "payment_terms",
                "shipping_methods", "certifications",
            ]),
            ("OTHER", ["rating", "notes"]),
        ]

        for section_name, fields in sections:
            ctk.CTkLabel(
                scroll, text=section_name,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=THEME["accent"],
            ).pack(anchor="w", pady=(8, 2))
            for field in fields:
                row = ctk.CTkFrame(scroll, fg_color="transparent")
                row.pack(fill="x", pady=1)
                ctk.CTkLabel(
                    row,
                    text=field.replace("_", " ").title() + ":",
                    width=140, anchor="w",
                    font=ctk.CTkFont(size=10),
                    text_color=THEME["text_dim"],
                ).pack(side="left")
                e = ctk.CTkEntry(
                    row, width=350,
                    fg_color=THEME["bg_card"],
                    border_color=THEME["border"],
                    font=ctk.CTkFont(size=10),
                )
                e.pack(side="left", padx=5)
                entries[field] = e

        def save():
            supplier = {}
            for f, e in entries.items():
                val = e.get().strip()
                if f in ("moq", "lead_time_days", "year_established"):
                    try:
                        val = int(val) if val else 0
                    except ValueError:
                        val = 0
                elif f == "rating":
                    try:
                        val = float(val) if val else 0.0
                    except ValueError:
                        val = 0.0
                supplier[f] = val
            if supplier.get("name"):
                self.app.db.add_supplier(supplier)
                self.refresh()
                dialog.destroy()

        ctk.CTkButton(
            scroll, text="Save Supplier", command=save,
            width=150, fg_color=THEME["success"], corner_radius=6,
        ).pack(pady=15)

    # ── Load Pre-Built Suppliers ───────────────────────────────────

    def _load_prebuilt_suppliers(self):
        from data_collectors.supplier_intel import SupplierDatabase

        existing = {s.get("name") for s in self.app.db.get_all_suppliers()}
        loaded = 0
        for supplier in SupplierDatabase.get_all_suppliers():
            if supplier["name"] not in existing:
                self.app.db.add_supplier(supplier)
                loaded += 1
        self.refresh()
        messagebox.showinfo("Loaded", f"{loaded} pre-built suppliers added.")

    # ── Match Products to Suppliers ────────────────────────────────

    def _match_products_to_suppliers(self):
        if not self.app.ideas:
            messagebox.showinfo("Info", "Run analysis first to have products to match.")
            return

        from data_collectors.supplier_intel import SupplierMatcher

        matcher = SupplierMatcher()
        suppliers = self.app.db.get_all_suppliers()
        if not suppliers:
            self._load_prebuilt_suppliers()
            suppliers = self.app.db.get_all_suppliers()

        top_products = sorted(
            self.app.ideas,
            key=lambda x: x.get("ai_score", 0),
            reverse=True,
        )[:20]

        if hasattr(self, "_match_container") and self._match_container:
            self._match_container.destroy()
            self._match_text = None

        self.suppliers_scroll.pack_forget()

        match_container = ctk.CTkFrame(
            self.tabview.tab("Suppliers"), fg_color="transparent",
        )
        match_container.pack(fill="both", expand=True, padx=8, pady=5)
        self._match_container = match_container

        close_btn = ctk.CTkButton(
            match_container, text="X Close", width=80, height=28,
            fg_color=THEME["danger"], font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=4,
            command=self._close_match_text,
        )
        close_btn.pack(anchor="e", padx=5, pady=(5, 2))

        self._match_text = ctk.CTkTextbox(
            match_container,
            font=ctk.CTkFont(family="Consolas", size=10),
            fg_color=THEME["bg_card"],
        )
        self._match_text.pack(fill="both", expand=True)
        self._match_text.insert("end", "=" * 55 + "\n")
        self._match_text.insert("end", "SUPPLIER MATCHING - TOP 20 PRODUCTS\n")
        self._match_text.insert("end", "=" * 55 + "\n\n")

        for p in top_products:
            try:
                result = matcher.match_product(p, suppliers)
                self._match_text.insert(
                    "end",
                    ">>> {} (ASIN: {})\n".format(
                        p.get("name", p.get("title", "Unknown"))[:45],
                        p.get("asin", ""),
                    ),
                )
                self._match_text.insert(
                    "end",
                    "    Amazon Price: £{:.2f}\n".format(result["amazon_price"]),
                )
                for i, match in enumerate(result["matches"][:3], 1):
                    sup = match["supplier"]
                    prc = match["pricing"]
                    self._match_text.insert(
                        "end",
                        "    #{} {} | Score: {}/100\n".format(
                            i, sup["name"], match["match_score"],
                        ),
                    )
                    self._match_text.insert(
                        "end",
                        "       Cost: £{:.2f} | Margin: {:.0f}% | Profit: £{:.2f}\n".format(
                            prc["unit_cost"], prc["margin_percent"],
                            prc["profit_per_unit"],
                        ),
                    )
                    self._match_text.insert(
                        "end",
                        "       MOQ: {} | Lead: {} days\n".format(
                            prc["moq"], prc["lead_time_days"],
                        ),
                    )
                    contact_parts = []
                    ph = sup.get("contact_phone") or sup.get("phone", "")
                    wa = sup.get("contact_whatsapp") or sup.get("whatsapp", "")
                    em = sup.get("contact_email") or sup.get("email", "")
                    wc = sup.get("contact_wechat", "")
                    if ph:
                        contact_parts.append(f"Ph: {ph}")
                    if wa:
                        contact_parts.append(f"WA: {wa}")
                    if em:
                        contact_parts.append(f"Em: {em}")
                    if wc:
                        contact_parts.append(f"WC: {wc}")
                    if contact_parts:
                        self._match_text.insert(
                            "end", "       {}\n".format(" | ".join(contact_parts)),
                        )
                    co = sup.get("company_name") or sup.get("company", "")
                    if co:
                        self._match_text.insert(
                            "end", f"       Company: {co}\n",
                        )
                    if sup.get("country"):
                        self._match_text.insert(
                            "end", "       Location: {}\n".format(sup["country"]),
                        )
                self._match_text.insert("end", "\n")
            except Exception as e:
                self._match_text.insert(
                    "end",
                    ">>> {} - Error: {}\n\n".format(
                        p.get("name", "Unknown")[:40], str(e)[:50],
                    ),
                )

    # ── CSV Import ─────────────────────────────────────────────────

    def _import_suppliers(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if path:
            count = self.app.db.import_suppliers_from_csv(path)
            self.refresh()
            messagebox.showinfo("Imported", f"{count} suppliers imported.")

    # ── CSV Export ─────────────────────────────────────────────────

    def _export_suppliers(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if path:
            count = self.app.db.export_suppliers_to_csv(path)
            if count > 0:
                messagebox.showinfo("Exported", f"{count} suppliers exported to CSV.")
            else:
                messagebox.showwarning("Warning", "No suppliers to export.")

    # ── Refresh Display ────────────────────────────────────────────

    def refresh(self):
        for c in self.supplier_cards:
            c.destroy()
        self.supplier_cards.clear()

        top20 = self.app._get_top20()

        # Build reverse map: supplier name/company -> list of top20 products
        supplier_to_products = {}
        for p in top20:
            sn = p.get("supplier_name", "").lower()
            sc = p.get("supplier_company", "").lower()
            for key in [sn, sc]:
                if key:
                    if key not in supplier_to_products:
                        supplier_to_products[key] = []
                    supplier_to_products[key].append(p)

        top20_supplier_names = set(supplier_to_products.keys())

        self.app.suppliers = self.app.db.get_all_suppliers()
        if not self.app.suppliers:
            lbl = ctk.CTkLabel(
                self.suppliers_scroll,
                text="No suppliers yet. Click 'Add Supplier' or 'Load Pre-Built'.",
                font=ctk.CTkFont(size=12), text_color=THEME["text_dim"],
            )
            lbl.pack(pady=20)
            self.supplier_cards.append(lbl)
            return

        # Sort: matched suppliers first, then unmatched
        matched = []
        unmatched = []
        for s in self.app.suppliers:
            sname = s.get("name", "").lower()
            scompany = s.get("company_name", "").lower()
            if sname in top20_supplier_names or scompany in top20_supplier_names:
                matched.append(s)
            else:
                unmatched.append(s)

        for s in matched + unmatched:
            card = ctk.CTkFrame(
                self.suppliers_scroll,
                fg_color=THEME["bg_card"], corner_radius=8,
            )
            card.pack(fill="x", padx=4, pady=3)

            hdr = ctk.CTkFrame(card, fg_color="transparent")
            hdr.pack(fill="x", padx=10, pady=(8, 3))

            rating = s.get("rating", 0)
            if rating >= 4.5:
                rating_color = THEME["success"]
            elif rating >= 4.0:
                rating_color = THEME["warning"]
            else:
                rating_color = THEME["text_dim"]

            snamelbl = ctk.CTkLabel(
                hdr, text=s.get("name", "Unknown"),
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=THEME["accent"],
            )
            snamelbl.pack(side="left")
            make_copyable(snamelbl, s.get("name", "Unknown"), self.app)

            ctk.CTkLabel(
                hdr, text=f" [{rating}/5.0] ",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="#000", fg_color=rating_color,
                corner_radius=3, padx=4,
            ).pack(side="left", padx=5)

            delete_btn = ctk.CTkButton(
                hdr, text="X", width=25, height=25,
                fg_color=THEME["danger"],
                font=ctk.CTkFont(size=9, weight="bold"),
                corner_radius=3,
                command=lambda sid=s.get("id"): self._delete_supplier(sid),
            )
            delete_btn.pack(side="right")

            ctk.CTkLabel(
                hdr,
                text="{} | {}".format(
                    s.get("business_type", ""),
                    s.get("company_name", "")[:30],
                ),
                font=ctk.CTkFont(size=10),
                text_color=THEME["text_dim"],
            ).pack(side="right", padx=5)

            make_copyable(
                hdr,
                "{}, {} ({})".format(
                    s.get("name", ""),
                    s.get("company_name", ""),
                    s.get("contact_email", ""),
                ),
                self.app,
            )

            contact_frame = ctk.CTkFrame(
                card, fg_color=THEME["bg_mid"], corner_radius=5,
            )
            contact_frame.pack(fill="x", padx=10, pady=(3, 3))

            cf_row1 = ctk.CTkFrame(contact_frame, fg_color="transparent")
            cf_row1.pack(fill="x", padx=8, pady=(5, 2))
            ctk.CTkLabel(
                cf_row1, text="CONTACT INFO",
                font=ctk.CTkFont(size=8, weight="bold"),
                text_color=THEME["accent"],
            ).pack(side="left")

            cf_row2 = ctk.CTkFrame(contact_frame, fg_color="transparent")
            cf_row2.pack(fill="x", padx=8, pady=1)
            for label, val in [
                ("Contact:", s.get("contact_person", "")),
                ("Email:", s.get("contact_email", s.get("email", ""))),
                ("Phone:", s.get("contact_phone", s.get("phone", ""))),
            ]:
                if val:
                    cf = ctk.CTkFrame(cf_row2, fg_color="transparent")
                    cf.pack(side="left", padx=4)
                    ctk.CTkLabel(
                        cf, text=label,
                        font=ctk.CTkFont(size=7),
                        text_color=THEME["text_muted"],
                    ).pack(side="top")
                    vlbl = ctk.CTkLabel(
                        cf, text=str(val)[:25],
                        font=ctk.CTkFont(size=8, weight="bold"),
                        text_color=THEME["text"],
                    )
                    vlbl.pack(side="top")
                    make_copyable(vlbl, str(val), self.app)

            cf_row3 = ctk.CTkFrame(contact_frame, fg_color="transparent")
            cf_row3.pack(fill="x", padx=8, pady=(1, 5))
            for label, val in [
                ("WhatsApp:", s.get("contact_whatsapp", s.get("whatsapp", ""))),
                ("WeChat:", s.get("contact_wechat", "")),
                ("Location:", "{}, {}".format(
                    s.get("location", ""), s.get("country", ""),
                )),
            ]:
                if val:
                    cf = ctk.CTkFrame(cf_row3, fg_color="transparent")
                    cf.pack(side="left", padx=4)
                    ctk.CTkLabel(
                        cf, text=label,
                        font=ctk.CTkFont(size=7),
                        text_color=THEME["text_muted"],
                    ).pack(side="top")
                    vlbl2 = ctk.CTkLabel(
                        cf, text=str(val)[:25],
                        font=ctk.CTkFont(size=8, weight="bold"),
                        text_color=THEME["info"],
                    )
                    vlbl2.pack(side="top")
                    make_copyable(vlbl2, str(val), self.app)

            # ── Matched Top 20 Products ─────────────────────────
            sname = s.get("name", "").lower()
            scompany = s.get("company_name", "").lower()
            matched_products = supplier_to_products.get(sname, []) or supplier_to_products.get(scompany, [])

            products_frame = ctk.CTkFrame(card, fg_color=THEME["bg_mid"], corner_radius=5)
            products_frame.pack(fill="x", padx=10, pady=(3, 3))

            pf_hdr = ctk.CTkFrame(products_frame, fg_color="transparent")
            pf_hdr.pack(fill="x", padx=8, pady=(5, 2))
            ctk.CTkLabel(
                pf_hdr,
                text=f"TOP 20 MATCHED PRODUCTS ({len(matched_products)})",
                font=ctk.CTkFont(size=8, weight="bold"),
                text_color=THEME["success"] if matched_products else THEME["text_dim"],
            ).pack(side="left")

            if matched_products:
                for i, p in enumerate(matched_products[:5]):
                    pf_row = ctk.CTkFrame(products_frame, fg_color="transparent")
                    pf_row.pack(fill="x", padx=8, pady=1)

                    pname = p.get("name", p.get("title", "Unknown"))[:40]
                    price = p.get("amazon_price", p.get("price", 0))
                    supplier_cost = p.get("supplier_cost", 0)
                    margin = p.get("margin_pct", p.get("margin", 0))

                    ctk.CTkLabel(
                        pf_row, text=f"{i + 1}. {pname}",
                        font=ctk.CTkFont(size=8, weight="bold"),
                        text_color=THEME["text"],
                    ).pack(side="left", padx=(0, 8))

                    if supplier_cost:
                        ctk.CTkLabel(
                            pf_row, text=f"Cost: £{supplier_cost:.2f}",
                            font=ctk.CTkFont(size=7),
                            text_color=THEME["warning"],
                        ).pack(side="left", padx=3)

                    if margin:
                        ctk.CTkLabel(
                            pf_row, text=f"Margin: {margin:.0f}%",
                            font=ctk.CTkFont(size=7),
                            text_color=THEME["success"] if margin >= 30 else THEME["warning"],
                        ).pack(side="left", padx=3)

                    if price:
                        ctk.CTkLabel(
                            pf_row, text=f"Sell: £{price:.2f}",
                            font=ctk.CTkFont(size=7),
                            text_color=THEME["info"],
                        ).pack(side="left", padx=3)

                if len(matched_products) > 5:
                    ctk.CTkLabel(
                        products_frame,
                        text=f"... and {len(matched_products) - 5} more",
                        font=ctk.CTkFont(size=7),
                        text_color=THEME["text_dim"],
                    ).pack(anchor="w", padx=8, pady=(2, 4))
            else:
                ctk.CTkLabel(
                    products_frame,
                    text="No top 20 products currently matched to this supplier",
                    font=ctk.CTkFont(size=8),
                    text_color=THEME["text_dim"],
                ).pack(anchor="w", padx=8, pady=4)

            terms_frame = ctk.CTkFrame(card, fg_color="transparent")
            terms_frame.pack(fill="x", padx=10, pady=(0, 8))

            for label, val, color in [
                ("MOQ:", str(s.get("moq", 0)), THEME["warning"]),
                ("Lead:", "{}d".format(s.get("lead_time_days", 0)), THEME["text"]),
                ("Payment:", s.get("payment_terms", "")[:15], THEME["text_dim"]),
                ("Shipping:", s.get("shipping_methods", "")[:15], THEME["text_dim"]),
                ("Since:", str(s.get("year_established", "")), THEME["text_dim"]),
                ("Staff:", s.get("employee_count", ""), THEME["text_dim"]),
            ]:
                if val:
                    tf = ctk.CTkFrame(terms_frame, fg_color="transparent")
                    tf.pack(side="left", padx=5)
                    ctk.CTkLabel(
                        tf, text=label,
                        font=ctk.CTkFont(size=7),
                        text_color=THEME["text_muted"],
                    ).pack(side="top")
                    ctk.CTkLabel(
                        tf, text=str(val),
                        font=ctk.CTkFont(size=8, weight="bold"),
                        text_color=color,
                    ).pack(side="top")

            if s.get("certifications"):
                cert_frame = ctk.CTkFrame(card, fg_color="transparent")
                cert_frame.pack(fill="x", padx=10, pady=(0, 5))
                for cert in s.get("certifications", "").split(",")[:5]:
                    cert = cert.strip()
                    if cert:
                        ctk.CTkLabel(
                            cert_frame, text=f" {cert} ",
                            font=ctk.CTkFont(size=7, weight="bold"),
                            text_color="#000", fg_color=THEME["success"],
                            corner_radius=2, padx=3,
                        ).pack(side="left", padx=2)

            quote_row = ctk.CTkFrame(card, fg_color="transparent")
            quote_row.pack(fill="x", padx=10, pady=(0, 6))
            ctk.CTkButton(
                quote_row, text="AI Generate Quote Email",
                width=160, height=24,
                fg_color="#7c3aed", hover_color="#6d28d9",
                font=ctk.CTkFont(size=9, weight="bold"),
                corner_radius=4,
                command=lambda s=s: self._generate_supplier_quote(s),
            ).pack(side="left")

            self.supplier_cards.append(card)

    # ── Delete Supplier ────────────────────────────────────────────

    def _close_match_text(self):
        if hasattr(self, "_match_container") and self._match_container:
            self._match_container.destroy()
            self._match_container = None
            self._match_text = None
        self.suppliers_scroll.pack(fill="both", expand=True, padx=8, pady=5)

    def _delete_supplier(self, supplier_id):
        if messagebox.askyesno("Delete", "Delete this supplier?"):
            self.app.db.delete_supplier(supplier_id)
            self.refresh()

    # ── AI Generate Supplier Quote ─────────────────────────────────

    def _generate_supplier_quote(self, supplier):
        top20 = self.app._get_top20()
        product = top20[0] if top20 else {
            "name": "Product", "category": "General", "amazon_price": 0,
        }

        self.app.status_label.configure(
            text="Generating quote for {}...".format(supplier.get("name", "")[:30]),
            text_color=THEME["warning"],
        )

        def run():
            try:
                result = self.app.ai_analyzer.generate_supplier_quote(
                    product, supplier,
                )
                self.app.after(
                    0,
                    lambda r=result, s=supplier: self._show_quote_result(r, s),
                )
                self.app.after(
                    0,
                    lambda: self.app.status_label.configure(
                        text="Quote generated", text_color=THEME["success"],
                    ),
                )
            except Exception as e:
                self.app.after(
                    0,
                    lambda e=e: self.app.status_label.configure(
                        text=f"Quote failed: {e}",
                        text_color=THEME["danger"],
                    ),
                )

        threading.Thread(target=run, daemon=True).start()

    # ── Show Quote Result ──────────────────────────────────────────

    def _show_quote_result(self, result, supplier):
        dialog = ctk.CTkToplevel(self.app)
        dialog.title("Quote — {}".format(supplier.get("name", "")[:40]))
        dialog.geometry("700x550")
        dialog.configure(fg_color=THEME["bg_dark"])
        dialog.transient(self.app)
        dialog.grab_set()

        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(
            header,
            text="Supplier Quote: {}".format(supplier.get("name", "")),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME["accent"],
        ).pack(side="left")

        email = supplier.get("contact_email", "")
        if email:
            ctk.CTkButton(
                header, text="Open Email Client",
                width=130, height=26,
                fg_color=THEME["success"],
                font=ctk.CTkFont(size=10, weight="bold"),
                corner_radius=5,
                command=lambda: webbrowser.open(
                    "mailto:{}?subject={}".format(
                        email, result.get("subject", ""),
                    ),
                ),
            ).pack(side="right")

        scroll = ctk.CTkScrollableFrame(
            dialog, fg_color="transparent",
            scrollbar_button_color=THEME["border"],
        )
        scroll.pack(fill="both", expand=True, padx=12, pady=4)

        ctk.CTkLabel(
            scroll, text="SUBJECT:",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=THEME["accent"],
        ).pack(anchor="w", pady=(4, 2))
        subj = ctk.CTkLabel(
            scroll, text=result.get("subject", ""),
            font=ctk.CTkFont(size=11),
            text_color=THEME["text"], wraplength=650, justify="left",
        )
        subj.pack(anchor="w")
        make_copyable(subj, result.get("subject", ""), self.app)

        ctk.CTkLabel(
            scroll, text="EMAIL BODY:",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=THEME["accent"],
        ).pack(anchor="w", pady=(10, 2))
        body = ctk.CTkLabel(
            scroll, text=result.get("body", ""),
            font=ctk.CTkFont(size=10),
            text_color=THEME["text"], wraplength=650, justify="left",
        )
        body.pack(anchor="w")
        make_copyable(body, result.get("body", ""), self.app)

        follow_up = result.get("follow_up", "")
        if follow_up:
            ctk.CTkLabel(
                scroll, text="FOLLOW-UP (3 days later):",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=THEME["warning"],
            ).pack(anchor="w", pady=(10, 2))
            fu = ctk.CTkLabel(
                scroll, text=follow_up,
                font=ctk.CTkFont(size=10),
                text_color=THEME["text"], wraplength=650, justify="left",
            )
            fu.pack(anchor="w")
            make_copyable(fu, follow_up, self.app)

        questions = result.get("key_questions", [])
        if questions:
            ctk.CTkLabel(
                scroll, text="KEY QUESTIONS TO ASK:",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=THEME["info"],
            ).pack(anchor="w", pady=(10, 2))
            for q in questions:
                ctk.CTkLabel(
                    scroll, text=f"  \u2022 {q}",
                    font=ctk.CTkFont(size=10),
                    text_color=THEME["text"], wraplength=650, justify="left",
                ).pack(anchor="w", pady=1)

        def copy_all():
            text = "Subject: {}\n\n{}\n\nFollow-up: {}".format(
                result.get("subject", ""),
                result.get("body", ""),
                follow_up,
            )
            self.app.clipboard_clear()
            self.app.clipboard_append(text)
            self.app.update()
            self.app.status_label.configure(
                text="Quote copied to clipboard",
                text_color=THEME["success"],
            )

        ctk.CTkButton(
            scroll, text="Copy All to Clipboard",
            width=160, height=28,
            fg_color=THEME["accent"],
            font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=5, command=copy_all,
        ).pack(pady=8)
