"""Reusable GUI widgets for MarketLens."""

import tkinter as tk
import webbrowser

import customtkinter as ctk

from gui.common import THEME


class LoadingOverlay(ctk.CTkFrame):
    """Reusable loading overlay with spinner animation."""

    def __init__(self, parent, text="Loading..."):
        super().__init__(parent, fg_color="#0a0e17e0", corner_radius=12)
        self.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.4, relheight=0.15)
        self.lift()
        self._dots = 0
        self._text = text
        ctk.CTkLabel(
            self, text=text,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#3b82f6",
        ).pack(expand=True)
        self._animate()

    def _animate(self):
        self._dots = (self._dots + 1) % 4
        children = self.winfo_children()
        if children:
            children[0].configure(text=self._text + "." * self._dots)
        try:
            self.after(400, self._animate)
        except Exception:
            pass

    def done(self, text="Done!", duration=1500):
        children = self.winfo_children()
        if children:
            children[0].configure(text=text, text_color="#10b981")
        self.after(duration, self.destroy)


def make_copyable(widget, text, app=None):
    """Bind right-click copy and double-click copy to a widget."""

    def _copy():
        if app:
            app.clipboard_clear()
            app.clipboard_append(str(text))
            app.update()
        else:
            widget.clipboard_clear()
            widget.clipboard_append(str(text))
            widget.update()

    def _show_menu(e):
        m = tk.Menu(
            widget, tearoff=0,
            bg=THEME["bg_card"], fg=THEME["text"],
            activebackground=THEME["accent"], activeforeground="#fff",
            font=("Segoe UI", 10),
        )
        m.add_command(label="Copy", command=_copy)
        m.tk_popup(e.x_root, e.y_root)

    widget.bind("<Button-3>", _show_menu)
    widget.bind("<Double-Button-1>", lambda e: _copy())


def build_product_row(parent, product, index, scroll_frame, app=None):
    """Build a single product row in a scrollable frame. Returns the row widget."""
    tl = product.get("traffic_light", "RED")
    tl_colors = {"GREEN": THEME["success"], "YELLOW": THEME["warning"], "RED": THEME["danger"]}
    tc = THEME.get("tier_" + product.get("priority", {}).get("tier", "medium").lower(), THEME["text_dim"])

    bg = THEME["bg_card"] if index % 2 == 0 else THEME["bg_mid"]
    row = ctk.CTkFrame(scroll_frame, fg_color=bg, corner_radius=0, height=28)
    row.pack(fill="x", pady=1)
    row.pack_propagate(False)

    is_gated = product.get("is_gated", product.get("gated", False))
    gating_conf = product.get("gating_confidence", 0)
    gating_level = product.get("gating_level", "")
    gating_reason = product.get("gated_reason", "")

    if is_gated:
        if gating_conf >= 0.8:
            gating_text = f"Gated ({gating_conf:.0%})"
            gating_color = THEME["danger"]
        elif gating_conf >= 0.5:
            gating_text = f"Likely ({gating_conf:.0%})"
            gating_color = THEME["warning"]
        else:
            gating_text = f"Maybe ({gating_conf:.0%})"
            gating_color = THEME["warning"]
    else:
        gating_text = "Ungated"
        gating_color = THEME["success"]

    vals = [
        (str(index), 35, THEME["text_dim"]),
        (product.get("name", product.get("title", ""))[:22], 150, THEME["text"]),
        (product.get("brand_name", "")[:12], 80, THEME["text_dim"]),
        (product.get("category", "")[:10], 60, THEME["text_dim"]),
        ("£{:.2f}".format(product.get("amazon_price", product.get("price", 0))), 50, THEME["text"]),
        ("{:.1f}".format(product.get("rating", 0)), 40, THEME["warning"]),
        ("{:,}".format(product.get("review_count", 0)), 55, THEME["text_dim"]),
        ("{:.0f}%".format(product.get("estimated_margin_pct", 0)), 40, THEME["success"]),
        ("{:.0%}".format(product.get("ai_score", 0)), 35, THEME["info"]),
        (product.get("seller_info", {}).get("seller_name", "N/A")[:10], 70, THEME["text"]),
        (
            "FBA" if product.get("seller_info", {}).get("is_fba") else "FBM",
            40,
            THEME["success"] if product.get("seller_info", {}).get("is_fba") else THEME["warning"],
        ),
        ("{:,}".format(product.get("seller_info", {}).get("monthly_sales_est", 0)), 50, THEME["gold"]),
        ({"GREEN": "EV", "YELLOW": "SE", "RED": "VO"}.get(tl, "N/A"), 40, tl_colors.get(tl, THEME["text_muted"])),
        (product.get("priority", {}).get("tier", ""), 45, tc),
        (gating_text, 55, gating_color),
    ]
    full_name = product.get("name", product.get("title", ""))
    for idx, (val, w, color) in enumerate(vals):
        lbl = ctk.CTkLabel(
            row, text=val, width=w, anchor="w", text_color=color,
            font=ctk.CTkFont(family="Consolas", size=9),
        )
        lbl.pack(side="left", padx=2)
        if idx == 1:
            make_copyable(lbl, full_name, app)

    url = product.get("url", "https://amazon.com/dp/{}".format(product.get("asin", "")))
    ctk.CTkButton(
        row, text="Go", width=35, height=20, fg_color=THEME["accent"],
        font=ctk.CTkFont(size=8), corner_radius=3,
        command=lambda u=url: webbrowser.open(u),
    ).pack(side="left", padx=2)

    return row


def build_column_header(parent, columns=None):
    """Build a column header row."""
    from gui.common import CATEGORY_COLUMNS
    if columns is None:
        columns = CATEGORY_COLUMNS

    hdr = ctk.CTkFrame(parent, fg_color=THEME["bg_mid"], corner_radius=0)
    hdr.pack(fill="x", padx=12, pady=(5, 0))
    for name, w in columns:
        ctk.CTkLabel(
            hdr, text=name, width=w, anchor="w",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=THEME["text_muted"],
        ).pack(side="left", padx=2, pady=5)
    return hdr
