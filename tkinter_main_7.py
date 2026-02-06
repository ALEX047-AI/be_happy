"""
TD — Treatment of Depression
"""

import os
import random
from datetime import date
import time

import matplotlib
matplotlib.use("TkAgg")

import tkinter as tk
try:
    import customtkinter as ctk
except Exception as _e:
    raise ImportError(
        "customtkinter is required for this version. Install it with: pip install customtkinter"
    ) from _e

from tkinter import messagebox
from tkinter import filedialog

from queue import Queue
from dataclasses import dataclass

from options.config import settings, TTS_VOICES, city_list
from language import LanguageStore
from content import ContentStore
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



class TDApp(ctk.CTk):

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
        self.diary = load_json(DIARY_PATH, {})

        # Загрузка языков
        self.lang_dir = os.path.join(settings.DATA, "language")
        self.content_dir = os.path.join(settings.DATA, "content")
        os.makedirs(self.lang_dir, exist_ok=True)
        os.makedirs(self.content_dir, exist_ok=True)

        self.lang_ui = getattr(settings.app_options, "LANG_UI", "ru")
        self.lang_chat = getattr(settings.app_options, "LANG_CHAT", self.lang_ui)
        self.lang_content = getattr(settings.app_options, "LANG_CONTENT", self.lang_ui)

        self.language = LanguageStore(self.lang_dir, default_lang="ru")
        self.language.load(self.lang_ui)
        self.tr = self.language.t
        self.lang_get = self.language.get

        # В будущем язык интерфейса и ЛЛМ могут быть разными
        self.language_chat = LanguageStore(self.lang_dir, default_lang="ru")
        self.language_chat.load(self.lang_chat)
        self.tr_chat = self.language_chat.t

        # Загружаем статьи, фразы поддержки и системный промпт
        self.content_store = ContentStore(self.content_dir, default_lang="ru")


        # customtkinter база используем fg_color вместо of bg
        try:
            if ctk is None:
                raise RuntimeError('customtkinter is not installed')
            self._apply_ctk_appearance()
        except Exception:
            try:
                self.configure(bg=self.BG)
            except Exception:
                pass

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
        start_llm = time.perf_counter()
        self.llm_item = LLM_IO(self.profile, settings.MODEL_SOURCE, ai_intro=settings.CHAT_INTRO_TEXT, shared_data=shared_data, lang_chat=self.lang_chat, lang_content=self.lang_content, content_dir=self.content_dir, lang_dir=self.lang_dir)
        est_time_ll = time.perf_counter() - start_llm
        print(f'{est_time_ll = }')
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
        CustomTkinter используем CTkScrollableFrame.
        Для совместимости временно возвращаем (canvas_or_None, content_frame).
        """
        try:
            sf = ctk.CTkScrollableFrame(parent, fg_color=self.BG, corner_radius=0)
            sf.pack(fill="both", expand=True)
            return None, sf
        except Exception:
            # совместимость с tkinter
            outer = tk.Frame(parent, bg=self.BG)
            outer.pack(fill="both", expand=True)

            canvas = tk.Canvas(outer, bg=self.BG, highlightthickness=0, bd=0)
            scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scrollbar.set)

            scrollbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)

            content = tk.Frame(canvas, bg=self.BG)
            win = canvas.create_window((0, 0), window=content, anchor="nw")

            def _on_configure(event):
                canvas.configure(scrollregion=canvas.bbox("all"))
                canvas.itemconfig(win, width=event.width)

            content.bind("<Configure>", _on_configure)
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


    def _apply_ctk_appearance(self):
        """Синхронизируем как выгладет CustomTkinter с выбранной Темой."""
        try:
            theme_name = str(getattr(settings.app_options, "THEME", "") or "")
            name_low = theme_name.lower()
            if ("тём" in name_low) or ("dark" in name_low):
                mode = "Dark"
            elif ("свет" in name_low) or ("light" in name_low):
                mode = "Light"
            else:
                mode = "System"
            ctk.set_appearance_mode(mode)
        except Exception:
            pass

    # ЗАПОЛНЕНИЕ ПРИЛОЖЕНИЯ

    def create_layout(self):
        self.create_menu()

        # Фон основного контейнера
        try:
            self.configure(fg_color=self.BG)
        except Exception:
            try:
                self.configure(bg=self.BG)
            except Exception:
                pass

        # Контейнеры страничек
        self.container = ctk.CTkFrame(self, fg_color=self.BG, corner_radius=0)
        self.container.pack(fill="both", expand=True)

        self.frames = {}
        for name in ("home", "chat", "diary", "profile", "options", "about"):
            frame = ctk.CTkFrame(self.container, fg_color=self.BG, corner_radius=0)
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.frames[name] = frame

        # Отрисовываем странички
        self.build_home()
        self.build_chat()

        # Дневник
        self.diary_view = DiaryView(
            parent=self.frames["diary"],
            diary=self.diary,
            save_callback=lambda d: save_json(DIARY_PATH, d),
            theme=self.theme,
            calendar_func=self.open_birthdate_picker,
            tr=self.tr,
            lang_get=self.lang_get,
        )

        self.build_profile()
        self.build_options()
        self.build_about()

    def rebuild_ui(self, keep_page: str | None = None):
        """Вновь создаем все страницы чтоб прменить Тему и Опции немедленно."""
        page = keep_page or getattr(self, "_current_frame", "home")

        # Очистка страниц (сохранение объектов Фреймов)
        for frame in getattr(self, "frames", {}).values():
            for w in frame.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass

        # Собственно перестраиваем
        self.build_home()
        self.build_chat()
        self.diary_view = DiaryView(
            parent=self.frames["diary"],
            diary=self.diary,
            save_callback=lambda d: save_json(DIARY_PATH, d),
            theme=self.theme,
            calendar_func=self.open_birthdate_picker,
            tr=self.tr,
            lang_get=self.lang_get,
        )
        self.build_profile()
        self.build_options()
        self.build_about()

        self.raise_frame(page)


    # Функции экспорта
    def export_profile0(self, initialfile=None):

        if initialfile is None:
            initialfile = f'Профиль {self.profile.get("Имя", "Пользователя")}'

        path = filedialog.asksaveasfilename(
            title=self.tr("dlg.export_profile_title","Экспорт профиля"),
            defaultextension=".json",
            initialfile=initialfile,
            filetypes=[("JSON", "*.json")]
        )
        if not path:
            return
        try:
            save_json(path, self.profile)
            messagebox.showinfo(self.tr("msg.ok_title","OK"), self.tr("msg.profile_exported","Профиль экспортирован."))
        except Exception as e:
            messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("dlg.export_profile_failed","Не удалось экспортировать профиль:\n{e}", e=e))

    def export_profile(self, initialfile=None):

        if initialfile is None:
            initialfile = f'Профиль {self.profile.get("Имя", "Пользователя")}'

        path = filedialog.asksaveasfilename(
            title=self.tr("dlg.export_profile_title","Экспорт профиля"),
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
                messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("dlg.filetype_error","Выберите .json .xlsx .ods .csv"))
                return

            messagebox.showinfo(self.tr("msg.ok_title","OK"), self.tr("msg.profile_exported","Профиль экспортирован."))
        except Exception as e:
            messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("dlg.export_profile_failed","Не удалось экспортировать профиль:\n{e}", e=e))

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
            messagebox.showinfo(self.tr("msg.ok_title","OK"), self.tr("msg.diary_exported","Дневник экспортирован."))
        except Exception as e:
            messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("dlg.export_diary_failed","Не удалось экспортировать дневник:\n{e}", e=e))

    def export_diary(self, initialfile=None):
        if initialfile is None:
            initialfile = f'Дневник {self.profile.get("Имя", "Пользователя")}'

        path = filedialog.asksaveasfilename(
            title=self.tr("dlg.export_diary_title","Экспорт дневника (ods csv xlsx json)"),
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
                dict_to_sheet(self.diary, path, format=ext, data_type = 'diary')
            else:
                messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("dlg.filetype_error","Выберите .json .xlsx .ods .csv"))
                return

            messagebox.showinfo(self.tr("msg.ok_title","OK"), self.tr("msg.diary_exported","Дневник экспортирован."))
        except Exception as e:
            messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("dlg.export_diary_failed","Не удалось экспортировать дневник:\n{e}", e=e))

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

            messagebox.showinfo(self.tr("msg.ok_title","OK"), self.tr("msg.profile_imported","Профиль импортирован."))
            self.show_profile()
        except Exception as e:
            messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("dlg.import_profile_failed","Не удалось импортировать профиль:\n{e}", e=e))

    def import_profile(self):
        path = filedialog.askopenfilename(
            title=self.tr("dlg.import_profile_title","Импорт профиля (ods csv xlsx json)"),
            filetypes=[("Тип файла:", ['*.ods', '*.csv', '*.xlsx', "*.json"])]
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()

        try:
            if ext == ".json":
                data = load_json(path, [])
                if not isinstance(data, dict):
                    message = self.tr("msg.profile_import_wrong","Файл профиля должен быть формата JSON[dict].")
                    messagebox.showinfo("OK", message)
                    raise ValueError(message)
            elif ext in (".xlsx", ".xlsm", ".xls", ".ods", ".csv"):
                data = sheet_to_dict(path, format=ext)
                if not isinstance(data, dict):
                    raise ValueError("Файл должен быть преобразован в dict.")
            else:
                messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("dlg.filetype_error","Выберите: ods csv xlsx json"))
                return

            data_fields_set = set(data)
            profile_fields_set = set(profile_fields)
            diff = data_fields_set - profile_fields_set
            if diff:
                messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("msg.profile_format_wrong","Формат данных не соответствует Профилю"))
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

            messagebox.showinfo(self.tr("msg.ok_title","OK"), self.tr("msg.profile_imported","Профиль импортирован."))
            self.show_profile()
        except Exception as e:
            messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("dlg.import_profile_failed","Не удалось импортировать профиль:\n{e}", e=e))

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
                self.diary_view.refresh_chart()

            messagebox.showinfo(self.tr("msg.ok_title","OK"), self.tr("msg.diary_imported","Дневник импортирован."))
            self.show_diary()
        except Exception as e:
            messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("dlg.import_diary_failed","Не удалось импортировать дневник:\n{e}", e=e))

    def import_diary(self):
        path = filedialog.askopenfilename(
            title=self.tr("dlg.import_diary_title","Импорт дневника (ods csv xlsx json)"),
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
                    raise ValueError("Файл дневника должен содержать JSON-массив (dict).")
            elif ext in (".xlsx", ".ods", ".csv"):
                data = sheet_to_dict(path, format=ext, data_type = 'diary')
                if not isinstance(data, dict):
                    raise ValueError("Файл должен быть преобразован в dict.")
            else:
                messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("dlg.filetype_error","Выберите: ods csv xlsx json"))
                return

            if len(data) == 0:
                messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("msg.diary_format_wrong","Формат данных не соответствует Дневнику"))
                return
            else:
                data_fields_set = set(next(iter(data.values())))
                diary_fields_set = set(diary_fields)
                diff = data_fields_set - diary_fields_set
                if diff:
                    messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("msg.diary_format_wrong","Формат данных не соответствует Дневнику"))
                    return

            self.diary = data
            save_json(DIARY_PATH, self.diary)  # сохраняем в стандартное место приложения

            if hasattr(self, "diary_view") and self.diary_view is not None:
                self.diary_view.diary = self.diary
                self.diary_view.refresh_chart()

            messagebox.showinfo(self.tr("msg.ok_title","OK"), self.tr("msg.diary_imported","Дневник импортирован."))
            self.show_diary()
        except Exception as e:
            messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("dlg.import_diary_failed","Не удалось импортировать дневник:\n{e}", e=e))

    def create_menu(self):
        menubar = tk.Menu(self)

        # Добавляем меню Файл
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=self.tr("menu.export_profile", "Экспорт Профиля"), command=self.export_profile)
        file_menu.add_command(label=self.tr("menu.import_profile", "Импорт Профиля"), command=self.import_profile)
        file_menu.add_separator()
        file_menu.add_command(label=self.tr("menu.export_diary", "Экспорт Дневника"), command=self.export_diary)
        file_menu.add_command(label=self.tr("menu.import_diary", "Импорт Дневника"), command=self.import_diary)
        file_menu.add_separator()
        file_menu.add_command(label=self.tr("menu.exit", "Выход"), underline=0, command=self.destroy)
        menubar.add_cascade(label=self.tr("menu.file", "Файл"), menu=file_menu)

        # верхнее меню
        menubar.add_command(label=self.tr("menu.home", "Главная"), underline=0, command=self.show_home)
        menubar.add_command(label=self.tr("menu.chat", "Чат поддержки"), underline=0, command=self.show_chat)
        menubar.add_command(label=self.tr("menu.diary", "Дневник"), underline=0, command=self.show_diary)
        menubar.add_command(label=self.tr("menu.profile", "Профиль"), underline=0, command=self.show_profile)
        menubar.add_command(label=self.tr("menu.options", "Настройки"), underline=0, command=self.show_options)
        menubar.add_command(label=self.tr("menu.about", "О проекте"), underline=0, command=self.show_about)

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
        self._current_frame = name
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
        for w in f.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        # Фон страницы
        try:
            f.configure(fg_color=self.BG)
        except Exception:
            pass

        ctk.CTkLabel(
            f,
            text=self.tr("home.slogan", settings.MAIN_SLOGAN),
            font=(self.FONT_NAME, 22, "bold"),
            text_color=self.FG,
        ).pack(pady=(28, 18), padx=20)

        self._home_quote = random.choice(self.content_store.get_support_phrases(self.lang_content) or support_phrases)
        self.quote_label = ctk.CTkLabel(
            f,
            text=self._home_quote,
            wraplength=720,
            justify="center",
            font=(self.FONT_NAME, self.FONT_SIZE),
            text_color=self.FG,
        )
        self.quote_label.pack(pady=(0, 16), padx=24)

        def refresh_quote():
            # меняем фразу случайным образом.
            phrase = random.choice(self.content_store.get_support_phrases(self.lang_content) or support_phrases)
            self._home_quote = phrase
            try:
                self.quote_label.configure(text=phrase)
            except Exception:
                pass

        ctk.CTkButton(
            f,
            text=self.tr("home.main_button", settings.MAIN_BTN_TEXT),
            command=self.show_chat_and_get_answer,
            fg_color=self.ACCENT,
            hover_color=self.ACCENT,
            text_color=self.FG,
            corner_radius=10,
            height=38,
        ).pack(pady=(8, 10))

        ctk.CTkButton(
            f,
            text=self.tr("home.new_phrase", "Новая фраза"),
            command=refresh_quote,
            fg_color=self.BTN,
            hover_color=self.ACTIVE_BG,
            text_color=self.FG,
            corner_radius=10,
            height=34,
        ).pack(pady=(0, 8))

        ctk.CTkLabel(
            f,
            text=self.tr("home.disclaimer", settings.MAIN_LABEL_TEXT),
            font=(self.FONT_NAME, 10),
            text_color=self.LABEL_FG,
            wraplength=720,
            justify="center",
        ).pack(pady=(24, 10), padx=24)

    def show_home(self):
        self.raise_frame("home")


    # ДНЕВНИК

    def show_diary(self):
        self.diary_view.refresh_chart()
        self.raise_frame("diary")


    # ЧАТ

    # Вспомогательные функции для Чата textbox

    def _chatbox_widget(self):
        tb = getattr(self, "chat_box", None)
        if tb is None:
            return None
        return getattr(tb, "_textbox", tb)

    def _chatbox_set_state(self, state: str):
        w = self._chatbox_widget()
        if w is None:
            return
        try:
            w.configure(state=state)
        except Exception:
            try:
                w.config(state=state)
            except Exception:
                pass

    def _chatbox_clear(self):
        w = self._chatbox_widget()
        if w is None:
            return
        try:
            w.delete("1.0", "end")
        except Exception:
            try:
                w.delete(0, "end")
            except Exception:
                pass

    def _chatbox_insert_end(self, text: str):
        w = self._chatbox_widget()
        if w is None:
            return
        try:
            w.insert("end", text)
        except Exception:
            try:
                w.insert(tk.END, text)
            except Exception:
                pass
        try:
            w.see("end")
        except Exception:
            try:
                w.see(tk.END)
            except Exception:
                pass


    def chat_set_intro(self):
        # self.append_chat(f"{settings.TD_CHAT_PREFIX}{settings.CHAT_INTRO_TEXT}")
        self.append_chat(f'{self.tr("chat.chat_intro_text", f"{settings.TD_CHAT_PREFIX}{settings.CHAT_INTRO_TEXT}")}')

    def renew_chat(self, clean_llm_history=True):
        # Очитсить Чат
        self._chatbox_set_state("normal")
        self._chatbox_clear()
        self.chat_set_intro()
        self._chatbox_set_state("disabled")

        # Очищаем историю LLM
        if clean_llm_history and \
            hasattr(self, "llm_item") and self.llm_item is not None:
                self.llm_item.clear_history()


        self.player_stop()
        self.player_resume()

    def build_chat(self):
        f = self.frames["chat"]
        for w in f.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        # Фон страницы
        try:
            f.configure(fg_color=self.BG)
        except Exception:
            pass

        ctk.CTkLabel(
            f,
            text=self.tr("chat.title","Чат поддержки"),
            font=(self.FONT_NAME, 18, "bold"),
            text_color=self.FG,
        ).pack(pady=(16, 8))

        # Собственно весь текст Чата
        self.chat_box = ctk.CTkTextbox(
            f,
            width=900,
            height=380,
            fg_color=self.PANEL,
            text_color=self.FG,
            corner_radius=10,
        )
        self.chat_box.pack(padx=20, pady=(0, 12), fill="both", expand=True)
        self._chatbox_set_state("disabled")

        # Ввод вопроса пользователем
        self.user_entry = ctk.CTkEntry(
            f,
            height=40,
            fg_color=self.BTN,
            text_color=self.FG,
            corner_radius=10,
            placeholder_text=self.tr("chat.placeholder","Введите сообщение…"),
        )
        self.user_entry.pack(padx=20, pady=(0, 12), fill="x")
        self.user_entry.bind("<Return>", lambda e: self.send_message())

        # Делаем новый фрейм для кнопок: два блока
        btn_area = ctk.CTkFrame(f, fg_color="transparent")
        btn_area.pack(padx=20, pady=(0, 14), fill="x")

        # 1й блок - отправить/очистить
        block1 = ctk.CTkFrame(btn_area, fg_color="transparent")
        block1.pack(fill="x")

        block1.grid_columnconfigure(0, weight=1)
        block1.grid_columnconfigure(1, weight=1)

        def mk_btn(parent, text, cmd, *, kind="primary", font=None, width=None):
            kw = dict(
                master=parent,
                text=text,
                command=cmd,
                corner_radius=10,
                height=38,
            )
            if width is not None:
                kw["width"] = width
            if font is not None:
                kw["font"] = font

            btn = ctk.CTkButton(**kw)
            if kind == "primary":
                btn.configure(fg_color=self.ACCENT, hover_color=self.ACCENT, text_color=self.FG)
            else:
                btn.configure(fg_color=self.BTN, hover_color=self.ACTIVE_BG, text_color=self.FG)
            return btn

        self.send_btn  = mk_btn(block1, self.tr("buttons.send","Отправить"), self.send_message, kind="primary")
        self.clear_btn = mk_btn(block1, self.tr("buttons.clear","Очистить"), self.renew_chat, kind="secondary")
        self.send_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.clear_btn.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        # 2й блок - контрль плеера.
        block2 = ctk.CTkFrame(btn_area, fg_color="transparent")
        block2.pack(fill="x", pady=(10, 0))

        block2.grid_columnconfigure((0, 1, 2), weight=1)

        icon_font = (self.FONT_NAME, 18, "bold")
        self.pause_btn  = mk_btn(block2, "⏸", self.player_pause, kind="primary", font=icon_font, width=52)
        self.resume_btn = mk_btn(block2, "▶", self.player_resume, kind="primary", font=icon_font, width=52)
        self.stop_btn   = mk_btn(block2, "⏹", self.player_stop, kind="primary", font=icon_font, width=52)

        # Уменьшаем высоту кнопочек
        for b in (self.pause_btn, self.resume_btn, self.stop_btn):
            try:
                b.configure(height=34)
            except Exception:
                pass

        self.pause_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.resume_btn.grid(row=0, column=1, sticky="ew", padx=8)
        self.stop_btn.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        # Всплывающие подсказки
        try:
            Hovertip(self.clear_btn,  "Очистка чата и истории общения.", hover_delay=500)
            Hovertip(self.pause_btn,  "Приостановить воспроизведение", hover_delay=500)
            Hovertip(self.resume_btn, "Продолжить воспроизведение", hover_delay=500)
            Hovertip(self.stop_btn,   "Продолжит воспроизведение только после нового ответа", hover_delay=500)
        except Exception:
            pass

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
                response = random.choice(self.content_store.get_support_phrases(self.lang_chat) or support_phrases)

            self.append_chat(f"{settings.TD_CHAT_PREFIX}{response}\n")

    def append_chat(self, text):
        self._chatbox_set_state("normal")
        self._chatbox_insert_end(text)
        self._chatbox_set_state("disabled")

    def show_chat(self):
        self.raise_frame("chat")
        self._chatbox_set_state("disabled")
        self.user_entry.focus_set()

    def show_chat_and_get_answer(self):
        self.raise_frame("chat")
        self._chatbox_set_state("disabled")
        self.user_entry.focus_set()
        delay_ms = 10
        self.after(delay_ms, lambda: self.send_message(default_msg='Дай мне совет'))


    # ПРОФИЛЬ

    def build_profile(self):
        f = self.frames["profile"]

        for w in f.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        # Фон страницы
        try:
            f.configure(fg_color=self.BG)
        except Exception:
            pass

        ctk.CTkLabel(
            f,
            text=self.tr("profile.title","Профиль"),
            font=(self.FONT_NAME, 18, "bold"),
            text_color=self.FG,
        ).pack(pady=(16, 8))

        # делаем страницу профиля полностью scrollable
        _, content = self.make_scrollable(f)

        # Опции в профиле
        fields_map = self.lang_get("profile.fields", {}) or {}
        values_map = self.lang_get("profile.values", {}) or {}
        cities_map = self.lang_get("profile.cities", {}) or {}

        def fld(k: str) -> str:
            return fields_map.get(k, k)

        def val(v: str) -> str:
            return values_map.get(v, v)

        gender_ru = ("Мужской", "Женский")
        marital_ru = ("Холост / Не замужем", "Женат / Замужем")
        yesno_ru = ("Да", "Нет")

        gender_list = tuple(val(x) for x in gender_ru)
        marital_list = tuple(val(x) for x in marital_ru)
        yesno_list = tuple(val(x) for x in yesno_ru)

        # Сверяем отображаемые и сохраненные значения
        self._profile_value_to_ru = {val(x): x for x in (list(gender_ru) + list(marital_ru) + list(yesno_ru))}

        city_allowed = tuple(city_list)

        def city_disp(c: str) -> str:
            if self.lang_ui == "ru":
                return c
            d = cities_map.get(c)
            if isinstance(d, str) and d.strip():
                return d
            return self._transliterate_ru(c)

        city_display_values = [city_disp(c) for c in city_allowed]
        self._profile_city_display_to_ru = {city_disp(c): c for c in city_allowed}

        self.name_var = tk.StringVar(value=str(self.profile.get("Имя", "")))

        # Сохраняем настроки профиля RU; Показываем перевод
        gender_ru_val = self.normalize_text_for_ui(self.profile.get("Пол", ""), gender_ru)
        self.gender_var = tk.StringVar(value=val(gender_ru_val))

        city_ru_val = self.normalize_text_for_ui(self.profile.get("Город", ""), city_allowed)
        self.city_var = tk.StringVar(value=city_disp(city_ru_val))

        self.birth_var = tk.StringVar(value=str(self.profile.get("Дата рождения", "")))

        marital_ru_val = self.normalize_text_for_ui(self.profile.get("Семейное положение", ""), marital_ru)
        self.marital_var = tk.StringVar(value=val(marital_ru_val))

        parents_ru_val = self.normalize_text_for_ui(self.profile.get("Родители", ""), yesno_ru)
        self.parents_var = tk.StringVar(value=val(parents_ru_val))

        friends_ru_val = self.normalize_text_for_ui(self.profile.get("Друзья", ""), yesno_ru)
        self.friends_var = tk.StringVar(value=val(friends_ru_val))

        try:
            children_default = int(self.profile.get("Дети", 0))
        except Exception:
            children_default = 0
        children_default = max(0, min(10, children_default))
        self.children_var = tk.IntVar(value=children_default)

        form = ctk.CTkFrame(content, fg_color="transparent")
        form.pack(padx=20, pady=10, fill="x")

        form.grid_columnconfigure(0, weight=0)
        form.grid_columnconfigure(1, weight=1)

        def label(row, text):
            ctk.CTkLabel(
                form,
                text=text + ":",
                text_color=self.FG,
                anchor="w",
                justify="left",
            ).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=6)

        label(0, fld("Имя"))
        ctk.CTkEntry(
            form,
            textvariable=self.name_var,
            fg_color=self.BTN,
            text_color=self.FG,
            height=34,
            corner_radius=10,
        ).grid(row=0, column=1, sticky="ew", pady=6)

        label(1, fld("Пол"))
        gender_frame = ctk.CTkFrame(form, fg_color="transparent")
        gender_frame.grid(row=1, column=1, sticky="w", pady=6)
        for i, g in enumerate(gender_list):
            ctk.CTkRadioButton(
                gender_frame,
                text=g,
                variable=self.gender_var,
                value=g,
                text_color=self.FG,
                fg_color=self.ACCENT,
            ).grid(row=0, column=i, padx=(0, 16))

        label(2, fld("Город"))
        try:
            self.city_menu = ctk.CTkOptionMenu(
                form,
                values=list(city_display_values) if city_allowed else [""],
                variable=self.city_var,
            )
            self.city_menu.configure(
                fg_color=self.BTN,
                button_color=self.ACCENT,
                button_hover_color=self.ACCENT,
                text_color=self.FG,
                dropdown_fg_color=self.PANEL,
                dropdown_hover_color=self.ACTIVE_BG,
                dropdown_text_color=self.FG,
            )
            self.city_menu.grid(row=2, column=1, sticky="w", pady=6)
        except Exception:
            ctk.CTkEntry(
                form,
                textvariable=self.city_var,
                fg_color=self.BTN,
                text_color=self.FG,
                height=34,
                corner_radius=10,
            ).grid(row=2, column=1, sticky="ew", pady=6)

        label(3, fld("Дата рождения"))
        birth_row = ctk.CTkFrame(form, fg_color="transparent")
        birth_row.grid(row=3, column=1, sticky="ew", pady=6)
        birth_row.grid_columnconfigure(0, weight=1)

        self.birth_entry = ctk.CTkEntry(
            birth_row,
            textvariable=self.birth_var,
            fg_color=self.BTN,
            text_color=self.FG,
            height=34,
            corner_radius=10,
        )
        self.birth_entry.grid(row=0, column=0, sticky="ew")
        try:
            self.birth_entry.configure(state="readonly")
        except Exception:
            pass

        ctk.CTkButton(
            birth_row,
            text="📅",
            width=44,
            height=34,
            corner_radius=10,
            fg_color=self.ACCENT,
            hover_color=self.ACCENT,
            text_color=self.FG,
            command=self.open_birthdate_picker,
        ).grid(row=0, column=1, padx=(10, 0))

        label(4, fld("Семейное положение"))
        marital_frame = ctk.CTkFrame(form, fg_color="transparent")
        marital_frame.grid(row=4, column=1, sticky="w", pady=6)
        for i, m in enumerate(marital_list):
            ctk.CTkRadioButton(
                marital_frame,
                text=m,
                variable=self.marital_var,
                value=m,
                text_color=self.FG,
                fg_color=self.ACCENT,
            ).grid(row=0, column=i, padx=(0, 16))

        label(5, fld("Родители"))
        parents_frame = ctk.CTkFrame(form, fg_color="transparent")
        parents_frame.grid(row=5, column=1, sticky="w", pady=6)
        for i, v in enumerate(yesno_list):
            ctk.CTkRadioButton(
                parents_frame,
                text=v,
                variable=self.parents_var,
                value=v,
                text_color=self.FG,
                fg_color=self.ACCENT,
            ).grid(row=0, column=i, padx=(0, 16))

        label(6, fld("Друзья"))
        friends_frame = ctk.CTkFrame(form, fg_color="transparent")
        friends_frame.grid(row=6, column=1, sticky="w", pady=6)
        for i, v in enumerate(yesno_list):
            ctk.CTkRadioButton(
                friends_frame,
                text=v,
                variable=self.friends_var,
                value=v,
                text_color=self.FG,
                fg_color=self.ACCENT,
            ).grid(row=0, column=i, padx=(0, 16))

        # Дети (0 - 10)
        label(7, fld("Дети"))
        children_row = ctk.CTkFrame(form, fg_color="transparent")
        children_row.grid(row=7, column=1, sticky="ew", pady=6)
        children_row.grid_columnconfigure(0, weight=1)

        self.children_slider = ctk.CTkSlider(
            children_row,
            from_=0,
            to=10,
            number_of_steps=10,
            fg_color=getattr(self.theme, "SLIDER_FG", None) or self.ACTIVE_BG,
            progress_color=getattr(self.theme, "SLIDER_PROGRESS", None) or self.ACCENT,
            button_color=getattr(self.theme, "SLIDER_BUTTON", None) or self.ACCENT,
            button_hover_color=getattr(self.theme, "SLIDER_BUTTON", None) or self.ACCENT,
            command=lambda v: self.children_var.set(int(round(v))),
        )
        self.children_slider.grid(row=0, column=0, sticky="ew")
        try:
            self.children_slider.set(children_default)
        except Exception:
            pass

        self.children_value_lbl = ctk.CTkLabel(children_row, textvariable=self.children_var, width=40, text_color=self.FG)
        self.children_value_lbl.grid(row=0, column=1, padx=(10, 0))

        # Многострочные поля
        def textbox(row, title, key, height=100):
            label(row, title)
            tb = ctk.CTkTextbox(
                form,
                height=height,
                fg_color=self.PANEL,
                text_color=self.FG,
                corner_radius=10,
            )
            tb.grid(row=row, column=1, sticky="ew", pady=6)
            tb.insert("1.0", str(self.profile.get(key, "")))
            return tb

        self.pets_text = textbox(8, fld("Домашние животные"), "Домашние животные", 90)
        self.hobby_text = textbox(9, fld("Хобби, интересы"), "Хобби, интересы", 90)
        self.comment_text = textbox(10, fld("Комментарий"), "Комментарий", 120)

        ctk.CTkButton(
            content,
            text=self.tr("profile.save_button","Сохранить профиль"),
            command=self.save_profile_data,
            fg_color=self.ACCENT,
            hover_color=self.ACCENT,
            text_color=self.FG,
            corner_radius=10,
            height=38,
        ).pack(pady=(14, 18))


    def open_birthdate_picker_0(self):
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
                messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("msg.invalid_date","Некорректная дата."))
                return

            self.birth_var.set(f"{yy:04d}-{mm:02d}-{dd:02d}")
            top.destroy()

        btns = tk.Frame(top, bg=self.BG)
        btns.grid(row=3, column=0, columnspan=2, pady=(5, 12))

        tk.Button(btns, text="OK", command=set_date, bg=self.ACCENT, fg=self.FG, relief="flat", padx=14, pady=6)\
            .pack(side="left", padx=8)
        tk.Button(btns, text="Отмена", command=top.destroy, bg=self.BTN, fg=self.FG, relief="flat", padx=14, pady=6)\
            .pack(side="left", padx=8)

    def open_birthdate_picker(self, title="Выбор даты", year_min=1900, year_max_shift=10, check_more_then_today=True, current=None, callback=None):
        top = tk.Toplevel(self)
        top.title(title)
        top.configure(bg=self.BG)
        top.resizable(False, False)
        top.grab_set()

        today = date.today()
        # year_min = year_min
        if year_max_shift < 0:
            year_max_shift = 0
        year_max = today.year - year_max_shift

        y, m, d = today.year, today.month, today.day
        if current is None:
            cur = self.birth_var.get().strip()
            try:
                parts = cur.split("-")
                if len(parts) == 3:
                    y = int(parts[0])
                    m = int(parts[1])
                    d = int(parts[2])
            except Exception:
                pass
        elif isinstance(current, date):
            y, m, d = current.year, current.month, current.day

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

        def is_valid_date(yy, mm, dd, check_more_then_today=check_more_then_today):
            try:
                new_date = date(yy, mm, dd)
                if check_more_then_today and new_date > today:
                    return False
                return True
            except Exception:
                return False

        def set_date(callback=callback):
            yy = int(year_var.get())
            mm = int(month_var.get())
            dd = int(day_var.get())

            if not is_valid_date(yy, mm, dd):
                messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("msg.invalid_date","Некорректная дата."))
                return
            if callback is None:
                self.birth_var.set(f"{yy:04d}-{mm:02d}-{dd:02d}")
            else:
                callback(date(yy, mm, dd))
            top.destroy()

        btns = tk.Frame(top, bg=self.BG)
        btns.grid(row=3, column=0, columnspan=2, pady=(5, 12))

        tk.Button(btns, text="OK", command=set_date, bg=self.ACCENT, fg=self.FG, relief="flat", padx=14, pady=6)\
            .pack(side="left", padx=8)
        tk.Button(btns, text="Отмена", command=top.destroy, bg=self.BTN, fg=self.FG, relief="flat", padx=14, pady=6)\
            .pack(side="left", padx=8)

    def save_profile_data(self):
        data = {
            "Имя": self.name_var.get().strip(),
            "Пол": (getattr(self, "_profile_value_to_ru", None) or {}).get(self.gender_var.get().strip(), self.gender_var.get().strip()),
            "Город": (getattr(self, "_profile_city_display_to_ru", None) or {}).get(self.city_var.get().strip(), self.city_var.get().strip()),
            "Дата рождения": self.birth_var.get().strip(),
            "Семейное положение": (getattr(self, "_profile_value_to_ru", None) or {}).get(self.marital_var.get().strip(), self.marital_var.get().strip()),
            "Родители": (getattr(self, "_profile_value_to_ru", None) or {}).get(self.parents_var.get().strip(), self.parents_var.get().strip()),
            "Дети": max(0, min(10, int(self.children_var.get()))),
            "Друзья": (getattr(self, "_profile_value_to_ru", None) or {}).get(self.friends_var.get().strip(), self.friends_var.get().strip()),
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
            messagebox.showinfo(self.tr("msg.saved_title","Сохранено"), self.tr("msg.profile_saved","Профиль сохранён."))
            self.show_home()
        else:
            messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("msg.profile_save_failed","Не удалось сохранить профиль."))

    def show_profile(self):
        self.raise_frame("profile")

    def refresh_profile_ui(self):
        # Если вкладка профиля ещё не построена — просто строим
        if not hasattr(self, "name_var"):
            self.build_profile()
            return


        self.name_var.set(str(self.profile.get("Имя", "")))
        self.gender_var.set(self.normalize_text_for_ui(self.profile.get("Пол", ""), ("Мужской", "Женский")))
        self.city_var.set(self.normalize_text_for_ui(self.profile.get("Город", ""), tuple(city_list)))
        self.birth_var.set(str(self.profile.get("Дата рождения", "")))
        self.marital_var.set(self.normalize_text_for_ui(
            self.profile.get("Семейное положение", ""),
            ("Холост / Не замужем", "Женат / Замужем"),
        ))
        self.parents_var.set(self.normalize_text_for_ui(self.profile.get("Родители", ""), ("Да", "Нет")))
        self.friends_var.set(self.normalize_text_for_ui(self.profile.get("Друзья", ""), ("Да", "Нет")))

        try:
            children_default = int(self.profile.get("Дети", 0))
        except Exception:
            children_default = 0
        self.children_var.set(max(0, min(10, children_default)))
        if hasattr(self, "children_slider"):
            try:
                self.children_slider.set(int(self.children_var.get()))
            except Exception:
                pass

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




    @staticmethod
    def _transliterate_ru(text: str) -> str:
        """Простая транслитерация для отображения некоторых элементов."""
        if not isinstance(text, str):
            return str(text)
        m = {
            "А":"A","Б":"B","В":"V","Г":"G","Д":"D","Е":"E","Ё":"Yo","Ж":"Zh","З":"Z","И":"I","Й":"Y","К":"K","Л":"L","М":"M","Н":"N","О":"O","П":"P","Р":"R","С":"S","Т":"T","У":"U","Ф":"F","Х":"Kh","Ц":"Ts","Ч":"Ch","Ш":"Sh","Щ":"Sch","Ъ":"","Ы":"Y","Ь":"","Э":"E","Ю":"Yu","Я":"Ya",
            "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"yo","ж":"zh","з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"kh","ц":"ts","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya",
        }
        return "".join(m.get(ch, ch) for ch in text)
    def normalize_text_for_ui(self, value: str, allowed: tuple[str, ...]) -> str:
        value = (value or "").strip()
        return value if value in allowed else (allowed[0] if allowed else "")


    # НАСТРОЙКИ

    def load_option_from_config(self, theme_list=None, voice_list=None):
        # Если вкладка настроек ещё не построена — просто строим
        if not hasattr(self, "opt_theme_var"):
            return
        theme_list = theme_list or tuple(settings.THEMES.keys()) or (settings.THEMES_DEFAULT,) or ("Тёмная",)
        voice_list = voice_list or tuple(TTS_VOICES.keys()) or ("Наталья",)

        opt = settings.app_options
        self.opt_use_asr_var.set(value=bool(getattr(opt, "USE_TTS", True)))
        theme_key = self.normalize_text_for_ui(getattr(opt, "THEME", theme_list[0]), theme_list)
        theme_name = (getattr(self, "_theme_key_to_name", None) or {}).get(theme_key, theme_key)
        self.opt_theme_var.set(value=theme_name)

        voice_key = self.normalize_text_for_ui(getattr(opt, "TTS_VOICE", voice_list[0]), voice_list)
        voice_name = (getattr(self, "_voice_key_to_name", None) or {}).get(voice_key, voice_key)
        self.opt_voice_var.set(value=voice_name)


        # Языковые установки по умолчанию
        try:
            ui_code = str(getattr(opt, "LANG_UI", "ru"))
            chat_code = str(getattr(opt, "LANG_CHAT", ui_code))
            content_code = str(getattr(opt, "LANG_CONTENT", ui_code))
            code_to_name = getattr(self, "_lang_code_to_name", None) or {}
            self.opt_lang_ui_var.set(value=code_to_name.get(ui_code, ui_code))
            self.opt_lang_chat_var.set(value=code_to_name.get(chat_code, chat_code))
            self.opt_lang_content_var.set(value=code_to_name.get(content_code, content_code))
        except Exception:
            pass



    def build_options(self):
        f = self.frames["options"]
        for w in f.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        # Фон страницы
        try:
            f.configure(fg_color=self.BG)
        except Exception:
            pass

        ctk.CTkLabel(
            f,
            text=self.tr("options.title", "Настройки"),
            font=(self.FONT_NAME, 18, "bold"),
            text_color=self.FG,
        ).pack(pady=(16, 8))

        # варианты выбора из
        theme_keys = tuple(settings.THEMES.keys()) or (settings.THEMES_DEFAULT,) or ("Тёмная",)
        voice_keys = tuple(TTS_VOICES.keys()) or ("Наталья",)

        # Выбор языка: показываем удобочитаемые названия, сохраняем коды
        langs = ("ru", "en", "it", "de")
        self._lang_code_to_name = {c: self.tr(f"language.{c}", c) for c in langs}
        self._lang_name_to_code = {v: k for k, v in self._lang_code_to_name.items()}
        lang_display_values = [self._lang_code_to_name[c] for c in langs]

        # Выбор темы
        themes_map = self.lang_get("options.themes", {}) or {}
        self._theme_key_to_name = {k: themes_map.get(k, k) for k in theme_keys}
        self._theme_name_to_key = {v: k for k, v in self._theme_key_to_name.items()}
        theme_display_values = [self._theme_key_to_name[k] for k in theme_keys]

        voices_map = self.lang_get("options.voices", {}) or {}

        def _voice_disp(v):
            if self.lang_ui == "ru":
                return v
            dv = voices_map.get(v)
            if isinstance(dv, str) and dv.strip():
                return dv
            return self._transliterate_ru(v)

        self._voice_key_to_name = {k: _voice_disp(k) for k in voice_keys}
        self._voice_name_to_key = {v: k for k, v in self._voice_key_to_name.items()}
        voice_display_values = [self._voice_key_to_name[k] for k in voice_keys]

        self.opt_use_asr_var = tk.BooleanVar()
        self.opt_theme_var = tk.StringVar()
        self.opt_voice_var = tk.StringVar()
        self.opt_lang_ui_var = tk.StringVar()
        self.opt_lang_chat_var = tk.StringVar()
        self.opt_lang_content_var = tk.StringVar()
        self.load_option_from_config(theme_keys, voice_keys)

        form = ctk.CTkFrame(f, fg_color="transparent")
        form.pack(padx=20, pady=10, fill="x")
        form.grid_columnconfigure(0, weight=0)
        form.grid_columnconfigure(1, weight=1)

        def label(row, text):
            ctk.CTkLabel(form, text=text + ":", text_color=self.FG, anchor="w")                .grid(row=row, column=0, sticky="w", padx=(0, 12), pady=8)

        # озвучивать ответ в чате
        label(0, self.tr("options.tts", "Озвучивать ответ в чате"))
        try:
            sw = ctk.CTkSwitch(
                form,
                text="",
                variable=self.opt_use_asr_var,
                onvalue=True,
                offvalue=False,
                fg_color=getattr(self.theme, "SWITCH_FG", None) or self.BTN,
                progress_color=getattr(self.theme, "SWITCH_PROGRESS", None) or self.ACCENT,
                button_color=getattr(self.theme, "SWITCH_BUTTON", None) or self.ACCENT,
                button_hover_color=getattr(self.theme, "SWITCH_BUTTON", None) or self.ACCENT,
            )
            sw.grid(row=0, column=1, sticky="w", pady=8)
        except Exception:
            cb = ctk.CTkCheckBox(form, text="", variable=self.opt_use_asr_var)
            try:
                cb.configure(fg_color=self.ACCENT, hover_color=self.ACCENT, text_color=self.FG, border_color=self.ACTIVE_BG)
            except Exception:
                pass
            cb.grid(row=0, column=1, sticky="w", pady=8)

        label(1, self.tr("options.theme", "Тема оформления"))
        self.opt_theme_menu = ctk.CTkOptionMenu(form, values=list(theme_display_values), variable=self.opt_theme_var)
        try:
            self.opt_theme_menu.configure(
                fg_color=self.BTN,
                button_color=self.ACCENT,
                button_hover_color=self.ACCENT,
                text_color=self.FG,
                dropdown_fg_color=self.PANEL,
                dropdown_hover_color=self.ACTIVE_BG,
                dropdown_text_color=self.FG,
            )
        except Exception:
            pass
        self.opt_theme_menu.grid(row=1, column=1, sticky="w", pady=8)

        label(2, self.tr("options.voice", "Голос чата"))
        self.opt_voice_menu = ctk.CTkOptionMenu(form, values=list(voice_display_values), variable=self.opt_voice_var)
        try:
            self.opt_voice_menu.configure(
                fg_color=self.BTN,
                button_color=self.ACCENT,
                button_hover_color=self.ACCENT,
                text_color=self.FG,
                dropdown_fg_color=self.PANEL,
                dropdown_hover_color=self.ACTIVE_BG,
                dropdown_text_color=self.FG,
            )
        except Exception:
            pass
        self.opt_voice_menu.grid(row=2, column=1, sticky="w", pady=8)

        label(3, self.tr("options.lang_ui", "Язык интерфейса"))
        self.opt_lang_ui_menu = ctk.CTkOptionMenu(form, values=list(lang_display_values), variable=self.opt_lang_ui_var)
        try:
            self.opt_lang_ui_menu.configure(
                fg_color=self.BTN,
                button_color=self.ACCENT,
                button_hover_color=self.ACCENT,
                text_color=self.FG,
                dropdown_fg_color=self.PANEL,
                dropdown_hover_color=self.ACTIVE_BG,
                dropdown_text_color=self.FG,
            )
        except Exception:
            pass
        self.opt_lang_ui_menu.grid(row=3, column=1, sticky="w", pady=8)

        label(4, self.tr("options.lang_chat", "Язык ответов (LLM)"))
        self.opt_lang_chat_menu = ctk.CTkOptionMenu(form, values=list(lang_display_values), variable=self.opt_lang_chat_var)
        try:
            self.opt_lang_chat_menu.configure(
                fg_color=self.BTN,
                button_color=self.ACCENT,
                button_hover_color=self.ACCENT,
                text_color=self.FG,
                dropdown_fg_color=self.PANEL,
                dropdown_hover_color=self.ACTIVE_BG,
                dropdown_text_color=self.FG,
                state="disabled",          # state=ctk.DISABLED
            )
        except Exception:
            pass
        self.opt_lang_chat_menu.grid(row=4, column=1, sticky="w", pady=8)

        label(5, self.tr("options.lang_content", "Язык контента"))
        self.opt_lang_content_menu = ctk.CTkOptionMenu(form, values=list(lang_display_values), variable=self.opt_lang_content_var)
        try:
            self.opt_lang_content_menu.configure(
                fg_color=self.BTN,
                button_color=self.ACCENT,
                button_hover_color=self.ACCENT,
                text_color=self.FG,
                dropdown_fg_color=self.PANEL,
                dropdown_hover_color=self.ACTIVE_BG,
                dropdown_text_color=self.FG,
                state="disabled",          # state=ctk.DISABLED
            )
        except Exception:
            pass
        self.opt_lang_content_menu.grid(row=5, column=1, sticky="w", pady=8)


        btns = ctk.CTkFrame(f, fg_color="transparent")
        btns.pack(pady=(10, 6))

        ctk.CTkButton(
            btns,
            text=self.tr("buttons.apply", "Применить"),
            command=self.save_options_data,
            fg_color=self.ACCENT,
            hover_color=self.ACCENT,
            text_color=self.FG,
            corner_radius=10,
            height=38,
            width=160,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btns,
            text=self.tr("buttons.reset", "Вернуть"),
            command=self.load_option_from_config,
            fg_color=self.BTN,
            hover_color=self.ACTIVE_BG,
            text_color=self.FG,
            corner_radius=10,
            height=38,
            width=140,
        ).pack(side="left", padx=10)

        ctk.CTkLabel(
            f,
            text=self.tr("options.hint","Изменения применяются сразу после нажатия «Применить».") ,
            text_color=self.LABEL_FG,
            font=(self.FONT_NAME, 10),
            justify="center",
            wraplength=720,
        ).pack(pady=(6, 10), padx=24)

    def save_options_data(self):
        # сохраняем app_options в data/app_options.json и сразу прменяем
        try:
            theme_list = tuple(settings.THEMES.keys()) or ("white",)
            voice_list = tuple(TTS_VOICES.keys()) or ("Наталья",)

            theme_disp = (self.opt_theme_var.get() or "").strip()
            voice_disp = (self.opt_voice_var.get() or "").strip()

            theme = (getattr(self, "_theme_name_to_key", None) or {}).get(theme_disp, theme_disp)
            voice = (getattr(self, "_voice_name_to_key", None) or {}).get(voice_disp, voice_disp)

            # небольшая нормализация
            if theme not in theme_list:
                theme = theme_list[0]
            if voice not in voice_list:
                voice = voice_list[0]

            # Запоминаем предыдущее состояние настроек.
            prev_ui = getattr(self, "lang_ui", "ru")
            prev_chat = getattr(self, "lang_chat", prev_ui)
            prev_content = getattr(self, "lang_content", prev_ui)

            settings.app_options.USE_TTS = bool(self.opt_use_asr_var.get())
            settings.app_options.THEME = theme

            settings.app_options.TTS_VOICE = voice

            # языки
            ui_sel = (self.opt_lang_ui_var.get() or "ru").strip()
            chat_sel = (self.opt_lang_chat_var.get() or ui_sel).strip()
            content_sel = (self.opt_lang_content_var.get() or ui_sel).strip()

            name_to_code = getattr(self, "_lang_name_to_code", None) or {}
            ui_lang = name_to_code.get(ui_sel, ui_sel)
            chat_lang = name_to_code.get(chat_sel, chat_sel)
            content_lang = name_to_code.get(content_sel, content_sel)

            # Синхронизируем язык ответа и контекста с языком интерфейса
            if prev_chat == prev_ui and chat_lang == prev_chat and ui_lang != prev_ui:
                chat_lang = ui_lang
            if prev_content == prev_ui and content_lang == prev_content and ui_lang != prev_ui:
                content_lang = ui_lang


            settings.app_options.LANG_UI = ui_lang
            settings.app_options.LANG_CHAT = chat_lang
            settings.app_options.LANG_CONTENT = content_lang
        except Exception:
            messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("msg.invalid_options","Некорректные настройки."))
            return

        if settings.save_app_options(settings.app_options):
            # применяем тему сразу
            try:
                self.theme_renew(settings.app_options.THEME)
            except Exception:
                pass

            # применить CTk вид и перерисовать чтоб настройки цвета вступили в силу
            try:
                self._apply_ctk_appearance()
            except Exception:
                pass
            # Перезагрузить языки
            try:
                self.lang_ui = settings.app_options.LANG_UI
                self.lang_chat = settings.app_options.LANG_CHAT
                self.lang_content = settings.app_options.LANG_CONTENT

                self.language.load(self.lang_ui)
                self.tr = self.language.t
                self.lang_get = self.language.get

                self.language_chat.load(self.lang_chat)
                self.tr_chat = self.language_chat.t
            except Exception:
                pass

            # обновляем системный промпт и статьи при смене языка
            try:
                if self.llm_item is not None:
                    self.llm_item.update_languages(self.lang_chat, self.lang_content)
            except Exception:
                pass

            try:
                self.create_menu()
            except Exception:
                pass

            try:
                self.rebuild_ui(keep_page="options")
            except Exception:
                pass

            messagebox.showinfo(self.tr("msg.saved_title","Сохранено"), self.tr("msg.options_saved","Настройки сохранены и применены."))
        else:
            messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("msg.save_failed","Не удалось сохранить настройки."))

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

        self.load_option_from_config(theme_list, voice_list)




    # О ПРИЛОЖЕНИИ

    def build_about(self):
        f = self.frames["about"]
        for w in f.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        # Фон страницы
        try:
            f.configure(fg_color=self.BG)
        except Exception:
            pass

        ctk.CTkLabel(
            f,
            text=self.tr("about.title","О проекте"),
            font=(self.FONT_NAME, 18, "bold"),
            text_color=self.FG,
        ).pack(pady=(16, 8))

        default_text = """Treatment of Depression «Ты не один» — учебный инженерный проект.
Настольное приложение на Python с графическим интерфейсом на базе Tkinter/CustomTkinter.
В одном приложении пользователь получает три базовые функции: быстрые поддерживающие подсказки, чат поддержку на базе LLM и дневник для записи самочувствия и настроения.

Важно: приложение не является медицинским изделием, не ставит диагноз и не заменяет врача/психолога.
При выраженном ухудшении самочувствия необходимо обратиться к специалистам и/или в службы экстренной помощи.

Функции:
• Слова поддержки
• Чат с использованием генеративной модели
• Дневник самочувствия
• Профиль пользователя
• Поддерживаются горячие клавиши (Ctrl + первая буква пункта меню)
"""

        text = self.tr("about.text", default_text)


        box = ctk.CTkTextbox(
            f,
            fg_color=self.PANEL,
            text_color=self.FG,
            corner_radius=10,
            height=420,
        )
        box.pack(padx=20, pady=(0, 16), fill="both", expand=True)
        box.insert("1.0", text)
        try:
            box.configure(state="disabled")
        except Exception:
            try:
                box._textbox.configure(state="disabled")
            except Exception:
                pass

    def show_about(self):
        self.raise_frame("about")


if __name__ == "__main__":
    app = TDApp()
    app.mainloop()
