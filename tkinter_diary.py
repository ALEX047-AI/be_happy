import tkinter as tk
from tkinter import messagebox
from datetime import datetime, date, time

import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class DiaryView:
    """
    Diary UI + logic, isolated from main app.

    Expects:
      - diary: list (mutable, will be appended/updated)
      - save_callback(diary_list): function to persist diary
      - theme dict with keys: BG, FG, BTN, ACCENT, PANEL
    """

    PERIODS = (
        ("Утро", "morning", 8),        # 08:00
        ("День", "afternoon", 14),     # 14:00
        ("Вечер", "evening", 20),      # 20:00
    )

    RU_MONTHS_SHORT = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]

    def __init__(self, parent, diary, save_callback, theme):
        self.parent = parent
        self.diary = diary
        self.save_callback = save_callback

        self.BG = theme["BG"]
        self.FG = theme["FG"]
        self.BTN = theme["BTN"]
        self.ACCENT = theme["ACCENT"]
        self.PANEL = theme["PANEL"]

        self._build()

    def _build(self):
        f = self.parent

        tk.Label(
            f, text="Дневник", fg=self.FG, bg=self.BG,
            font=("Arial", 18, "bold")
        ).pack(pady=15)

        # ---- Period selector
        period_row = tk.Frame(f, bg=self.BG)
        period_row.pack(fill="x", padx=12, pady=(0, 6))

        tk.Label(period_row, text="Период:", bg=self.BG, fg=self.FG).pack(side="left")

        self.period_var = tk.StringVar(value=self._guess_period())

        PERIOD_BTN = dict(
            indicatoron=0,
            bg=self.BTN,
            fg=self.FG,
            activebackground="#2a2a2a",
            activeforeground=self.FG,
            selectcolor=self.ACCENT,
            relief="flat",
            padx=10,
            pady=6,
            borderwidth=0,
            highlightthickness=0,
        )

        for label, code, _hour in self.PERIODS:
            tk.Radiobutton(
                period_row,
                text=label,
                variable=self.period_var,
                value=code,
                **PERIOD_BTN
            ).pack(side="left", padx=8)

        # ---- Text (optional)
        self.diary_text = tk.Text(
            f, height=6,
            bg=self.PANEL, fg=self.FG, insertbackground=self.FG,
            relief="flat", wrap="word"
        )
        self.diary_text.pack(fill="x", padx=12, pady=(5, 8))

        # ---- Mood
        mood_row = tk.Frame(f, bg=self.BG)
        mood_row.pack(fill="x", padx=12)

        tk.Label(
            mood_row, text="Самочувствие (1–10):",
            bg=self.BG, fg=self.FG
        ).pack(side="left")

        self.diary_mood = tk.IntVar(value=5)
        tk.Scale(
            mood_row, from_=1, to=10, orient="horizontal",
            variable=self.diary_mood,
            bg=self.BG, fg=self.FG,
            troughcolor=self.PANEL,
            highlightthickness=0
        ).pack(side="left", fill="x", expand=True, padx=10)

        # ---- Buttons
        btn_row = tk.Frame(f, bg=self.BG)
        btn_row.pack(fill="x", padx=12, pady=(8, 8))

        tk.Button(
            btn_row, text="Сохранить запись",
            command=self.save_entry,
            bg=self.BTN, fg=self.FG, relief="flat", padx=10, pady=6
        ).pack(side="left")

        tk.Button(
            btn_row, text="Очистить",
            command=lambda: self.diary_text.delete("1.0", "end"),
            bg=self.BTN, fg=self.FG, relief="flat", padx=10, pady=6
        ).pack(side="left", padx=10)

        # ---- Chart
        chart_wrap = tk.Frame(f, bg=self.BG)
        chart_wrap.pack(fill="both", expand=True, padx=12, pady=(5, 12))

        self.fig = Figure(figsize=(6, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_wrap)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.refresh()

    def _guess_period(self) -> str:
        h = datetime.now().hour
        if h < 12:
            return "morning"
        if h < 18:
            return "afternoon"
        return "evening"

    def _period_hour(self) -> int:
        code = self.period_var.get()
        for _label, c, h in self.PERIODS:
            if c == code:
                return h
        return 8

    def _period_to_iso_datetime(self) -> str:
        today = date.today()
        hour = self._period_hour()
        dt = datetime.combine(today, time(hour=hour, minute=0, second=0))
        return dt.isoformat()

    def _matches_day_period(self, entry_date_str: str, target_day: date, target_hour: int) -> bool:
        try:
            dt = datetime.fromisoformat(entry_date_str)
        except Exception:
            return False
        return (dt.date() == target_day) and (dt.hour == target_hour)

    def save_entry(self):
        # text is OPTIONAL
        text = self.diary_text.get("1.0", "end").strip()
        mood = int(self.diary_mood.get())

        target_day = date.today()
        target_hour = self._period_hour()
        fixed_iso = self._period_to_iso_datetime()

        replaced = False
        for i, item in enumerate(self.diary):
            if isinstance(item, dict) and self._matches_day_period(item.get("date", ""), target_day, target_hour):
                self.diary[i] = {"date": fixed_iso, "mood": mood, "text": text}
                replaced = True
                break

        if not replaced:
            self.diary.append({"date": fixed_iso, "mood": mood, "text": text})

        try:
            self.save_callback(self.diary)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить дневник:\n{e}")
            return

        self.diary_text.delete("1.0", "end")
        self.refresh()

    def refresh(self):
        self.ax.clear()

        points = []
        for item in self.diary:
            if not isinstance(item, dict):
                continue
            try:
                dt = datetime.fromisoformat(item.get("date", ""))
                mood = int(item.get("mood", 0))
                points.append((dt, mood))
            except Exception:
                continue

        points.sort(key=lambda x: x[0])

        if points:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            years = {dt.year for dt in xs}
            show_year = (len(years) > 1)

            self.ax.plot(xs, ys, marker="o", color=self.ACCENT)
            self.ax.set_ylim(0, 10)
            self.ax.set_title("Самочувствие (по датам)")
            self.ax.set_ylabel("Оценка")

            locator = mdates.AutoDateLocator(minticks=3, maxticks=7)
            self.ax.xaxis.set_major_locator(locator)

            def ru_fmt(x, pos=None):
                dt = mdates.num2date(x)
                mon = self.RU_MONTHS_SHORT[dt.month - 1]
                # always show time (you use 08:00 / 14:00 / 20:00)
                if show_year:
                    return f"{dt.day} {mon} {dt.year}" # {dt:%H:%M}"
                return f"{dt.day} {mon}" # {dt:%H:%M}"

            self.ax.xaxis.set_major_formatter(FuncFormatter(ru_fmt))

            for lbl in self.ax.get_xticklabels():
                lbl.set_rotation(30)
                lbl.set_horizontalalignment("right")

            self.fig.tight_layout()

        self.canvas.draw()
