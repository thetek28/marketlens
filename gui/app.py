"""MarketLens - AI-Powered Amazon Product Research
Thin orchestrator that delegates to modular tab classes.
"""

import json
import math
import os
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.dirname(sys.executable))
else:
    BASE_DIR = str(Path(__file__).parent.parent)

sys.path.insert(0, BASE_DIR)

from analyzers.ai_analyzer import AIAnalyzer
from calculators.profit import ProfitCalculator
from charts.generator import ChartGenerator
from data_collectors.multi_pricing import MultiSourcePricing
from database.manager import DatabaseManager
from gui.activation_dialog import ActivationDialog
from gui.common import CYCLE_INTERVAL_MINUTES, DEFAULT_CATEGORIES, THEME
from gui.tabs import (
    ChartsTab,
    KeywordsTab,
    ListingTab,
    PortfolioTab,
    ProductsTab,
    ProfitsTab,
    ResearchTab,
    SuppliersTab,
    ToolsTab,
)
from security.key_store import KeyStore
from security.license_manager import LicenseManager
from services.analysis_service import AnalysisService
from services.collection_service import CollectionService
from services.export_service import ExportService
from utils.commercial import (
    DataValidator,
    init_commercial,
)
from utils.commercial import (
    logger as app_logger,
)
from utils.config import Config

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class SplashScreen(ctk.CTkToplevel):
    def __init__(self, parent, screen_w, screen_h):
        super().__init__(parent)
        self.overrideredirect(True)
        w, h = 480, 360
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.configure(fg_color=THEME["bg_dark"])
        self.geometry(f"{w}x{h}+{x}+{y}")

        radar_h = 220
        c = tk.Canvas(self, width=w, height=radar_h, highlightthickness=0, bg=THEME["bg_dark"])
        c.pack()
        cx, cy = w // 2, radar_h // 2
        R = 98
        self._R = R

        c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill="#93c5fd", outline="#dbeafe")

        for r, col, lw in [(R, "#1e40af", 2), (int(R * 0.75), "#162240", 1),
                            (int(R * 0.5), "#162240", 1), (int(R * 0.25), "#141e30", 1)]:
            c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=col, width=lw)

        for deg in range(0, 360, 15):
            rad = math.radians(deg)
            inner = 0 if deg % 90 == 0 else int(R * 0.25)
            x1 = cx + int(inner * math.cos(rad))
            y1 = cy + int(inner * math.sin(rad))
            x2 = cx + int(R * math.cos(rad))
            y2 = cy + int(R * math.sin(rad))
            c.create_line(x1, y1, x2, y2, fill="#111a2e" if deg % 90 != 0 else "#1a2d4a")

        for deg in [30, 60, 120, 150, 210, 240, 300, 330]:
            rad = math.radians(deg)
            x1 = cx + int(R * 0.5 * math.cos(rad))
            y1 = cy + int(R * 0.5 * math.sin(rad))
            x2 = cx + int(R * 0.75 * math.cos(rad))
            y2 = cy + int(R * 0.75 * math.sin(rad))
            c.create_line(x1, y1, x2, y2, fill="#0e1525")

        self._blips = [
            (0.52, -0.62, "#10b981", 4, "4.7"),
            (-0.45, 0.42, "#f59e0b", 4, "£29"),
            (0.70, 0.30, "#06b6d4", 3, "FBA"),
            (-0.62, -0.38, "#8b5cf6", 4, "89%"),
            (0.33, 0.65, "#ef4444", 3, "CRIT"),
            (-0.26, -0.70, "#10b981", 3, "Top"),
            (0.13, -0.48, "#f59e0b", 3, "£45"),
            (-0.58, 0.13, "#06b6d4", 3, "FBM"),
            (0.45, 0.50, "#10b981", 3, "4.5"),
            (-0.72, -0.15, "#f59e0b", 3, "£35"),
        ]
        self._blip_items = []
        for rx, ry, col, sz, label in self._blips:
            bx = cx + int(R * rx)
            by = cy + int(R * ry)
            outer_glow = c.create_oval(bx - sz - 6, by - sz - 6, bx + sz + 6, by + sz + 6,
                                        fill="", outline="", width=0)
            inner_glow = c.create_oval(bx - sz - 3, by - sz - 3, bx + sz + 3, by + sz + 3,
                                        fill="", outline="", width=0)
            dot = c.create_oval(bx - sz, by - sz, bx + sz, by + sz,
                                 fill="", outline="", width=0)
            txt = c.create_text(bx, by + sz + 10, text=label, font=("Consolas", 7, "bold"),
                                 fill="", anchor="center")
            self._blip_items.append((outer_glow, inner_glow, dot, txt, bx, by, col, label))

        self._ping_rings = []
        self._pulse_rings = []
        self._pulse_tick = 0
        self._noise_ids = []

        self._c = c
        self._cx = cx
        self._cy = cy
        self._angle = 0
        self._dynamic_ids = []

        right_panel = ctk.CTkFrame(self, fg_color="transparent", width=120)
        right_panel.place(x=w - 135, y=18)

        stats = [("Rating", "4.7", "#10b981"), ("Price", "£29", "#f59e0b"),
                 ("Score", "89%", "#8b5cf6"), ("Sales", "550", "#06b6d4")]
        for name, val, col in stats:
            row = ctk.CTkFrame(right_panel, fg_color="transparent", height=20)
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=8),
                         text_color="#4b5563", width=45, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=val, font=ctk.CTkFont(size=9, weight="bold"),
                         text_color=col, width=45, anchor="e").pack(side="right")

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=20)

        ctk.CTkLabel(bottom, text="MarketLens", font=ctk.CTkFont(size=26, weight="bold"),
                     text_color="#f1f5f9").pack(pady=(8, 0))
        ctk.CTkLabel(bottom, text="AI-Powered Product Intelligence",
                     font=ctk.CTkFont(size=10), text_color="#94a3b8").pack()

        self.progress = ctk.CTkProgressBar(bottom, width=340, height=5,
                                            fg_color=THEME["border"],
                                            progress_color=THEME["accent"])
        self.progress.pack(pady=(12, 4))
        self.progress.set(0)

        self.status = ctk.CTkLabel(bottom, text="Initializing...",
                                    font=ctk.CTkFont(size=9),
                                    text_color=THEME["text_muted"])
        self.status.pack()

        self._tick(0)
        self._animate_scan()

    def _animate_scan(self):
        c = self._c
        cx, cy, R = self._cx, self._cy, self._R
        angle = self._angle

        for tid in self._dynamic_ids:
            c.delete(tid)
        self._dynamic_ids.clear()

        sweep_deg = 60
        steps = 32
        for i in range(steps):
            frac = i / steps
            a0 = math.radians(angle - sweep_deg + frac * sweep_deg)
            a1 = math.radians(angle - sweep_deg + (frac + 1 / steps) * sweep_deg)
            bright = frac ** 0.5
            if bright < 0.05:
                color = "#060d18"
            elif bright < 0.15:
                color = "#0a1628"
            elif bright < 0.3:
                color = "#0f2240"
            elif bright < 0.5:
                color = "#163060"
            elif bright < 0.65:
                color = "#1d4ed8"
            elif bright < 0.8:
                color = "#3b82f6"
            elif bright < 0.92:
                color = "#60a5fa"
            else:
                color = "#93c5fd"
            pts = []
            segs = 8
            for j in range(segs + 1):
                a = a0 + (a1 - a0) * j / segs
                pts.extend([cx + int(R * math.cos(a)), cy + int(R * math.sin(a))])
            pts.extend([cx, cy])
            tid = c.create_polygon(pts, fill=color, outline="", smooth=False)
            self._dynamic_ids.append(tid)

        rad = math.radians(angle)
        x2 = cx + int(R * math.cos(rad))
        y2 = cy + int(R * math.sin(rad))
        tid = c.create_line(cx, cy, x2, y2, fill="#dbeafe", width=2)
        self._dynamic_ids.append(tid)

        for gr in [12, 8, 5]:
            col = "#1e3a5f" if gr == 12 else "#2563eb" if gr == 8 else "#3b82f6"
            tid = c.create_oval(cx - gr, cy - gr, cx + gr, cy + gr,
                                 fill="", outline=col, width=1)
            self._dynamic_ids.append(tid)

        for tip_r in [6, 3]:
            col = "#93c5fd" if tip_r == 6 else "#e0f2fe"
            tid = c.create_oval(x2 - tip_r, y2 - tip_r, x2 + tip_r, y2 + tip_r,
                                 fill="" if tip_r == 6 else col,
                                 outline="#93c5fd" if tip_r == 6 else "#bfdbfe", width=1)
            self._dynamic_ids.append(tid)

        self._pulse_tick += 1
        if self._pulse_tick % 20 == 0:
            self._pulse_rings.append(0)
        new_prings = []
        for pr in self._pulse_rings:
            pr += 2
            if pr > R:
                continue
            r = int(pr)
            opacity = max(0, int(255 * (1 - pr / R)))
            tid = c.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 fill="", outline="#1e3a5f", width=1)
            self._dynamic_ids.append(tid)
            new_prings.append(pr)
        self._pulse_rings = new_prings

        new_pings = []
        for px, py, pr, pcol in self._ping_rings:
            pr += 1.5
            if pr > 18:
                continue
            r = int(pr)
            tid = c.create_oval(px - r, py - r, px + r, py + r,
                                 fill="", outline=pcol, width=1)
            self._dynamic_ids.append(tid)
            new_pings.append((px, py, pr, pcol))
        self._ping_rings = new_pings

        if self._pulse_tick % 8 == 0:
            for _ in range(2):
                nx = cx + int((R - 10) * (2 * (hash(str(angle) + str(_)) % 1000) / 1000 - 1))
                ny = cy + int((R - 10) * (2 * (hash(str(angle) + str(_) + "y") % 1000) / 1000 - 1))
                if math.sqrt((nx - cx) ** 2 + (ny - cy) ** 2) < R - 5:
                    sz = 1
                    tid = c.create_oval(nx - sz, ny - sz, nx + sz, ny + sz,
                                         fill="#1a2d4a", outline="")
                    self._dynamic_ids.append(tid)

        for outer_g, inner_g, dot, txt, bx, by, col, _label in self._blip_items:
            dx, dy = bx - cx, by - cy
            blip_angle = math.degrees(math.atan2(dy, dx)) % 360
            angle_diff = (angle - blip_angle + 360) % 360

            if angle_diff < 6 or angle_diff > 356:
                c.itemconfig(outer_g, fill="", outline=col, width=1)
                c.itemconfig(inner_g, fill="", outline=col, width=1)
                c.itemconfig(dot, fill=col, outline="#ffffff", width=1)
                c.itemconfig(txt, fill="#ffffff")
                if self._pulse_tick % 25 == 0 and angle_diff < 6:
                    self._ping_rings.append((bx, by, 0, col))
            elif angle_diff < 60:
                fade = 1.0 - (angle_diff / 60.0)
                fade = fade ** 0.6
                c.itemconfig(outer_g, fill="", outline=col if fade > 0.6 else "", width=1)
                c.itemconfig(inner_g, fill="", outline=col if fade > 0.3 else "", width=1)
                c.itemconfig(dot, fill=col if fade > 0.4 else "",
                             outline="#ffffff" if fade > 0.7 else col if fade > 0.3 else "", width=1)
                c.itemconfig(txt, fill=col if fade > 0.3 else "")
            else:
                c.itemconfig(outer_g, fill="", outline="", width=0)
                c.itemconfig(inner_g, fill="", outline="", width=0)
                c.itemconfig(dot, fill="", outline="", width=0)
                c.itemconfig(txt, fill="")

        self._angle = (angle + 2) % 360
        self.after(16, self._animate_scan)

    def _tick(self, val):
        if val <= 1.0:
            self.progress.set(val)
            msgs = ["Scanning market data...", "Analyzing product metrics...",
                    "Building dashboard...", "Ready!"]
            idx = min(int(val * len(msgs)), len(msgs) - 1)
            self.status.configure(text=msgs[idx])
            self.after(30, lambda: self._tick(val + 0.04))
        else:
            self.after(80, self.destroy)


class AmazonProductAIApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MarketLens - AI Product Research")
        self.configure(fg_color=THEME["bg_dark"])
        self.withdraw()
        self.after(50, self._center_window)

        _icon = os.path.join(BASE_DIR, "assets", "marketlens_logo.ico")
        if os.path.exists(_icon):
            self.iconbitmap(_icon)

        self.config = Config()
        self.db = DatabaseManager()
        self.calculator = ProfitCalculator()
        self.chart_gen = ChartGenerator()
        self.ai_analyzer = AIAnalyzer(self.config)
        self.pricing_engine = MultiSourcePricing()
        self.collection_service = CollectionService(self.config)
        self.analysis_service = AnalysisService(self.config, self.ai_analyzer)
        self.export_service = ExportService(self.db)

        self.data_dir = os.environ.get("MLENS_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
        os.makedirs(self.data_dir, exist_ok=True)
        self.products_file = os.path.join(self.data_dir, "products.json")
        self.api_keys_file = os.path.join(self.data_dir, "api_keys.json")
        self.tracker_file = os.path.join(self.data_dir, "tracker.json")
        self.keywords_db_file = os.path.join(self.data_dir, "keywords.json")

        self.commercial = init_commercial(self.data_dir)
        self.validator = DataValidator()

        self.license_mgr = LicenseManager(self.data_dir)
        self.key_store = KeyStore(self.data_dir)
        self._activation_dialog = ActivationDialog(self, self.license_mgr)
        self.ai_analyzer.set_license_manager(self.license_mgr)
        self._activation_open = False

        self.ideas = []
        self.hidden_gems = []
        self.suppliers = []
        self.supplier_products = []
        self.pricing = []
        self.charts = {}
        self.all_products = []
        self.realtime_products = []
        self.portfolio_summary = {}
        self.forecast_summary = {}

        self.tracked_products = self._load_json(self.tracker_file, [])
        self.saved_keywords = self._load_json(self.keywords_db_file, [])
        self.seen_asins_file = os.path.join(self.data_dir, "seen_asins.json")
        self.seen_asins = set(self._load_json(self.seen_asins_file, []))

        self.categories = list(DEFAULT_CATEGORIES)
        self.keywords = ["trending", "best seller", "new arrival", "hot", "popular"]

        self.google_trends_var = ctk.BooleanVar(value=True)
        self.amazon_var = ctk.BooleanVar(value=True)
        self.social_var = ctk.BooleanVar(value=True)

        self.analysis_running = False
        self.analysis_start_time = None
        self.analysis_cycle_count = 0
        self.analysis_total_products = 0
        self.analysis_stop_event = threading.Event()
        self.all_time_products = []
        self._data_lock = threading.Lock()

        self.after(100, self._show_splash)
        self.after(1000, self._build_app)

    def _show_splash(self):
        try:
            import ctypes
            sw = ctypes.windll.user32.GetSystemMetrics(0)
            sh = ctypes.windll.user32.GetSystemMetrics(1)
        except Exception:
            sw, sh = 1920, 1080
        SplashScreen(self, sw, sh)

    def _build_app(self):
        self._create_titlebar()
        self._create_body()
        self._create_status_bar()
        self._load_saved_api_keys()
        self._load_saved_products()
        self._start_auto_save()
        self._setup_keyboard_shortcuts()
        self.after(200, self._update_cat_list)
        self.after(200, self._update_kw_list)
        self.after(300, self._check_license_on_startup)

        if not self.ideas:
            self.after(1500, self._start_infinite_analysis)

        app_logger.audit("APP_BUILD", "MarketLens ready")

    def _center_window(self):
        try:
            self.deiconify()
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w = int(sw * 0.85)
            h = int(sh * 0.90)
            x = (sw - w) // 2
            y = (sh - h) // 2
            self.geometry(f"{w}x{h}+{x}+{y}")
            self.lift()
            self.focus_force()
        except Exception as e:
            app_logger.warning(f"Failed to center window: {e}")

    def _start_auto_save(self):
        try:
            from utils.commercial import auto_saver
            if auto_saver:
                auto_saver.start(self._get_save_data)
        except Exception as e:
            app_logger.warning(f"Failed to start auto-save: {e}")

    def _get_save_data(self):
        data = {
            "products": (self.ideas, self.products_file),
            "tracker": (self.tracked_products, self.tracker_file),
            "keywords": (self.saved_keywords, self.keywords_db_file),
        }
        result = {}
        for _key, (value, filepath) in data.items():
            result[filepath] = value
        return result

    def _stop_auto_save(self):
        try:
            from utils.commercial import auto_saver
            if auto_saver:
                auto_saver.stop()
                auto_saver.save_now()
        except Exception:
            pass

    def _load_json(self, path, default):
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            app_logger.warning(f"Failed to load JSON from {path}: {e}")
        return default

    def _save_json(self, path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            app_logger.error(f"Failed to save JSON to {path}: {e}")

    # ─── Custom Title Bar ─────────────────────────────────────────
    def _create_titlebar(self):
        self.titlebar = ctk.CTkFrame(self, height=48, fg_color=THEME["bg_mid"],
                                     border_width=0)
        self.titlebar.pack(fill="x", padx=0, pady=0)
        self.titlebar.pack_propagate(False)

        # accent line under titlebar
        self._accent_line = ctk.CTkFrame(self, height=2, fg_color=THEME["accent"])
        self._accent_line.pack(fill="x")

        left = ctk.CTkFrame(self.titlebar, fg_color="transparent")
        left.pack(side="left", fill="y")

        # painted lens icon on canvas
        self._lens_canvas = tk.Canvas(left, width=32, height=32, highlightthickness=0,
                                       bg=THEME["bg_mid"])
        self._lens_canvas.pack(side="left", padx=(10, 2), pady=8)
        lc = self._lens_canvas
        lc.create_oval(4, 4, 28, 28, outline=THEME["accent"], width=2, fill="#0d1525")
        lc.create_oval(8, 8, 24, 24, outline="#1e40af", width=1, fill="#0f1d32")
        lc.create_oval(13, 13, 19, 19, fill=THEME["accent"], outline="#60a5fa", width=1)

        ctk.CTkLabel(left, text="MarketLens",
                     font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
                     text_color=THEME["accent"]).pack(side="left", padx=(2, 4), pady=6)

        ctk.CTkFrame(left, width=1, height=20, fg_color=THEME["border"]).pack(side="left", padx=6, pady=8)

        self.run_btn = ctk.CTkButton(
            left, text="  START  ", width=90, height=28,
            fg_color=THEME["success"], hover_color="#059669",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._start_infinite_analysis, corner_radius=5)
        self.run_btn.pack(side="left", padx=3, pady=8)

        self.stop_btn = ctk.CTkButton(
            left, text="STOP", width=50, height=28,
            fg_color=THEME["danger"], hover_color="#dc2626",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._stop_analysis, state="disabled", corner_radius=5)
        self.stop_btn.pack(side="left", padx=3, pady=8)

        ctk.CTkFrame(left, width=1, fg_color=THEME["border"]).pack(side="left", fill="y", padx=4, pady=8)

        self.mp_btn = ctk.CTkButton(
            left, text="Multi-Market", width=100, height=28,
            fg_color="#7c3aed", hover_color="#6d28d9",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._collect_marketplace, corner_radius=5)
        self.mp_btn.pack(side="left", padx=3, pady=8)

        self.export_btn = ctk.CTkButton(
            left, text="Export", width=60, height=26,
            fg_color=THEME["warning"], hover_color="#d97706",
            text_color="#000", font=ctk.CTkFont(size=10, weight="bold"),
            command=self._export_master, corner_radius=4)
        self.export_btn.pack(side="left", padx=3, pady=8)

        self.ai_badge = ctk.CTkLabel(left, text=" AI:OFF ",
                                     font=ctk.CTkFont(size=9, weight="bold"),
                                     text_color=THEME["text_muted"],
                                     fg_color=THEME["bg_card"], corner_radius=4, padx=5)
        self.ai_badge.pack(side="left", padx=3)

        self.api_keys_btn = ctk.CTkButton(
            left, text="API", width=36, height=24,
            fg_color=THEME["bg_card"], hover_color=THEME["bg_hover"],
            text_color=THEME["text"], font=ctk.CTkFont(size=9, weight="bold"),
            command=self._open_api_keys_dialog, corner_radius=4)
        self.api_keys_btn.pack(side="left", padx=3)

        ctk.CTkFrame(left, width=1, height=20, fg_color=THEME["border"]).pack(side="left", padx=4, pady=8)

        self.license_badge = ctk.CTkButton(
            left, text=self.license_mgr.get_status_text(), width=120, height=24,
            fg_color=self.license_mgr.get_status_color(),
            hover_color=THEME["accent_hover"],
            text_color="#fff", font=ctk.CTkFont(size=9, weight="bold"),
            corner_radius=4, command=self._show_activation)
        self.license_badge.pack(side="left", padx=3)

        right = ctk.CTkFrame(self.titlebar, fg_color="transparent")
        right.pack(side="right", padx=12)

        self._theme_mode = "dark"
        self.theme_toggle_btn = ctk.CTkButton(right, text="\u263E", width=30, height=26,
                                               fg_color=THEME["bg_card"], hover_color=THEME["bg_hover"],
                                               text_color=THEME["text"], font=ctk.CTkFont(size=14),
                                               corner_radius=4, command=self._toggle_theme)
        self.theme_toggle_btn.pack(side="right", padx=(0, 6), pady=8)

        self.timer_label = ctk.CTkLabel(right, text="00:00:00",
                                        font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                                        text_color=THEME["warning"])
        self.timer_label.pack(side="right", padx=(0, 8), pady=8)

        self.progress = ctk.CTkProgressBar(right, width=140, height=6,
                                           fg_color=THEME["border"],
                                           progress_color=THEME["accent"])
        self.progress.pack(side="right", padx=4, pady=8)
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(right, text="Ready",
                                         font=ctk.CTkFont(size=10, weight="bold"),
                                         text_color=THEME["text_dim"])
        self.status_label.pack(side="right", padx=4, pady=8)

        center = ctk.CTkFrame(self.titlebar, fg_color="transparent")
        center.pack(side="left", fill="both", expand=True, padx=4)

        src = ctk.CTkFrame(center, fg_color="transparent")
        src.pack(side="left", padx=(6, 0))
        ctk.CTkCheckBox(src, text="Trends", variable=self.google_trends_var,
                        font=ctk.CTkFont(size=10),
                        fg_color=THEME["accent"]).pack(side="left", padx=2)
        ctk.CTkCheckBox(src, text="Amazon", variable=self.amazon_var,
                        font=ctk.CTkFont(size=10),
                        fg_color=THEME["accent"]).pack(side="left", padx=2)
        ctk.CTkCheckBox(src, text="Social", variable=self.social_var,
                        font=ctk.CTkFont(size=10),
                        fg_color=THEME["accent"]).pack(side="left", padx=2)

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._filter_products())
        self.search_entry = ctk.CTkEntry(center, width=150, textvariable=self.search_var,
                                         placeholder_text="Search...",
                                         height=26, font=ctk.CTkFont(size=10),
                                         fg_color=THEME["bg_card"], border_color=THEME["border"])
        self.search_entry.pack(side="left", padx=6)

    def _toggle_theme(self):
        try:
            if self._theme_mode == "dark":
                ctk.set_appearance_mode("light")
                self._theme_mode = "light"
                self.theme_toggle_btn.configure(text="\u2600")
            else:
                ctk.set_appearance_mode("dark")
                self._theme_mode = "dark"
                self.theme_toggle_btn.configure(text="\u263E")
        except Exception as e:
            app_logger.warning(f"Failed to toggle theme: {e}")

    # ─── Body: Sidebar + Content ──────────────────────────────────
    def _create_body(self):
        self._body = ctk.CTkFrame(self, fg_color=THEME["bg_dark"])
        self._body.pack(fill="both", expand=True, padx=0, pady=0)

        self._create_sidebar()
        self._create_tabview()

    def _create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self._body, width=180, fg_color=THEME["bg_mid"],
                                    border_width=1, border_color=THEME["border"])
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)
        self.sidebar.pack_propagate(False)

        nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_frame.pack(fill="both", expand=True, padx=6, pady=6)

        ctk.CTkLabel(nav_frame, text="NAVIGATION",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=THEME["text_muted"]).pack(pady=(4, 8), anchor="w")

        self._nav_buttons = {}
        nav_items = [
            ("Research", "\u2609 Research"), ("Products", "\u2605 Products"),
            ("Keywords", "\u2637 Keywords"), ("Listing", "\u270E Listing"),
            ("Profits", "\u2796 Profits"), ("Suppliers", "\u2630 Suppliers"),
            ("Portfolio", "\u2631 Portfolio"), ("Tools", "\u2699 Tools"),
            ("Charts", "\u25A3 Charts"),
        ]
        for tab_name, label in nav_items:
            btn = ctk.CTkButton(
                nav_frame, text=label, anchor="w", height=34,
                fg_color="transparent", hover_color=THEME["bg_hover"],
                text_color=THEME["text"], font=ctk.CTkFont(size=11),
                corner_radius=6,
                command=lambda t=tab_name: self._nav_switch(t))
            btn.pack(fill="x", pady=1)
            self._nav_buttons[tab_name] = btn

        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=THEME["border"])
        sep.pack(fill="x", padx=8, pady=6)

        ctk.CTkLabel(self.sidebar, text="SOURCES",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=THEME["text_muted"]).pack(anchor="w", padx=12, pady=(4, 2))

        src_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        src_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkCheckBox(src_frame, text="Trends", variable=self.google_trends_var,
                        font=ctk.CTkFont(size=9),
                        fg_color=THEME["accent"]).pack(anchor="w", pady=1)
        ctk.CTkCheckBox(src_frame, text="Amazon", variable=self.amazon_var,
                        font=ctk.CTkFont(size=9),
                        fg_color=THEME["accent"]).pack(anchor="w", pady=1)
        ctk.CTkCheckBox(src_frame, text="Social", variable=self.social_var,
                        font=ctk.CTkFont(size=9),
                        fg_color=THEME["accent"]).pack(anchor="w", pady=1)

        sep2 = ctk.CTkFrame(self.sidebar, height=1, fg_color=THEME["border"])
        sep2.pack(fill="x", padx=8, pady=6)

        ctk.CTkLabel(self.sidebar, text="QUICK ADD",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=THEME["text_muted"]).pack(anchor="w", padx=12, pady=(4, 2))

        self.cat_entry = ctk.CTkEntry(self.sidebar, width=155, placeholder_text="+ Category",
                                       height=26, font=ctk.CTkFont(size=9),
                                       fg_color=THEME["bg_card"], border_color=THEME["border"])
        self.cat_entry.pack(padx=10, pady=2)
        self.cat_entry.bind("<Return>", lambda e: self._add_category())

        self.cat_tags_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.cat_tags_frame.pack(fill="x", padx=8)

        self.kw_entry = ctk.CTkEntry(self.sidebar, width=155, placeholder_text="+ Keyword",
                                      height=26, font=ctk.CTkFont(size=9),
                                      fg_color=THEME["bg_card"], border_color=THEME["border"])
        self.kw_entry.pack(padx=10, pady=2)
        self.kw_entry.bind("<Return>", lambda e: self._add_keyword())

        self.kw_tags_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.kw_tags_frame.pack(fill="x", padx=8)

        self._nav_switch("Research")

    def _nav_switch(self, tab_name):
        try:
            for name, btn in self._nav_buttons.items():
                if name == tab_name:
                    btn.configure(fg_color=THEME["accent"], text_color="#fff")
                else:
                    btn.configure(fg_color="transparent", text_color=THEME["text"])
            try:
                self.tabview.set(tab_name)
                self._ensure_tab(tab_name)
            except Exception as e:
                app_logger.warning(f"Failed to switch to tab {tab_name}: {e}")
        except Exception as e:
            app_logger.warning(f"Failed to update navigation: {e}")

    # ─── Tabs ────────────────────────────────────────────────────
    def _create_tabview(self):
        self.tabview = ctk.CTkTabview(self._body, fg_color=THEME["bg_dark"], border_width=0,
                                       segmented_button_fg_color=THEME["bg_mid"],
                                       segmented_button_selected_color=THEME["accent"])
        self.tabview.pack(fill="both", expand=True, padx=0, pady=0)

        tabs = ["Research", "Products", "Keywords", "Listing", "Profits",
                "Suppliers", "Portfolio", "Tools", "Charts"]
        for t in tabs:
            self.tabview.add(t)

        try:
            self.tabview._segmented_button.grid_remove()
        except Exception:
            pass

        self.tabview.set("Research")

        self._tab_built = {t: False for t in tabs}

        self.research_tab = ResearchTab(self.tabview, self)
        self.products_tab = ProductsTab(self.tabview, self)
        self._tab_built["Research"] = True
        self._tab_built["Products"] = True

        self._last_tab = "Research"
        self._dirty_refresh = False

    def _ensure_tab(self, tab_name):
        if self._tab_built.get(tab_name):
            return
        builders = {
            "Keywords": lambda: KeywordsTab(self.tabview, self),
            "Listing": lambda: ListingTab(self.tabview, self),
            "Profits": lambda: ProfitsTab(self.tabview, self),
            "Suppliers": lambda: SuppliersTab(self.tabview, self),
            "Portfolio": lambda: PortfolioTab(self.tabview, self),
            "Tools": lambda: ToolsTab(self.tabview, self),
            "Charts": lambda: ChartsTab(self.tabview, self),
        }
        if tab_name in builders:
            tab_obj = builders[tab_name]()
            setattr(self, f"{tab_name.lower()}_tab", tab_obj)
            self._tab_built[tab_name] = True

    def _create_status_bar(self):
        bar = ctk.CTkFrame(self, height=28, fg_color=THEME["bg_mid"],
                           border_width=1, border_color=THEME["border"])
        bar.pack(fill="x", padx=0, pady=(0, 0))
        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.pack(side="left", fill="y")
        self.stat_products = ctk.CTkLabel(left, text="  Products: 0  ", font=ctk.CTkFont(size=10), text_color=THEME["text_dim"])
        self.stat_products.pack(side="left", padx=4, pady=3)
        self.stat_gems = ctk.CTkLabel(left, text="  Gems: 0  ", font=ctk.CTkFont(size=10), text_color=THEME["success"])
        self.stat_gems.pack(side="left", padx=4, pady=3)
        self.stat_suppliers = ctk.CTkLabel(left, text="  Suppliers: 0  ", font=ctk.CTkFont(size=10), text_color=THEME["text_dim"])
        self.stat_suppliers.pack(side="left", padx=4, pady=3)
        self.stat_margin = ctk.CTkLabel(left, text="  Margin: 0%  ", font=ctk.CTkFont(size=10), text_color=THEME["warning"])
        self.stat_margin.pack(side="left", padx=4, pady=3)
        self.stat_ai = ctk.CTkLabel(left, text="  AI: N/A  ", font=ctk.CTkFont(size=10), text_color=THEME["info"])
        self.stat_ai.pack(side="left", padx=4, pady=3)
        self.stat_cycle = ctk.CTkLabel(left, text="  Cycles: 0  ", font=ctk.CTkFont(size=10), text_color=THEME["warning"])
        self.stat_cycle.pack(side="left", padx=4, pady=3)
        self.stat_time = ctk.CTkLabel(bar, text="", font=ctk.CTkFont(size=9), text_color=THEME["text_muted"])
        self.stat_time.pack(side="right", padx=12, pady=3)
        self._tick_clock()

    def _tick_clock(self):
        try:
            now = datetime.now()
            self.stat_time.configure(text=now.strftime("%H:%M:%S"))
            if self.analysis_running and self.analysis_start_time:
                elapsed = now - self.analysis_start_time
                hrs = int(elapsed.total_seconds() // 3600)
                mins = int((elapsed.total_seconds() % 3600) // 60)
                secs = int(elapsed.total_seconds() % 60)
                self.timer_label.configure(text=f"{hrs:02d}:{mins:02d}:{secs:02d}")
            self.after(1000, self._tick_clock)
        except Exception as e:
            app_logger.debug(f"Clock tick error: {e}")

    # ─── Sentiment Analysis ─────────────────────────────────────
    def _run_sentiment_analysis(self, product):
        asin = product.get("asin", "")
        name = product.get("name", product.get("title", "Product"))
        category = product.get("category", "")
        reviews = product.get("review_highlights", product.get("reviews", []))

        self.status_label.configure(text=f"Analyzing sentiment for {name[:30]}...", text_color=THEME["warning"])

        def run():
            try:
                result = self.ai_analyzer.analyze_review_sentiment(name, category, reviews)
                self.db.save_review_sentiment(asin, name, result)
                self.after(0, lambda r=result, n=name, a=asin: self._show_sentiment_result(r, n, a))
                self.after(0, lambda: self.status_label.configure(text="Sentiment analysis complete", text_color=THEME["success"]))
            except Exception as e:
                self.after(0, lambda e=e: self.status_label.configure(text=f"Sentiment failed: {e}", text_color=THEME["danger"]))

        threading.Thread(target=run, daemon=True).start()

    def _show_sentiment_result(self, result, name, asin):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Sentiment - {name[:40]}")
        dialog.geometry("650x520")
        dialog.configure(fg_color=THEME["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()

        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(header, text=f"Review Sentiment: {name[:50]}", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=THEME["accent"]).pack(side="left")
        ctk.CTkLabel(header, text=f"ASIN: {asin}", font=ctk.CTkFont(size=10),
                     text_color=THEME["text_muted"]).pack(side="left", padx=10)

        stats = ctk.CTkFrame(dialog, fg_color=THEME["bg_card"], corner_radius=8)
        stats.pack(fill="x", padx=12, pady=4)
        for label, val, color in [
            ("Positive", f"{result.get('positive_pct', 0):.0f}%", THEME["success"]),
            ("Negative", f"{result.get('negative_pct', 0):.0f}%", THEME["danger"]),
            ("Neutral", f"{result.get('neutral_pct', 0):.0f}%", THEME["text_dim"]),
        ]:
            f = ctk.CTkFrame(stats, fg_color="transparent")
            f.pack(side="left", padx=15, pady=6)
            ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=9), text_color=THEME["text_muted"]).pack()
            ctk.CTkLabel(f, text=val, font=ctk.CTkFont(size=16, weight="bold"), text_color=color).pack()

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent", scrollbar_button_color=THEME["border"])
        scroll.pack(fill="both", expand=True, padx=12, pady=4)

        summary = result.get("summary", "")
        if summary:
            ctk.CTkLabel(scroll, text=summary, font=ctk.CTkFont(size=11),
                         text_color=THEME["text"], wraplength=600, justify="left").pack(anchor="w", pady=4)

        for section, items, color in [
            ("TOP PRAISES", result.get("top_praises", []), THEME["success"]),
            ("TOP COMPLAINTS", result.get("top_complaints", []), THEME["danger"]),
            ("RECURRING ISSUES", result.get("recurring_issues", []), THEME["warning"]),
            ("IMPROVEMENT IDEAS", result.get("improvement_ideas", []), THEME["info"]),
        ]:
            if items:
                ctk.CTkLabel(scroll, text=section, font=ctk.CTkFont(size=10, weight="bold"),
                             text_color=color).pack(anchor="w", pady=(8, 2))
                for item in items:
                    ctk.CTkLabel(scroll, text=f"  - {item}", font=ctk.CTkFont(size=10),
                                 text_color=THEME["text"], wraplength=580, justify="left").pack(anchor="w", pady=1)

    # ─── Analysis Engine ─────────────────────────────────────────
    def _start_infinite_analysis(self):
        if self.analysis_running:
            return
        if not self._check_feature("products"):
            return
        self.analysis_running = True
        self.analysis_start_time = datetime.now()
        self.analysis_cycle_count = 0
        self.all_time_products = []
        self.analysis_stop_event.clear()

        self.run_btn.configure(state="disabled", text="  RUNNING  ", fg_color=THEME["warning"], text_color="#000")
        self.stop_btn.configure(state="normal")
        self.progress.set(0)
        self.status_label.configure(text="Starting...", text_color=THEME["warning"])

        threading.Thread(target=self._infinite_worker, daemon=True).start()

    def _infinite_worker(self):
        try:
            while not self.analysis_stop_event.is_set():
                with self._data_lock:
                    self.analysis_cycle_count += 1
                    cycle = self.analysis_cycle_count
                self._update_status(f"Cycle {cycle}...")

                self._collect_cycle()
                self._process_all()

                self._log_rt(f"Cycle {cycle} done. {len(self.all_time_products)} products total.")
                self.after(0, self._refresh_all)

                if self.analysis_stop_event.is_set():
                    break

                self._update_status(f"Next in {CYCLE_INTERVAL_MINUTES} min...")
                for _ in range(CYCLE_INTERVAL_MINUTES * 60):
                    if self.analysis_stop_event.is_set():
                        break
                    time.sleep(1)

            self.after(0, self._on_complete)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            try:
                err_file = os.path.join(self.data_dir, "error.log")
                with open(err_file, "a") as f:
                    f.write(tb)
            except Exception:
                pass
            self.after(0, lambda e=e: self._log_rt(f"ERROR: {e}"))
            self.after(0, lambda: setattr(self, 'analysis_running', False))
            self.after(0, self._reset_buttons)

    def _collect_cycle(self):
        sources = []
        if self.amazon_var.get():
            sources.append("Amazon")
        if self.google_trends_var.get():
            sources.append("Google Trends")
        if self.social_var.get():
            sources.append("Social Media")

        self.collection_service.seen_asins = self.seen_asins

        cycle_products = self.collection_service.collect_cycle(
            categories=list(self.categories),
            keywords=list(self.keywords),
            sources=sources,
            status_callback=self._update_status,
            progress_callback=self._update_progress,
        )

        with self._data_lock:
            self.seen_asins = self.collection_service.seen_asins
            self.all_time_products.extend(cycle_products)

    def _collect_marketplace(self):
        threading.Thread(target=self._marketplace_worker, daemon=True).start()

    def _marketplace_worker(self):
        try:
            from data_collectors.marketplace import collect_from_marketplaces
            self._update_status("Collecting from Walmart, eBay, Shopify...")
            self._update_progress(0)
            cats = list(self.categories) or ["general"]
            kws = list(self.keywords) or ["trending"]
            products = collect_from_marketplaces(self.config, cats, kws)
            self._update_progress(0.7)
            if products:
                for p in products:
                    if not p.get("name"):
                        continue
                    p.setdefault("ai_score", 0)
                    p.setdefault("margin_estimate", 0)
                    p.setdefault("demand_score", 0)
                    p.setdefault("competition_score", 0)
                    p.setdefault("composite_score", 0)
                    p["source_marketplace"] = p.get("source", "unknown")
                self.ideas.extend(products)
                if self.db:
                    self.db.batch_upsert_products(products)
                self.after(0, lambda: self._refresh_all())
                self._update_status(f"Multi-marketplace: {len(products)} products collected")
            else:
                self._update_status("Multi-marketplace collection returned 0 products")
            self._update_progress(1.0)
        except Exception as e:
            self._update_status(f"Multi-marketplace error: {str(e)[:80]}")
            self._update_progress(0)

    def _process_all(self):
        if not self.all_time_products:
            return

        raw_data = {"amazon": self.all_time_products, "trends": [], "social": []}

        with self._data_lock:
            self.ideas = self.analysis_service.analyze(
                products=self.all_time_products,
                raw_data=raw_data,
                status_callback=self._update_status,
            )

            self.portfolio_summary = {}
            try:
                from analyzers import ConsistencyAnalyzer
                consistency = ConsistencyAnalyzer(self.config)
                self.portfolio_summary = consistency.get_portfolio_summary(self.ideas)
            except Exception:
                pass

            try:
                from analyzers.hidden_gems import HiddenGemsFinder
                finder = HiddenGemsFinder(self.config)
                raw_data = {"amazon": self.all_time_products, "trends": [], "social": []}
                analysis_for_gems = {"clusters": {"clusters": []}}
                try:
                    from analyzers.clustering import KeywordClustering
                    clustering = KeywordClustering(self.config)
                    cluster_result = clustering.cluster_keywords(
                        [p.get("name", p.get("title", "")) for p in self.all_time_products if isinstance(p, dict)]
                    )
                    analysis_for_gems["clusters"] = cluster_result
                except Exception:
                    pass
                self.hidden_gems = finder.find(raw_data, analysis_for_gems)
            except Exception:
                pass

            self.ideas = self.ideas[:100]
        self._save_products()

    def _on_complete(self):
        self.analysis_running = False
        self.timer_label.configure(text="STOPPED", text_color=THEME["warning"])
        self._update_status(f"Stopped - {len(self.ideas)} products")
        self._refresh_all()
        self._reset_buttons()
        self.run_btn.configure(text="  START ANALYSIS  ", fg_color=THEME["success"], text_color="#fff")

    def _stop_analysis(self):
        self.analysis_stop_event.set()
        self.analysis_running = False
        self.status_label.configure(text="Stopping...", text_color=THEME["danger"])

    def _get_sample_products(self):
        return self.collection_service.get_sample_products(self.categories)

    def _calc_priority(self, idea, rank):
        from services.analysis_service import calculate_priority
        return calculate_priority(idea, rank)

    # ─── Refresh ────────────────────────────────────────────────
    def _refresh_all(self):
        if self._dirty_refresh:
            return
        self._dirty_refresh = True
        self.after(500, self._do_refresh_all)

    def _do_refresh_all(self):
        self._dirty_refresh = False
        try:
            if hasattr(self, "research_tab"):
                self.research_tab.refresh()
        except Exception as e:
            app_logger.warning(f"Failed to refresh research tab: {e}")
        try:
            if hasattr(self, "products_tab"):
                self.products_tab.refresh()
        except Exception as e:
            app_logger.warning(f"Failed to refresh products tab: {e}")
        try:
            if hasattr(self, "portfolio_tab"):
                self.portfolio_tab.refresh()
        except Exception as e:
            app_logger.warning(f"Failed to refresh portfolio tab: {e}")
        try:
            if hasattr(self, "profits_tab"):
                self.profits_tab.refresh_selector()
        except Exception as e:
            app_logger.warning(f"Failed to refresh profits tab: {e}")
        try:
            if hasattr(self, "keywords_tab"):
                self.keywords_tab.refresh_selector()
        except Exception as e:
            app_logger.warning(f"Failed to refresh keywords tab: {e}")
        try:
            if hasattr(self, "listing_tab"):
                self.listing_tab.refresh_selector()
        except Exception as e:
            app_logger.warning(f"Failed to refresh listing tab: {e}")
        try:
            if hasattr(self, "suppliers_tab"):
                self.suppliers_tab.refresh()
        except Exception as e:
            app_logger.warning(f"Failed to refresh suppliers tab: {e}")
        try:
            if hasattr(self, "tools_tab"):
                self.tools_tab._refresh_analytics()
        except Exception as e:
            app_logger.warning(f"Failed to refresh tools tab: {e}")
        self._update_status_bar()

    def _update_status(self, text):
        try:
            self.after(0, lambda t=text: self.status_label.configure(text=t))
        except Exception as e:
            app_logger.debug(f"Failed to update status: {e}")

    def _update_progress(self, value):
        try:
            self.after(0, lambda v=value: self.progress.set(v))
        except Exception as e:
            app_logger.debug(f"Failed to update progress: {e}")

    def _log_rt(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")

    def _update_status_bar(self):
        top20_count = len(self._get_top20())
        self.stat_products.configure(text=f"  Top 20: {top20_count}  ")
        self.stat_gems.configure(text=f"  Total: {len(self.ideas)}  ")
        self.stat_suppliers.configure(text=f"  Suppliers: {len(self.suppliers)}  ")
        self.stat_cycle.configure(text=f"  Cycles: {self.analysis_cycle_count}  ")
        if self.ideas:
            am = sum(i.get("estimated_margin_pct", 0) for i in self.ideas) / len(self.ideas)
            avg = sum(i.get("ai_score", 0) for i in self.ideas) / len(self.ideas)
            self.stat_margin.configure(text=f"  Margin: {am:.0f}%  ")
            self.stat_ai.configure(text=f"  AI: {avg:.0%}  ")

    def _reset_buttons(self):
        self.after(0, lambda: self.run_btn.configure(state="normal"))
        self.after(0, lambda: self.stop_btn.configure(state="disabled"))

    def _filter_products(self):
        query = self.search_var.get().strip().lower()
        if not query:
            if hasattr(self, '_all_ideas_backup') and self._all_ideas_backup is not None:
                self.ideas = self._all_ideas_backup
                self._all_ideas_backup = None
            self._refresh_all()
            return
        if not hasattr(self, '_all_ideas_backup') or self._all_ideas_backup is None:
            self._all_ideas_backup = list(self.ideas)
        all_products = self._all_ideas_backup
        filtered = [p for p in all_products if isinstance(p, dict) and (
            query in p.get("name", p.get("title", "")).lower()
            or query in p.get("category", "").lower()
            or query in p.get("asin", "").lower())]
        self.ideas = filtered
        self._refresh_all()

    def _setup_keyboard_shortcuts(self):
        self.bind("<Control-s>", lambda e: self._save_products())
        self.bind("<Control-e>", lambda e: self._export_master())
        self.bind("<Control-r>", lambda e: self._start_infinite_analysis())
        self.bind("<Escape>", lambda e: self._stop_analysis())
        self.bind("<F5>", lambda e: self._start_infinite_analysis())
        self.bind("<Control-f>", lambda e: self.search_entry.focus_set())

    def _copy_text(self, text):
        self.clipboard_clear()
        self.clipboard_append(str(text))
        self.update()

    # ─── Export ──────────────────────────────────────────────────
    def _export_master(self):
        if not self.ideas:
            messagebox.showwarning("Warning", "Run analysis first.")
            return

        top20 = self._get_top20()
        if not top20:
            messagebox.showwarning("Warning", "No products available to export.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Export Options")
        dialog.geometry("350x250")
        dialog.configure(fg_color=THEME["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Choose Export Format", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=THEME["accent"]).pack(pady=(15, 10))

        def export_excel():
            dialog.destroy()

            def _do_export():
                path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                                   filetypes=[("Excel", "*.xlsx")],
                                                   initialfile="marketlens_report.xlsx")
                if path:
                    ok, msg = self.export_service.export_excel(top20, path, hidden_gems=self.hidden_gems, portfolio_summary=self.portfolio_summary)
                    if ok:
                        self.license_mgr.record_usage("exports")
                        messagebox.showinfo("Exported", f"Excel saved to:\n{path}")
                    else:
                        messagebox.showerror("Error", f"Export failed:\n{msg}")

            self.after(200, _do_export)

        def export_pdf():
            dialog.destroy()

            def _do_export():
                path = filedialog.asksaveasfilename(defaultextension=".pdf",
                                                   filetypes=[("PDF", "*.pdf")],
                                                   initialfile="marketlens_report.pdf")
                if path:
                    ok, msg = self.export_service.export_pdf(top20, path, hidden_gems=self.hidden_gems)
                    if ok:
                        self.license_mgr.record_usage("exports")
                        messagebox.showinfo("Exported", f"PDF saved to:\n{path}")
                    else:
                        messagebox.showerror("Error", f"Export failed:\n{msg}")

            self.after(200, _do_export)

        def export_json():
            dialog.destroy()

            def _do_export():
                path = filedialog.asksaveasfilename(defaultextension=".json",
                                                   filetypes=[("JSON", "*.json")],
                                                   initialfile="marketlens_report.json")
                if path:
                    ok, msg = self.export_service.export_json(top20, path, hidden_gems=self.hidden_gems, portfolio_summary=self.portfolio_summary, categories=self.categories, keywords=self.keywords)
                    if ok:
                        self.license_mgr.record_usage("exports")
                        messagebox.showinfo("Exported", f"JSON saved to:\n{path}")
                    else:
                        messagebox.showerror("Error", f"Export failed:\n{msg}")

            self.after(200, _do_export)

        ctk.CTkButton(dialog, text="Export to Excel (.xlsx)", width=250, height=35,
                     fg_color=THEME["success"], font=ctk.CTkFont(size=12, weight="bold"),
                     corner_radius=6, command=export_excel).pack(pady=5)

        ctk.CTkButton(dialog, text="Export to PDF Report", width=250, height=35,
                     fg_color=THEME["danger"], font=ctk.CTkFont(size=12, weight="bold"),
                     corner_radius=6, command=export_pdf).pack(pady=5)

        ctk.CTkButton(dialog, text="Export to JSON", width=250, height=35,
                     fg_color=THEME["info"], font=ctk.CTkFont(size=12, weight="bold"),
                     corner_radius=6, command=export_json).pack(pady=5)

    # ─── Persistence ─────────────────────────────────────────────
    def _get_analyzed_products(self):
        return list(self.ideas) if self.ideas else []

    def _get_top20(self):
        products = [p for p in (self.ideas if self.ideas else []) if not p.get("gated", False)]

        def composite_score(p):
            ai = p.get("ai_score", 0)
            margin = min(p.get("estimated_margin_pct", 0) / 100, 1.0)
            rating = p.get("rating", 0) / 5.0
            tl_bonus = {"GREEN": 0.15, "YELLOW": 0.05, "RED": -0.1}.get(p.get("traffic_light", "RED"), 0)
            return ai * 0.45 + margin * 0.30 + rating * 0.15 + tl_bonus

        return sorted(products, key=composite_score, reverse=True)[:20]

    def _get_all_products(self):
        all_products = [p for p in (self.ideas if self.ideas else []) if not p.get("gated", False)]
        if self.hidden_gems:
            all_products.extend([g for g in self.hidden_gems if not g.get("gated", False)])
        return all_products

    def _save_products(self):
        self.export_service.save_products(
            products=self.ideas,
            hidden_gems=self.hidden_gems,
            categories=self.categories,
            keywords=self.keywords,
            cycle=self.analysis_cycle_count,
            path=self.products_file,
        )
        if self.ideas:
            self.db.batch_upsert_products(self.ideas)
        try:
            with open(self.seen_asins_file, "w") as f:
                json.dump(list(self.seen_asins), f)
        except Exception:
            pass

    def _load_saved_products(self):
        data = self.export_service.load_products(self.products_file)
        if data is None:
            return
        self.ideas = data.get("ideas", [])
        self.hidden_gems = data.get("hidden_gems", [])
        if data.get("categories"):
            self.categories = data["categories"]
        if data.get("keywords"):
            self.keywords = data["keywords"]
        for p in self.ideas:
            asin = p.get("asin", "")
            if asin:
                self.seen_asins.add(asin)
        if self.ideas:
            self.after(500, lambda: self._do_refresh_all())

    def _open_api_keys_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("API Keys")
        dialog.geometry("420x260")
        dialog.configure(fg_color=THEME["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="OpenAI API Key:", text_color=THEME["text"],
                     font=ctk.CTkFont(size=11)).pack(padx=15, pady=(15, 2), anchor="w")
        openai_entry = ctk.CTkEntry(dialog, width=380, height=30,
                                    fg_color=THEME["bg_card"], border_color=THEME["border"],
                                    font=ctk.CTkFont(size=10))
        openai_entry.pack(padx=15, pady=(0, 8))
        openai_entry.insert(0, os.getenv("OPENAI_API_KEY", ""))

        ctk.CTkLabel(dialog, text="Claude API Key:", text_color=THEME["text"],
                     font=ctk.CTkFont(size=11)).pack(padx=15, pady=(0, 2), anchor="w")
        claude_entry = ctk.CTkEntry(dialog, width=380, height=30,
                                    fg_color=THEME["bg_card"], border_color=THEME["border"],
                                    font=ctk.CTkFont(size=10))
        claude_entry.pack(padx=15, pady=(0, 8))
        claude_entry.insert(0, os.getenv("ANTHROPIC_API_KEY", ""))

        def save():
            o = openai_entry.get().strip()
            c = claude_entry.get().strip()
            if o:
                os.environ["OPENAI_API_KEY"] = o
                self.ai_analyzer.openai_key = o
            if c:
                os.environ["ANTHROPIC_API_KEY"] = c
                self.ai_analyzer.claude_key = c
            if o:
                self.ai_badge.configure(text=" AI: OPENAI ", text_color=THEME["success"])
            elif c:
                self.ai_badge.configure(text=" AI: CLAUDE ", text_color=THEME["success"])
            else:
                self.ai_badge.configure(text=" AI: OFF ", text_color=THEME["text_muted"])
            self._save_api_keys()
            dialog.destroy()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="Save", command=save, width=100, height=30,
                      fg_color=THEME["success"], hover_color="#059669",
                      font=ctk.CTkFont(size=11, weight="bold"), corner_radius=6).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Cancel", command=dialog.destroy, width=100, height=30,
                      fg_color=THEME["danger"], hover_color="#dc2626",
                      font=ctk.CTkFont(size=11, weight="bold"), corner_radius=6).pack(side="left", padx=6)

    def _save_api_keys(self):
        try:
            keys = {"openai": os.getenv("OPENAI_API_KEY", ""),
                    "claude": os.getenv("ANTHROPIC_API_KEY", "")}
            self.key_store.save(keys)
        except Exception as e:
            print(f"Failed to save API keys: {e}")

    def _check_license_on_startup(self):
        tier = self.license_mgr.get_tier()
        if tier == "none":
            self.license_mgr.start_trial()
            self._update_license_status()
        self._license_startup_done = True

    def _show_activation(self):
        if self._activation_open:
            return
        self._activation_open = True
        self._activation_dialog.show()

    def _update_license_status(self):
        if hasattr(self, "license_badge"):
            self.license_badge.configure(
                text=self.license_mgr.get_status_text(),
                fg_color=self.license_mgr.get_status_color(),
            )

    def _check_feature(self, feature):
        if self.license_mgr.can_use_feature(feature):
            return True
        tier = self.license_mgr.get_tier()
        if tier == "none":
            self._show_activation()
        elif tier == "trial":
            usage = self.license_mgr.get_usage()
            limit = usage.get(f"{feature}_limit", 0)
            used = usage.get(feature, 0)
            messagebox.showwarning(
                "Feature Limit",
                "Trial {} limit reached ({}/{}).\nUpgrade to PRO for unlimited access.".format(
                    feature.replace("_", " "), used, limit),
            )
        return False

    def _load_saved_api_keys(self):
        try:
            keys = self.key_store.load()
            o = keys.get("openai", "")
            c = keys.get("claude", "")
            if o:
                os.environ["OPENAI_API_KEY"] = o
                self.ai_analyzer.openai_key = o
                self.ai_badge.configure(text=" AI: OPENAI ", text_color=THEME["success"])
            if c:
                os.environ["ANTHROPIC_API_KEY"] = c
                self.ai_analyzer.claude_key = c
                if not o:
                    self.ai_badge.configure(text=" AI: CLAUDE ", text_color=THEME["success"])
        except Exception as e:
            print(f"Failed to load API keys: {e}")

    def _add_category(self):
        cat = self.cat_entry.get().strip()
        if cat and cat not in self.categories:
            self.categories.append(cat)
            self._update_cat_list()
            self.cat_entry.delete(0, "end")

    def _add_keyword(self):
        kw = self.kw_entry.get().strip()
        if kw and kw not in self.keywords:
            self.keywords.append(kw)
            self._update_kw_list()
            self.kw_entry.delete(0, "end")

    def _remove_category(self, cat):
        if cat in self.categories:
            self.categories.remove(cat)
            self._update_cat_list()

    def _remove_keyword(self, kw):
        if kw in self.keywords:
            self.keywords.remove(kw)
            self._update_kw_list()

    def _update_cat_list(self):
        for w in self.cat_tags_frame.winfo_children():
            w.destroy()
        for cat in self.categories[:8]:
            f = ctk.CTkFrame(self.cat_tags_frame, fg_color=THEME["bg_card"], corner_radius=3)
            f.pack(side="left", padx=1, pady=1)
            ctk.CTkLabel(f, text=cat[:8], font=ctk.CTkFont(size=8), text_color=THEME["text_dim"]).pack(side="left", padx=3, pady=1)
            ctk.CTkButton(
                f, text="x", width=12, height=12, font=ctk.CTkFont(size=7),
                fg_color="transparent", text_color=THEME["danger"],
                hover_color=THEME["bg_mid"],
                command=lambda c=cat: self._remove_category(c),
            ).pack(side="left", padx=(0, 2), pady=0)

    def _update_kw_list(self):
        for w in self.kw_tags_frame.winfo_children():
            w.destroy()
        for kw in self.keywords[:5]:
            f = ctk.CTkFrame(self.kw_tags_frame, fg_color=THEME["bg_card"], corner_radius=3)
            f.pack(side="left", padx=1, pady=1)
            ctk.CTkLabel(f, text=kw[:8], font=ctk.CTkFont(size=8), text_color=THEME["text_dim"]).pack(side="left", padx=3, pady=1)
            ctk.CTkButton(
                f, text="x", width=12, height=12, font=ctk.CTkFont(size=7),
                fg_color="transparent", text_color=THEME["danger"],
                hover_color=THEME["bg_mid"],
                command=lambda k=kw: self._remove_keyword(k),
            ).pack(side="left", padx=(0, 2), pady=0)

    # ─── Shutdown ────────────────────────────────────────────────
    def on_closing(self):
        try:
            self._stop_analysis()
            self._stop_auto_save()
            self._save_products()
            self._save_api_keys()
            app_logger.audit("APP_CLOSE", "Graceful shutdown")
        except Exception as e:
            app_logger.error(f"Error during shutdown: {e}")
        self.destroy()


def main():
    app = AmazonProductAIApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
