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
from tkinter import filedialog

from queue import Queue
from dataclasses import dataclass

from options.config import settings, TTS_VOICES, city_list
from services.city_events import EVENTS_INFO_DYNAMIC, SharedData

from articles import support_phrases
from profile_manage import (load_profile, save_profile, crisis_keywords, load_json, save_json,
                            sheet_to_list, sheet_to_dict, dict_to_sheet, profile_fields, diary_fields)
from llm import LLM_IO  # get_frase_from_llm, get_frase_from_llm_stream
from services.speech_service import SpeechPlayer, TTS_Stream
from tkinter_diary import DiaryView
from idlelib.tooltip import Hovertip

DATA = settings.DATA
DIARY_PATH = os.path.join(DATA, settings.diary_file_name)
os.makedirs(DATA, exist_ok=True)



class TDApp(tk.Tk):

    # BG = settings.BG
    # FG = settings.FG
    # ACTIVE_BG = settings.ACTIVE_BG
    # LABEL_FG = settings.LABEL_FG
    # BTN = settings.BTN
    # ACCENT = settings.ACCENT
    # PANEL = settings.PANEL

    # FONT_SIZE = settings.FONT_SIZE
    # FONT_NAME = settings.FONT_NAME

    def __init__(self):
        super().__init__()

        self.title(settings.TITLE)
        self.geometry(settings.GEOMETRY)

        self.theme_renew(settings.app_options.THEME)
        self.profile = load_profile()
        self.diary = load_json(DIARY_PATH, [])

        self.configure(bg=self.BG)

        self.create_layout()

        if not self.profile:
            self.show_profile()
        else:
            self.show_home()


        self.q_text = Queue()
        self.q_speech = Queue()
        self.player = None
        self.tts_stream = None
        self.llm_item = None
        self.ivents_renew = None
        self.events_doc = None

        if settings.app_options.USE_TTS:
            self.player = SpeechPlayer(q_in=self.q_speech, finished_item=True, daemon=True)
            self.player.start()

            self.tts_stream = TTS_Stream(q_in=self.q_text, q_out=self.q_speech, daemon=True,
                                voice=settings.tts_voice,
                                finished_item=True, save_to_disk=False,
                                sample_rate=24000, channels=1
                    )
            self.tts_stream.start()

        shared_data = SharedData()

        self.llm_item = LLM_IO(self.profile, settings.MODEL_SOURCE, ai_intro=settings.CHAT_INTRO_TEXT, shared_data=shared_data)
        self.llm_item.text_stream_last_queue = self.q_text

        if settings.USE_EVENTS:
            self.ivents_renew = EVENTS_INFO_DYNAMIC(shared_data)
            self.ivents_renew.start()

            self._user_city = self.profile.get('Город')
            self.tk_renew_events()

        # if self._user_city:
        #     if isinstance(self._user_city, str):
        #         self.ivents_renew.set_query_param({"city": self._user_city.title()}, renew=True)
        #         self.ivents_renew.reniew_events()
        #         pass
        """ data = get_events_info(
                # from_day="2026-01-24",
                # to_day="2026-01-31",
                city=self.user_city,
                limit=settings.EVENT_LIMIT_LOAD,
            )

            self.events_doc = compile_events_info(data) """
        """ self.events_doc = shared_data.get()
            print(self.events_doc)

            # добавляем события
            self.llm_item.update_events(self.events_doc) """

        self._active_stream = None  # для отмены предыдущего потока, если это нужно

    def make_scrollable(self, parent):
        """
        Делает область scrollable: Canvas + Scrollbar + inner Frame.
        Возвращает (canvas, content_frame).
        """
        outer = tk.Frame(parent, bg=self.BG)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=self.BG, highlightthickness=0, bd=0)
        canvas.pack(side="left", fill="both", expand=True)

        scroll = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        scroll.pack(side="left", fill="y")
        canvas.configure(yscrollcommand=scroll.set)

        content = tk.Frame(canvas, bg=self.BG)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def on_configure(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_resize(event):
            # растягиваем inner frame по ширине canvas
            canvas.itemconfig(window_id, width=event.width)

        content.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", on_canvas_resize)

        # колесо мыши (Linux/Windows/macOS)
        def on_mousewheel(event):
            # Windows/macOS: event.delta; Linux: Button-4/5
            if hasattr(event, "delta") and event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                if event.num == 4:
                    canvas.yview_scroll(-3, "units")
                elif event.num == 5:
                    canvas.yview_scroll(3, "units")

        # чтобы работало когда курсор над страницей
        outer.bind_all("<MouseWheel>", on_mousewheel)     # Windows/macOS
        outer.bind_all("<Button-4>", on_mousewheel)       # Linux up
        outer.bind_all("<Button-5>", on_mousewheel)       # Linux down

        return canvas, content

    def tk_renew_events(self):
        if settings.USE_EVENTS and self.ivents_renew is not None:
            self._user_city = self.profile.get('Город')
            if self._user_city:
                if isinstance(self._user_city, str):
                    self.ivents_renew.set_query_param({"city": self._user_city.title()}, renew=True)
                    # self.ivents_renew.reniew_events()
                    pass

    def player_pause(self):
        if self.player is not None:
            self.player.pause()

    def player_resume(self):
        if self.player is not None:
            self.player.resume()

    def llm_queue_pause(self):
        if self.llm_item:
            self.llm_item.pause_last_llm_text_stream_to_queue()

    def tts_stream_resume(self):
        if self.tts_stream is not None:
            self.tts_stream.resume_queue()

    def player_stop(self, full_stop=True):
        # только для прерывания генерации. такой как СТОП.
        # для кнопки отправка сообщения это не нужно
        if full_stop:
            self.llm_queue_pause()
            if self.tts_stream is not None:
                self.tts_stream.stop_queue()
        if self.player is not None:
            # self.player.pause()
            self.player.stop()
            # self.player.resume()


    def theme_renew(self, name=settings.app_options.THEME):

        self.theme = settings.THEMES.get(name) or settings.THEMES[settings.THEMES_DEFAULT] or settings.THEMES['Тёмная']

        self.BG = self.theme.BG
        self.FG = self.theme.FG
        self.ACTIVE_BG = self.theme.ACTIVE_BG
        self.LABEL_FG = self.theme.LABEL_FG
        self.BTN = self.theme.BTN
        self.ACCENT = self.theme.ACCENT
        self.PANEL = self.theme.PANEL
        self.FONT_SIZE = self.theme.FONT_SIZE
        self.FONT_NAME = self.theme.FONT_NAME

    # ЗАПОЛНЕНИЕ ПРИЛОЖЕНИЯ

    def create_layout(self):
        self.create_menu()

        self.container = tk.Frame(self, bg=self.BG)
        self.container.pack(fill="both", expand=True)

        self.frames = {}
        for name in ("home", "chat", "diary", "profile", "options", "about"):
            frame = tk.Frame(self.container, bg=self.BG)
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.frames[name] = frame

        self.build_home()
        self.build_chat()

        # Дневник
        self.diary_view = DiaryView(
            parent=self.frames["diary"],
            diary=self.diary,
            save_callback=lambda d: save_json(DIARY_PATH, d),
            theme=self.theme,
        )
        # theme={"BG": self.BG, "FG": self.FG, "BTN": self.BTN, "ACCENT": self.ACCENT, "PANEL": self.PANEL},

        self.build_profile()
        self.build_about()


    # Функции экспорта
    def export_profile0(self, initialfile=None):

        if initialfile is None:
            initialfile = f'Профиль {self.profile.get("Имя", "Пользователя")}'

        path = filedialog.asksaveasfilename(
            title="Экспорт профиля",
            defaultextension=".json",
            initialfile=initialfile,
            filetypes=[("JSON", "*.json")]
        )
        if not path:
            return
        try:
            save_json(path, self.profile)
            messagebox.showinfo("OK", "Профиль экспортирован.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось экспортировать профиль:\n{e}")

    def export_profile(self, initialfile=None):

        if initialfile is None:
            initialfile = f'Профиль {self.profile.get("Имя", "Пользователя")}'

        path = filedialog.asksaveasfilename(
            title="Экспорт профиля",
            defaultextension=".json",
            initialfile=initialfile,
            filetypes=[
                ("OpenDocument", "*.ods"),
                ("Excel", "*.xlsx"),
                ("CSV", "*.csv"),
                ("JSON", "*.json"),
            ]
        )
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()

        try:
            if ext == ".json":
                save_json(path, self.profile)
            elif ext in (".xlsx", ".ods", ".csv"):
                dict_to_sheet(self.profile, path, format=ext)
            else:
                messagebox.showerror("Ошибка", "Выберите .json .xlsx .ods .csv")
                return

            messagebox.showinfo("OK", "Профиль экспортирован.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось экспортировать профиль:\n{e}")

    def export_diary0(self, initialfile=None):
        if initialfile is None:
            initialfile = f'Дневник {self.profile.get("Имя", "Пользователя")}'

        path = filedialog.asksaveasfilename(
            title="Экспорт дневника",
            defaultextension=".json",
            initialfile=initialfile,
            filetypes=[("JSON", "*.json")]
        )
        if not path:
            return
        try:
            save_json(path, self.diary)
            messagebox.showinfo("OK", "Дневник экспортирован.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось экспортировать дневник:\n{e}")

    def export_diary(self, initialfile=None):
        if initialfile is None:
            initialfile = f'Дневник {self.profile.get("Имя", "Пользователя")}'

        path = filedialog.asksaveasfilename(
            title="Экспорт дневника (ods csv xlsx json)",
            defaultextension=".json",
            initialfile=initialfile,
            filetypes=[
                ("OpenDocument", "*.ods"),
                ("Excel", "*.xlsx"),
                ("CSV", "*.csv"),
                ("JSON", "*.json"),
            ],
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()

        try:
            if ext == ".json":
                save_json(path, self.diary)
            elif ext in (".xlsx", ".ods", ".csv"):
                dict_to_sheet(self.diary, path, format=ext)
            else:
                messagebox.showerror("Ошибка", "Выберите .json .xlsx .ods .csv")
                return

            messagebox.showinfo("OK", "Дневник экспортирован.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось экспортировать дневник:\n{e}")

    def update_llm_profile(self):
        # Обновляем LLM profile без потери данных профиля
        # И очищаем историю
        if hasattr(self, "llm_item") and self.llm_item is not None:
            self.llm_item.update_profile(self.profile)
            self.llm_item.clear_history()

    def update_llm_gender(self, gender_value):
        # Обновляем LLM profile без потери данных профиля
        # И очищаем историю
        if hasattr(self, "llm_item") and self.llm_item is not None:
            self.llm_item.update_gender(gender_value)
            # self.llm_item.clear_history()

    def import_profile0(self):
        path = filedialog.askopenfilename(
            title="Импорт профиля",
            filetypes=[("JSON", "*.json")]
        )
        if not path:
            return
        try:
            data = load_json(path, {})
            if not isinstance(data, dict):
                message = "Файл профиля должен быть формата JSON."
                messagebox.showinfo("OK", message)
                raise ValueError(message)

            self.profile = data
            save_profile(self.profile)  # так же обновляем данные на диске
            self.renew_chat(clean_llm_history=False)
            self.update_llm_profile()

            # Обновляем данные о пользователе в Интерфейсе
            try:
                self.refresh_profile_ui()
            except Exception:
                pass

            messagebox.showinfo("OK", "Профиль импортирован.")
            self.show_profile()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось импортировать профиль:\n{e}")

    def import_profile(self):
        path = filedialog.askopenfilename(
            title="Импорт профиля (ods csv xlsx json)",
            filetypes=[("Тип файла:", ['*.ods', '*.csv', '*.xlsx', "*.json"])]
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()

        try:
            if ext == ".json":
                data = load_json(path, [])
                if not isinstance(data, dict):
                    message = "Файл профиля должен быть формата JSON[dict]"
                    messagebox.showinfo("OK", message)
                    raise ValueError(message)
            elif ext in (".xlsx", ".xlsm", ".xls", ".ods", ".csv"):
                data = sheet_to_dict(path, format=ext)
                if not isinstance(data, dict):
                    raise ValueError("Файл должен быть преобразован в dict.")
            else:
                messagebox.showerror("Ошибка", "Выберите: ods csv xlsx json")
                return

            data_fields_set = set(data)
            profile_fields_set = set(profile_fields)
            diff = data_fields_set - profile_fields_set
            if diff:
                messagebox.showerror("Ошибка", "Формат данных не соответствует Профилю")
                return
            self.profile = data
            save_profile(self.profile)  # так же обновляем данные на диске
            self.renew_chat(clean_llm_history=False)
            self.update_llm_profile()

            # Обновляем данные о пользователе в Интерфейсе
            try:
                self.refresh_profile_ui()
            except Exception:
                pass

            messagebox.showinfo("OK", "Профиль импортирован.")
            self.show_profile()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось импортировать профиль:\n{e}")

    def import_diary0(self):
        path = filedialog.askopenfilename(
            title="Импорт дневника",
            filetypes=[("JSON", "*.json")]
        )
        if not path:
            return
        try:
            data = load_json(path, [])
            if not isinstance(data, list):
                message = "Файл дневника должен быть формата JSON."
                messagebox.showinfo("OK", message)
                raise ValueError(message)
            self.diary = data
            save_json(DIARY_PATH, self.diary)  # так же обновляем данные на диске

            # обновляем данные о дневнике во вкладке
            if hasattr(self, "diary_view") and self.diary_view is not None:
                self.diary_view.diary = self.diary
                self.diary_view.refresh()

            messagebox.showinfo("OK", "Дневник импортирован.")
            self.show_diary()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось импортировать дневник:\n{e}")

    def import_diary(self):
        path = filedialog.askopenfilename(
            title="Импорт дневника (ods csv xlsx json)",
            filetypes=[
                ("Тип файла:", ['*.ods', '*.csv', '*.xlsx', "*.json"])
            ],
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()

        try:
            if ext == ".json":
                data = load_json(path, [])
                if not isinstance(data, list):
                    raise ValueError("Файл дневника должен содержать JSON-массив (list).")
            elif ext in (".xlsx", ".ods", ".csv"):
                data = sheet_to_list(path, format=ext)
                if not isinstance(data, list):
                    raise ValueError("Файл должен быть преобразован в list[dict].")
            else:
                messagebox.showerror("Ошибка", "Выберите: ods csv xlsx json")
                return

            if len(data) == 0:
                messagebox.showerror("Ошибка", "Формат данных не соответствует Дневнику")
                return
            else:
                data_fields_set = set(data[0])
                diary_fields_set = set(diary_fields)
                diff = data_fields_set - diary_fields_set
                if diff:
                    messagebox.showerror("Ошибка", "Формат данных не соответствует Дневнику")
                    return

            self.diary = data
            save_json(DIARY_PATH, self.diary)  # сохраняем в стандартное место приложения

            if hasattr(self, "diary_view") and self.diary_view is not None:
                self.diary_view.diary = self.diary
                self.diary_view.refresh()

            messagebox.showinfo("OK", "Дневник импортирован.")
            self.show_diary()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось импортировать дневник:\n{e}")

    def create_menu(self):
        menubar = tk.Menu(self)

        # Добавляем меню Файл
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Экспорт Профиля", command=self.export_profile)
        file_menu.add_command(label="Импорт Профиля", command=self.import_profile)
        file_menu.add_separator()
        file_menu.add_command(label="Экспорт Дневника", command=self.export_diary)
        file_menu.add_command(label="Импорт Дневника", command=self.import_diary)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", underline=0, command=self.destroy)
        menubar.add_cascade(label="Файл", menu=file_menu)

        # верхнее меню
        menubar.add_command(label="Главная", underline=0, command=self.show_home)
        menubar.add_command(label="Чат поддержки", underline=0, command=self.show_chat)
        menubar.add_command(label="Дневник", underline=0, command=self.show_diary)
        menubar.add_command(label="Профиль", underline=0, command=self.show_profile)
        menubar.add_command(label="Настройки", underline=0, command=self.show_options)
        menubar.add_command(label="О проекте", underline=0, command=self.show_about)

        self.config(menu=menubar)

        """ self.bind_all("<Control-Cyrillic_ghe>", lambda e: self.show_home())
        self.bind_all("<Control-u>", lambda e: self.show_home())
        self.bind_all("<Control-c>", lambda e: self.show_chat())
        self.bind_all("<Control-d>", lambda e: self.show_diary())
        self.bind_all("<Control-p>", lambda e: self.show_profile())
        self.bind_all("<Control-a>", lambda e: self.show_about())
        self.bind_all("<Control-e>", lambda e: self.destroy()) """

        # self.bind_all("<KeyPress>", self.on_ctrl_shortcuts)
        # self.bind_all("<KeyPress>", lambda e: print(e.keysym, repr(e.char), e.state))

        # обработка горячих главиш
        self.bind_all("<Control-KeyPress>", self.on_ctrl_shortcuts)

    def on_ctrl_shortcuts(self, e):
        if settings.DEBUG:
            # печатает клавишу, котую мы нажимаем
            print(e.keysym, repr(e.char), e.state)

        # Ctrl+Буква. сделано так что все сочетания физической буквы обрабатываются
        # и английские и русские и с капсом/шифтом
        # U -> \x15, X -> \x18, L -> \x0c, P -> \x10, J -> \x0a, D -> \x04, Y -> \x19
        actions = {
            "\x15": self.show_home,    # Ctrl+U  ( Ctrl+Г )
            "\x18": self.show_chat,    # Ctrl+X  ( Ctrl+Ч)
            "\x0c": self.show_diary,   # Ctrl+L  ( Ctrl+Д)
            "\x07": self.show_profile, # Ctrl+G  ( Ctrl+П)
            "\x0a": self.show_about,   # Ctrl+J  ( Ctrl+О)
            "\x04": self.destroy,      # Ctrl+D  ( Ctrl+В)
            "\x19": self.show_options, # Ctrl+Y  ( Ctrl+Н)
        }

        fn = actions.get(e.char)
        if fn:
            fn()
            return "break"

    """def on_ctrl_shortcuts(self, e):
        ks = e.keysym

        if ks in (
            "Cyrillic_che", "Cyrillic_CHE", "x", "X",       # ч / Ч  (x / X)
            "Cyrillic_ghe", "Cyrillic_GHE", "u", "U",       # г / Г  (u / U)
            "Cyrillic_de",  "Cyrillic_DE",  "l", "L",       # д / Д  (l / L)
            "Cyrillic_ze",  "Cyrillic_ZE",  "p", "P",       # з / З  (p / P)
            "Cyrillic_o",   "Cyrillic_O",   "j", "J",       # о / О  (j / J)
            "Cyrillic_ve",  "Cyrillic_VE",  "d", "D",       # в / В  (d / D)
            "Cyrillic_en",  "Cyrillic_EN",  "y", "Y",       # н / Н  (y / Y)
        ):
            self.show_home()
            return "break" """

    def raise_frame(self, name):
        self.frames[name].tkraise()

    # вспомогательные функции для процесса стримминга текста в окнах приложения

    def _cancel_stream(self):
        self._active_stream = None

    def _run_stream(self, gen, on_chunk, on_done, on_error, delay_ms=10):
        # если вдруг еще один текст начинает печататься то текущий останавливаем
        if gen is None or gen is not self._active_stream:
            return

        try:
            chunk = next(gen)
        except StopIteration:
            self._active_stream = None
            try:
                on_done()
            except Exception:
                pass
            return
        except Exception as e:
            self._active_stream = None
            on_error(e)
            return

        try:
            on_chunk(chunk)
        except Exception as e:
            self._active_stream = None
            on_error(e)
            return

        self.after(delay_ms, lambda: self._run_stream(gen, on_chunk, on_done, on_error, delay_ms))

    def start_stream(self, gen, on_chunk, on_done=lambda: None, on_error=lambda e: None, delay_ms=10):
        self._cancel_stream()
        self._active_stream = gen
        self._run_stream(gen, on_chunk, on_done, on_error, delay_ms)

    # ГЛАВНАЯ СТРАНИЦА

    def build_home(self):
        f = self.frames["home"]

        tk.Label(
            f, text=settings.MAIN_SLOGAN, fg=self.FG, bg=self.BG,
            font=("Arial", 22, "bold")
        ).pack(pady=30)

        self.quote_var = tk.StringVar(value=random.choice(support_phrases))

        tk.Label(
            f, textvariable=self.quote_var, wraplength=600,
            fg=self.FG, bg=self.BG, font=(self.FONT_NAME, self.FONT_SIZE)
        ).pack(pady=20)

        def refresh_quote(stream=settings.USE_STREAM):
            if settings.USE_LLM:
                try:
                    if not stream:
                        self.quote_var.set(self.llm_item.get_frase_from_llm())
                        return

                    self.quote_var.set("")
                    gen = self.llm_item.get_frase_from_llm_stream()

                    total = {"text": ""}

                    def on_chunk(chunk):
                        total["text"] += chunk
                        self.quote_var.set(total["text"])

                    def on_done():
                        pass

                    def on_error(e):
                        # ошибка fallback
                        self.quote_var.set(random.choice(support_phrases))

                    self.start_stream(gen, on_chunk, on_done, on_error)
                    return
                except Exception:
                    pass

            self.quote_var.set(random.choice(support_phrases))

        tk.Button(
            f,
            text=settings.MAIN_BTN_TEXT,
            # command=refresh_quote,
            command=self.show_chat_and_get_answer,
            bg=self.ACCENT, fg="white", relief="flat",
            padx=10, pady=6
        ).pack(pady=10)

        tk.Label(
            f,
            text=settings.MAIN_LABEL_TEXT,
            fg=self.LABEL_FG, bg=self.BG, font=("Arial", 10),
            justify="center"
        ).pack(pady=40)

    def show_home(self):
        self.raise_frame("home")


    # ДНЕВНИК

    def show_diary(self):
        self.diary_view.refresh()
        self.raise_frame("diary")

    # ЧАТ

    def chat_set_intro(self):
        self.append_chat(f"{settings.TD_CHAT_PREFIX}{settings.CHAT_INTRO_TEXT}")

    def renew_chat(self, clean_llm_history=True):
        self.chat_box.config(state="normal")
        self.chat_box.delete("1.0", tk.END)
        self.chat_set_intro()
        self.chat_box.config(state="disabled")

        if clean_llm_history and \
            hasattr(self, "llm_item") and self.llm_item is not None:
                self.llm_item.clear_history()

        # self.tts_stream.stop_generation()
        self.player_stop()
        self.player_resume()
        # self.tts_stream_resume()

    def build_chat(self):
        f = self.frames["chat"]

        tk.Label(
            f, text="Чат поддержки", fg=self.FG, bg=self.BG,
            font=("Arial", 18, "bold")
        ).pack(pady=20)

        self.chat_box = tk.Text(
            f, height=20, width=80,
            bg=self.PANEL, fg=self.FG, insertbackground=self.FG,
            relief="flat", wrap="word"
        )
        self.chat_box.pack(padx=20, pady=10)
        self.chat_box.config(state="disabled")

        self.user_entry = tk.Entry(
            f, width=60,
            bg=self.BTN, fg=self.FG, insertbackground=self.FG,
            relief="flat"
        )

        self.user_entry.pack(pady=10)
        self.user_entry.bind("<Return>", lambda e: self.send_message())

        # Делаем новый фрейм для кнопок
        btn_row = tk.Frame(f, bg=self.BG)
        btn_row.pack(pady=(0, 10), fill="x")

        tk.Label(btn_row, bg=self.BG, text="").pack(side="left", expand=True)

        self.send_btn = tk.Button(
            btn_row, text="Отправить",
            command=self.send_message,
            bg=self.ACCENT, fg="white",
            relief="flat", padx=10, pady=6
        )
        self.send_btn.pack(side="left", padx=5)

        self.clear_btn = tk.Button(
            btn_row, text="Очистить чат",
            command=self.renew_chat,
            bg=self.ACCENT, fg="white",
            relief="flat", padx=10, pady=6
        )
        self.clear_btn.pack(side="left", padx=5)

        # Кнопки управление аудио

        self.pause_btn = tk.Button(
            btn_row, text="Пауза",
            command=self.player_pause,
            bg=self.ACCENT, fg="white",
            relief="flat", padx=10, pady=6
        )
        self.pause_btn.pack(side="left", padx=5)
        Hovertip(self.pause_btn, 'Проджить воспроизведение', hover_delay=500)

        self.resume_btn = tk.Button(
            btn_row, text="Продолжить",
            command=self.player_resume,
            bg=self.ACCENT, fg="white",
            relief="flat", padx=10, pady=6
        )
        self.resume_btn.pack(side="left", padx=5)
        Hovertip(self.resume_btn, 'Проджить воспроизведение', hover_delay=500)

        self.stop_btn = tk.Button(
            btn_row, text="Стоп",
            command=self.player_stop,
            bg=self.ACCENT, fg="white",
            relief="flat", padx=10, pady=6
        )
        self.stop_btn.pack(side="left", padx=5)
        # Добавить всплывающую подсказку к кнопке
        Hovertip(self.stop_btn, 'Продолжит воспроизведение только после нового ответа', hover_delay=500)


        tk.Label(btn_row, bg=self.BG, text="").pack(side="left", expand=True)

        self.chat_set_intro()

        self.user_entry.focus_set()

    def send_message(self, stream=settings.USE_STREAM, default_msg: str|None = None):
        if default_msg is None:
            msg = self.user_entry.get().strip()
            if not msg:
                return
            self.user_entry.delete(0, tk.END)
        else:
            msg = default_msg

        # self.tts_stream.stop_generation()
        self.player_stop(full_stop=False)
        self.player_resume()
        self.tts_stream_resume()

        self.append_chat(f"\n{settings.USER_CHAT_PREFIX}{msg}\n")
        lower = msg.lower()


        if settings.USE_LLM:
            try:
                if not stream:
                    response = self.llm_item.get_frase_from_llm(lower)
                    self.append_chat(f"\n{settings.TD_CHAT_PREFIX}{response}\n")
                    return

                # тут получаем данные из ЛЛМ по кусочкам
                gen = self.llm_item.get_frase_from_llm_stream(lower)

                self.user_entry.configure(state="disabled")
                self.send_btn.configure(state="disabled")

                self.append_chat(f"\n{settings.TD_CHAT_PREFIX}")

                def on_chunk(chunk):
                    self.append_chat(chunk)

                def on_done():
                    self.append_chat("\n")
                    self.user_entry.configure(state="normal")
                    self.send_btn.configure(state="normal")
                    self.user_entry.focus_set()

                def on_error(e):
                    self.append_chat(f"\n[Ошибка LLM: {repr(e)}]\n")
                    self.user_entry.configure(state="normal")
                    self.send_btn.configure(state="normal")
                    self.user_entry.focus_set()

                self.start_stream(gen, on_chunk, on_done, on_error)
                return
            except Exception:
                pass
        else:
            if any(k in lower for k in crisis_keywords):
                response = (
                    "Мне очень жаль, что тебе так тяжело. Я не могу заменить профессиональную помощь.\n"
                    "Если ты в опасности или думаешь о самоповреждении — пожалуйста, немедленно обратись в экстренные службы "
                    "в твоей стране, или позвони близкому человеку.\n"
                    "Если можешь — скажи, где ты находишься (страна/город), и я подскажу, куда обратиться.\n"
                )
                self.append_chat(f"\n{settings.TD_CHAT_PREFIX}{response}\n")
                return

            if "плохо" in lower or "тяжело" in lower or "груст" in lower:
                response = "Понимаю. Хочешь рассказать, что именно сейчас больше всего давит?"
            elif "один" in lower or "одна" in lower:
                response = "Ощущать одиночество очень больно. Есть ли кто-то, кому ты мог(ла) бы написать прямо сейчас?"
            elif "не знаю" in lower:
                response = "Это нормально — не знать. Давай начнём с малого: что ты чувствуешь в данный момент?"
            else:
                response = random.choice(support_phrases)

            self.append_chat(f"{settings.TD_CHAT_PREFIX}{response}\n")

    def append_chat(self, text):
        # if getattr(self, 'chat_box'):
        self.chat_box.config(state="normal")
        self.chat_box.insert(tk.END, text)
        self.chat_box.see(tk.END)
        self.chat_box.config(state="disabled")

    def show_chat(self):
        self.raise_frame("chat")
        self.chat_box.config(state="disabled")
        self.user_entry.focus_set()

    def show_chat_and_get_answer(self):
        self.raise_frame("chat")
        self.chat_box.config(state="disabled")
        self.user_entry.focus_set()
        delay_ms = 10
        self.after(delay_ms, lambda: self.send_message(default_msg='Дай мне совет'))

    # ПРОФИЛЬ

    def build_profile(self):
        f = self.frames["profile"]

        for w in f.winfo_children():
            w.destroy()

        # делаем страницу профиля полностью scrollable
        self.profile_canvas, content = self.make_scrollable(f)

        tk.Label(
            content, text="Профиль", fg=self.FG, bg=self.BG,
            font=("Arial", 18, "bold")
        ).pack(pady=20)

        def normalize(value: str, allowed: tuple[str, ...]) -> str:
            value = (value or "").strip()
            return value if value in allowed else ""

        RADIO_BTN = dict(
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

        self.name_var = tk.StringVar(value=str(self.profile.get("Имя", "")))
        self.gender_var = tk.StringVar(value=normalize(self.profile.get("Пол", ""), ("Мужской", "Женский")))
        self.city_var = tk.StringVar(value=normalize(self.profile.get("Город", ""), tuple(city_list)))
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
        pets_default = str(self.profile.get("Домашние животные", ""))
        hobby_default = str(self.profile.get("Хобби, интересы", ""))

        # form = tk.Frame(f, bg=self.BG)
        form = tk.Frame(content, bg=self.BG)
        form.pack(pady=10)

        def label(row, text):
            tk.Label(form, text=text + ":", fg=self.FG, bg=self.BG, anchor="w", width=25)\
                .grid(row=row, column=0, sticky="w", padx=5, pady=6)

        label(0, "Имя")
        tk.Entry(form, textvariable=self.name_var, width=40, bg=self.BTN, fg=self.FG, insertbackground=self.FG, relief="flat")\
            .grid(row=0, column=1, sticky="w", padx=5, pady=6)

        label(1, "Пол")
        gender_frame = tk.Frame(form, bg=self.BG)
        gender_frame.grid(row=1, column=1, sticky="w", padx=5, pady=6)
        tk.Radiobutton(gender_frame, text="Мужской", variable=self.gender_var, value="Мужской", **RADIO_BTN)\
            .pack(side="left", padx=(0, 10))
        tk.Radiobutton(gender_frame, text="Женский", variable=self.gender_var, value="Женский", **RADIO_BTN)\
            .pack(side="left")

        label(2, "Город")
        city_frame = tk.Frame(form, bg=self.BG)
        city_frame.grid(row=2, column=1, sticky="w", padx=5, pady=6)

        # выподающий список городов
        self.city_menu = tk.OptionMenu(city_frame, self.city_var, *city_list)
        self.city_menu.config(
            bg=self.BTN, fg=self.FG, activebackground=self.ACTIVE_BG, activeforeground=self.FG,
            relief="flat", highlightthickness=0, padx=8, pady=4
        )
        # настройка выпадающего меню (внутреннее Menu)
        self.city_menu["menu"].config(
            bg=self.BTN, fg=self.FG, activebackground=self.ACTIVE_BG, activeforeground=self.FG,
            relief="flat", borderwidth=0
        )
        self.city_menu.pack(side="left")

        label(3, "Дата рождения")
        birth_frame = tk.Frame(form, bg=self.BG)
        birth_frame.grid(row=3, column=1, sticky="w", padx=5, pady=6)
        tk.Entry(birth_frame, textvariable=self.birth_var, width=20, bg=self.BTN, fg=self.FG, insertbackground=self.FG, relief="flat")\
            .pack(side="left", padx=(0, 10))
        tk.Button(birth_frame, text="Выбрать", command=self.open_birthdate_picker,
                  bg=self.ACCENT, fg="white", relief="flat", padx=10, pady=4)\
            .pack(side="left")

        label(4, "Семейное положение")
        marital_frame = tk.Frame(form, bg=self.BG)
        marital_frame.grid(row=4, column=1, sticky="w", padx=5, pady=6)
        tk.Radiobutton(marital_frame, text="Холост / Не замужем", variable=self.marital_var,
                       value="Холост / Не замужем", **RADIO_BTN).pack(side="left", padx=(0, 10))
        tk.Radiobutton(marital_frame, text="Женат / Замужем", variable=self.marital_var,
                       value="Женат / Замужем", **RADIO_BTN).pack(side="left")

        label(5, "Родители")
        parents_frame = tk.Frame(form, bg=self.BG)
        parents_frame.grid(row=5, column=1, sticky="w", padx=5, pady=6)
        tk.Radiobutton(parents_frame, text="Да", variable=self.parents_var, value="Да", **RADIO_BTN)\
            .pack(side="left", padx=(0, 10))
        tk.Radiobutton(parents_frame, text="Нет", variable=self.parents_var, value="Нет", **RADIO_BTN)\
            .pack(side="left")

        label(6, "Дети")
        tk.Spinbox(form, from_=0, to=10, textvariable=self.children_var,
                   width=5, bg=self.BTN, fg=self.FG, insertbackground=self.FG, relief="flat", buttonbackground=self.BTN)\
            .grid(row=6, column=1, sticky="w", padx=5, pady=6)

        label(7, "Друзья")
        friends_frame = tk.Frame(form, bg=self.BG)
        friends_frame.grid(row=7, column=1, sticky="w", padx=5, pady=6)
        tk.Radiobutton(friends_frame, text="Да", variable=self.friends_var, value="Да", **RADIO_BTN)\
            .pack(side="left", padx=(0, 10))
        tk.Radiobutton(friends_frame, text="Нет", variable=self.friends_var, value="Нет", **RADIO_BTN)\
            .pack(side="left")

        label(8, "Домашние животные")
        pets_frame = tk.Frame(form, bg=self.BG)
        pets_frame.grid(row=8, column=1, sticky="w", padx=5, pady=6)

        self.pets_text = tk.Text(
            pets_frame, width=40, height=3, bg=self.PANEL, fg=self.FG,
            insertbackground=self.FG, relief="flat", wrap="word"
        )
        self.pets_text.pack(side="left")
        self.pets_text.insert("1.0", pets_default)
        pets_scroll = tk.Scrollbar(pets_frame, command=self.pets_text.yview)
        pets_scroll.pack(side="left", fill="y", padx=(6, 0))
        self.pets_text.configure(yscrollcommand=pets_scroll.set)

        label(9, "Хобби, интересы")
        hobby_frame = tk.Frame(form, bg=self.BG)
        hobby_frame.grid(row=9, column=1, sticky="w", padx=5, pady=6)

        self.hobby_text = tk.Text(
            hobby_frame, width=40, height=3, bg=self.PANEL, fg=self.FG,
            insertbackground=self.FG, relief="flat", wrap="word"
        )
        self.hobby_text.pack(side="left")
        self.hobby_text.insert("1.0", hobby_default)

        hobby_scroll = tk.Scrollbar(hobby_frame, command=self.hobby_text.yview)
        hobby_scroll.pack(side="left", fill="y", padx=(6, 0))
        self.hobby_text.configure(yscrollcommand=hobby_scroll.set)

        label(10, "Комментарий")
        comment_frame = tk.Frame(form, bg=self.BG)
        comment_frame.grid(row=10, column=1, sticky="w", padx=5, pady=6)

        self.comment_text = tk.Text(
            comment_frame, width=40, height=5, bg=self.PANEL, fg=self.FG,
            insertbackground=self.FG, relief="flat", wrap="word"
        )
        self.comment_text.pack(side="left")
        self.comment_text.insert("1.0", comment_default)

        scroll = tk.Scrollbar(comment_frame, command=self.comment_text.yview)
        scroll.pack(side="left", fill="y", padx=(6, 0))
        self.comment_text.configure(yscrollcommand=scroll.set)

        tk.Button(
            # f, text="Сохранить профиль",
            content, text="Сохранить профиль",
            command=self.save_profile_data,
            bg=self.ACCENT, fg="white", relief="flat",
            padx=10, pady=6
        ).pack(pady=20)

    def open_birthdate_picker(self):
        top = tk.Toplevel(self)
        top.title("Выбор даты рождения")
        top.configure(bg=self.BG)
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

        tk.Label(top, text="Год:", fg=self.FG, bg=self.BG).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Label(top, text="Месяц:", fg=self.FG, bg=self.BG).grid(row=1, column=0, padx=10, pady=10, sticky="e")
        tk.Label(top, text="День:", fg=self.FG, bg=self.BG).grid(row=2, column=0, padx=10, pady=10, sticky="e")

        year_var = tk.IntVar(value=y)
        month_var = tk.IntVar(value=m)
        day_var = tk.IntVar(value=d)

        tk.Spinbox(top, from_=year_min, to=year_max, textvariable=year_var, width=8,
                   bg=self.BTN, fg=self.FG, insertbackground=self.FG, relief="flat")\
            .grid(row=0, column=1, padx=10, pady=10, sticky="w")

        tk.Spinbox(top, from_=1, to=12, textvariable=month_var, width=8,
                   bg=self.BTN, fg=self.FG, insertbackground=self.FG, relief="flat")\
            .grid(row=1, column=1, padx=10, pady=10, sticky="w")

        tk.Spinbox(top, from_=1, to=31, textvariable=day_var, width=8,
                   bg=self.BTN, fg=self.FG, insertbackground=self.FG, relief="flat")\
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

        btns = tk.Frame(top, bg=self.BG)
        btns.grid(row=3, column=0, columnspan=2, pady=(5, 12))

        tk.Button(btns, text="OK", command=set_date, bg=self.ACCENT, fg="white", relief="flat", padx=14, pady=6)\
            .pack(side="left", padx=8)
        tk.Button(btns, text="Отмена", command=top.destroy, bg=self.BTN, fg=self.FG, relief="flat", padx=14, pady=6)\
            .pack(side="left", padx=8)

    def save_profile_data(self):
        data = {
            "Имя": self.name_var.get().strip(),
            "Пол": self.gender_var.get().strip(),
            "Город": self.city_var.get().strip(),
            "Дата рождения": self.birth_var.get().strip(),
            "Семейное положение": self.marital_var.get().strip(),
            "Родители": self.parents_var.get().strip(),
            "Дети": max(0, min(10, int(self.children_var.get()))),
            "Друзья": self.friends_var.get().strip(),
            "Домашние животные": self.pets_text.get("1.0", "end").strip(),
            "Хобби, интересы": self.hobby_text.get("1.0", "end").strip(),
            "Комментарий": self.comment_text.get("1.0", "end").strip(),
        }


        self.renew_chat(clean_llm_history=False)

        if save_profile(data):
            self.profile = data
            # нужно обновить
            self._user_city = self.profile.get('Город')

            self.update_llm_profile()
            self.tk_renew_events()
            messagebox.showinfo("Сохранено", "Профиль сохранён.")
            self.show_home()
        else:
            messagebox.showerror("Ошибка", "Не удалось сохранить профиль.")

    def show_profile(self):
        self.raise_frame("profile")

    def refresh_profile_ui(self):
        # Если вкладка профиля ещё не построена — просто строим
        if not hasattr(self, "name_var"):
            self.build_profile()
            return

        def normalize(value: str, allowed: tuple[str, ...]) -> str:
            value = (value or "").strip()
            return value if value in allowed else ""


        self.name_var.set(str(self.profile.get("Имя", "")))
        self.gender_var.set(normalize(self.profile.get("Пол", ""), ("Мужской", "Женский")))
        self.city_var.set(normalize(self.profile.get("Город", ""), tuple(city_list)))
        self.birth_var.set(str(self.profile.get("Дата рождения", "")))
        self.marital_var.set(normalize(
            self.profile.get("Семейное положение", ""),
            ("Холост / Не замужем", "Женат / Замужем"),
        ))
        self.parents_var.set(normalize(self.profile.get("Родители", ""), ("Да", "Нет")))
        self.friends_var.set(normalize(self.profile.get("Друзья", ""), ("Да", "Нет")))

        try:
            children_default = int(self.profile.get("Дети", 0))
        except Exception:
            children_default = 0
        self.children_var.set(max(0, min(10, children_default)))

        pets_default = str(self.profile.get("Домашние животные", ""))
        hobby_default = str(self.profile.get("Хобби, интересы", ""))
        comment_default = str(self.profile.get("Комментарий", ""))

        if hasattr(self, "pets_text"):
            self.pets_text.delete("1.0", "end")
            self.pets_text.insert("1.0", pets_default)

        if hasattr(self, "hobby_text"):
            self.hobby_text.delete("1.0", "end")
            self.hobby_text.insert("1.0", hobby_default)

        if hasattr(self, "comment_text"):
            self.comment_text.delete("1.0", "end")
            self.comment_text.insert("1.0", comment_default)


    # НАСТРОЙКИ

    def build_options(self):
        f = self.frames["options"]
        #self.frames["options"] = tk.Frame(parent_container, bg=self.BG)

        tk.Label(
            f, text="Настройки", fg=self.FG, bg=self.BG,
            font=("Arial", 18, "bold")
        ).pack(pady=20)

        def normalize(value: str, allowed: tuple[str, ...]) -> str:
            value = (value or "").strip()
            return value if value in allowed else ""

        # варианты выбора из
        theme_list = tuple(settings.THEMES.keys())
        voice_list = tuple(TTS_VOICES.keys())

        # если вдруг списки пустые — не падаем
        if not theme_list:
            theme_list = ("Светлая",)
        if not voice_list:
            voice_list = ("Наталья",)

        # значения по умолчанию
        opt = settings.app_options

        self.opt_use_asr_var = tk.BooleanVar(value=bool(getattr(opt, "USE_TTS", True)))
        self.opt_theme_var = tk.StringVar(value=normalize(getattr(opt, "THEME", "white"), theme_list))
        self.opt_voice_var = tk.StringVar(value=normalize(getattr(opt, "TTS_VOICE", "Наталья"), voice_list))

        form = tk.Frame(f, bg=self.BG)
        form.pack(pady=10)

        def label(row, text):
            tk.Label(form, text=text + ":", fg=self.FG, bg=self.BG, anchor="w", width=25)\
                .grid(row=row, column=0, sticky="w", padx=5, pady=6)

        # озвучивать ответ в чате
        label(0, "Озвучивать ответ в чате *")
        chk = tk.Checkbutton(
            form, variable=self.opt_use_asr_var,
            bg=self.BG, fg=self.FG,
            activebackground=self.BG, activeforeground=self.FG,
            selectcolor=self.ACCENT,
            highlightthickness=0, borderwidth=0
        )
        chk.grid(row=0, column=1, sticky="w", padx=5, pady=6)

        # выбрать тему
        label(1, "Тема оформления *")
        theme_frame = tk.Frame(form, bg=self.BG)
        theme_frame.grid(row=1, column=1, sticky="w", padx=5, pady=6)

        self.opt_theme_menu = tk.OptionMenu(theme_frame, self.opt_theme_var, *theme_list)
        self.opt_theme_menu.config(
            bg=self.BTN, fg=self.FG,
            activebackground=self.ACTIVE_BG, activeforeground=self.FG,
            relief="flat", highlightthickness=0, padx=8, pady=4
        )
        self.opt_theme_menu["menu"].config(
            bg=self.BTN, fg=self.FG,
            activebackground=self.ACTIVE_BG, activeforeground=self.FG,
            relief="flat", borderwidth=0
        )
        self.opt_theme_menu.pack(side="left")

        # голос
        label(2, "Голос Чата")
        voice_frame = tk.Frame(form, bg=self.BG)
        voice_frame.grid(row=2, column=1, sticky="w", padx=5, pady=6)

        self.opt_voice_menu = tk.OptionMenu(voice_frame, self.opt_voice_var, *voice_list)
        self.opt_voice_menu.config(
            bg=self.BTN, fg=self.FG,
            activebackground=self.ACTIVE_BG, activeforeground=self.FG,
            relief="flat", highlightthickness=0, padx=8, pady=4
        )
        self.opt_voice_menu["menu"].config(
            bg=self.BTN, fg=self.FG,
            activebackground=self.ACTIVE_BG, activeforeground=self.FG,
            relief="flat", borderwidth=0
        )
        self.opt_voice_menu.pack(side="left")

        tk.Button(
            f, text="Сохранить настройки",
            command=self.save_options_data,
            bg=self.ACCENT, fg="white", relief="flat",
            padx=10, pady=6
        ).pack(pady=20)

        tk.Label(
            f,
            text='* Настройки обновляются поле перезагрузки',
            fg=self.LABEL_FG, bg=self.BG, font=("Arial", 10),
            justify="center"
        ).pack(pady=10)

    def save_options_data(self):
        # сохраняем app_options в data/app_options.json
        try:
            theme_list = tuple(settings.THEMES.keys()) or ("white",)
            voice_list = tuple(TTS_VOICES.keys()) or ("Наталья",)

            theme = (self.opt_theme_var.get() or "").strip()
            voice = (self.opt_voice_var.get() or "").strip()

            # небольшая нормализация
            if theme not in theme_list:
                theme = theme_list[0]
            if voice not in voice_list:
                voice = voice_list[0]

            settings.app_options.USE_TTS = bool(self.opt_use_asr_var.get())
            settings.app_options.THEME = theme
            settings.app_options.TTS_VOICE = voice

        except Exception:
            messagebox.showerror("Ошибка", "Некорректные настройки.")
            return

        if settings.save_app_options(settings.app_options):
            # применяем тему сразу
            if hasattr(self, "theme_renew"):
                try:
                    self.theme_renew(settings.app_options.THEME)
                except Exception:
                    pass

            messagebox.showinfo("Сохранено", "Настройки сохранены.")
            self.show_home()
        else:
            messagebox.showerror("Ошибка", "Не удалось сохранить настройки.")

    def show_options(self):
        self.raise_frame("options")
        self.refresh_options_ui()

    def refresh_options_ui(self):
        # Если вкладка настроек ещё не построена — просто строим
        if not hasattr(self, "opt_theme_var"):
            self.build_options()
            return

        # подгружаем актуальные данные с диска (на случай изменений)
        settings.load_app_options()
        opt = settings.app_options

        theme_list = tuple(settings.THEMES.keys()) or ("white",)
        voice_list = tuple(TTS_VOICES.keys()) or ("Наталья",)

        def normalize(value: str, allowed: tuple[str, ...]) -> str:
            value = (value or "").strip()
            return value if value in allowed else allowed[0]

        self.opt_use_asr_var.set(bool(getattr(opt, "USE_TTS", True)))
        self.opt_theme_var.set(normalize(getattr(opt, "THEME", theme_list[0]), theme_list))
        self.opt_voice_var.set(normalize(getattr(opt, "TTS_VOICE", voice_list[0]), voice_list))




    # О ПРИЛОЖЕНИИ

    def build_about(self):
        f = self.frames["about"]

        tk.Label(
            f, text="О проекте", fg=self.FG, bg=self.BG,
            font=("Arial", 18, "bold")
        ).pack(pady=20)

        text = (
            "Treatment of Depression «Ты не один» — учебный инженерный проект. \n"
            "Настольное приложение на Python с графическим интерфейсом на базе Tkinter (далее Treatment of Depression или TD). В одном приложении пользователь получает три базовые функции: быстрые поддерживающие подсказки, чат поддержку на базе LLM и дневник для записи самочувствия и настроения. Дополнительно реализованы профиль пользователя и настройки. \n"
            "Приложение предназначено для поддержки (саморегуляции), организации дня и снижения стресса.\n"
            "\nВажно: приложение не является медицинским изделием, не ставит диагноз и не заменяет врача/психолога. При выраженном ухудшении самочувствия необходимо обратиться к специалистам и/или в службы экстренной помощи.\n"
            "\nФункции:\n"
            "- Слова поддержки\n"
            "- Чат с использованием генративной модели\n"
            "- Дневник самочувствия\n"
            "- Профиль пользователя\n"
            "- поддерживаются горячие клавиши. Ctrl + первая буква пункта меню"
        )

        tk.Label(f, text=text, fg=self.FG, bg=self.BG, wraplength=600).pack(padx=20, pady=40)

    def show_about(self):
        self.raise_frame("about")


if __name__ == "__main__":
    app = TDApp()
    app.mainloop()
