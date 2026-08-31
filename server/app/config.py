import secrets
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVER_DIR = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=SERVER_DIR / ".env", extra="ignore")
    mall_server_host: str = "0.0.0.0"
    mall_server_port: int = 8000
    mall_db_path: str = str(SERVER_DIR / "data" / "mall.db")
    default_mall_id: str = "mall_demo"
    token_secret: str = secrets.token_urlsafe(48)
    token_ttl_seconds: int = 86400
    demo_debug: bool = True
    llm_mode: str = "scripted"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    llm_timeout_seconds: int = 40
    wx_auth_mode: str = "mock"
    wx_app_id: str = ""
    wx_app_secret: str = ""
    tts_mode: str = "windows_sapi"

settings = Settings()
