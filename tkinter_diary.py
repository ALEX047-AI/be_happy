import tkinter as tk
from tkinter import messagebox
from datetime import datetime

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class DiaryView:

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

        self.diary_text = tk.Text(
            f, height=6,
            bg=self.PANEL, fg=self.FG, insertbackground=self.FG,
            relief="flat", wrap="word"
        )
        self.diary_text.pack(fill="x", padx=12, pady=(5, 8))

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

        chart_wrap = tk.Frame(f, bg=self.BG)
        chart_wrap.pack(fill="both", expand=True, padx=12, pady=(5, 12))

        self.fig = Figure(figsize=(6, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_wrap)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.refresh()

    def save_entry(self):
        text = self.diary_text.get("1.0", "end").strip()
        mood = int(self.diary_mood.get())

        if not text:
            messagebox.showwarning("Пустая запись", "Введите текст записи перед сохранением.")
            return

        self.diary.append({
            "date": datetime.now().isoformat(),
            "mood": mood,
            "text": text
        })

        # callback
        try:
            self.save_callback(self.diary)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить дневник:\n{e}")
            return

        self.diary_text.delete("1.0", "end")
        self.refresh()

    def refresh(self):
        self.ax.clear()

        if self.diary:
            moods = []
            for dct in self.diary:
                try:
                    moods.append(int(dct.get("mood", 0)))
                except Exception:
                    moods.append(0)

            self.ax.plot(moods, marker="o", color=self.ACCENT)
            self.ax.set_ylim(0, 10)
            self.ax.set_title("Самочувствие (по записям)")
            self.ax.set_xlabel("Запись")
            self.ax.set_ylabel("Оценка")

        self.canvas.draw()
