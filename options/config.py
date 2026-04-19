from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field
from zoneinfo import ZoneInfo

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

    # Дополнительное оформление графиков Matplotlib (Дневник)
    CHART_BG: str | None = None          # Figure фон
    CHART_AX_BG: str | None = None       # Axes фон
    CHART_FG: str | None = None          # Текст ticks spines
    CHART_GRID: str | None = None        # Цвет грида
    CHART_LINE: str | None = None        # Цвет основной линии
    CHART_SELECTED: str | None = None    # Цвет точек выбранного дня.

    # Слайдеры и Переключатели
    SWITCH_FG: str | None = None
    SWITCH_PROGRESS: str | None = None
    SWITCH_BUTTON: str | None = None

    SLIDER_FG: str | None = None
    SLIDER_PROGRESS: str | None = None
    SLIDER_BUTTON: str | None = None

# список городов (должен совпадать с build_profile)
city_list = ["Москва", "Санкт-Петербург", "Оренбург",
             'Абакан', 'Альметьевск', 'Ангарск', 'Арзамас', 'Армавир', 'Артём', 'Архангельск', 'Астрахань', 'Балаково', 'Балашиха', 'Барнаул', 'Батайск', 'Белгород', 'Бердск', 'Березники', 'Бийск', 'Благовещенск', 'Братск', 'Брянск', 'Великий Новгород', 'Видное', 'Владивосток', 'Владикавказ', 'Владимир', 'Волгоград', 'Волгодонск', 'Волжский', 'Вологда', 'Воронеж', 'Грозный', 'Дербент', 'Дзержинск', 'Димитровград', 'Долгопрудный', 'Домодедово', 'Евпатория', 'Екатеринбург', 'Ессентуки', 'Жуковский', 'Златоуст', 'Иваново', 'Ижевск', 'Иркутск', 'Йошкар-Ола', 'Казань', 'Калининград', 'Калуга', 'Каменск-Уральский', 'Камышин', 'Каспийск', 'Кемерово', 'Керчь', 'Киров', 'Кисловодск', 'Ковров', 'Коломна', 'Комсомольск-на-Амуре', 'Копейск', 'Королёв', 'Кострома', 'Красногорск', 'Краснодар', 'Красноярск', 'Курган', 'Курск', 'Кызыл', 'Липецк', 'Люберцы', 'Магнитогорск', 'Майкоп', 'Махачкала', 'Миасс', 'Михайловск', 'Мурино', 'Мурманск', 'Муром', 'Мытищи', 'Набережные Челны', 'Назрань', 'Нальчик', 'Находка', 'Невинномысск', 'Нефтекамск', 'Нефтеюганск', 'Нижневартовск', 'Нижнекамск', 'Нижний Новгород', 'Нижний Тагил', 'Новокузнецк', 'Новомосковск', 'Новороссийск', 'Новосибирск', 'Новочебоксарск', 'Новочеркасск', 'Новошахтинск', 'Новый Уренгой', 'Ногинск', 'Норильск', 'Ноябрьск', 'Обнинск', 'Одинцово', 'Октябрьский', 'Омск', 'Орехово-Зуево', 'Орск', 'Орёл', 'Пенза', 'Первоуральск', 'Пермь', 'Петрозаводск', 'Петропавловск-Камчатский', 'Подольск', 'Прокопьевск', 'Псков', 'Пушкино', 'Пятигорск', 'Раменское', 'Реутов', 'Ростов-на-Дону', 'Рубцовск', 'Рыбинск', 'Рязань', 'Салават', 'Самара', 'Саранск', 'Саратов', 'Севастополь', 'Северодвинск', 'Северск', 'Серпухов', 'Симферополь', 'Смоленск', 'Сочи', 'Ставрополь', 'Старый Оскол', 'Стерлитамак', 'Сургут', 'Сызрань', 'Сыктывкар', 'Таганрог', 'Тамбов', 'Тверь', 'Тольятти', 'Томск', 'Тула', 'Тюмень', 'Улан-Удэ', 'Ульяновск', 'Уссурийск', 'Уфа', 'Хабаровск', 'Ханты-Мансийск', 'Хасавюрт', 'Химки', 'Чебоксары', 'Челябинск', 'Череповец', 'Черкесск', 'Чита', 'Шахты', 'Щёлково', 'Электросталь', 'Элиста', 'Энгельс', 'Южно-Сахалинск', 'Якутск', 'Ярославль']

TTS_VOICES = {
    "Марфа": {
        "id": "May_24000",
        "gender": "female",
        "ssml": "",
        "sample": "",
        "languages": ["ru"]
    },
    "Наталья": {
        "id": "Nec_24000",
        "gender": "female",
        "ssml": "",
        "sample": "",
        "languages": ["ru"]
    },
    "Александра": {
        "id": "Ost_24000",
        "gender": "female",
        "ssml": "",
        "sample": "",
        "languages": ["ru"]
    },

    "Борис": {
        "id": "Bys_24000",
        "gender": "male",
        "ssml": "",
        "sample": "",
        "languages": ["ru"]
    },
    "Тарас": {
        "id": "Tur_24000",
        "gender": "male",
        "ssml": "",
        "sample": "",
        "languages": ["ru"]
    },
    "Сергей": {
        "id": "Pon_24000",
        "gender": "male",
        "ssml": "",
        "sample": "",
        "languages": ["ru"]
    },
    "Кира": {
        "id": "Kin_24000",
        "gender": "female",
        "ssml": "",
        "sample": "",
        "languages": ["en"]
    },
}


