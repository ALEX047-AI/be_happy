from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    API_KEY: str = ""
    BASE_URL: str = ""

    USE_LLM: bool = True

    DATA: str = "data"
    profile_file_name: str = "user_profile.json"
    diary_file_name: str = "diary.json"

    # максимальное количество документов, получаемых от retriever
    retriever_docs_number: int = 2

    # ТЕМА
    BG: str = "#101010"
    FG: str = "#EAEAEA"
    BTN: str = "#202020"
    ACCENT: str = "#3A7AFE"
    PANEL: str = "#151515"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
    )

settings = Settings()
