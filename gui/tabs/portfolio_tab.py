"""Portfolio tab for MarketLens."""

import customtkinter as ctk

from gui.common import THEME
from gui.widgets import make_copyable


class PortfolioTab:
    """5-year portfolio strategy tab with summary stats and product cards."""

    def __init__(self, tabview, app):
        self.tabview = tabview
        self.app = app
        self.port_cards = []
        self._build()

    def _build(self):
        tab = self.tabview.tab("Portfolio")
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 5))
        ctk.CTkLabel(
            top, text="5-Year Portfolio Strategy",
            font=THEME["font_title"],
        ).pack(side="left")
        ctk.CTkLabel(
            top, text="Long-term product portfolio planning and forecasting",
            font=THEME["font_subtitle"], text_color=THEME["text_muted"],
        ).pack(side="left", padx=15)

        self.port_scroll = ctk.CTkScrollableFrame(
            tab, fg_color="transparent", scrollbar_button_color=THEME["border"],
        )
        self.port_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.refresh()

    def refresh(self):
        for c in self.port_cards:
            c.destroy()
        self.port_cards.clear()

        if not self.app.ideas:
            lbl = ctk.CTkLabel(
                self.port_scroll,
                text="No products yet. Start analysis to build your portfolio.",
                font=ctk.CTkFont(size=12), text_color=THEME["text_muted"],
            )
            lbl.pack(pady=20)
            self.port_cards.append(lbl)
            return

        top20 = self.app._get_top20()

        # ── Summary stats ──
        summary_frame = ctk.CTkFrame(
            self.port_scroll, fg_color=THEME["bg_card"], corner_radius=THEME["corner_radius"],
        )
        summary_frame.pack(fill="x", padx=4, pady=3)

        green = sum(1 for p in top20 if p.get("traffic_light") == "GREEN")
        yellow = sum(1 for p in top20 if p.get("traffic_light") == "YELLOW")
        red = sum(1 for p in top20 if p.get("traffic_light") == "RED")
        anchor = sum(1 for p in top20 if p.get("portfolio_type") == "ANCHOR")
        growth = sum(1 for p in top20 if p.get("portfolio_type") == "GROWTH")
        balanced = sum(1 for p in top20 if p.get("portfolio_type") == "BALANCED")
        watchlist = sum(1 for p in top20 if p.get("portfolio_type") == "WATCHLIST")
        avg_c = (
            sum(p.get("consistency_score", 0) for p in top20)
            / max(len(top20), 1)
        )
        avg_margin = (
            sum(p.get("estimated_margin_pct", 0) for p in top20)
            / max(len(top20), 1)
        )

        stats = ctk.CTkFrame(summary_frame, fg_color="transparent")
        stats.pack(fill="x", padx=10, pady=8)

        for label, val, color in [
            ("Top 20", len(top20), THEME["text"]),
            ("Evergreen", green, THEME["success"]),
            ("Seasonal", yellow, THEME["warning"]),
            ("Volatile", red, THEME["danger"]),
            ("Anchor", anchor, THEME["accent"]),
            ("Growth", growth, THEME["info"]),
            ("Balanced", balanced, THEME["gold"]),
            ("Watchlist", watchlist, THEME["text_dim"]),
            ("Avg Consistency", f"{avg_c:.0%}", THEME["success"]),
            ("Avg Margin", f"{avg_margin:.0%}", THEME["warning"]),
        ]:
            f = ctk.CTkFrame(stats, fg_color="transparent")
            f.pack(side="left", padx=8)
            ctk.CTkLabel(
                f, text=str(val),
                font=ctk.CTkFont(size=18, weight="bold"), text_color=color,
            ).pack(side="top")
            ctk.CTkLabel(
                f, text=label,
                font=ctk.CTkFont(size=9), text_color=THEME["text_muted"],
            ).pack(side="top")

        self.port_cards.append(summary_frame)

        # ── 5-Year Revenue Forecast Summary ──
        forecast_frame = ctk.CTkFrame(
            self.port_scroll, fg_color=THEME["bg_card"], corner_radius=THEME["corner_radius"],
        )
        forecast_frame.pack(fill="x", padx=4, pady=3)

        ctk.CTkLabel(
            forecast_frame, text="5-Year Revenue Forecast (Top 20 Combined)",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["accent"],
        ).pack(anchor="w", padx=10, pady=(8, 2))

        yearly_totals = {yr: 0 for yr in range(1, 6)}
        for p in top20:
            fc = p.get("forecast", {})
            yf = fc.get("yearly_forecast", [])
            for yr_idx in range(min(5, len(yf))):
                yearly_totals[yr_idx + 1] += yf[yr_idx].get("yearly_total", 0)

        bar_container = ctk.CTkFrame(forecast_frame, fg_color="transparent")
        bar_container.pack(fill="x", padx=10, pady=(0, 8))

        max_rev = max(yearly_totals.values()) if yearly_totals.values() else 1
        bar_colors = [THEME["info"], THEME["accent"], THEME["success"], THEME["warning"], THEME["gold"]]

        for yr in range(1, 6):
            yr_frame = ctk.CTkFrame(bar_container, fg_color="transparent")
            yr_frame.pack(fill="x", pady=1)

            ctk.CTkLabel(
                yr_frame, text=f"Yr {yr}", width=35,
                font=ctk.CTkFont(size=9), text_color=THEME["text_dim"],
            ).pack(side="left")

            bar_width = max(1, int(250 * (yearly_totals[yr] / max_rev)))
            bar = ctk.CTkFrame(yr_frame, height=14, width=bar_width,
                               fg_color=bar_colors[yr - 1], corner_radius=3)
            bar.pack(side="left", padx=(4, 6))
            bar.pack_propagate(False)

            ctk.CTkLabel(
                yr_frame, text=f"£{yearly_totals[yr]:,.0f}",
                font=ctk.CTkFont(size=9, weight="bold"), text_color=THEME["text"],
            ).pack(side="left")

        self.port_cards.append(forecast_frame)

        # ── Product cards ──
        sorted_p = sorted(
            top20, key=lambda x: x.get("consistency_score", 0), reverse=True,
        )
        for i, p in enumerate(sorted_p, 1):
            card = ctk.CTkFrame(
                self.port_scroll, fg_color=THEME["bg_card"], corner_radius=THEME["corner_radius"],
            )
            card.pack(fill="x", padx=4, pady=2)

            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=10, pady=(6, 2))

            ptitle = "#{} {}".format(
                i, p.get("name", p.get("title", ""))[:40],
            )
            plbl = ctk.CTkLabel(
                header, text=ptitle,
                font=ctk.CTkFont(size=11, weight="bold"), anchor="w",
            )
            plbl.pack(side="left")
            make_copyable(plbl, p.get("name", p.get("title", "")), self.app)

            # traffic light badge
            tl = p.get("traffic_light", "")
            tl_color = {"GREEN": THEME["success"], "YELLOW": THEME["warning"], "RED": THEME["danger"]}.get(tl, THEME["text_muted"])
            ctk.CTkLabel(
                header, text=f" {tl} ", font=ctk.CTkFont(size=9, weight="bold"),
                text_color="#fff", fg_color=tl_color, corner_radius=4, padx=4,
            ).pack(side="right", padx=(4, 0))

            # portfolio type badge
            pt = p.get("portfolio_type", "")
            pt_color = {"ANCHOR": THEME["accent"], "GROWTH": THEME["info"],
                        "BALANCED": THEME["gold"], "WATCHLIST": THEME["text_dim"]}.get(pt, THEME["text_muted"])
            ctk.CTkLabel(
                header, text=f" {pt} ", font=ctk.CTkFont(size=9, weight="bold"),
                text_color="#fff", fg_color=pt_color, corner_radius=4, padx=4,
            ).pack(side="right", padx=(4, 0))

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(fill="x", padx=10, pady=(0, 3))

            for label, val, color in [
                ("Consistency:",
                 "{:.0%}".format(p.get("consistency_score", 0)),
                 THEME["success"]),
                ("AI:", "{:.0%}".format(p.get("ai_score", 0)), THEME["info"]),
                ("Margin:", "{:.0%}".format(p.get("estimated_margin_pct", 0) / 100),
                 THEME["warning"]),
                ("Price:", "£{:.2f}".format(p.get("amazon_price", p.get("price", 0))), THEME["text"]),
                ("Reviews:", str(p.get("review_count", 0)), THEME["text_dim"]),
            ]:
                ctk.CTkLabel(
                    info, text=label,
                    font=ctk.CTkFont(size=9), text_color=THEME["text_muted"],
                ).pack(side="left", padx=3)
                ctk.CTkLabel(
                    info, text=val,
                    font=ctk.CTkFont(size=9, weight="bold"), text_color=color,
                ).pack(side="left", padx=(0, 8))

            # 5-year mini forecast
            forecast_row = ctk.CTkFrame(card, fg_color="transparent")
            forecast_row.pack(fill="x", padx=10, pady=(0, 6))

            ctk.CTkLabel(
                forecast_row, text="Forecast:",
                font=ctk.CTkFont(size=9), text_color=THEME["text_muted"],
            ).pack(side="left", padx=(0, 4))

            fc = p.get("forecast", {})
            yf = fc.get("yearly_forecast", [])
            cagr_pct = fc.get("cagr_pct", 0)
            ctk.CTkLabel(
                forecast_row, text=f"CAGR: {cagr_pct:.1f}%",
                font=ctk.CTkFont(size=8, weight="bold"), text_color=THEME["accent"],
            ).pack(side="left", padx=(0, 8))

            for yr_idx in range(min(5, len(yf))):
                yr_data = yf[yr_idx]
                val = yr_data.get("yearly_total", 0)
                ctk.CTkLabel(
                    forecast_row, text=f"Yr{yr_idx + 1}: £{val:,.0f}",
                    font=ctk.CTkFont(size=8), text_color=bar_colors[yr_idx],
                ).pack(side="left", padx=(0, 6))

            self.port_cards.append(card)
