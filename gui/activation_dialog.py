"""
MarketLens Activation Dialog
Serial key entry, trial mode, license status display.
"""


import customtkinter as ctk

from gui.common import THEME


class ActivationDialog:
    """License activation dialog with key entry and trial mode."""

    def __init__(self, app, license_manager):
        self.app = app
        self.lm = license_manager
        self.dialog = None

    def show(self):
        if self.dialog:
            self.dialog.lift()
            return
        self.dialog = ctk.CTkToplevel(self.app)
        self.dialog.title("MarketLens — License Activation")
        self.dialog.geometry("520x580")
        self.dialog.configure(fg_color=THEME["bg_dark"])
        self.dialog.transient(self.app)
        self.dialog.grab_set()
        try:
            self.dialog.after(50, self.dialog.lift)
        except Exception:
            pass

        header = ctk.CTkFrame(self.dialog, fg_color=THEME["bg_card"], corner_radius=THEME["corner_radius"])
        header.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(
            header, text="MarketLens License",
            font=ctk.CTkFont(size=20, weight="bold"), text_color=THEME["accent"],
        ).pack(pady=(12, 4))
        ctk.CTkLabel(
            header, text="Activate your copy or start a free trial",
            font=ctk.CTkFont(size=11), text_color=THEME["text_muted"],
        ).pack(pady=(0, 12))

        self._build_status_section()
        self._build_key_section()
        self._build_trial_section()
        self._build_tier_info()

    def _build_status_section(self):
        frame = ctk.CTkFrame(self.dialog, fg_color=THEME["bg_card"], corner_radius=THEME["corner_radius"])
        frame.pack(fill="x", padx=16, pady=4)

        status = self.lm.get_status_text()
        color = self.lm.get_status_color()
        ctk.CTkLabel(
            frame, text="Status:", font=ctk.CTkFont(size=11),
            text_color=THEME["text_dim"],
        ).pack(side="left", padx=12, pady=10)
        ctk.CTkLabel(
            frame, text=status, font=ctk.CTkFont(size=12, weight="bold"),
            text_color=color,
        ).pack(side="left", padx=4, pady=10)

        if self.lm.get_tier() == "trial":
            usage = self.lm.get_usage()
            ctk.CTkLabel(
                frame, text="AI: {}/{}  |  Exports: {}/{}".format(
                    usage["ai_calls"], usage["ai_limit"],
                    usage["exports"], usage["export_limit"]),
                font=ctk.CTkFont(size=10), text_color=THEME["text_muted"],
            ).pack(side="right", padx=12, pady=10)

    def _build_key_section(self):
        frame = ctk.CTkFrame(self.dialog, fg_color=THEME["bg_card"], corner_radius=THEME["corner_radius"])
        frame.pack(fill="x", padx=16, pady=4)

        ctk.CTkLabel(
            frame, text="Serial Key:", font=ctk.CTkFont(size=11),
            text_color=THEME["text_dim"],
        ).pack(anchor="w", padx=12, pady=(10, 2))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 4))

        self.key_entry = ctk.CTkEntry(
            row, placeholder_text="ML-XXXX-XXXX-XXXX",
            width=300, height=36,
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            fg_color=THEME["bg_mid"], border_color=THEME["border"],
        )
        self.key_entry.pack(side="left", padx=(0, 8))
        self.key_entry.bind("<Return>", lambda e: self._activate())

        ctk.CTkButton(
            row, text="Activate", width=100, height=36,
            fg_color=THEME["success"], hover_color="#059669",
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=6, command=self._activate,
        ).pack(side="left")

        self.key_status = ctk.CTkLabel(
            frame, text="", font=ctk.CTkFont(size=10),
            text_color=THEME["text_muted"],
        )
        self.key_status.pack(anchor="w", padx=12, pady=(0, 8))

        ctk.CTkLabel(
            frame, text="Get your key from marketlens.dev/license",
            font=ctk.CTkFont(size=9), text_color=THEME["text_muted"],
        ).pack(anchor="w", padx=12, pady=(0, 8))

    def _build_trial_section(self):
        frame = ctk.CTkFrame(self.dialog, fg_color=THEME["bg_card"], corner_radius=THEME["corner_radius"])
        frame.pack(fill="x", padx=16, pady=4)

        if self.lm.get_tier() == "trial":
            days = self.lm._trial_days_left()
            ctk.CTkLabel(
                frame, text=f"Free Trial — {days} days remaining",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=THEME["warning"],
            ).pack(anchor="w", padx=12, pady=(10, 4))

            usage = self.lm.get_usage()
            bar_frame = ctk.CTkFrame(frame, fg_color="transparent")
            bar_frame.pack(fill="x", padx=12, pady=(0, 8))

            for label, used, limit in [
                ("AI Calls", usage["ai_calls"], usage["ai_limit"]),
                ("Exports", usage["exports"], usage["export_limit"]),
            ]:
                pct = used / max(limit, 1)
                ctk.CTkLabel(
                    bar_frame, text=f"{label}: {used}/{limit}",
                    font=ctk.CTkFont(size=10), text_color=THEME["text_dim"],
                ).pack(anchor="w", pady=1)
                bar = ctk.CTkProgressBar(bar_frame, width=280, height=6,
                                          fg_color=THEME["border"],
                                          progress_color=THEME["warning"])
                bar.pack(anchor="w", pady=(0, 4))
                bar.set(min(pct, 1.0))
        elif self.lm.get_tier() == "none":
            ctk.CTkLabel(
                frame, text="No License Active",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=THEME["text_muted"],
            ).pack(anchor="w", padx=12, pady=(10, 4))

            ctk.CTkButton(
                frame, text="Start 14-Day Free Trial", width=200, height=32,
                fg_color=THEME["warning"], hover_color="#d97706",
                text_color="#000", font=ctk.CTkFont(size=11, weight="bold"),
                corner_radius=6, command=self._start_trial,
            ).pack(padx=12, pady=(0, 10))
        else:
            ctk.CTkLabel(
                frame, text="Fully licensed — all features unlocked",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=THEME["success"],
            ).pack(anchor="w", padx=12, pady=10)

    def _build_tier_info(self):
        frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        frame.pack(fill="x", padx=16, pady=(8, 0))

        tiers = [
            ("BASIC", "50 AI calls, 10 exports, 50 products", THEME["text_muted"]),
            ("PRO", "Unlimited AI, exports, products", THEME["accent"]),
            ("ENTERPRISE", "Everything + priority support + API", THEME["gold"]),
        ]
        for name, desc, color in tiers:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(
                row, text=name, width=80, anchor="w",
                font=ctk.CTkFont(size=10, weight="bold"), text_color=color,
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=desc, font=ctk.CTkFont(size=9),
                text_color=THEME["text_dim"],
            ).pack(side="left")

    def _activate(self):
        key = self.key_entry.get().strip()
        if not key:
            self.key_status.configure(text="Enter a serial key", text_color=THEME["warning"])
            return

        success, result = self.lm.activate(key)
        if success:
            self.key_status.configure(
                text=f"Activated! {result.upper()} license enabled",
                text_color=THEME["success"],
            )
            self.app.after(1000, self._close_and_refresh)
        else:
            self.key_status.configure(text=result, text_color=THEME["danger"])

    def _start_trial(self):
        self.lm.start_trial()
        self._close_and_refresh()

    def _close_and_refresh(self):
        if self.dialog:
            self.dialog.destroy()
            self.dialog = None
        if hasattr(self.app, "_activation_open"):
            self.app._activation_open = False
        if hasattr(self.app, "_update_license_status"):
            self.app._update_license_status()

    def close(self):
        if self.dialog:
            self.dialog.destroy()
            self.dialog = None
        if hasattr(self.app, "_activation_open"):
            self.app._activation_open = False
