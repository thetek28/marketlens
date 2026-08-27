"""Charts & Analytics Dashboard tab for MarketLens."""

import os
import threading
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

from gui.common import THEME


class ChartsTab:
    """Charts and analytics dashboard tab."""

    def __init__(self, tabview, app):
        self.tabview = tabview
        self.app = app
        self._build()

    def _build(self):
        tab = self.tabview.tab("Charts")
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 5))
        ctk.CTkLabel(
            top, text="Charts & Analytics Dashboard",
            font=THEME["font_title"],
        ).pack(side="left")
        ctk.CTkLabel(
            top, text="Visualize trends, sales data and market insights",
            font=THEME["font_subtitle"], text_color=THEME["text_muted"],
        ).pack(side="left", padx=15)

        btn = ctk.CTkFrame(tab, fg_color="transparent")
        btn.pack(fill="x", padx=12, pady=5)
        ctk.CTkButton(
            btn, text="Generate Charts", width=110, fg_color=THEME["accent"],
            font=ctk.CTkFont(size=10, weight="bold"), corner_radius=6,
            command=self._generate_charts,
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            btn, text="Open Dashboard", width=110, fg_color="transparent",
            border_color=THEME["accent"], border_width=1,
            font=ctk.CTkFont(size=10, weight="bold"), corner_radius=6,
            command=self._open_dashboard,
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            btn, text="AI Seasonality", width=110, fg_color="#7c3aed",
            hover_color="#6d28d9", font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=6, command=self._run_seasonality_analysis,
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            btn, text="AI Competitors", width=110, fg_color="#0891b2",
            hover_color="#0e7490", font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=6, command=self._run_competitor_analysis,
        ).pack(side="left", padx=3)

        self.charts_text = ctk.CTkTextbox(
            tab, font=ctk.CTkFont(family="Consolas", size=10),
            fg_color=THEME["bg_card"],
        )
        self.charts_text.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    def _generate_charts(self):
        top20 = self.app._get_top20()
        if not top20:
            messagebox.showwarning("Warning", "Run analysis first.")
            return
        self.app.charts = self.app.chart_gen.generate_all(top20, self.app.hidden_gems)
        self.charts_text.delete("1.0", "end")
        self.charts_text.insert("end", "CHARTS GENERATED\n" + "=" * 50 + "\n\n")

        self.charts_text.insert("end", "PRICE DISTRIBUTION\n" + "-" * 30 + "\n")
        brackets = {"<£10": 0, "£10-25": 0, "£25-50": 0, "£50-100": 0, "£100+": 0}
        for p in top20:
            price = p.get("amazon_price", p.get("price", 0))
            if price < 10: brackets["<£10"] += 1
            elif price < 25: brackets["£10-25"] += 1
            elif price < 50: brackets["£25-50"] += 1
            elif price < 100: brackets["£50-100"] += 1
            else: brackets["£100+"] += 1
        max_count = max(brackets.values()) or 1
        for label, count in brackets.items():
            bar_len = int(count / max_count * 25) if max_count else 0
            bar = "▓" * bar_len + "░" * (25 - bar_len)
            self.charts_text.insert("end", f"  {label:>8s} |{bar}| {count}\n")
        self.charts_text.insert("end", "\n")

        self.charts_text.insert("end", "AI SCORE DISTRIBUTION\n" + "-" * 30 + "\n")
        score_buckets = {"0.0-0.3": 0, "0.3-0.5": 0, "0.5-0.7": 0, "0.7-0.9": 0, "0.9-1.0": 0}
        for p in top20:
            s = p.get("ai_score", 0)
            if s < 0.3: score_buckets["0.0-0.3"] += 1
            elif s < 0.5: score_buckets["0.3-0.5"] += 1
            elif s < 0.7: score_buckets["0.5-0.7"] += 1
            elif s < 0.9: score_buckets["0.7-0.9"] += 1
            else: score_buckets["0.9-1.0"] += 1
        max_count = max(score_buckets.values()) or 1
        for label, count in score_buckets.items():
            bar_len = int(count / max_count * 25) if max_count else 0
            bar = "▓" * bar_len + "░" * (25 - bar_len)
            self.charts_text.insert("end", f"  {label:>8s} |{bar}| {count}\n")
        self.charts_text.insert("end", "\n")

        self.charts_text.insert("end", "MARGIN DISTRIBUTION\n" + "-" * 30 + "\n")
        margin_buckets = {"<25%": 0, "25-40%": 0, "40-60%": 0, "60%+": 0}
        for p in top20:
            m = p.get("estimated_margin_pct", 0)
            if m < 25: margin_buckets["<25%"] += 1
            elif m < 40: margin_buckets["25-40%"] += 1
            elif m < 60: margin_buckets["40-60%"] += 1
            else: margin_buckets["60%+"] += 1
        max_count = max(margin_buckets.values()) or 1
        for label, count in margin_buckets.items():
            bar_len = int(count / max_count * 25) if max_count else 0
            bar = "▓" * bar_len + "░" * (25 - bar_len)
            self.charts_text.insert("end", f"  {label:>8s} |{bar}| {count}\n")
        self.charts_text.insert("end", "\n")

        if self.app.hidden_gems:
            self.charts_text.insert("end", f"HIDDEN GEMS: {len(self.app.hidden_gems)} found\n" + "-" * 30 + "\n")
            for g in self.app.hidden_gems[:5]:
                self.charts_text.insert("end", f"  {g.get('name', '')[:35]:35s} Score: {g.get('potential_score', 0):.2f}\n")
                for r in g.get("reasons", [])[:2]:
                    self.charts_text.insert("end", f"    -> {r}\n")
            self.charts_text.insert("end", "\n")

        self.charts_text.insert("end", "CHART FILES\n" + "-" * 30 + "\n")
        for name, path in self.app.charts.items():
            self.charts_text.insert("end", f"  {name}: {os.path.basename(path)}\n")
        self.charts_text.insert("end", "\nClick 'Open Dashboard' for interactive HTML charts.\n")

    def _open_dashboard(self):
        path = os.path.join(self.app.chart_gen.output_dir, "dashboard.html")
        if os.path.exists(path):
            webbrowser.open(f"file://{path}")

    def _run_seasonality_analysis(self):
        top20 = self.app._get_top20()
        if not top20:
            messagebox.showwarning("Warning", "Run analysis first.")
            return

        dialog = ctk.CTkToplevel(self.app)
        dialog.title("AI Seasonality Analysis")
        dialog.geometry("650x500")
        dialog.configure(fg_color=THEME["bg_dark"])
        dialog.transient(self.app)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="Select Product:", font=ctk.CTkFont(size=11),
            text_color=THEME["text_dim"],
        ).pack(anchor="w", padx=12, pady=(10, 2))
        sel = ctk.CTkComboBox(
            dialog,
            values=["{} ({})".format(p.get("name", "")[:40], p.get("asin", "")) for p in top20],
            width=550, fg_color=THEME["bg_mid"], border_color=THEME["border"],
        )
        sel.pack(padx=12, pady=4)
        if top20:
            sel.set("{} ({})".format(top20[0].get("name", "")[:40], top20[0].get("asin", "")))

        output = ctk.CTkTextbox(
            dialog, font=ctk.CTkFont(family="Consolas", size=10),
            fg_color=THEME["bg_card"],
        )
        output.pack(fill="both", expand=True, padx=12, pady=8)

        def run():
            from datetime import datetime

            selection = sel.get()
            product = None
            for p in top20:
                label = "{} ({})".format(p.get("name", "")[:40], p.get("asin", ""))
                if label == selection:
                    product = p
                    break
            if not product:
                product = top20[0]

            name = product.get("name", product.get("title", ""))
            category = product.get("category", "")
            history = self.app.db.get_price_history(product.get("asin", ""))

            output.delete("1.0", "end")
            output.insert("1.0", f"Analyzing seasonality for {name}...\n")

            def _do_seasonality():
                try:
                    result = self.app.ai_analyzer.analyze_seasonality(name, category, history)
                    self.app.db.save_seasonality(product.get("asin", ""), name, {
                        "month": datetime.now().month,
                        "demand_level": result.get("season_pattern", "medium"),
                        "peak_month": result.get("peak_months", [11])[0] if result.get("peak_months") else 11,
                        "low_month": result.get("low_months", [1])[0] if result.get("low_months") else 1,
                        "season_pattern": result.get("season_pattern", ""),
                        "notes": result.get("strategy", ""),
                    })
                except Exception as e:
                    result = {"error": str(e)}
                self.app.after(0, _show_seasonality, result)

            def _show_seasonality(result):
                output.delete("1.0", "end")
                if isinstance(result, dict) and "error" in result:
                    output.insert("1.0", "Error: {}\n".format(result["error"]))
                    return
                output.insert("1.0", "SEASONALITY ANALYSIS: {}\n{}\n\n".format(name, "=" * 50))
                output.insert("end", "Pattern: {}\n".format(result.get("season_pattern", "N/A")))
                output.insert("end", "Peak Months: {}\n".format(", ".join(str(m) for m in result.get("peak_months", []))))
                output.insert("end", "Low Months: {}\n".format(", ".join(str(m) for m in result.get("low_months", []))))
                output.insert("end", "Revenue Impact: {}\n\n".format(result.get("revenue_impact", "N/A")))
                output.insert("end", "MONTHLY DEMAND:\n")
                months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                monthly = result.get("monthly_demand", {})
                for m in range(1, 13):
                    level = monthly.get(str(m), monthly.get(m, "medium"))
                    bar_len = {"very_high": 20, "high": 15, "medium": 10, "low": 5, "very_low": 2}.get(level, 10)
                    bar = "\u2588" * bar_len
                    output.insert("end", f"  {months[m - 1]}: {bar} {level}\n")
                output.insert("end", "\nEvents: {}\n".format(", ".join(result.get("events", []))))
                output.insert("end", "\nStrategy:\n{}\n".format(result.get("strategy", "")))

            threading.Thread(target=_do_seasonality, daemon=True).start()

        ctk.CTkButton(
            dialog, text="Run Analysis", width=120, fg_color="#7c3aed",
            hover_color="#6d28d9", font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=6, command=run,
        ).pack(pady=5)

        dialog.after(100, run)

    def _run_competitor_analysis(self):
        top20 = self.app._get_top20()
        if not top20:
            messagebox.showwarning("Warning", "Run analysis first.")
            return

        dialog = ctk.CTkToplevel(self.app)
        dialog.title("AI Competitor Analysis")
        dialog.geometry("700x550")
        dialog.configure(fg_color=THEME["bg_dark"])
        dialog.transient(self.app)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="Select Product:", font=ctk.CTkFont(size=11),
            text_color=THEME["text_dim"],
        ).pack(anchor="w", padx=12, pady=(10, 2))
        sel = ctk.CTkComboBox(
            dialog,
            values=["{} ({})".format(p.get("name", "")[:40], p.get("asin", "")) for p in top20],
            width=600, fg_color=THEME["bg_mid"], border_color=THEME["border"],
        )
        sel.pack(padx=12, pady=4)
        if top20:
            sel.set("{} ({})".format(top20[0].get("name", "")[:40], top20[0].get("asin", "")))

        output = ctk.CTkTextbox(
            dialog, font=ctk.CTkFont(family="Consolas", size=10),
            fg_color=THEME["bg_card"],
        )
        output.pack(fill="both", expand=True, padx=12, pady=8)

        def run():
            selection = sel.get()
            product = None
            for p in top20:
                label = "{} ({})".format(p.get("name", "")[:40], p.get("asin", ""))
                if label == selection:
                    product = p
                    break
            if not product:
                product = top20[0]

            pname = product.get("name", product.get("title", ""))
            category = product.get("category", "")

            output.delete("1.0", "end")
            output.insert("1.0", f"Analyzing competitors for {pname}...\n")

            threading.Thread(
                target=_do_analysis, args=(pname, category), daemon=True
            ).start()

        def _do_analysis(pname, category):
            try:
                result = self.app.ai_analyzer.analyze_competitors(pname, category, [])
            except Exception as e:
                result = {"error": str(e)}
            self.app.after(0, _show_result, pname, result)

        def _show_result(pname, result):
            output.delete("1.0", "end")
            if isinstance(result, dict) and "error" in result:
                output.insert("1.0", "Error: {}\n".format(result["error"]))
                return
            output.insert("1.0", "COMPETITOR ANALYSIS: {}\n{}\n\n".format(pname, "=" * 50))
            output.insert("end", "Competition Level: {}\n".format(result.get("competition_level", "N/A")))
            output.insert("end", "Market Saturation: {}/100\n".format(result.get("market_saturation", 0)))
            output.insert("end", "Pricing Strategy: {}\n".format(result.get("pricing_strategy", "N/A")))
            pr = result.get("recommended_price_range", {})
            output.insert("end", "Price Range: £{:.2f} - £{:.2f}\n\n".format(pr.get("min", 0), pr.get("max", 0)))
            output.insert("end", "COMPETITOR WEAKNESSES:\n")
            for w in result.get("top_competitor_weaknesses", []):
                output.insert("end", f"  \u2022 {w}\n")
            output.insert("end", "\nDIFFERENTIATION OPPORTUNITIES:\n")
            for o in result.get("differentiation_opportunities", []):
                output.insert("end", f"  \u2022 {o}\n")
            output.insert("end", "\nBARRIERS TO ENTRY:\n")
            for b in result.get("barriers_to_entry", []):
                output.insert("end", f"  \u2022 {b}\n")
            output.insert("end", "\n{}\n".format(result.get("market_share_estimate", "")))

        ctk.CTkButton(
            dialog, text="Run Analysis", width=120, fg_color="#0891b2",
            hover_color="#0e7490", font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=6, command=run,
        ).pack(pady=5)

        dialog.after(100, run)