class Settings(BaseSettings):

    class AppOptions(BaseModel):
        # USE_ASR: bool = True  # Озвучивать ответ ЛЛМ
        USE_TTS: bool = True  # Озвучивать ответ ЛЛМ
        TTS_VOICE: str = "Марфа"  # Голос ЛЛМ - словарь # TTS_VOICES
        THEME: str = "Тёмная"  # 'Тёмная' # выбор только Темная и Светлая
        LANG_UI: str = "ru"  # Код языка интерфейса: ru|en|it|de
        LANG_CHAT: str = "ru"  # Код языка ответа LLM
        LANG_CONTENT: str = "ru"  # Код языка контента (фразы/статьи)
        POP_MSG_ON: bool = False # Оботражать информационные сообщение (Профиль сохранён)
        ADD_LABELS: bool = False # Отображать доп информацию в виде label
        # LANGUAGE = 'russian'
        # CHAT_LANGUAGE = 'russian'

    TTS_VOICE_DEFAULT:str = "Марфа"
    TTS_VOICE_DEFAULT_ID:str = "May_24000"
    LLM_GENDER_DEFAULT: str = 'female'
    gender_dict: dict = {
        'female': 'Женщина',
        'male': 'Мужчина'
    }
    tz:ZoneInfo = ZoneInfo("Europe/Moscow")

    DEBUG: bool = False
    LLM_DEBUG: bool = True

    # события
    TIMEPAD_BASE_URL:str = ""
    TIMEPAD_TOKEN:str = ""
    EVENT_LIMIT_LOAD: int = 10
    EVENT_LIMIT_SEND_TO_LLM: int = 10
    PROBA_LIMIT: float = 0.50

    USE_SPEECH: bool = True #Не используется -> USE_TTS
    SALUTE_TOKEN: str = ""
    SALUTE_TOKEN_URL: str = ""
    SALUTE_RqUID: str = ""
    SALUTE_SYNTHESIZE_URL: str = ""
    SALUTE_RECOGNIZE_URL: str = ""

    MODEL_SOURCE: str = 'gigachat'  # mistral | openrouter | gigachat

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = ""
    OPENROUTER_TEMPERATURE: int = 0
    # OPENROUTER_MODEL: str = "arcee-ai/trinity-large-preview:free"
    OPENROUTER_MODEL: str = 'tngtech/deepseek-r1t2-chimera:free'
    # OPENROUTER_MODEL: str = 'qwen/qwen3-next-80b-a3b-instruct:free'

    # больше не поддерживаются
    # OPENROUTER_MODEL: str = 'google/gemma-3-27b-it:free'
    # OPENROUTER_MODEL: str = "mistralai/mistral-small-3.2-24b-instruct:free"
    #   model="mistralai/mistral-7b-instruct:free"

    GIGACHAT_CREDENTIALS: str = "MDE5ZDgzMWItNTVmYy03YmFmLTgyNjgtYjViMGJjZDg4NWM5OjczNTZmODc4LTMyZDctNDQ2Yi1iN2I2LTQ1ZjQ4ZDY3NTJlYQ=="
    GIGACHAT_MODEL: str = 'GigaChat-2-Max'
    GIGACHAT_BASE_URL: str = "https://gigachat.devices.sberbank.ru/api/v1"

    MISTRAL_API_KEY: str
    MISTRAL_BASE_URL: str
    MISTRAL_TEMPERATURE: int = 0
    MISTRAL_MODEL: str = 'mistral-large-latest'
    # MISTRAL_MODEL: str = 'open-mistral-7b'
    #   model_name="mistral-large-latest"

    USE_LLM: bool = True
    USE_STREAM: bool = True
    USE_EVENTS: bool = True
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
    GEOMETRY: str = "700x650"
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

    THEMES_DEFAULT: str = 'Тёмная'
    THEMES: dict[str, Theme] = {
        "Тёмная": Theme(
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
        "Светлая": Theme(
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

    @property
    def llm_gender(self):
        gender = self.LLM_GENDER_DEFAULT
        try:
            voice_name = self.app_options.TTS_VOICE
        except Exception as e:
            voice_name = self.TTS_VOICE_DEFAULT
        try:
            voice_data = TTS_VOICES.get(voice_name, {})
            gender = voice_data.get('gender', self.LLM_GENDER_DEFAULT)
        except Exception as e:
            voice_id = self.TTS_VOICE_DEFAULT_ID

        return self.gender_dict.get(gender, '')


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
                opt.THEME = "Светлая" if "Светлая" in self.THEMES else self.THEMES_DEFAULT

            # Коды языков
            _langs = ("ru", "en", "it", "de")
            if getattr(opt, "LANG_UI", None) not in _langs:
                opt.LANG_UI = "ru"
            if getattr(opt, "LANG_CHAT", None) not in _langs:
                opt.LANG_CHAT = opt.LANG_UI
            if getattr(opt, "LANG_CONTENT", None) not in _langs:
                opt.LANG_CONTENT = opt.LANG_UI


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
