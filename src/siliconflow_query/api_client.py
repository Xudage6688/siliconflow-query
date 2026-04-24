"""SiliconFlow API客户端"""
from typing import List, Dict, Any, Optional
import requests
from .config import Config


class SiliconFlowClient:
    """SiliconFlow API客户端"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.API_KEY
        self.base_url = Config.API_BASE_URL
        self.timeout = Config.TIMEOUT

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def list_models(
        self,
        model_type: Optional[str] = None,
        sub_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取模型列表"""
        if not self.api_key:
            return []

        url = f"{self.base_url}/models"
        params = {}
        if model_type:
            params["type"] = model_type
        if sub_type:
            params["sub_type"] = sub_type

        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except requests.RequestException:
            return []

    def verify_model(self, model_id: str) -> bool:
        """验证模型是否可用"""
        if not self.api_key:
            return False

        models = self.list_models()
        return any(m.get("id") == model_id for m in models)

    def get_model_ids(self) -> List[str]:
        """获取所有可用模型ID"""
        models = self.list_models()
        return [m.get("id", "") for m in models if m.get("id")]
