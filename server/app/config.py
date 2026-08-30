"""全局配置。"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    server_host: str = "0.0.0.0"
    server_port: int = 8200
    mall_db: str = "sqlite:///./data/mall.db"

    # LLM
    llm_provider: str = "openai"
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: int = 25

    # 微信
    wx_appid: str = ""
    wx_secret: str = ""

    # Web 登录
    web_admin_user: str = "admin"
    web_admin_password: str = ""

    default_mall_id: str = "mall-main"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
