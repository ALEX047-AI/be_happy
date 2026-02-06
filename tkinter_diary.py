import tkinter as tk
from tkinter import messagebox
try:
    import customtkinter as ctk
except Exception as _e:
    raise ImportError(
        "customtkinter is required for this version. Install it with: pip install customtkinter"
    ) from _e
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

    def __init__(self, parent, diary: dict, save_callback, theme, calendar_func, tr=None, lang_get=None):
        self.parent = parent
        self.diary: dict = diary
        self.save_callback = save_callback
        self.calendar_func = calendar_func

        # Локализованный текст интерфейса (опционально)
        self.tr = tr if callable(tr) else (lambda k, d=None, **fmt: (d or k).format(**fmt) if fmt else (d or k))
        self.lang_get = lang_get if callable(lang_get) else (lambda k, default=None: default)
        self.diary_init_mood = 0

        # Тема
        self.BG = theme.BG
        self.FG = theme.FG
        self.ACTIVE_BG = theme.ACTIVE_BG
        self.LABEL_FG = theme.LABEL_FG
        self.BTN = theme.BTN
        self.ACCENT = theme.ACCENT
        self.PANEL = theme.PANEL

        self.FONT_NAME = getattr(theme, "FONT_NAME", "Arial")
        self.FONT_SIZE = getattr(theme, "FONT_SIZE", 12)

        # Опционально (Схема и Слайдеры)
        self.CHART_BG = getattr(theme, "CHART_BG", None) or self.BG
        self.CHART_AX_BG = getattr(theme, "CHART_AX_BG", None) or self.PANEL
        self.CHART_FG = getattr(theme, "CHART_FG", None) or self.FG
        self.CHART_GRID = getattr(theme, "CHART_GRID", None) or self.ACTIVE_BG
        self.CHART_LINE = getattr(theme, "CHART_LINE", None) or self.ACCENT
        self.CHART_SELECTED = getattr(theme, "CHART_SELECTED", None) or self.FG

        self.SLIDER_FG = getattr(theme, "SLIDER_FG", None) or self.ACTIVE_BG
        self.SLIDER_PROGRESS = getattr(theme, "SLIDER_PROGRESS", None) or self.ACCENT
        self.SLIDER_BUTTON = getattr(theme, "SLIDER_BUTTON", None) or self.ACCENT

        self.selected_day = date.today()

        self._build()

    def _build(self):
        f = self.parent

        # для перерисовки
        for w in f.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        try:
            f.configure(fg_color=self.BG)
        except Exception:
            try:
                f.configure(bg=self.BG)
            except Exception:
                pass

        ctk.CTkLabel(
            f,
            text=self.tr("diary.title", "Дневник"),
            font=(self.FONT_NAME, 18, "bold"),
            text_color=self.FG,
        ).pack(pady=(14, 10))

        header_row = ctk.CTkFrame(f, fg_color="transparent")
        header_row.pack(fill="x", padx=12, pady=(0, 6))

        self.now_lbl = ctk.CTkLabel(
            header_row,
            text="",
            text_color=self.LABEL_FG,
        )
        self.now_lbl.pack(side="left")
        self._update_now_label()

        day_ctrl = ctk.CTkFrame(header_row, fg_color="transparent")
        day_ctrl.pack(side="right")

        self.prev_day_btn = ctk.CTkButton(
            day_ctrl,
            text="◀",
            width=44,
            height=32,
            corner_radius=10,
            fg_color=self.ACCENT,
            hover_color=self.ACCENT,
            text_color="white",
            command=self.goto_prev_day,
        )
        self.prev_day_btn.pack(side="left", padx=(0, 8))

        self.today_btn = ctk.CTkButton(
            day_ctrl,
            text=self.tr("diary.today", "Сегодня"),
            width=110,
            height=32,
            corner_radius=10,
            fg_color=self.BTN,
            hover_color=self.ACTIVE_BG,
            text_color=self.FG,
            command=self.goto_today,
        )
        self.today_btn.pack(side="left", padx=(0, 8))

        def pick_date():
            def on_pick(d: date):
                self._set_selected_day(d)
            try:
                self.calendar_func(title=self.tr("diary.pick_date", "Выбор даты"), year_max_shift=0, current=self.selected_day, callback=on_pick)
            except TypeError:
                # if calendar_func has old signature
                self.calendar_func(callback=on_pick)

        self.calendar_btn = ctk.CTkButton(
            day_ctrl,
            text="📅",
            width=160,
            height=32,
            corner_radius=10,
            fg_color=self.BTN,
            hover_color=self.ACTIVE_BG,
            text_color=self.FG,
            command=pick_date,
        )
        self.calendar_btn.pack(side="left", padx=(0, 8))

        self.next_day_btn = ctk.CTkButton(
            day_ctrl,
            text="▶",
            width=44,
            height=32,
            corner_radius=10,
            fg_color=self.ACCENT,
            hover_color=self.ACCENT,
            text_color="white",
            command=self.goto_next_day,
        )
        self.next_day_btn.pack(side="left")

        # Выбор периода
        period_row = ctk.CTkFrame(f, fg_color="transparent")
        period_row.pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkLabel(period_row, text=self.tr("diary.period", "Период") + ":", text_color=self.FG).pack(side="left", padx=(0, 10))

        self.period_var = tk.StringVar(value=self._guess_period())

        self.period_rbs = {}
        for label, code, _hour in self.PERIODS:
            label = self.tr(f"diary.periods.{code}", label)
            rb = ctk.CTkRadioButton(
                period_row,
                text=label,
                variable=self.period_var,
                value=code,
                text_color=self.FG,
                fg_color=self.ACCENT,
                command=self._load_selected_slot,
            )
            rb.pack(side="left", padx=8)
            self.period_rbs[_hour] = rb

        # Текст (необязательно)
        """ self.diary_text = tk.Text(
            f, height=6,
            bg=self.PANEL, fg=self.FG, insertbackground=self.FG,
            relief="flat", wrap="word"
        )
        self.diary_text.pack(fill="x", padx=12, pady=(5, 8)) """
        self.diary_text = ctk.CTkTextbox(
            f,
            height=110,
            fg_color=self.PANEL,
            text_color=self.FG,
            corner_radius=10,
        )
        self.diary_text.pack(fill="x", padx=12, pady=(4, 10))

        # Настроение
        mood_row = tk.Frame(f, bg=self.BG)
        mood_row.pack(fill="x", padx=12)

        mood_row = ctk.CTkFrame(f, fg_color="transparent")
        mood_row.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(mood_row, text=self.tr("diary.mood", "Настроение") + ":", text_color=self.FG).pack(side="left", padx=(0, 10))

        self.diary_mood = tk.IntVar(value=self.diary_init_mood)

        self.mood_slider = ctk.CTkSlider(
            mood_row,
            from_=0,
            to=10,
            number_of_steps=10,
            fg_color=self.SLIDER_FG,
            progress_color=self.SLIDER_PROGRESS,
            button_color=self.SLIDER_BUTTON,
            button_hover_color=self.SLIDER_BUTTON,
            command=lambda v: self.diary_mood.set(int(round(v))),
        )
        self.mood_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        try:
            self.mood_slider.set(self.diary_mood.get())
        except Exception:
            pass

        ctk.CTkLabel(mood_row, textvariable=self.diary_mood, text_color=self.FG, width=32).pack(side="left")

        """ ctk.CTkLabel(f, text="Комментарий:", text_color=self.FG).pack(anchor="w", padx=12)
        self.comment_box = ctk.CTkTextbox(
            f,
            height=110,
            fg_color=self.PANEL,
            text_color=self.FG,
            corner_radius=10,
        )
        self.comment_box.pack(fill="x", padx=12, pady=(4, 10)) """

        ctk.CTkButton(
            f,
            text=self.tr("diary.save", "Сохранить"),
            fg_color=self.ACCENT,
            hover_color=self.ACCENT,
            text_color="white",
            corner_radius=10,
            height=36,
            command=self.save_entry,
        ).pack(pady=(0, 8))

        # Схема
        chart_wrap = ctk.CTkFrame(f, fg_color="transparent")
        chart_wrap.pack(fill="both", expand=True, padx=12, pady=(5, 12))

        self.fig = Figure(figsize=(6, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_wrap)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.refresh_chart()
        self._set_selected_day(self.selected_day)


    def _update_now_label(self):
        """Обновляем небольшие часы в Дневнике"""
        try:
            now = datetime.now()
            self.now_lbl.configure(text=self.tr("diary.clock", "Сейчас: {now:%d.%m.%Y %H:%M}", now=now))
        except Exception:
            return
        # обновляем каждые 10 секунд
        try:
            self.parent.after(10_000, self._update_now_label)
        except Exception:
            pass

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
        value_changed = True
        if any((text, mood)):
            current_item = {}
            if mood: current_item["mood"] = mood
            if text: current_item["text"] = text
            self.diary[fixed_iso] = current_item
        else:
            value_changed = False if (self.diary.pop(fixed_iso, None) is None) else True

        """ replaced = False
        for i, item in enumerate(self.diary):
            if isinstance(item, dict) and self._matches_day_period(item.get("date", ""), target_day, target_hour):
                current_item = {}
                if mood:
                    current_item["mood"] = mood
                if text:
                    current_item["text"] = text
                if current_item:
                    current_item["date"] = fixed_iso
                    self.diary[i] = current_item
                else:
                    try:
                        self.diary.pop(i)
                    except Exception as e:
                        print('Ошибка удаления элемента Дневника')

                replaced = True
                break

        if not replaced:
            current_item = {"date": fixed_iso}
            current_item = {}
            if mood:
                current_item["mood"] = mood
            if text:
                current_item["text"] = text
            if current_item:
                current_item["date"] = fixed_iso
                self.diary.append(current_item)
            # self.diary.append({"date": fixed_iso, "mood": mood, "text": text})
         """
        try:
            if value_changed:
                self.diary = dict(sorted(self.diary.items()))
                self.save_callback(self.diary)
        except Exception as e:
            messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("diary.errors.save_failed", "Не удалось сохранить дневник:\n{e}", e=e))
            return

        self._load_selected_slot()
        self.refresh_chart()

    def _format_day(self, d: date) -> str:
        mon = self.lang_get('diary.months_short', self.RU_MONTHS_SHORT)[d.month - 1]
        return f"{d.day} {mon} {d.year}"

    def _set_selected_day(self, d: date):
        self.selected_day = d
        if hasattr(self, "calendar_btn"):
            # self.day_var.set(self._format_day(self.selected_day))
            self.calendar_btn.configure(text=self._format_day(self.selected_day))
        self._on_selection_change()
        datetime_now = datetime.now()
        if self.selected_day >= date.today():
            day_next_state = 'disabled'
            self.period_var.set('morning')
        else:
            day_next_state = 'normal'
        for radio_hour, rb in self.period_rbs.items():
            if radio_hour == 8:
                rb.configure(state="normal")

            elif radio_hour <= datetime_now.hour:
                rb.configure(state="normal")
            else:
                rb.configure(state=day_next_state)
        self.next_day_btn.configure(state=day_next_state)

    def goto_prev_day(self):
        self._set_selected_day(self.selected_day - timedelta(days=1))

    def goto_next_day(self):
        self._set_selected_day(self.selected_day + timedelta(days=1))

    def goto_today(self):
        self._set_selected_day(date.today())

    def _get_slot_entry(self, target_day: date, target_hour: int):
        for key, value in self.diary.items():
            if isinstance(value, dict) and self._matches_day_period(key, target_day, target_hour):
                return key, value
        return None, None

    def _load_selected_slot(self):
        target_day = self.selected_day
        target_hour = self._period_hour()
        _i, item = self._get_slot_entry(target_day, target_hour)
        if item is None:
            self.diary_mood.set(self.diary_init_mood)
            self.mood_slider.set(self.diary_init_mood)
            self.diary_text.delete("1.0", "end")
            return

        try:
            mood = int(item.get("mood", self.diary_init_mood))
        except Exception:
            mood = self.diary_init_mood
        mood = max(1, min(10, mood))
        self.diary_mood.set(mood)
        self.mood_slider.set(mood)

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
        self.refresh_chart()


    def _apply_chart_theme(self):
        """Применить цвета темы для Matplotlib figure/axes."""
        try:
            self.fig.patch.set_facecolor(self.CHART_BG)
        except Exception:
            pass
        try:
            self.ax.set_facecolor(self.CHART_AX_BG)
        except Exception:
            pass
        try:
            self.canvas.get_tk_widget().configure(bg=self.CHART_BG)
        except Exception:
            pass

        # Для ticks и spines
        try:
            self.ax.tick_params(axis="both", colors=self.CHART_FG)
        except Exception:
            pass
        for spine in getattr(self.ax, "spines", {}).values():
            try:
                spine.set_color(self.CHART_FG)
            except Exception:
                pass

    def refresh_chart(self):
        self.ax.clear()
        self._apply_chart_theme()

        points = []
        for key, item in self.diary.items():
            if not isinstance(item, dict):
                continue
            try:
                dt = datetime.fromisoformat(key)
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

            self.ax.plot(xs, ys, marker="o", color=self.CHART_LINE)

            sel = [(dt, mood) for dt, mood in points if dt.date() == self.selected_day]
            if sel:
                xs_sel = [p[0] for p in sel]
                ys_sel = [p[1] for p in sel]
                self.ax.plot(xs_sel, ys_sel, marker="o", linestyle="None", color=self.CHART_SELECTED, zorder=5)
            self.ax.set_ylim(0, 10)
            self.ax.set_title(self.tr("diary.chart_title", "Самочувствие (по датам)"), color=self.CHART_FG)
            try:
                self.ax.grid(True, color=self.CHART_GRID, alpha=0.35)
            except Exception:
                pass
            self.ax.set_ylabel(self.lang_get('diary.score', "Оценка"), color=self.CHART_FG)
            locator = mdates.AutoDateLocator(minticks=3, maxticks=7)
            self.ax.xaxis.set_major_locator(locator)

            def ru_fmt(x, pos=None):
                dt = mdates.num2date(x)
                mon = self.lang_get('diary.months_short', self.RU_MONTHS_SHORT)[dt.month - 1]
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
