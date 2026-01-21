from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel

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

class Settings(BaseSettings):

    DEBUG: bool = False
    LLM_DEBUG: bool = True

    SALUT_TOKEN: str = ""
    SALUT_TOKEN_URL: str = ""
    SALUT_RqUID: str = ""
    SALUT_SYNTHESIZE_URL: str = ""

    MODEL_SOURCE: str = 'openrouter' # mistral | openrouter

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

    # максимальное количество документов, получаемых от retriever
    retriever_docs_number: int = 2

    # tkinter конфигурация
    TITLE: str = "TD — Treatment of Depression"
    GEOMETRY: str = "900x650"
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

    THEMES_DEFAULT: str = 'white'
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

settings = Settings()
