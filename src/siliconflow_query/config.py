"""配置管理"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """配置类"""
    API_BASE_URL: str = "https://api.siliconflow.cn/v1"
    API_KEY: str = os.getenv("SILICONFLOW_API_KEY", "")
    TIMEOUT: int = 30

    @classmethod
    def has_api_key(cls) -> bool:
        return bool(cls.API_KEY and cls.API_KEY.strip())
