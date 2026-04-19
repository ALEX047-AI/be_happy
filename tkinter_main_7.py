"""
TD — Treatment of Depression
"""

import os
import random
from datetime import date
import time
import threading
import tempfile
import wave

import matplotlib
matplotlib.use("TkAgg")

import tkinter as tk
import customtkinter as ctk
from PIL import Image
from tkinter import messagebox
from tkinter import filedialog, simpledialog

from queue import Queue, Empty
from dataclasses import dataclass

from options.config import settings, TTS_VOICES, city_list
from language import LanguageStore
from content import ContentStore
from services.city_events import EVENTS_INFO_DYNAMIC, SharedData

from articles import support_phrases
from profile_manage import (load_profile, save_profile, load_diary, save_diary, crisis_keywords, load_json, save_json,
                            sheet_to_list, sheet_to_dict, dict_to_sheet, profile_fields, diary_fields)
from auth_storage import auth_manager, AuthError, InvalidCredentials, UserAlreadyExists, UserNotFound, CryptoUnavailable
from llm import LLM_IO  # get_frase_from_llm, get_frase_from_llm_stream
from services.speech_service import SpeechPlayer, TTS_Stream, ASR_Stream, ASRJob, ASRResult
from tkinter_diary import DiaryView
from idlelib.tooltip import Hovertip

