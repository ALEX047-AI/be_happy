import tkinter as tk
from tkinter import messagebox
from datetime import datetime, date, time, timedelta

import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class DiaryView:
    """
    Дневник самочувствия
    Получает словарь с данными о настроении и коментариях по дням:
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

        self.BG = theme.BG
        self.FG = theme.FG
        self.ACTIVE_BG = theme.ACTIVE_BG
        self.LABEL_FG = theme.LABEL_FG
        self.BTN = theme.BTN
        self.ACCENT = theme.ACCENT
        self.PANEL = theme.PANEL
        self.FONT_SIZE = theme.FONT_SIZE
        self.FONT_NAME = theme.FONT_NAME

        self.selected_day = date.today()

        self._build()

    def _build(self):
        f = self.parent

        tk.Label(
            f, text="Дневник", fg=self.FG, bg=self.BG,
            font=("Arial", 18, "bold")
        ).pack(pady=15)

        header_row = tk.Frame(f, bg=self.BG)
        header_row.pack(fill="x", padx=12, pady=(0, 6))

        self.now_lbl = tk.Label(header_row, text="", bg=self.BG, fg=self.FG)
        self.now_lbl.pack(side="left")

        day_ctrl = tk.Frame(header_row, bg=self.BG)
        day_ctrl.pack(side="right")

        DAY_BTN = dict(
            bg=self.BTN,
            fg=self.FG,
            activebackground=self.ACTIVE_BG,
            activeforeground=self.FG,
            relief="flat",
            padx=8,
            pady=4,
            borderwidth=0,
            highlightthickness=0,
        )

        tk.Button(day_ctrl, text="◀", command=self.day_prev, **DAY_BTN).pack(side="left")
        self.day_var = tk.StringVar(value=self._format_day(self.selected_day))
        tk.Label(day_ctrl, textvariable=self.day_var, bg=self.BG, fg=self.FG).pack(side="left", padx=8)
        tk.Button(day_ctrl, text="Сегодня", command=self.day_today, **DAY_BTN).pack(side="left", padx=(0, 6))
        tk.Button(day_ctrl, text="▶", command=self.day_next, **DAY_BTN).pack(side="left")

        # Выбор периода
        period_row = tk.Frame(f, bg=self.BG)
        period_row.pack(fill="x", padx=12, pady=(0, 6))

        tk.Label(period_row, text="Период:", bg=self.BG, fg=self.FG).pack(side="left")

        self.period_var = tk.StringVar(value=self._guess_period())

        PERIOD_BTN = dict(
            indicatoron=0,
            bg=self.BTN,
            fg=self.FG,
            activebackground=self.ACTIVE_BG,
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

        # Текст (необязательно)
        self.diary_text = tk.Text(
            f, height=6,
            bg=self.PANEL, fg=self.FG, insertbackground=self.FG,
            relief="flat", wrap="word"
        )
        self.diary_text.pack(fill="x", padx=12, pady=(5, 8))

        # Настроение
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

        # Кнопочки
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

        # Схема
        chart_wrap = tk.Frame(f, bg=self.BG)
        chart_wrap.pack(fill="both", expand=True, padx=12, pady=(5, 12))

        self.fig = Figure(figsize=(6, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_wrap)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.period_var.trace_add("write", lambda *_: self._on_selection_change())

        self._load_selected_slot()
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

    def _period_to_iso_datetime(self, day=None) -> str:
        if day is None:
            day = self.selected_day
        hour = self._period_hour()
        dt = datetime.combine(day, time(hour=hour, minute=0, second=0))
        return dt.isoformat()

    def _matches_day_period(self, entry_date_str: str, target_day: date, target_hour: int) -> bool:
        try:
            dt = datetime.fromisoformat(entry_date_str)
        except Exception:
            return False
        return (dt.date() == target_day) and (dt.hour == target_hour)

    def save_entry(self):
        # Текст необязателен
        text = self.diary_text.get("1.0", "end").strip()
        mood = int(self.diary_mood.get())

        target_day = self.selected_day
        target_hour = self._period_hour()
        fixed_iso = self._period_to_iso_datetime(target_day)

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

        self._load_selected_slot()
        self.refresh()

    def _format_day(self, d: date) -> str:
        mon = self.RU_MONTHS_SHORT[d.month - 1]
        return f"{d.day} {mon} {d.year}"

    def _set_selected_day(self, d: date):
        self.selected_day = d
        if hasattr(self, "day_var"):
            self.day_var.set(self._format_day(self.selected_day))
        self._on_selection_change()

    def day_prev(self):
        self._set_selected_day(self.selected_day - timedelta(days=1))

    def day_next(self):
        self._set_selected_day(self.selected_day + timedelta(days=1))

    def day_today(self):
        self._set_selected_day(date.today())

    def _get_slot_entry(self, target_day: date, target_hour: int):
        for i, item in enumerate(self.diary):
            if isinstance(item, dict) and self._matches_day_period(item.get("date", ""), target_day, target_hour):
                return i, item
        return None, None

    def _load_selected_slot(self):
        target_day = self.selected_day
        target_hour = self._period_hour()
        _i, item = self._get_slot_entry(target_day, target_hour)
        if item is None:
            self.diary_mood.set(5)
            self.diary_text.delete("1.0", "end")
            return

        try:
            mood = int(item.get("mood", 5))
        except Exception:
            mood = 5
        mood = max(1, min(10, mood))
        self.diary_mood.set(mood)

        text = (item.get("text", "") or "").strip()
        self.diary_text.delete("1.0", "end")
        if text:
            self.diary_text.insert("1.0", text)

    def _on_selection_change(self):
        # Смена выбранной даты или периода
        try:
            self._load_selected_slot()
        except Exception:
            return
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

            sel = [(dt, mood) for dt, mood in points if dt.date() == self.selected_day]
            if sel:
                xs_sel = [p[0] for p in sel]
                ys_sel = [p[1] for p in sel]
                self.ax.plot(xs_sel, ys_sel, marker="o", linestyle="None", color=self.FG, zorder=5)
            self.ax.set_ylim(0, 10)
            self.ax.set_title("Самочувствие (по датам)")
            self.ax.set_ylabel("Оценка")

            locator = mdates.AutoDateLocator(minticks=3, maxticks=7)
            self.ax.xaxis.set_major_locator(locator)

            def ru_fmt(x, pos=None):
                dt = mdates.num2date(x)
                mon = self.RU_MONTHS_SHORT[dt.month - 1]
                # Показываем время но только 08:00 / 14:00 / 20:00
                if show_year:
                    return f"{dt.day} {mon} {dt.year}" # {dt:%H:%M}"
                return f"{dt.day} {mon}" # {dt:%H:%M}"

            self.ax.xaxis.set_major_formatter(FuncFormatter(ru_fmt))

            for lbl in self.ax.get_xticklabels():
                lbl.set_rotation(30)
                lbl.set_horizontalalignment("right")

            self.fig.tight_layout()

        self.canvas.draw()
