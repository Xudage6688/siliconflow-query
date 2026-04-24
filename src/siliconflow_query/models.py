"""硅基流动免费模型筛选工具"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import json
from pathlib import Path


@dataclass
class ModelInfo:
    """模型信息数据类"""
    id: str
    name: str
    provider: str
    model_type: str
    context_length: int = 0
    max_output: int = 4096
    parameters: str = ""
    description: str = ""
    provider_cn: str = ""
    capabilities: List[str] = field(default_factory=list)
    pricing_tier: str = "free"
    source: str = ""
    last_verified: str = ""

    def __post_init__(self):
        if not self.provider_cn:
            self.provider_cn = self.provider

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelInfo":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            provider=data.get("provider", ""),
            provider_cn=data.get("provider_cn", ""),
            model_type=data.get("model_type", "chat"),
            context_length=data.get("context_length", 0),
            max_output=data.get("max_output", 4096),
            parameters=data.get("parameters", ""),
            description=data.get("description", ""),
            capabilities=data.get("capabilities", []),
            pricing_tier=data.get("pricing_tier", "free"),
            source=data.get("source", ""),
            last_verified=data.get("last_verified", ""),
        )


class FreeModelsDB:
    """免费模型数据库"""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent / "free_models.json"
        self.db_path = db_path
        self._models: List[ModelInfo] = []
        self._last_updated: str = ""
        self._source: str = ""
        self._load()

    def _load(self) -> None:
        if not self.db_path.exists():
            return
        with open(self.db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._last_updated = data.get("last_updated", "")
        self._source = data.get("source", "")
        self._models = [
            ModelInfo.from_dict(m) for m in data.get("models", [])
        ]

    def get_all(self) -> List[ModelInfo]:
        return self._models.copy()

    def get_by_id(self, model_id: str) -> Optional[ModelInfo]:
        for model in self._models:
            if model.id == model_id:
                return model
        return None

    def search(self, query: str) -> List[ModelInfo]:
        query_lower = query.lower()
        results = []
        for model in self._models:
            if (query_lower in model.id.lower() or
                query_lower in model.name.lower() or
                query_lower in model.provider.lower() or
                query_lower in model.description.lower()):
                results.append(model)
        return results

    def filter(
        self,
        provider: Optional[str] = None,
        model_type: Optional[str] = None,
        min_context: Optional[int] = None,
        capability: Optional[str] = None,
    ) -> List[ModelInfo]:
        results = self._models.copy()
        if provider:
            results = [m for m in results if m.provider.lower() == provider.lower()]
        if model_type:
            results = [m for m in results if m.model_type.lower() == model_type.lower()]
        if min_context:
            results = [m for m in results if m.context_length >= min_context]
        if capability:
            results = [m for m in results if capability.lower() in [c.lower() for c in m.capabilities]]
        return results

    @property
    def last_updated(self) -> str:
        return self._last_updated

    @property
    def source(self) -> str:
        return self._source

    def get_providers(self) -> List[str]:
        return sorted(set(m.provider for m in self._models))

    def get_capabilities(self) -> List[str]:
        caps = set()
        for m in self._models:
            caps.update(m.capabilities)
        return sorted(caps)