DATA = settings.DATA
DIARY_PATH = os.path.join(DATA, settings.diary_file_name)
PROFILE_PATH = os.path.join(DATA, settings.profile_file_name)
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
        self.auth = auth_manager
        self.profile = {}
        self.diary = {}
        try:
            self._home_auth_mode = "signin" if self.auth.has_any_user() else "signup"
        except Exception:
            self._home_auth_mode = "signin"
        self._auth_username_value = ""
        self._auth_password_value = ""
        self._auth_confirm_value = ""
        self.auth_username_entry = None
        self.auth_password_entry = None
        self.auth_confirm_entry = None

        # Загрузка языков
        self.lang_dir = os.path.join(settings.DATA, "language")
        self.content_dir = os.path.join(settings.DATA, "content")
        os.makedirs(self.lang_dir, exist_ok=True)
        os.makedirs(self.content_dir, exist_ok=True)

        self.lang_ui = getattr(settings.app_options, "LANG_UI", "ru")
        self.lang_chat = getattr(settings.app_options, "LANG_CHAT", self.lang_ui)
        self.lang_content = getattr(settings.app_options, "LANG_CONTENT", self.lang_ui)
        opt = settings.app_options
        self.opt_add_labels = tk.BooleanVar()
        self.opt_add_labels.set(value=bool(getattr(opt, "ADD_LABELS", False)))
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
                raise RuntimeError('Пакет customtkinter не установлен')
            self._apply_ctk_appearance()
        except Exception:
            try:
                self.configure(bg=self.BG)
            except Exception:
                pass

        self.create_layout()
        self._startup_auth_flow()

        if self._is_signed_in():
            if not self.profile:
                self.show_profile()
            else:
                self.show_home()
        else:
            self.show_home()


        self.q_text = Queue()
        self.q_speech = Queue()
        self.q_asr_in = Queue()
        self.q_asr_out = Queue()
        self.asr_stream = None
        self._asr_recording = False  # идет запись
        self._asr_busy = False       # идет распознование
        self._asr_polling = False
        self._asr_stop_event = threading.Event()
        self._asr_rec_thread = None
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


    def _asr_lang_param(self) -> str:
        """Возвращает язык для ASR в формате Salute ('ru-RU', 'en-US')."""
        try:
            lang = getattr(settings.app_options, "LANG_CHAT", None) or getattr(settings.app_options, "LANG_UI", "ru")
        except Exception:
            lang = "ru"
        lang = str(lang).lower()
        return {"ru": "ru-RU", "en": "en-US"}.get(lang, "ru-RU")

    def _ensure_asr_worker(self) -> bool:
        """Ленивая инициализация ASR worker (чтобы не падать при старте приложения)."""
        try:
            if self.asr_stream is not None and getattr(self.asr_stream, "is_alive", lambda: False)():
                return True
        except Exception:
            pass

        try:
            self.asr_stream = ASR_Stream(self.q_asr_in, self.q_asr_out, daemon=True, finished_item=False)
            self.asr_stream.start()
            return True
        except Exception as e:
            try:
                messagebox.showerror(self.tr("errors.asr_title","ASR"), f"{self.tr('errors.asr_init','Не удалось запустить распознавание речи')}: {e}")
            except Exception:
                pass
            return False
    def _record_mic_to_pcm_stream(
        self,
        *,
        stop_event: threading.Event,
        max_seconds: int = 59,
        prefer_rate: int = 16000,
        channels: int = 1,
        silence_seconds: float = 3.0,
        silence_rms: float = 400.0,
        min_voice_ms: int = 200,
    ) -> tuple[str, int, int]:
        """
        Запись микрофона в RAW PCM16LE (.pcm) c возможностью:
        - остановить вручную (stop_event)
        - авто-остановка по времени (max_seconds)
        - авто-остановка по тишине: если после того, как пользователь начал говорить,
          тишина длится silence_seconds секунд.

        Возвращает (path, sample_rate, channels).
        """
        try:
            import sounddevice as sd
        except Exception as e:
            raise RuntimeError(f"Пакет sounddevice недоступен: {e}")

        import audioop

        rates_to_try = [int(prefer_rate), 8000]  # 8k — запасной

        # лимит передачи в сервис АСР (2мб - для Салют)
        asr_audio_max_bytes = 2 * 1024 * 1024 - 4096

        last_err = None
        for sr in rates_to_try:
            try:
                sr = int(sr)
                ch = int(channels)
                if ch not in (1, 2):
                    ch = 1

                # 50мс блок — для определения тишины
                blocksize = max(256, int(sr * 0.05))

                chunks: list[bytes] = []
                total_bytes = 0

                start_ts = time.time()
                last_voice_ts = start_ts
                heard_voice = False
                voice_ms_acc = 0.0

                # максимально допустимый размер записи (в байтах pcm16)
                max_bytes = min(int(sr * max_seconds * ch * 2), asr_audio_max_bytes)

                def callback(indata, frames, time_info, status):
                    nonlocal total_bytes, last_voice_ts, heard_voice, voice_ms_acc

                    if stop_event.is_set():
                        raise sd.CallbackStop

                    # RawInputStream даёт bytes-like
                    b = bytes(indata) if indata is not None else b""
                    if not b:
                        return

                    # гарантируем кратность 2 байтам (int16)
                    if len(b) % 2 != 0:
                        b = b[:-1]
                        if not b:
                            return

                    # ограничиваем размер
                    remain = max_bytes - total_bytes
                    if remain <= 0:
                        stop_event.set()
                        raise sd.CallbackStop
                    if len(b) > remain:
                        b = b[:remain - (remain % 2)]
                        stop_event.set()

                    chunks.append(b)
                    total_bytes += len(b)

                    now = time.time()

                    # определяем речь/тишину
                    try:
                        rms = float(audioop.rms(b, 2))
                    except Exception:
                        rms = 0.0

                    if rms >= float(silence_rms):
                        last_voice_ts = now
                        voice_ms_acc += (frames / sr) * 1000.0
                        if voice_ms_acc >= float(min_voice_ms):
                            heard_voice = True

                    # автоостановка по времени (1 минута)
                    if (now - start_ts) >= float(max_seconds):
                        stop_event.set()
                        raise sd.CallbackStop

                    # автоостановка по тишине — только если уже было что-то похожее на речь
                    if heard_voice and (now - last_voice_ts) >= float(silence_seconds):
                        stop_event.set()
                        raise sd.CallbackStop

                with sd.RawInputStream(
                    samplerate=sr,
                    channels=ch,
                    dtype="int16",
                    blocksize=blocksize,
                    callback=callback,
                ):
                    while not stop_event.is_set():
                        sd.sleep(50)

                fd, path = tempfile.mkstemp(prefix="td_asr_", suffix=".pcm")
                os.close(fd)
                with open(path, "wb") as f:
                    f.write(b"".join(chunks))

                return path, sr, ch

            except Exception as e:
                last_err = e
                try:
                    stop_event.clear()
                except Exception:
                    pass
                continue

        raise RuntimeError(f"Не удалось записать микрофон: {last_err}")

    def _ensure_asr_polling(self):
        if getattr(self, "_asr_polling", False):
            return
        self._asr_polling = True
        self.after(200, self._poll_asr_results)

    def _poll_asr_results(self):
        try:
            res = self.q_asr_out.get_nowait()
        except Empty:
            self.after(200, self._poll_asr_results)
            return
        except Exception:
            self.after(200, self._poll_asr_results)
            return

        if res is None:
            self._asr_polling = False
            return

        try:
            if isinstance(res, ASRResult) and res.error:
                self.append_chat(f"\n[ASR error: {res.error}]\n")
                text = ""
            else:
                texts = []
                if isinstance(res, ASRResult):
                    texts = res.texts or []
                elif isinstance(res, (list, tuple)):
                    texts = list(res)
                text = " ".join([t for t in texts if t]).strip()

            self._asr_recording = False
            self._asr_busy = False
            try:
                self._asr_stop_event.clear()
            except Exception:
                pass
            try:
                if hasattr(self, "say_btn") and self.say_btn is not None:
                    self.say_btn.configure(state="normal", text=self.tr("buttons.say","Сказать"))
            except Exception:
                pass

            if text and hasattr(self, "user_entry") and self.user_entry is not None:
                try:
                    self.user_entry.configure(state="normal")
                except Exception:
                    pass
                self.user_entry.delete(0, tk.END)
                self.user_entry.insert(0, text)
                self.user_entry.focus_set()
        finally:
            try:
                if self.q_asr_out.qsize() > 0:
                    self.after(50, self._poll_asr_results)
                    return
            except Exception:
                pass
            self._asr_polling = False

    def _asr_set_btn(self, *, state: str | None = None, text: str | None = None):
        try:
            if not hasattr(self, "say_btn") or self.say_btn is None:
                return
            if state is not None:
                self.say_btn.configure(state=state)
            if text is not None:
                self.say_btn.configure(text=text)
        except Exception:
            pass

    def asr_toggle(self, max_seconds: int = 59, silence_seconds: float = 3.0):
        """
        Кнопка "Сказать":
        - 1-е нажатие: начинаем слушать
        - 2-е нажатие: останавливаем запись и отправляем в ASR

        Авто-стоп:
        - по тишине silence_seconds (после того, как пользователь начал говорить)
        - или по max_seconds.
        """
        if getattr(self, "_asr_busy", False):
            return

        if not getattr(self, "_asr_recording", False):
            self._asr_start_listen(max_seconds=max_seconds, silence_seconds=silence_seconds)
        else:
            self._asr_stop_listen()

    def _asr_start_listen(self, *, max_seconds: int = 59, silence_seconds: float = 3.0):
        if getattr(self, "_asr_recording", False) or getattr(self, "_asr_busy", False):
            return
        if not self._ensure_asr_worker():
            return

        self._asr_recording = True
        try:
            self._asr_stop_event.clear()
        except Exception:
            pass

        self._asr_set_btn(state="normal", text=self.tr("buttons.listening", "Слушаю…"))

        def worker():
            try:
                path, sr, ch = self._record_mic_to_pcm_stream(
                    stop_event=self._asr_stop_event,
                    max_seconds=max_seconds,
                    prefer_rate=16000,
                    channels=1,
                    silence_seconds=silence_seconds,
                    silence_rms=400.0,
                    min_voice_ms=200,
                )

                def ui_recognizing():
                    self._asr_recording = False
                    self._asr_busy = True
                    self._asr_set_btn(state="disabled", text=self.tr("buttons.recognizing", "Распознаю…"))
                self.after(0, ui_recognizing)

                lang = self._asr_lang_param()
                c_type = f"audio/x-pcm;bit=16;rate={sr}"
                qparam = f"?language={lang}&sample_rate={sr}&channels_count={ch}"
                self.q_asr_in.put(ASRJob(file=path, c_type=c_type, query_param=qparam, cleanup=True))

                self.after(0, self._ensure_asr_polling)

            except Exception as e:
                def ui_err():
                    self._asr_recording = False
                    self._asr_busy = False
                    try:
                        self._asr_stop_event.clear()
                    except Exception:
                        pass
                    self._asr_set_btn(state="normal", text=self.tr("buttons.say", "Сказать"))
                    self.append_chat(f"\n[ASR error: {e}]\n")
                self.after(0, ui_err)

        self._asr_rec_thread = threading.Thread(target=worker, daemon=True)
        self._asr_rec_thread.start()

    def _asr_stop_listen(self):
        """Останавливаем запись (2-е нажатие). Распознавание выполнит worker."""
        if not getattr(self, "_asr_recording", False):
            return
        try:
            self._asr_stop_event.set()
        except Exception:
            pass

        # UI отклик сразу: пользователь нажал — мы реагируем
        self._asr_set_btn(state="disabled", text=self.tr("buttons.recognizing", "Распознаю…"))
        self._asr_busy = True

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
    try:
        # ЗАПОЛНЕНИЕ ПРИЛОЖЕНИЯ
        # Эффекты для кнопок: нажатие/проведение мышкой
        @staticmethod
        def _clamp_int(v: float, lo: int = 0, hi: int = 255) -> int:
            try:
                iv = int(round(float(v)))
            except Exception:
                iv = 0
            return max(lo, min(hi, iv))

        @classmethod
        def _hex_to_rgb(cls, color: str):
            if not isinstance(color, str):
                return None
            c = color.strip()
            if not c:
                return None
            if c.startswith("#"):
                c = c[1:]
            if len(c) != 6:
                return None
            try:
                r = int(c[0:2], 16)
                g = int(c[2:4], 16)
                b = int(c[4:6], 16)
                return (r, g, b)
            except Exception:
                return None

        @staticmethod
        def _rgb_to_hex(rgb) -> str:
            try:
                r, g, b = rgb
                return "#{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))
            except Exception:
                return "#000000"

        @classmethod
        def _mix_hex(cls, c1: str, c2: str, t: float) -> str:
            """Смешивает два hex-цвета: t=0 -> c1, t=1 -> c2."""
            a = cls._hex_to_rgb(c1)
            b = cls._hex_to_rgb(c2)
            if a is None or b is None:
                return c1
            t = max(0.0, min(1.0, float(t)))
            r = cls._clamp_int(a[0] + (b[0] - a[0]) * t)
            g = cls._clamp_int(a[1] + (b[1] - a[1]) * t)
            b2 = cls._clamp_int(a[2] + (b[2] - a[2]) * t)
            return cls._rgb_to_hex((r, g, b2))

        @classmethod
        def _shift_hex(cls, c: str, amount: float) -> str:
            """
            Осветляет или затемняет hex-цвет.
            amount > 0 -> светлее (к белому), amount < 0 -> темнее (к чёрному).
            """
            if cls._hex_to_rgb(c) is None:
                return c
            a = max(-1.0, min(1.0, float(amount)))
            if a >= 0:
                return cls._mix_hex(c, "#FFFFFF", a)
            return cls._mix_hex(c, "#000000", -a)

        @classmethod
        def _is_dark_hex(cls, c: str) -> bool:
            rgb = cls._hex_to_rgb(c)
            if rgb is None:
                return False
            r, g, b = rgb
            # Воспринимаемая яркость (приблизительно)
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            return lum < 140

        @classmethod
        def _contrast_text_for_bg(cls, bg: str, fallback: str) -> str:
            rgb = cls._hex_to_rgb(bg)
            if rgb is None:
                return fallback
            return (settings.THEMES.get("Светлая").BG if cls._is_dark_hex(bg) else settings.THEMES.get("Тёмная").BG) if hasattr(settings, "THEMES") else fallback

        @staticmethod
        def _is_descendant(widget, ancestor) -> bool:
            try:
                w = widget
                while w is not None:
                    if w == ancestor:
                        return True
                    w = w.master
            except Exception:
                pass
            return False

        def _pointer_inside(self, widget, x_root: int, y_root: int) -> bool:
            try:
                w = widget.winfo_containing(x_root, y_root)
                return self._is_descendant(w, widget)
            except Exception:
                return False


        def _rel_lum(self, c: str) -> float | None:
            """Относительная яркость для hex-цветов. Возвращает None, если цвет некорректен."""
            rgb = self._hex_to_rgb(c)
            if rgb is None:
                return None

            def _to_lin(v: int) -> float:
                x = v / 255.0
                return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

            r, g, b = rgb
            rl, gl, bl = _to_lin(r), _to_lin(g), _to_lin(b)
            return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl

        def _contrast_ratio(self, bg: str, fg: str) -> float | None:
            lb = self._rel_lum(bg)
            lf = self._rel_lum(fg)
            if lb is None or lf is None:
                return None
            L1, L2 = (lb, lf) if lb >= lf else (lf, lb)
            return (L1 + 0.05) / (L2 + 0.05)

        def _best_contrast(self, bg: str, c1: str, c2: str) -> str:
            """Выбирает между c1/c2 вариант с лучшим контрастом на bg. Используются только цвета темы."""
            r1 = self._contrast_ratio(bg, c1) or 0.0
            r2 = self._contrast_ratio(bg, c2) or 0.0
            return c1 if r1 >= r2 else c2

        def _btn_palette_for_theme(self, theme, kind: str = "secondary") -> dict:
            kind = (kind or "secondary").lower()

            accent = theme.ACCENT
            btn = theme.BTN
            hover_bg = theme.ACTIVE_BG

            # Возможные цвета текста: theme.FG и theme.BG
            def _text_for(bg_hex: str) -> str:
                return self._best_contrast(bg_hex, theme.FG, theme.BG)

            if kind in ("primary", "accent"):
                text = _text_for(accent)
                hover = self._mix_hex(accent, text, 0.12)
                pressed = self._mix_hex(accent, text, 0.22)
                return {"fg": accent, "hover": hover, "pressed": pressed, "text": text}

            # Вторичный / нейтральный
            text = _text_for(btn)
            hover = hover_bg
            try:
                same_hover = str(hover).strip().lower() == str(btn).strip().lower()
            except Exception:
                same_hover = False
            if same_hover:
                hover = self._mix_hex(btn, text, 0.10)
            pressed = self._mix_hex(hover, text, 0.18)
            return {"fg": btn, "hover": hover, "pressed": pressed, "text": text}

        def _btn_palette(self, kind: str = "secondary") -> dict:
            """Палитра для текущей темы (вычисляется из цветов темы в config.py)."""
            return self._btn_palette_for_theme(self.theme, kind)

        def _bind_ctk_button_recursively(self, btn: "ctk.CTkButton", sequence: str, func) -> None:
            """CTkButton состоит из внутренних виджетов. Биндим на все, чтобы press/release работали везде."""
            targets = [btn]
            for attr in ("_canvas", "_text_label", "_image_label"):
                try:
                    w = getattr(btn, attr, None)
                    if w is not None:
                        targets.append(w)
                except Exception:
                    pass
            try:
                for ch in btn.winfo_children():
                    if ch not in targets:
                        targets.append(ch)
            except Exception:
                pass

            for w in targets:
                try:
                    w.bind(sequence, func, add="+")
                except Exception:
                    pass

        def _apply_ctk_button_effects(self, btn: "ctk.CTkButton", kind: str = "secondary") -> None:
            """
            Единый стиль для CTkButton:
            - цвет наведения (встроенный)
            - эффект нажатия (mouse down/up)
            """
            pal = self._btn_palette(kind)
            try:
                btn.configure(
                    fg_color=pal["fg"],
                    hover_color=pal["hover"],
                    text_color=pal["text"],
                )
            except Exception:
                return

            normal = pal["fg"]
            hover = pal["hover"]
            pressed = pal["pressed"]

            def _is_disabled() -> bool:
                try:
                    return str(btn.cget("state")).lower() == "disabled"
                except Exception:
                    return False

            def on_press(event):
                if _is_disabled():
                    return
                try:
                    btn.configure(fg_color=pressed)
                except Exception:
                    pass

            def on_release(event):
                if _is_disabled():
                    return
                inside = self._pointer_inside(btn, getattr(event, "x_root", 0), getattr(event, "y_root", 0))
                try:
                    btn.configure(fg_color=(hover if inside else normal))
                except Exception:
                    pass

            def on_leave(event):
                if _is_disabled():
                    return
                try:
                    btn.configure(fg_color=normal)
                except Exception:
                    pass

            try:
                self._bind_ctk_button_recursively(btn, "<ButtonPress-1>", on_press)
                self._bind_ctk_button_recursively(btn, "<ButtonRelease-1>", on_release)
                self._bind_ctk_button_recursively(btn, "<Leave>", on_leave)
            except Exception:
                pass

            # Тень (тема-ориентированная, не влияет на макет)
            try:
                self._apply_ctk_button_shadow(btn, kind=kind)
            except Exception:
                pass

        def _apply_ctk_optionmenu_effects(self, menu: "ctk.CTkOptionMenu", kind: str = "secondary") -> None:
            """Эффект наведения/нажатия для CTkOptionMenu с учётом темы (например, Город / Настройки)."""
            base_fg = self.BTN
            base_btn = self.ACCENT
            text = self._best_contrast(base_fg, self.FG, self.BG)
            btn_text = self._best_contrast(base_btn, self.FG, self.BG)
            hover_btn = self._mix_hex(base_btn, btn_text, 0.12)
            pressed_btn = self._mix_hex(base_btn, btn_text, 0.22)

            try:
                menu.configure(
                    fg_color=base_fg,
                    button_color=base_btn,
                    button_hover_color=hover_btn,
                    text_color=text,
                    dropdown_fg_color=self.PANEL,
                    dropdown_hover_color=self.ACTIVE_BG,
                    dropdown_text_color=self.FG,
                )
            except Exception:
                return

            def _is_disabled() -> bool:
                try:
                    return str(menu.cget("state")).lower() == "disabled"
                except Exception:
                    return False

            def on_enter(_event):
                if _is_disabled():
                    return
                try:
                    menu.configure(button_color=hover_btn)
                except Exception:
                    pass

            def on_leave(_event):
                if _is_disabled():
                    return
                try:
                    menu.configure(button_color=base_btn)
                except Exception:
                    pass

            def on_press(_event):
                if _is_disabled():
                    return
                try:
                    menu.configure(button_color=pressed_btn)
                except Exception:
                    pass

            def on_release(event):
                if _is_disabled():
                    return
                inside = self._pointer_inside(menu, getattr(event, "x_root", 0), getattr(event, "y_root", 0))
                try:
                    menu.configure(button_color=(hover_btn if inside else base_btn))
                except Exception:
                    pass

            try:
                self._bind_ctk_button_recursively(menu, "<Enter>", on_enter)
                self._bind_ctk_button_recursively(menu, "<Leave>", on_leave)
                self._bind_ctk_button_recursively(menu, "<ButtonPress-1>", on_press)
                self._bind_ctk_button_recursively(menu, "<ButtonRelease-1>", on_release)
            except Exception:
                pass

        def _apply_ctk_slider_effects(self, slider: "ctk.CTkSlider") -> None:
            """Эффект наведения/нажатия для ползунка CTkSlider (например, Дети)."""
            base_fg = getattr(self.theme, "SLIDER_FG", None) or self.ACTIVE_BG
            base_progress = getattr(self.theme, "SLIDER_PROGRESS", None) or self.ACCENT
            base_button = getattr(self.theme, "SLIDER_BUTTON", None) or self.ACCENT
            btn_text = self._best_contrast(base_button, self.FG, self.BG)
            hover_button = self._mix_hex(base_button, btn_text, 0.12)
            pressed_button = self._mix_hex(base_button, btn_text, 0.22)
            try:
                slider.configure(
                    fg_color=base_fg,
                    progress_color=base_progress,
                    button_color=base_button,
                    button_hover_color=hover_button,
                )
            except Exception:
                return

            def on_enter(_event):
                try:
                    slider.configure(button_color=hover_button)
                except Exception:
                    pass

            def on_leave(_event):
                try:
                    slider.configure(button_color=base_button)
                except Exception:
                    pass

            def on_press(_event):
                try:
                    slider.configure(button_color=pressed_button)
                except Exception:
                    pass

            def on_release(event):
                inside = self._pointer_inside(slider, getattr(event, "x_root", 0), getattr(event, "y_root", 0))
                try:
                    slider.configure(button_color=(hover_button if inside else base_button))
                except Exception:
                    pass

            try:
                self._bind_ctk_button_recursively(slider, "<Enter>", on_enter)
                self._bind_ctk_button_recursively(slider, "<Leave>", on_leave)
                self._bind_ctk_button_recursively(slider, "<ButtonPress-1>", on_press)
                self._bind_ctk_button_recursively(slider, "<ButtonRelease-1>", on_release)
            except Exception:
                pass


        def _pointer_inside(self, widget, x_root: int, y_root: int) -> bool:
            try:
                w = widget.winfo_containing(x_root, y_root)
                return self._is_descendant(w, widget)
            except Exception:
                return False

        def mk_btn(self, parent, text: str, cmd, *, kind: str = "secondary", icon: str | None = None, icon_size: int = 18, **kwargs):
            """
            Фабрика для CTkButton с:
            - цветами с учётом темы (из тем config.py)
            - эффектом наведения и нажатия
            - необязательными PNG-иконками, загружаемыми из DATA/png

            Иконки используются только если явно переданы через icon=... .
            Автоматическое сопоставление unicode-символов не используется.
            """
            kw = dict(
                master=parent,
                text=text,
                command=cmd,
            )
            kw.update(kwargs)
            kw.setdefault("corner_radius", 10)
            kw.setdefault("height", 38)

            if icon and ("image" not in kw):
                icon_img = self._get_btn_icon(icon, size=icon_size)
                if icon_img is not None:
                    kw["image"] = icon_img
                    if text:
                        kw.setdefault("compound", "left")
                    else:
                        kw["text"] = ""

            btn = ctk.CTkButton(**kw)
            self._apply_ctk_button_effects(btn, kind=kind)
            return btn

        def mk_icon_btn(self, parent, cmd, *, icon: str, kind: str = "secondary", icon_size: int = 18, **kwargs):
            """Для кнопок с PNG-картинками."""
            kwargs.setdefault("width", 44)
            return self.mk_btn(
                parent,
                "",
                cmd,
                kind=kind,
                icon=icon,
                icon_size=icon_size,
                **kwargs,
            )


        def _icon_candidates(self, name: str) -> list[str]:
            name = (name or "").strip().lower()
            mapping = {
                "pause": ["pause-button.png", "pause.png"],
                "play": ["play-button.png", "play.png"],
                "stop": ["stop-button.png", "stop.png"],
                "calendar": ["calendar.png", "calendar(1).png"],
                "microphone": ["microphone.png", "mic.png"],
            }
            return mapping.get(name, [f"{name}.png"])

        def _get_btn_icon(self, name: str, *, size: int = 18):
            """Загружает и кэширует PNG-иконки из DATA/png. Рисование/генерация иконок не используется."""
            try:
                cache = getattr(self, "_td_icon_cache", None)
                if cache is None:
                    cache = {}
                    setattr(self, "_td_icon_cache", cache)
                key = (name, int(size))
                if key in cache:
                    return cache[key]
            except Exception:
                cache = None

            icon_dir = os.path.join(DATA, "png")
            path = None
            for fname in self._icon_candidates(name):
                fp = os.path.join(icon_dir, fname)
                if os.path.exists(fp):
                    path = fp
                    break

            if path is None:
                return None

            try:
                img = Image.open(path)
                if getattr(img, "mode", None) not in ("RGBA", "LA"):
                    img = img.convert("RGBA")
                icon = ctk.CTkImage(light_image=img, dark_image=img, size=(int(size), int(size)))
                if cache is not None:
                    try:
                        cache[key] = icon
                    except Exception:
                        pass
                return icon
            except Exception:
                return None

        def _apply_tk_button_effects(self, btn: "tk.Button", kind: str = "secondary") -> None:
            """Та же идея, что и для CTk-кнопок, но для классического tk.Button (используется в выборе даты)."""
            pal = self._btn_palette(kind)

            normal = pal["fg"]
            hover = pal["hover"]
            pressed = pal["pressed"]
            text = pal["text"]

            try:
                btn.configure(
                    bg=normal,
                    fg=text,
                    activebackground=hover,
                    activeforeground=text,
                    relief="flat",
                    highlightthickness=0,
                    bd=0,
                )
            except Exception:
                return

            def on_enter(_):
                try:
                    btn.configure(bg=hover)
                except Exception:
                    pass

            def on_leave(_):
                try:
                    btn.configure(bg=normal)
                except Exception:
                    pass

            def on_press(_):
                try:
                    btn.configure(bg=pressed)
                except Exception:
                    pass

            def on_release(event):
                inside = True
                try:
                    inside = (btn.winfo_containing(event.x_root, event.y_root) is not None)
                except Exception:
                    pass
                try:
                    btn.configure(bg=(hover if inside else normal))
                except Exception:
                    pass

            try:
                btn.bind("<Enter>", on_enter, add="+")
                btn.bind("<Leave>", on_leave, add="+")
                btn.bind("<ButtonPress-1>", on_press, add="+")
                btn.bind("<ButtonRelease-1>", on_release, add="+")
            except Exception:
                pass
            # Тень для классического tk.Button
            try:
                self._apply_tk_button_shadow(btn)
            except Exception:
                pass



        # Тень для кнопок + вспомогательные функции для видимости всплывающих окон

        @staticmethod
        def _tk_safe_color(c: str, fallback: str) -> str:
            """Виджеты Tk не поддерживают значение 'transparent'. Оставляем безопасные цвета для Linux/Windows."""
            try:
                if not isinstance(c, str):
                    return fallback
                s = c.strip()
                if not s:
                    return fallback
                if s.lower() == "transparent":
                    return fallback
                return s
            except Exception:
                return fallback

        def _shadow_base_color(self) -> str:
            """Подбирает мягкий цвет тени только из цветов темы (без магических констант)."""
            bg = self.BG
            if self._hex_to_rgb(bg) is None:
                bg = self.PANEL

            # Выбираем самую тёмную доступную поверхность темы как целевую для тени
            candidates = []
            for c in (self.BG, self.PANEL, self.BTN, self.ACTIVE_BG):
                if self._hex_to_rgb(c) is not None:
                    candidates.append(c)
            if not candidates:
                return bg

            def _lum(c):
                return self._rel_lum(c) if hasattr(self, "_rel_lum") else 0.0

            target = min(candidates, key=lambda c: (_lum(c) if _lum(c) is not None else 0.0))

            t = 0.55 if self._is_dark_hex(bg) else 0.22
            return self._mix_hex(bg, target, t)

        def _apply_ctk_button_shadow(self, btn: "ctk.CTkButton", kind: str = "secondary", *, offset=(2, 2)) -> None:
            """Добавляет тень за CTkButton без изменения его менеджера геометрии (pack/grid)."""
            try:
                sh = getattr(btn, "_td_shadow", None)
                if sh is not None and sh.winfo_exists():
                    try:
                        sh.configure(fg_color=self._shadow_base_color())
                    except Exception:
                        pass
                    return
            except Exception:
                pass

            parent = getattr(btn, "master", None)
            if parent is None:
                return

            try:
                radius = int(btn.cget("corner_radius"))
            except Exception:
                radius = 10

            shadow_color = self._shadow_base_color()
            try:
                sh = ctk.CTkFrame(parent, fg_color=shadow_color, corner_radius=radius)
            except Exception:
                return

            try:
                setattr(btn, "_td_shadow", sh)
            except Exception:
                pass

            dx, dy = offset

            def _sync(_evt=None):
                try:
                    if not btn.winfo_exists() or not sh.winfo_exists():
                        return
                except Exception:
                    return
                try:
                    if not btn.winfo_ismapped():
                        btn.after(20, _sync)
                        return
                except Exception:
                    pass
                try:
                    x, y = btn.winfo_x(), btn.winfo_y()
                    w, h = btn.winfo_width(), btn.winfo_height()
                    if w <= 1 or h <= 1:
                        btn.after(20, _sync)
                        return
                    sh.place(x=x + dx, y=y + dy, width=w, height=h)
                    try:
                        sh.lower(btn)
                    except Exception:
                        try:
                            sh.lower()
                        except Exception:
                            pass
                except Exception:
                    pass

            def _cleanup(_evt=None):
                try:
                    if sh.winfo_exists():
                        sh.destroy()
                except Exception:
                    pass

            try:
                btn.bind("<Configure>", _sync, add="+")
                btn.bind("<Map>", lambda e: btn.after(1, _sync), add="+")
                btn.bind("<Destroy>", _cleanup, add="+")
            except Exception:
                pass

            try:
                btn.after(1, _sync)
            except Exception:
                pass

        def _apply_tk_button_shadow(self, btn: "tk.Button", *, offset=(2, 2)) -> None:
            """Тень для классического tk.Button (используется в окнах выбора даты)."""
            try:
                sh = getattr(btn, "_td_shadow", None)
                if sh is not None and sh.winfo_exists():
                    try:
                        sh.configure(bg=self._shadow_base_color())
                    except Exception:
                        pass
                    return
            except Exception:
                pass

            parent = getattr(btn, "master", None)
            if parent is None:
                return

            shadow_color = self._shadow_base_color()
            try:
                sh = tk.Frame(parent, bg=shadow_color, highlightthickness=0, bd=0)
            except Exception:
                return

            try:
                setattr(btn, "_td_shadow", sh)
            except Exception:
                pass

            dx, dy = offset

            def _sync(_evt=None):
                try:
                    if not btn.winfo_exists() or not sh.winfo_exists():
                        return
                except Exception:
                    return
                try:
                    if not btn.winfo_ismapped():
                        btn.after(20, _sync)
                        return
                except Exception:
                    pass
                try:
                    x, y = btn.winfo_x(), btn.winfo_y()
                    w, h = btn.winfo_width(), btn.winfo_height()
                    if w <= 1 or h <= 1:
                        btn.after(20, _sync)
                        return
                    sh.place(x=x + dx, y=y + dy, width=w, height=h)
                    try:
                        sh.lower(btn)
                    except Exception:
                        try:
                            sh.lower()
                        except Exception:
                            pass
                except Exception:
                    pass

            def _cleanup(_evt=None):
                try:
                    if sh.winfo_exists():
                        sh.destroy()
                except Exception:
                    pass

            try:
                btn.bind("<Configure>", _sync, add="+")
                btn.bind("<Map>", lambda e: btn.after(1, _sync), add="+")
                btn.bind("<Destroy>", _cleanup, add="+")
            except Exception:
                pass

            try:
                btn.after(1, _sync)
            except Exception:
                pass

        def _popup_front(self, top: "tk.Toplevel") -> None:
            """В Linux/Ubuntu некоторые оконные менеджеры открывают диалоги позади главного окна."""
            try:
                top.transient(self)
            except Exception:
                pass
            try:
                top.lift()
                top.focus_force()
            except Exception:
                pass
            try:
                top.attributes("-topmost", True)
                top.after(180, lambda: top.attributes("-topmost", False))
            except Exception:
                pass


        def _is_signed_in(self) -> bool:
            try:
                return bool(self.auth.is_signed_in())
            except Exception:
                return False

        def _legacy_profile_path(self) -> str:
            return PROFILE_PATH

        def _legacy_diary_path(self) -> str:
            return DIARY_PATH

        def _require_signed_in(self, *, show_message: bool = True) -> bool:
            if self._is_signed_in():
                return True
            if show_message:
                messagebox.showinfo(
                    self.tr("auth.title", "Аккаунт"),
                    self.tr("auth.please_sign_in", "Войдите через страницу «Настройки» или меню «Файл»."),
                )
            return False

        def _load_legacy_plain_data(self):
            profile_data = load_json(self._legacy_profile_path(), {})
            diary_data = load_json(self._legacy_diary_path(), {})
            if not isinstance(profile_data, dict):
                profile_data = {}
            if not isinstance(diary_data, dict):
                diary_data = {}
            return profile_data, diary_data

        def _unique_backup_path(self, path: str) -> str:
            base = f"{path}.bak"
            if not os.path.exists(base):
                return base
            idx = 1
            while True:
                candidate = f"{path}.bak{idx}"
                if not os.path.exists(candidate):
                    return candidate
                idx += 1

        def _backup_legacy_plain_files(self) -> None:
            for path in (self._legacy_profile_path(), self._legacy_diary_path()):
                if os.path.exists(path):
                    try:
                        os.replace(path, self._unique_backup_path(path))
                    except Exception:
                        pass

        def _sync_session_state_after_sign_in(self, *, show_message: bool = True) -> None:
            self.profile = load_profile()
            self.diary = load_diary(default={})
            if not isinstance(self.profile, dict):
                self.profile = {}
            if not isinstance(self.diary, dict):
                self.diary = {}

            self._user_city = self.profile.get('Город')

            try:
                self.refresh_profile_ui()
            except Exception:
                pass

            if hasattr(self, "diary_view") and self.diary_view is not None:
                self.diary_view.diary = self.diary
                try:
                    self.diary_view.refresh_chart()
                except Exception:
                    pass

            try:
                self.renew_chat(clean_llm_history=False)
            except Exception:
                pass

            if hasattr(self, "llm_item") and self.llm_item is not None:
                try:
                    self.update_llm_profile()
                except Exception:
                    pass

            try:
                self.tk_renew_events()
            except Exception:
                pass

            self.create_menu()

            try:
                self.build_home()
            except Exception:
                pass
            try:
                self.build_options()
            except Exception:
                pass

            if show_message:
                messagebox.showinfo(
                    self.tr("auth.title", "Аккаунт"),
                    self.tr("auth.signed_in_as", "Вы вошли как: {username}", username=self.auth.current_user() or ""),
                )

        def _sync_session_state_after_sign_out(self, *, show_message: bool = True) -> None:
            self.profile = {}
            self.diary = {}
            self._user_city = None

            try:
                self.refresh_profile_ui()
            except Exception:
                pass

            if hasattr(self, "diary_view") and self.diary_view is not None:
                self.diary_view.diary = self.diary
                try:
                    self.diary_view.refresh_chart()
                except Exception:
                    pass

            try:
                self.renew_chat(clean_llm_history=True)
            except Exception:
                pass

            if hasattr(self, "llm_item") and self.llm_item is not None:
                try:
                    self.llm_item.update_profile({})
                    self.llm_item.clear_history()
                except Exception:
                    pass

            self.create_menu()

            try:
                self.build_home()
            except Exception:
                pass
            try:
                self.build_options()
            except Exception:
                pass

            if show_message:
                messagebox.showinfo(
                    self.tr("auth.title", "Аккаунт"),
                    self.tr("auth.signed_out", "Вы вышли из аккаунта."),
                )

        def _menu_sign_in(self):
            self._set_home_auth_mode("signin", focus=True)

        def _menu_sign_up(self):
            self._set_home_auth_mode("signup", focus=True)

        def _menu_sign_out(self):
            if not self._is_signed_in():
                return
            if messagebox.askyesno(
                self.tr("auth.title", "Аккаунт"),
                self.tr("auth.confirm_sign_out", "Выйти из текущего аккаунта?"),
            ):
                self.auth.sign_out()
                self._clear_auth_form(keep_username=True)
                self._sync_session_state_after_sign_out(show_message=self.opt_pop_msg_on.get())
                self.show_options()

        def _auth_menu_action(self):
            if self._is_signed_in():
                self._menu_sign_out()
            else:
                self._menu_sign_in()

        def _clear_auth_form(self, *, keep_username: bool = True) -> None:
            if not keep_username:
                self._auth_username_value = ""
            self._auth_password_value = ""
            self._auth_confirm_value = ""

            try:
                if self.auth_password_entry is not None:
                    self.auth_password_entry.delete(0, tk.END)
            except Exception:
                pass
            try:
                if self.auth_confirm_entry is not None:
                    self.auth_confirm_entry.delete(0, tk.END)
            except Exception:
                pass

        def _focus_auth_input(self) -> None:
            target = self.auth_username_entry or self.auth_password_entry
            try:
                if target is not None:
                    target.focus_set()
                    target.icursor("end")
            except Exception:
                pass

        def _set_home_auth_mode(self, mode: str = "signin", *, focus: bool = False) -> None:
            self._home_auth_mode = "signup" if mode == "signup" else "signin"
            try:
                self.build_options()
            except Exception:
                pass
            self.show_options()
            if focus:
                self.after(80, self._focus_auth_input)

        def _submit_home_auth(self, mode: str | None = None) -> bool:
            mode = (mode or self._home_auth_mode or "signin").strip().lower()
            is_signup = mode == "signup"
            title = self.tr("auth.title", "Аккаунт")

            username = self._auth_username_value
            password = self._auth_password_value
            confirm = self._auth_confirm_value

            try:
                if self.auth_username_entry is not None:
                    username = self.auth_username_entry.get().strip()
                if self.auth_password_entry is not None:
                    password = self.auth_password_entry.get()
                if self.auth_confirm_entry is not None:
                    confirm = self.auth_confirm_entry.get()
            except Exception:
                pass

            self._auth_username_value = username
            self._auth_password_value = password
            self._auth_confirm_value = confirm

            if not username:
                messagebox.showerror(title, self.tr("auth.username_empty", "Имя пользователя не может быть пустым."))
                self.after(50, self._focus_auth_input)
                return False
            if not password:
                messagebox.showerror(title, self.tr("auth.password_empty", "Пароль не может быть пустым."))
                try:
                    if self.auth_password_entry is not None:
                        self.auth_password_entry.focus_set()
                except Exception:
                    pass
                return False

            if not is_signup:
                try:
                    self.auth.sign_in(username, password)
                    self._clear_auth_form(keep_username=True)
                    self._sync_session_state_after_sign_in(show_message=self.opt_pop_msg_on.get())
                    if not self.profile:
                        self.show_profile()
                    else:
                        self.show_options()
                    return True
                except UserNotFound:
                    messagebox.showerror(title, self.tr("auth.user_not_found", "Пользователь не найден."))
                except InvalidCredentials:
                    messagebox.showerror(title, self.tr("auth.invalid_credentials", "Неверное имя пользователя или пароль."))
                except CryptoUnavailable as e:
                    messagebox.showerror(title, str(e))
                except Exception as e:
                    messagebox.showerror(title, f"{self.tr('auth.sign_in_failed', 'Не удалось войти')}: {e}")

                self._auth_password_value = ""
                self._auth_confirm_value = ""
                try:
                    if self.auth_password_entry is not None:
                        self.auth_password_entry.delete(0, tk.END)
                        self.auth_password_entry.focus_set()
                except Exception:
                    pass
                return False

            if password != confirm:
                messagebox.showerror(title, self.tr("auth.password_mismatch", "Пароли не совпадают."))
                try:
                    if self.auth_confirm_entry is not None:
                        self.auth_confirm_entry.focus_set()
                except Exception:
                    pass
                return False

            try:
                if self.auth.user_exists(username):
                    messagebox.showerror(title, self.tr("auth.user_exists", "Такой пользователь уже существует."))
                    try:
                        if self.auth_username_entry is not None:
                            self.auth_username_entry.focus_set()
                    except Exception:
                        pass
                    return False
            except Exception as e:
                messagebox.showerror(title, f"{self.tr('auth.storage_error', 'Storage error')}: {e}")
                return False

            migrate_plain = False
            try:
                if (not self.auth.has_any_user()) and self.auth.legacy_plaintext_exists(self._legacy_profile_path(), self._legacy_diary_path()):
                    migrate_plain = messagebox.askyesno(
                        title,
                        self.tr("auth.migrate_plaintext", "Найдены старые незашифрованные файлы профиля и дневника. Перенести их в новый зашифрованный аккаунт?"),
                    )
            except Exception:
                migrate_plain = False

            profile_data, diary_data = ({}, {})
            if migrate_plain:
                profile_data, diary_data = self._load_legacy_plain_data()

            try:
                self.auth.register_user(username, password, profile_data=profile_data, diary_data=diary_data)
                self.auth.sign_in(username, password)
                self._clear_auth_form(keep_username=True)
                self._sync_session_state_after_sign_in(show_message=self.opt_pop_msg_on.get())
                if migrate_plain:
                    self._backup_legacy_plain_files()
                if not self.profile:
                    self.show_profile()
                else:
                    self.show_options()
                return True
            except UserAlreadyExists:
                messagebox.showerror(title, self.tr("auth.user_exists", "Такой пользователь уже существует."))
            except CryptoUnavailable as e:
                messagebox.showerror(title, str(e))
            except Exception as e:
                messagebox.showerror(title, f"{self.tr('auth.create_failed', 'Не удалось создать пользователя')}: {e}")
            return False

        def _open_auth_dialog(self, *, allow_create: bool = True) -> bool:
            try:
                has_users = self.auth.has_any_user()
            except Exception:
                has_users = True
            target_mode = "signup" if allow_create and not has_users else "signin"
            self._set_home_auth_mode(target_mode, focus=True)
            return False

        def _startup_auth_flow(self) -> None:
            try:
                self._home_auth_mode = "signin" if self.auth.has_any_user() else "signup"
            except Exception:
                self._home_auth_mode = "signin"
    except:
        ...

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
            save_callback=lambda d: save_diary(d),
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
            save_callback=lambda d: save_diary(d),
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
        if not self._require_signed_in():
            return

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
        if not self._require_signed_in():
            return
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
        if not self._require_signed_in():
            return
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
            save_diary(self.diary)  # так же обновляем данные на диске

            # обновляем данные о дневнике во вкладке
            if hasattr(self, "diary_view") and self.diary_view is not None:
                self.diary_view.diary = self.diary
                self.diary_view.refresh_chart()

            messagebox.showinfo(self.tr("msg.ok_title","OK"), self.tr("msg.diary_imported","Дневник импортирован."))
            self.show_diary()
        except Exception as e:
            messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("dlg.import_diary_failed","Не удалось импортировать дневник:\n{e}", e=e))

    def import_diary(self):
        if not self._require_signed_in():
            return
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
            save_diary(self.diary)  # сохраняем в зашифрованное хранилище текущего пользователя

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

        if self._is_signed_in():
            file_menu.add_command(
                label=self.tr("menu.current_account", "Текущий аккаунт: {username}", username=self.auth.current_user() or ""),
                state="disabled",
            )
            file_menu.add_command(label=self.tr("menu.sign_out", "Выйти"), command=self._menu_sign_out)
        else:
            file_menu.add_command(label=self.tr("menu.sign_in", "Войти"), command=self._menu_sign_in)
            file_menu.add_command(label=self.tr("menu.sign_up", "Зарегистрироваться"), command=self._menu_sign_up)

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
            phrase = random.choice(self.content_store.get_support_phrases(self.lang_content) or support_phrases)
            self._home_quote = phrase
            try:
                self.quote_label.configure(text=phrase)
            except Exception:
                pass

        self.mk_btn(
            f,
            text=self.tr("home.main_button", settings.MAIN_BTN_TEXT),
            cmd=self.show_chat_and_get_answer,
            kind="primary",
            height=38,
        ).pack(pady=(8, 10))

        self.mk_btn(
            f,
            text=self.tr("home.new_phrase", "Новая фраза"),
            cmd=refresh_quote,
            kind="secondary",
            height=34,
        ).pack(pady=(0, 8))

        if self._is_signed_in():
            top_note = self.tr("auth.signed_in_as", "Вы вошли как: {username}", username=self.auth.current_user() or "")
        else:
            top_note = self.tr("auth.please_sign_in", "Сначала войдите через страницу «Настройки» или меню «Файл».")

        if True: #self.opt_add_labels.get():
            ctk.CTkLabel(
                f,
                text=top_note,
                wraplength=720,
                justify="center",
                font=(self.FONT_NAME, 12),
                text_color=self.LABEL_FG,
            ).pack(pady=(12, 14), padx=24)

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
        if not self._require_signed_in():
            return
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

        block1.grid_columnconfigure(0, weight=1, uniform="btns")
        block1.grid_columnconfigure(1, weight=1, uniform="btns")

        # Кнопки: единый стиль + эффекты (hover + pressed)

        self.send_btn  = self.mk_btn(block1, self.tr("buttons.send","Отправить"), self.send_message, kind="primary")
        self.clear_btn = self.mk_btn(block1, self.tr("buttons.clear","Очистить"), self.renew_chat, kind="secondary")
        # self.send_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        # self.clear_btn.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.send_btn.grid(row=0, column=0, sticky="ew", padx=4)
        self.clear_btn.grid(row=0, column=1, sticky="ew", padx=4)

        # Голосовой ввод (ASR)
        if self.lang_chat in ('ru', 'en'):
            block1.grid_columnconfigure(2, weight=1, uniform="btns")
            self.say_btn = self.mk_btn(block1, self.tr("buttons.say","Сказать"), lambda: self.asr_toggle(max_seconds=59, silence_seconds=3.0), kind="primary", icon="microphone")
            # self.say_btn.grid(row=1, column=2, sticky="ew", padx=(10, 0))
            # self.say_btn.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
            self.say_btn.grid(row=0, column=2, sticky="ew", padx=4)

        # 2й блок - контроль плеера
        block2 = ctk.CTkFrame(btn_area, fg_color="transparent")
        block2.pack(fill="x", pady=(10, 0))

        block2.grid_columnconfigure(0, weight=1, uniform="player")
        block2.grid_columnconfigure(1, weight=1, uniform="player")
        block2.grid_columnconfigure(2, weight=1, uniform="player")

        icon_font = (self.FONT_NAME, 18, "bold")

        self.pause_btn = self.mk_icon_btn(block2, self.player_pause, kind="primary", icon="pause", icon_size=18, font=icon_font, width=52)
        self.resume_btn = self.mk_icon_btn(block2, self.player_resume, kind="primary", icon="play", icon_size=18, font=icon_font, width=52)
        self.stop_btn = self.mk_icon_btn(block2, self.player_stop, kind="primary", icon="stop", icon_size=18, font=icon_font, width=52)

        for b in (self.pause_btn, self.resume_btn, self.stop_btn):
            try:
                b.configure(height=34)
            except Exception:
                pass

        self.pause_btn.grid(row=0, column=0, sticky="ew", padx=4)
        self.resume_btn.grid(row=0, column=1, sticky="ew", padx=4)
        self.stop_btn.grid(row=0, column=2, sticky="ew", padx=4)
        # Всплывающие подсказки
        try:
            Hovertip(self.clear_btn,  self.tr("tips.clear_chat","Очистка чата и истории общения."), hover_delay=500)
            Hovertip(self.say_btn, self.tr("tips.say","Нажмите, говорите. Нажмите ещё раз, чтобы остановить. Авто-стоп по тишине ~3 сек."), hover_delay=500)
            Hovertip(self.pause_btn,  self.tr("tips.pause","Приостановить воспроизведение"), hover_delay=500)
            Hovertip(self.resume_btn, self.tr("tips.resume","Продолжить воспроизведение"), hover_delay=500)
            Hovertip(self.stop_btn,   self.tr("tips.stop","Остановить. Продолжит воспроизведение только после нового ответа"), hover_delay=500)
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
        if not self._require_signed_in():
            return
        self.raise_frame("chat")
        self._chatbox_set_state("disabled")
        self.user_entry.focus_set()

    def show_chat_and_get_answer(self):
        if not self._require_signed_in():
            return
        self.raise_frame("chat")
        self._chatbox_set_state("disabled")
        self.user_entry.focus_set()
        delay_ms = 10
        self.after(delay_ms, lambda: self.send_message(default_msg=self.tr("home.main_button_text_to_chat", 'Дай мне совет')))


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
            self._apply_ctk_optionmenu_effects(self.city_menu, kind="secondary")
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

        pick_btn = self.mk_icon_btn(
            birth_row,
            self.open_birthdate_picker,
            kind="primary",
            icon="calendar",
            icon_size=18,
            width=44,
            height=34,
        )
        pick_btn.grid(row=0, column=1, padx=(10, 0))
        try:
            Hovertip(pick_btn, self.tr("tips.pick_date","Выбрать дату"), hover_delay=500)
        except Exception:
            pass
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
        try:
            self._apply_ctk_slider_effects(self.children_slider)
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

        self.mk_btn(
            content,
            text=self.tr("profile.save_button","Сохранить профиль"),
            cmd=self.save_profile_data,
            kind="primary",
            height=38,
        ).pack(pady=(14, 18))


    def open_birthdate_picker_0(self):
        top = tk.Toplevel(self)
        top.title("Выбор даты рождения")
        # безопасные цвета для Tk + показываем окно поверх (Linux/Ubuntu)
        bg = self._tk_safe_color(self.BG, self.BG)
        if self._hex_to_rgb(bg) is None:
            bg = self._tk_safe_color(self.PANEL, self.PANEL)
        top.configure(bg=bg)
        top.resizable(False, False)
        self._popup_front(top)
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

        # цвета для Tk (на Linux некоторые темы не любят 'transparent')
        fg = self._tk_safe_color(self.FG, self.FG)
        btn_bg = self._tk_safe_color(self.BTN, self.BTN)
        insert_fg = fg

        tk.Label(top, text="Год:", fg=fg, bg=bg).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Label(top, text="Месяц:", fg=fg, bg=bg).grid(row=1, column=0, padx=10, pady=10, sticky="e")
        tk.Label(top, text="День:", fg=fg, bg=bg).grid(row=2, column=0, padx=10, pady=10, sticky="e")

        year_var = tk.IntVar(value=y)
        month_var = tk.IntVar(value=m)
        day_var = tk.IntVar(value=d)

        tk.Spinbox(top, from_=year_min, to=year_max, textvariable=year_var, width=8,
                   bg=btn_bg, fg=fg, insertbackground=insert_fg, relief="flat")\
            .grid(row=0, column=1, padx=10, pady=10, sticky="w")

        tk.Spinbox(top, from_=1, to=12, textvariable=month_var, width=8,
                   bg=btn_bg, fg=fg, insertbackground=insert_fg, relief="flat")\
            .grid(row=1, column=1, padx=10, pady=10, sticky="w")

        tk.Spinbox(top, from_=1, to=31, textvariable=day_var, width=8,
                   bg=btn_bg, fg=fg, insertbackground=insert_fg, relief="flat")\
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

        btns = tk.Frame(top, bg=bg)
        btns.grid(row=3, column=0, columnspan=2, pady=(5, 12))

        ok_btn = tk.Button(btns, text=self.tr("buttons.ok","OK"), command=set_date, padx=14, pady=6)
        self._apply_tk_button_effects(ok_btn, kind="primary")
        ok_btn.pack(side="left", padx=8)

        cancel_btn = tk.Button(btns, text=self.tr("buttons.cancel","Отмена"), command=top.destroy, padx=14, pady=6)
        self._apply_tk_button_effects(cancel_btn, kind="secondary")
        cancel_btn.pack(side="left", padx=8)

    def open_birthdate_picker(self, title="Выбор даты", year_min=1900, year_max_shift=10, check_more_then_today=True, current=None, callback=None):
        top = tk.Toplevel(self)
        top.title(title)
        # безопасные цвета для Tk + показываем окно поверх (Linux/Ubuntu)
        bg = self._tk_safe_color(self.BG, self.BG)
        if self._hex_to_rgb(bg) is None:
            bg = self._tk_safe_color(self.PANEL, self.PANEL)
        top.configure(bg=bg)
        top.resizable(False, False)
        self._popup_front(top)
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

        # цвета для Tk (на Linux некоторые темы не любят 'transparent')
        fg = self._tk_safe_color(self.FG, self.FG)
        btn_bg = self._tk_safe_color(self.BTN, self.BTN)
        insert_fg = fg

        tk.Label(top, text=self.tr("diary.pick_year","Год:"), fg=fg, bg=bg).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Label(top, text=self.tr("diary.pick_month","Месяц:"), fg=fg, bg=bg).grid(row=1, column=0, padx=10, pady=10, sticky="e")
        tk.Label(top, text=self.tr("diary.pick_day","День:"), fg=fg, bg=bg).grid(row=2, column=0, padx=10, pady=10, sticky="e")

        year_var = tk.IntVar(value=y)
        month_var = tk.IntVar(value=m)
        day_var = tk.IntVar(value=d)

        tk.Spinbox(top, from_=year_min, to=year_max, textvariable=year_var, width=8,
                   bg=btn_bg, fg=fg, insertbackground=insert_fg, relief="flat")\
            .grid(row=0, column=1, padx=10, pady=10, sticky="w")

        tk.Spinbox(top, from_=1, to=12, textvariable=month_var, width=8,
                   bg=btn_bg, fg=fg, insertbackground=insert_fg, relief="flat")\
            .grid(row=1, column=1, padx=10, pady=10, sticky="w")

        tk.Spinbox(top, from_=1, to=31, textvariable=day_var, width=8,
                   bg=btn_bg, fg=fg, insertbackground=insert_fg, relief="flat")\
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

        btns = tk.Frame(top, bg=bg)
        btns.grid(row=3, column=0, columnspan=2, pady=(5, 12))

        ok_btn = tk.Button(btns, text=self.tr("buttons.ok","OK"), command=set_date, padx=14, pady=6)
        self._apply_tk_button_effects(ok_btn, kind="primary")
        ok_btn.pack(side="left", padx=8)

        cancel_btn = tk.Button(btns, text=self.tr("buttons.cancel","Отмена"), command=top.destroy, padx=14, pady=6)
        self._apply_tk_button_effects(cancel_btn, kind="secondary")
        cancel_btn.pack(side="left", padx=8)

    def save_profile_data(self):
        if not self._require_signed_in():
            return
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
            self.opt_use_asr_var
            if self.opt_pop_msg_on.get():
                messagebox.showinfo(self.tr("msg.saved_title","Сохранено"), self.tr("msg.profile_saved","Профиль сохранён."))
            self.show_home()
        else:
            messagebox.showerror(self.tr("msg.error_title","Ошибка"), self.tr("msg.profile_save_failed","Не удалось сохранить профиль."))

    def show_profile(self):
        if not self._require_signed_in():
            return
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
        self.opt_pop_msg_on.set(value=bool(getattr(opt, "POP_MSG_ON", False)))
        self.opt_add_labels.set(value=bool(getattr(opt, "ADD_LABELS", False)))
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

        if True: #self.opt_add_labels.get():
            ctk.CTkLabel(
                f,
                text=self.tr("options.title", "Настройки"),
                font=(self.FONT_NAME, 18, "bold"),
                text_color=self.FG,
            ).pack(pady=(16, 8))
        else:
            ctk.CTkLabel(
                f,
                text="",
                font=(self.FONT_NAME, 1, "bold"),
                text_color=self.FG,
            ).pack(pady=(1, 1))

        # делаем страницу настроек полностью scrollable
        _, content = self.make_scrollable(f)

        self._build_auth_settings_panel(content)

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
        self.opt_pop_msg_on = tk.BooleanVar()
        # self.opt_add_labels = tk.BooleanVar()
        self.opt_theme_var = tk.StringVar()
        self.opt_voice_var = tk.StringVar()
        self.opt_lang_ui_var = tk.StringVar()
        self.opt_lang_chat_var = tk.StringVar()
        self.opt_lang_content_var = tk.StringVar()
        self.load_option_from_config(theme_keys, voice_keys)

        form = ctk.CTkFrame(content, fg_color="transparent")
        form.pack(padx=20, pady=(0, 10), fill="x")
        form.grid_columnconfigure(0, weight=0)
        form.grid_columnconfigure(1, weight=1)

        def label(row, text):
            ctk.CTkLabel(form, text=text + ":", text_color=self.FG, anchor="w").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=8)

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
            self._apply_ctk_optionmenu_effects(self.opt_theme_menu, kind="secondary")
        except Exception:
            pass
        self.opt_theme_menu.grid(row=1, column=1, sticky="w", pady=8)

        label(2, self.tr("options.voice", "Голос чата"))
        self.opt_voice_menu = ctk.CTkOptionMenu(form, values=list(voice_display_values), variable=self.opt_voice_var)
        try:
            self._apply_ctk_optionmenu_effects(self.opt_voice_menu, kind="secondary")
        except Exception:
            pass
        self.opt_voice_menu.grid(row=2, column=1, sticky="w", pady=8)

        label(3, self.tr("options.lang_ui", "Язык интерфейса"))
        self.opt_lang_ui_menu = ctk.CTkOptionMenu(form, values=list(lang_display_values), variable=self.opt_lang_ui_var)
        try:
            self._apply_ctk_optionmenu_effects(self.opt_lang_ui_menu, kind="secondary")
        except Exception:
            pass
        self.opt_lang_ui_menu.grid(row=3, column=1, sticky="w", pady=8)

        label(4, self.tr("options.lang_chat", "Язык ответов (LLM)"))
        self.opt_lang_chat_menu = ctk.CTkOptionMenu(form, values=list(lang_display_values), variable=self.opt_lang_chat_var)
        try:
            self._apply_ctk_optionmenu_effects(self.opt_lang_chat_menu, kind="secondary")
            self.opt_lang_chat_menu.configure(state="disabled")
        except Exception:
            pass
        self.opt_lang_chat_menu.grid(row=4, column=1, sticky="w", pady=8)

        label(5, self.tr("options.lang_content", "Язык контента"))
        self.opt_lang_content_menu = ctk.CTkOptionMenu(form, values=list(lang_display_values), variable=self.opt_lang_content_var)
        try:
            self._apply_ctk_optionmenu_effects(self.opt_lang_content_menu, kind="secondary")
            self.opt_lang_content_menu.configure(state="disabled")
        except Exception:
            pass
        self.opt_lang_content_menu.grid(row=5, column=1, sticky="w", pady=8)

        btns = ctk.CTkFrame(content, fg_color="transparent")
        btns.pack(pady=(10, 6))

        self.mk_btn(
            btns,
            text=self.tr("buttons.apply", "Применить"),
            cmd=self.save_options_data,
            kind="primary",
            height=38,
            width=160,
        ).pack(side="left", padx=10)

        self.mk_btn(
            btns,
            text=self.tr("buttons.reset", "Вернуть"),
            cmd=self.load_option_from_config,
            kind="secondary",
            height=38,
            width=140,
        ).pack(side="left", padx=10)

        ctk.CTkLabel(
            content,
            text=self.tr("options.hint", "Изменения применяются сразу после нажатия «Применить»."),
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
            if self.opt_pop_msg_on.get():
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


    def _build_auth_settings_panel(self, parent):
        self.auth_username_entry = None
        self.auth_password_entry = None
        self.auth_confirm_entry = None

        auth_wrap = ctk.CTkFrame(parent, fg_color=self.BG, corner_radius=0)
        auth_wrap.pack(padx=20, pady=(4, 8), fill="x")


        if self._is_signed_in():
            ctk.CTkLabel(
                auth_wrap,
                text=self.tr("auth.panel_title", "Аккаунт"),
                font=(self.FONT_NAME, 16, "bold"),
                text_color=self.FG,
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=4, pady=(0, 8))

            ctk.CTkLabel(
                auth_wrap,
                text=self.tr("auth.signed_in_as", "Вы вошли как: {username}", username=self.auth.current_user() or ""),
                font=(self.FONT_NAME, self.FONT_SIZE),
                text_color=self.FG,
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=4, pady=(0, 6))

            ctk.CTkLabel(
                auth_wrap,
                text=self.tr("auth.encrypted_storage_active", "Для текущего аккаунта включено зашифрованное хранение данных."),
                font=(self.FONT_NAME, 11),
                text_color=self.LABEL_FG,
                anchor="w",
                justify="left",
                wraplength=760,
            ).pack(fill="x", padx=4, pady=(0, 12))

            btns = ctk.CTkFrame(auth_wrap, fg_color="transparent")
            btns.pack(fill="x", padx=0, pady=(0, 2))
            btns.grid_columnconfigure(0, weight=1, uniform="auth")
            btns.grid_columnconfigure(1, weight=1, uniform="auth")

            self.mk_btn(
                btns,
                text=self.tr("menu.profile", "Профиль"),
                cmd=self.show_profile,
                kind="secondary",
                height=36,
            ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
            self.mk_btn(
                btns,
                text=self.tr("menu.sign_out", "Выйти"),
                cmd=self._menu_sign_out,
                kind="primary",
                height=36,
            ).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        else:
            header = ctk.CTkFrame(auth_wrap, fg_color="transparent")
            header.pack(fill="x", padx=0, pady=(0, 8))
            header.grid_columnconfigure(0, weight=1)
            header.grid_columnconfigure(1, weight=0)
            header.grid_columnconfigure(2, weight=0)

            ctk.CTkLabel(
                header,
                text=self.tr("auth.panel_title", "Аккаунт"),
                font=(self.FONT_NAME, 16, "bold"),
                text_color=self.FG,
            ).grid(row=0, column=0, sticky="w", padx=(0, 8))

            self.mk_btn(
                header,
                text=self.tr("menu.sign_in", "Войти"),
                cmd=lambda: self._set_home_auth_mode("signin", focus=True),
                kind="primary" if self._home_auth_mode != "signup" else "secondary",
                height=30,
                width=110,
            ).grid(row=0, column=1, padx=4, sticky="e")

            self.mk_btn(
                header,
                text=self.tr("menu.sign_up", "Зарегистрироваться"),
                cmd=lambda: self._set_home_auth_mode("signup", focus=True),
                kind="primary" if self._home_auth_mode == "signup" else "secondary",
                height=30,
                width=110,
            ).grid(row=0, column=2, padx=(4, 0), sticky="e")

            body = ctk.CTkFrame(auth_wrap, fg_color="transparent")
            body.pack(fill="x", padx=0, pady=(0, 0))
            body.grid_columnconfigure(0, weight=1)

            mode_is_signup = self._home_auth_mode == "signup"
            action_label = self.tr("menu.sign_up", "Зарегистрироваться") if mode_is_signup else self.tr("menu.sign_in", "Войти")

            ctk.CTkLabel(
                body,
                text=self.tr("auth.username_label", "Имя пользователя"),
                text_color=self.FG,
                anchor="w",
            ).grid(row=0, column=0, sticky="w", pady=(0, 4))
            self.auth_username_entry = ctk.CTkEntry(
                body,
                height=36,
                fg_color=self.BTN,
                text_color=self.FG,
                corner_radius=10,
                placeholder_text=self.tr("auth.username_placeholder", "Введите имя пользователя"),
            )
            self.auth_username_entry.grid(row=1, column=0, sticky="ew", pady=(0, 10))
            if self._auth_username_value:
                try:
                    self.auth_username_entry.insert(0, self._auth_username_value)
                except Exception:
                    pass

            ctk.CTkLabel(
                body,
                text=self.tr("auth.password_label", "Пароль"),
                text_color=self.FG,
                anchor="w",
            ).grid(row=2, column=0, sticky="w", pady=(0, 4))
            self.auth_password_entry = ctk.CTkEntry(
                body,
                height=36,
                fg_color=self.BTN,
                text_color=self.FG,
                corner_radius=10,
                placeholder_text=self.tr("auth.password_placeholder", "Введите пароль"),
                show="*",
            )
            self.auth_password_entry.grid(row=3, column=0, sticky="ew", pady=(0, 10))

            submit_row = 4
            if mode_is_signup:
                ctk.CTkLabel(
                    body,
                    text=self.tr("auth.confirm_password_label", "Подтвердите пароль"),
                    text_color=self.FG,
                    anchor="w",
                ).grid(row=4, column=0, sticky="w", pady=(0, 4))
                self.auth_confirm_entry = ctk.CTkEntry(
                    body,
                    height=36,
                    fg_color=self.BTN,
                    text_color=self.FG,
                    corner_radius=10,
                    placeholder_text=self.tr("auth.confirm_password_placeholder", "Повторите пароль"),
                    show="*",
                )
                self.auth_confirm_entry.grid(row=5, column=0, sticky="ew", pady=(0, 10))
                submit_row = 6

            self.auth_username_entry.bind("<Return>", lambda e: self.auth_password_entry.focus_set() if self.auth_password_entry is not None else self._submit_home_auth())
            self.auth_password_entry.bind("<Return>", lambda e: self._submit_home_auth())
            if self.auth_confirm_entry is not None:
                self.auth_confirm_entry.bind("<Return>", lambda e: self._submit_home_auth())

            self.mk_btn(
                body,
                text=action_label,
                cmd=self._submit_home_auth,
                kind="primary",
                height=36,
            ).grid(row=submit_row, column=0, sticky="ew", pady=(2, 8))

            hint_parts = [self.tr("auth.inline_hint", "Профиль и дневник хранятся в отдельных зашифрованных файлах для каждого аккаунта.")]
            try:
                if (not self.auth.has_any_user()) and self.auth.legacy_plaintext_exists(self._legacy_profile_path(), self._legacy_diary_path()):
                    hint_parts.append(self.tr("auth.legacy_found_hint", "Найдены старые незашифрованные данные. Создайте первый аккаунт, чтобы перенести их в зашифрованное хранилище."))
            except Exception:
                pass

            if self.opt_add_labels.get():
                ctk.CTkLabel(
                    body,
                    text="\n".join(hint_parts),
                    font=(self.FONT_NAME, 11),
                    text_color=self.LABEL_FG,
                    wraplength=760,
                    justify="left",
                    anchor="w",
                ).grid(row=submit_row + 1, column=0, sticky="w", pady=(0, 2))

            self.after(80, self._focus_auth_input)

        divider_color = getattr(self.theme, "BORDER", None) or self.ACTIVE_BG or self.PANEL
        divider = ctk.CTkFrame(parent, fg_color=divider_color, corner_radius=0, height=1)
        divider.pack(padx=20, pady=(2, 12), fill="x")




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
