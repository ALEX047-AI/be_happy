from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field

import json
import os


class Theme(BaseModel):
    BG: str
    ACTIVE_BG: str
    FG: str
    LABEL_FG: str
    BTN: str
    ACCENT: str
    PANEL: str
    FONT_SIZE: int = 14
    FONT_NAME: str = "Arial"

# список городов (должен совпадать с build_profile)
city_list = ["Москва", "Оренбург","Новосибирск","Екатеринбург","Красноярск","Нижний Новгород","Челябинск","Уфа","Краснодар","Самара","Ростов-на-Дону","Омск","Воронеж","Пермь","Волгоград"]

TTS_VOICES = {
    "Наталья": {
        "id": "Nec_24000",
        "ssml": "",
        "sample": "",
        "languages": []
    },
    "Марфа": {
        "id": "May_24000",
        "ssml": "",
        "sample": "",
        "languages": []
    },
}


class Settings(BaseSettings):

    class AppOptions(BaseModel):
        # USE_ASR: bool = True  # Озвучивать ответ ЛЛМ
        USE_TTS: bool = True  # Озвучивать ответ ЛЛМ        
        TTS_VOICE: str = "Марфа"  # Голос ЛЛМ - словарь # TTS_VOICES
        THEME: str = "white"  # 'black' # выбор только Темная и Светлая
        # LANGUAGE = 'russian'
        # CHAT_LANGUAGE = 'russian'
    TTS_VOICE_DEFAULT:str = "Марфа"
    TTS_VOICE_DEFAULT_ID:str = "May_24000"

    DEBUG: bool = False
    LLM_DEBUG: bool = True

    USE_SPEECH: bool = True #Не используется -> USE_TTS
    SALUTE_TOKEN: str = ""
    SALUTE_TOKEN_URL: str = ""
    SALUTE_RqUID: str = ""
    SALUTE_SYNTHESIZE_URL: str = ""
    SALUTE_RECOGNIZE_URL: str = ""

    MODEL_SOURCE: str = 'openrouter'  # mistral | openrouter

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = ""

    OPENROUTER_MODEL: str = 'google/gemma-3-27b-it:free'
    #   model="mistralai/mistral-7b-instruct:free"
    #   model="mistralai/mistral-small-3.2-24b-instruct:free"

    MISTRAL_API_KEY: str
    MISTRAL_BASE_URL: str
    MISTRAL_MODEL: str = 'mistral-large-latest'
    # MISTRAL_MODEL: str = 'open-mistral-7b'
    #   model_name="mistral-large-latest"

    USE_LLM: bool = True
    USE_STREAM: bool = True
    LLM_TRIMMER_MAX_TOKENS: int = 6

    TD_CHAT_PREFIX: str = 'TD: '
    USER_CHAT_PREFIX: str = 'Вы: '

    DATA: str = "data"
    profile_file_name: str = "user_profile.json"
    diary_file_name: str = "diary.json"

    # сохранение в json
    app_options_file_name: str = "app_options.json"

    # загружаемые/сохраняемые опции приложения
    app_options: AppOptions = Field(default_factory=AppOptions)

    # максимальное количество документов, получаемых от retriever
    retriever_docs_number: int = 2

    # tkinter конфигурация
    TITLE: str = "TD — Treatment of Depression"
    GEOMETRY: str = "900x800"
    MAIN_BTN_TEXT: str = "Быстрый совет"
    MAIN_LABEL_TEXT: str = ("Это образовательное приложение. Если Вам нужна экстренная помощь —\n"
                           "пожалуйста, обратитесь в местные службы поддержки или к близким.")
    MAIN_SLOGAN: str = "Ты не один"
    CHAT_INTRO_TEXT: str = "Привет. Я могу выслушать Вас. Что сейчас на душе?\n"
    # FONT_NAME: str = "Arial"
    # FONT_SIZE: int = 14

    # ТЕМА

    """BG: str = "#101010"
    ACTIVE_BG" = "#2a2a2a",
    FG: str = "#EAEAEA"
    LABEL_FG = "#bbbbbb"
    BTN: str = "#202020"
    ACCENT: str = "#3A7AFE"
    PANEL: str = "#151515" """

    THEMES_DEFAULT: str = 'black'
    THEMES: dict[str, Theme] = {
        "black": Theme(
            BG="#101010",
            ACTIVE_BG="#2a2a2a",
            FG="#EAEAEA",
            LABEL_FG="#bbbbbb",
            BTN="#202020",
            ACCENT="#3A7AFE",
            PANEL="#151515",
            FONT_SIZE=14,
            FONT_NAME="Arial"
        ),
        "white": Theme(
            BG="#f4f4f4",
            ACTIVE_BG="#e6e6e6",
            FG="#111111",
            LABEL_FG="#333333",
            BTN="#ffffff",
            ACCENT="#2b6cff",
            PANEL="#ffffff",
            FONT_SIZE=14,
            FONT_NAME="Arial"
        ),
    }

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
    )

    @property
    def tts_voice(self):
        try:
            voice_name = self.app_options.TTS_VOICE
        except Exception as e:
            voice_name = self.TTS_VOICE_DEFAULT
        try:
            voice_data = TTS_VOICES.get(voice_name, {})
            voice_id = voice_data.get('id', self.TTS_VOICE_DEFAULT_ID)
        except Exception as e:
            voice_id = self.TTS_VOICE_DEFAULT_ID

        return voice_id


    def app_options_path(self) -> str:
        return os.path.join(self.DATA, self.app_options_file_name)

    def load_app_options(self) -> AppOptions:
        os.makedirs(self.DATA, exist_ok=True)
        path = self.app_options_path()

        # создать файл если его нет
        if not os.path.exists(path):
            self.save_app_options(self.app_options)
            return self.app_options

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f) or {}

            # формируем из json
            opt = self.AppOptions(**raw)

            # проверки
            if opt.TTS_VOICE not in TTS_VOICES:
                opt.TTS_VOICE = "Наталья" if "Наталья" in TTS_VOICES else next(iter(TTS_VOICES.keys()), "")
            if opt.THEME not in self.THEMES:
                opt.THEME = "white" if "white" in self.THEMES else self.THEMES_DEFAULT

            self.app_options = opt

        except Exception:
            # если json сломан --> настройки оставляем
            self.app_options = self.AppOptions()
            self.save_app_options(self.app_options)

        return self.app_options

    def save_app_options(self, options: AppOptions | None = None) -> bool:
        os.makedirs(self.DATA, exist_ok=True)
        path = self.app_options_path()

        try:
            opt = options or self.app_options
            with open(path, "w", encoding="utf-8") as f:
                json.dump(opt.model_dump(), f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False


settings = Settings()

# загружаем сохранёные пользователем опции
settings.load_app_options()
