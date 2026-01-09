"""
TD — Treatment of Depression
"""

import os
import random
from datetime import date

import matplotlib
matplotlib.use("TkAgg")

import tkinter as tk
from tkinter import messagebox

from options.config import settings

from articles import support_phrases
from profile_manage import load_profile, save_profile, crisis_keywords, load_json, save_json
from llm import get_frase_from_llm

from tkinter_diary import DiaryView


DATA = settings.DATA
DIARY_PATH = os.path.join(DATA, settings.diary_file_name)
os.makedirs(DATA, exist_ok=True)

BG = settings.BG
FG = settings.FG
BTN = settings.BTN
ACCENT = settings.ACCENT
PANEL = settings.PANEL


class TDApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("TD — Treatment of Depression")
        self.geometry("900x600")
        self.configure(bg=BG)

        self.profile = load_profile()
        self.diary = load_json(DIARY_PATH, [])

        self.create_layout()

        if not self.profile:
            self.show_profile()
        else:
            self.show_home()

    # ЗАПОЛНЕНИЕ ПРИЛОЖЕНИЯ

    def create_layout(self):
        self.create_menu()

        self.container = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True)

        self.frames = {}
        for name in ("home", "chat", "diary", "profile", "about"):
            frame = tk.Frame(self.container, bg=BG)
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.frames[name] = frame

        self.build_home()
        self.build_chat()


        # Дневник
        self.diary_view = DiaryView(
            parent=self.frames["diary"],
            diary=self.diary,
            save_callback=lambda d: save_json(DIARY_PATH, d),
            theme={"BG": BG, "FG": FG, "BTN": BTN, "ACCENT": ACCENT, "PANEL": PANEL},
        )

        self.build_profile()
        self.build_about()

    def create_menu(self):
        menubar = tk.Menu(self)

        nav_menu = tk.Menu(menubar, tearoff=0)
        nav_menu.add_command(label="Главная\t (Ctrl+H)", command=self.show_home)
        nav_menu.add_command(label="Чат поддержки\t (Ctrl+C)", command=self.show_chat)
        nav_menu.add_command(label="Дневник\t (Ctrl+D)", command=self.show_diary)
        nav_menu.add_command(label="Профиль\t (Ctrl+P)", command=self.show_profile)
        menubar.add_cascade(label="Файл", menu=nav_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="О проекте\t (Ctrl+A)", command=self.show_about)
        help_menu.add_command(label="Выход\t (Ctrl+E)", command=self.destroy)
        menubar.add_cascade(label="Помощь", menu=help_menu)

        self.config(menu=menubar)

        self.bind_all("<Control-h>", lambda e: self.show_home())
        self.bind_all("<Control-c>", lambda e: self.show_chat())
        self.bind_all("<Control-d>", lambda e: self.show_diary())
        self.bind_all("<Control-p>", lambda e: self.show_profile())
        self.bind_all("<Control-a>", lambda e: self.show_about())
        self.bind_all("<Control-e>", lambda e: self.destroy())

    def raise_frame(self, name):
        self.frames[name].tkraise()


    # ГЛАВНАЯ СТРАНИЦА

    def build_home(self):
        f = self.frames["home"]

        tk.Label(
            f, text="Ты не один", fg=FG, bg=BG,
            font=("Arial", 22, "bold")
        ).pack(pady=30)

        self.quote_var = tk.StringVar(value=random.choice(support_phrases))

        tk.Label(
            f, textvariable=self.quote_var, wraplength=600,
            fg=FG, bg=BG, font=("Arial", 14)
        ).pack(pady=20)

        def refresh_quote():
            if settings.USE_LLM:
                try:
                    self.quote_var.set(get_frase_from_llm(self.profile))
                    return
                except Exception:
                    pass
            self.quote_var.set(random.choice(support_phrases))

        tk.Button(
            f,
            text="Случайная поддержка",
            command=refresh_quote,
            bg=ACCENT, fg="white", relief="flat",
            padx=10, pady=6
        ).pack(pady=10)

        tk.Label(
            f,
            text="Это образовательное приложение. Если Вам нужна экстренная помощь —\n"
                 "пожалуйста, обратитесь в местные службы поддержки или к близким.",
            fg="#bbbbbb", bg=BG, font=("Arial", 10),
            justify="center"
        ).pack(pady=40)

    def show_home(self):
        self.raise_frame("home")


    # ДНЕВНИК

    def show_diary(self):
        self.diary_view.refresh()
        self.raise_frame("diary")

    # ЧАТ

    def build_chat(self):
        f = self.frames["chat"]

        tk.Label(
            f, text="Чат поддержки", fg=FG, bg=BG,
            font=("Arial", 18, "bold")
        ).pack(pady=20)

        self.chat_box = tk.Text(
            f, height=20, width=80,
            bg=PANEL, fg=FG, insertbackground=FG,
            relief="flat", wrap="word"
        )
        self.chat_box.pack(padx=20, pady=10)

        self.user_entry = tk.Entry(
            f, width=60,
            bg=BTN, fg=FG, insertbackground=FG,
            relief="flat"
        )
        self.user_entry.pack(pady=10)
        self.user_entry.bind("<Return>", lambda e: self.send_message())

        tk.Button(
            f, text="Отправить",
            command=self.send_message,
            bg=ACCENT, fg="white",
            relief="flat", padx=10, pady=6
        ).pack(pady=5)

        self.append_chat("Привет. Я могу выслушать Вас. Что сейчас на душе?\n")

    def send_message(self):
        msg = self.user_entry.get().strip()
        if not msg:
            return
        self.user_entry.delete(0, tk.END)

        self.append_chat(f"Ты: {msg}\n")
        lower = msg.lower()

        if any(k in lower for k in crisis_keywords):
            response = (
                "Мне очень жаль, что тебе так тяжело. Я не могу заменить профессиональную помощь.\n"
                "Если ты в опасности или думаешь о самоповреждении — пожалуйста, немедленно обратись в экстренные службы "
                "в твоей стране, или позвони близкому человеку.\n"
                "Если можешь — скажи, где ты находишься (страна/город), и я подскажу, куда обратиться.\n"
            )
            self.append_chat(f"TD: {response}\n")
            return

        if "плохо" in lower or "тяжело" in lower or "груст" in lower:
            response = "Понимаю. Хочешь рассказать, что именно сейчас больше всего давит?"
        elif "один" in lower or "одна" in lower:
            response = "Ощущать одиночество очень больно. Есть ли кто-то, кому ты мог(ла) бы написать прямо сейчас?"
        elif "не знаю" in lower:
            response = "Это нормально — не знать. Давай начнём с малого: что ты чувствуешь в данный момент?"
        else:
            response = random.choice(support_phrases)

        self.append_chat(f"TD: {response}\n")

    def append_chat(self, text):
        self.chat_box.insert(tk.END, text)
        self.chat_box.see(tk.END)

    def show_chat(self):
        self.raise_frame("chat")

    # ПРОФИЛЬ

    def build_profile(self):
        f = self.frames["profile"]

        tk.Label(
            f, text="Профиль", fg=FG, bg=BG,
            font=("Arial", 18, "bold")
        ).pack(pady=20)

        def normalize(value: str, allowed: tuple[str, ...]) -> str:
            value = (value or "").strip()
            return value if value in allowed else ""

        RADIO_BTN = dict(
            indicatoron=0,
            bg=BTN,
            fg=FG,
            activebackground="#2a2a2a",
            activeforeground=FG,
            selectcolor=ACCENT,
            relief="flat",
            padx=10,
            pady=6,
            borderwidth=0,
            highlightthickness=0,
        )

        self.name_var = tk.StringVar(value=str(self.profile.get("Имя", "")))
        self.gender_var = tk.StringVar(value=normalize(self.profile.get("Пол", ""), ("Мужской", "Женский")))
        self.birth_var = tk.StringVar(value=str(self.profile.get("Дата рождения", "")))
        self.marital_var = tk.StringVar(
            value=normalize(self.profile.get("Семейное положение", ""), ("Холост / Не замужем", "Женат / Замужем"))
        )
        self.parents_var = tk.StringVar(value=normalize(self.profile.get("Родители", ""), ("Да", "Нет")))
        self.friends_var = tk.StringVar(value=normalize(self.profile.get("Друзья", ""), ("Да", "Нет")))

        try:
            children_default = int(self.profile.get("Дети", 0))
        except Exception:
            children_default = 0
        self.children_var = tk.IntVar(value=max(0, min(10, children_default)))

        comment_default = str(self.profile.get("Комментарий", ""))

        form = tk.Frame(f, bg=BG)
        form.pack(pady=10)

        def label(row, text):
            tk.Label(form, text=text + ":", fg=FG, bg=BG, anchor="w", width=25)\
                .grid(row=row, column=0, sticky="w", padx=5, pady=6)

        label(0, "Имя")
        tk.Entry(form, textvariable=self.name_var, width=40, bg=BTN, fg=FG, insertbackground=FG, relief="flat")\
            .grid(row=0, column=1, sticky="w", padx=5, pady=6)

        label(1, "Пол")
        gender_frame = tk.Frame(form, bg=BG)
        gender_frame.grid(row=1, column=1, sticky="w", padx=5, pady=6)
        tk.Radiobutton(gender_frame, text="Мужской", variable=self.gender_var, value="Мужской", **RADIO_BTN)\
            .pack(side="left", padx=(0, 10))
        tk.Radiobutton(gender_frame, text="Женский", variable=self.gender_var, value="Женский", **RADIO_BTN)\
            .pack(side="left")

        label(2, "Дата рождения")
        birth_frame = tk.Frame(form, bg=BG)
        birth_frame.grid(row=2, column=1, sticky="w", padx=5, pady=6)
        tk.Entry(birth_frame, textvariable=self.birth_var, width=20, bg=BTN, fg=FG, insertbackground=FG, relief="flat")\
            .pack(side="left", padx=(0, 10))
        tk.Button(birth_frame, text="Выбрать", command=self.open_birthdate_picker,
                  bg=ACCENT, fg="white", relief="flat", padx=10, pady=4)\
            .pack(side="left")

        label(3, "Семейное положение")
        marital_frame = tk.Frame(form, bg=BG)
        marital_frame.grid(row=3, column=1, sticky="w", padx=5, pady=6)
        tk.Radiobutton(marital_frame, text="Холост / Не замужем", variable=self.marital_var,
                       value="Холост / Не замужем", **RADIO_BTN).pack(side="left", padx=(0, 10))
        tk.Radiobutton(marital_frame, text="Женат / Замужем", variable=self.marital_var,
                       value="Женат / Замужем", **RADIO_BTN).pack(side="left")

        label(4, "Родители")
        parents_frame = tk.Frame(form, bg=BG)
        parents_frame.grid(row=4, column=1, sticky="w", padx=5, pady=6)
        tk.Radiobutton(parents_frame, text="Да", variable=self.parents_var, value="Да", **RADIO_BTN)\
            .pack(side="left", padx=(0, 10))
        tk.Radiobutton(parents_frame, text="Нет", variable=self.parents_var, value="Нет", **RADIO_BTN)\
            .pack(side="left")

        label(5, "Дети")
        tk.Spinbox(form, from_=0, to=10, textvariable=self.children_var,
                   width=5, bg=BTN, fg=FG, insertbackground=FG, relief="flat", buttonbackground=BTN)\
            .grid(row=5, column=1, sticky="w", padx=5, pady=6)

        label(6, "Друзья")
        friends_frame = tk.Frame(form, bg=BG)
        friends_frame.grid(row=6, column=1, sticky="w", padx=5, pady=6)
        tk.Radiobutton(friends_frame, text="Да", variable=self.friends_var, value="Да", **RADIO_BTN)\
            .pack(side="left", padx=(0, 10))
        tk.Radiobutton(friends_frame, text="Нет", variable=self.friends_var, value="Нет", **RADIO_BTN)\
            .pack(side="left")

        label(7, "Комментарий")
        comment_frame = tk.Frame(form, bg=BG)
        comment_frame.grid(row=7, column=1, sticky="w", padx=5, pady=6)

        self.comment_text = tk.Text(comment_frame, width=40, height=5, bg=PANEL, fg=FG,
                                    insertbackground=FG, relief="flat", wrap="word")
        self.comment_text.pack(side="left")
        self.comment_text.insert("1.0", comment_default)

        scroll = tk.Scrollbar(comment_frame, command=self.comment_text.yview)
        scroll.pack(side="left", fill="y", padx=(6, 0))
        self.comment_text.configure(yscrollcommand=scroll.set)

        tk.Button(
            f, text="Сохранить профиль",
            command=self.save_profile_data,
            bg=ACCENT, fg="white", relief="flat",
            padx=10, pady=6
        ).pack(pady=20)

    def open_birthdate_picker(self):
        top = tk.Toplevel(self)
        top.title("Выбор даты рождения")
        top.configure(bg=BG)
        top.resizable(False, False)
        top.grab_set()

        today = date.today()
        year_min = 1900
        year_max = today.year - 10

        y, m, d = today.year, today.month, today.day
        cur = self.birth_var.get().strip()
        try:
            parts = cur.split("-")
            if len(parts) == 3:
                y = int(parts[0])
                m = int(parts[1])
                d = int(parts[2])
        except Exception:
            pass

        y = max(year_min, min(year_max, y))
        m = max(1, min(12, m))
        d = max(1, min(31, d))

        tk.Label(top, text="Год:", fg=FG, bg=BG).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Label(top, text="Месяц:", fg=FG, bg=BG).grid(row=1, column=0, padx=10, pady=10, sticky="e")
        tk.Label(top, text="День:", fg=FG, bg=BG).grid(row=2, column=0, padx=10, pady=10, sticky="e")

        year_var = tk.IntVar(value=y)
        month_var = tk.IntVar(value=m)
        day_var = tk.IntVar(value=d)

        tk.Spinbox(top, from_=year_min, to=year_max, textvariable=year_var, width=8,
                   bg=BTN, fg=FG, insertbackground=FG, relief="flat")\
            .grid(row=0, column=1, padx=10, pady=10, sticky="w")

        tk.Spinbox(top, from_=1, to=12, textvariable=month_var, width=8,
                   bg=BTN, fg=FG, insertbackground=FG, relief="flat")\
            .grid(row=1, column=1, padx=10, pady=10, sticky="w")

        tk.Spinbox(top, from_=1, to=31, textvariable=day_var, width=8,
                   bg=BTN, fg=FG, insertbackground=FG, relief="flat")\
            .grid(row=2, column=1, padx=10, pady=10, sticky="w")

        def is_valid_date(yy, mm, dd):
            try:
                date(yy, mm, dd)
                return True
            except Exception:
                return False

        def set_date():
            yy = int(year_var.get())
            mm = int(month_var.get())
            dd = int(day_var.get())

            if not is_valid_date(yy, mm, dd):
                messagebox.showerror("Ошибка", "Некорректная дата.")
                return

            self.birth_var.set(f"{yy:04d}-{mm:02d}-{dd:02d}")
            top.destroy()

        btns = tk.Frame(top, bg=BG)
        btns.grid(row=3, column=0, columnspan=2, pady=(5, 12))

        tk.Button(btns, text="OK", command=set_date, bg=ACCENT, fg="white", relief="flat", padx=14, pady=6)\
            .pack(side="left", padx=8)
        tk.Button(btns, text="Отмена", command=top.destroy, bg=BTN, fg=FG, relief="flat", padx=14, pady=6)\
            .pack(side="left", padx=8)

    def save_profile_data(self):
        data = {
            "Имя": self.name_var.get().strip(),
            "Пол": self.gender_var.get().strip(),
            "Дата рождения": self.birth_var.get().strip(),
            "Семейное положение": self.marital_var.get().strip(),
            "Родители": self.parents_var.get().strip(),
            "Дети": max(0, min(10, int(self.children_var.get()))),
            "Друзья": self.friends_var.get().strip(),
            "Комментарий": self.comment_text.get("1.0", "end").strip(),
        }

        if save_profile(data):
            self.profile = data
            messagebox.showinfo("Сохранено", "Профиль сохранён.")
            self.show_home()
        else:
            messagebox.showerror("Ошибка", "Не удалось сохранить профиль.")

    def show_profile(self):
        self.raise_frame("profile")

    # О ПРИЛОЖЕНИИ

    def build_about(self):
        f = self.frames["about"]

        tk.Label(
            f, text="О проекте", fg=FG, bg=BG,
            font=("Arial", 18, "bold")
        ).pack(pady=20)

        text = (
            "TD — образовательное приложение о поддержке при трудных эмоциях.\n\n"
            "Важно:\n"
            "- Это НЕ медицинский инструмент.\n"
            "- Если тебе нужна экстренная помощь — обратись к специалистам или в службы помощи.\n\n"
            "Функции:\n"
            "- Слова поддержки\n"
            "- Простой чат\n"
            "- Дневник\n"
            "- Профиль\n"
        )

        tk.Label(f, text=text, fg=FG, bg=BG, wraplength=600).pack(padx=20, pady=40)

    def show_about(self):
        self.raise_frame("about")


if __name__ == "__main__":
    app = TDApp()
    app.mainloop()
