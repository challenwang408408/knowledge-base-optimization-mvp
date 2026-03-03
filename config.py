import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

    @classmethod
    def validate(cls) -> list[str]:
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未设置，请在 .env 或侧边栏中配置")
        if not cls.LLM_BASE_URL:
            errors.append("LLM_BASE_URL 未设置")
        if not cls.LLM_MODEL:
            errors.append("LLM_MODEL 未设置")
        return errors

    @classmethod
    def reload(cls):
        load_dotenv(override=True)
        cls.LLM_API_KEY = os.getenv("LLM_API_KEY", "")
        cls.LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        cls.LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


settings = Settings()
