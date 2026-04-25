"""测试模型数据模块"""
import json
import pytest
from pathlib import Path
from unittest.mock import mock_open, patch

from siliconflow_query.models import ModelInfo, FreeModelsDB


class TestModelInfo:
    """ModelInfo 数据类测试"""

    def test_from_dict_creates_model_with_all_fields(self):
        """从字典创建模型，包含所有字段"""
        data = {
            "id": "Qwen/Qwen3-8B",
            "name": "Qwen3-8B",
            "provider": "Qwen",
            "provider_cn": "通义千问",
            "model_type": "chat",
            "context_length": 131072,
            "max_output": 4096,
            "parameters": "8B",
            "description": "通义千问3 8B模型",
            "capabilities": ["chat", "reasoning"],
            "pricing_tier": "free",
            "source": "scraped",
            "last_verified": "2026-04-25",
        }
        model = ModelInfo.from_dict(data)
        assert model.id == "Qwen/Qwen3-8B"
        assert model.name == "Qwen3-8B"
        assert model.provider == "Qwen"
        assert model.provider_cn == "通义千问"
        assert model.context_length == 131072
        assert model.capabilities == ["chat", "reasoning"]

    def test_from_dict_handles_missing_fields(self):
        """缺失字段时使用默认值"""
        data = {"id": "test/model", "name": "Test", "provider": "test"}
        model = ModelInfo.from_dict(data)
        assert model.model_type == "chat"
        assert model.context_length == 0
        assert model.capabilities == []

    def test_post_init_sets_provider_cn_from_provider(self):
        """未设置 provider_cn 时从 provider 复制"""
        model = ModelInfo(
            id="test/model",
            name="Test",
            provider="TestProvider",
            model_type="chat",
        )
        assert model.provider_cn == "TestProvider"

    def test_post_init_keeps_explicit_provider_cn(self):
        """显式设置 provider_cn 时保留原值"""
        model = ModelInfo(
            id="test/model",
            name="Test",
            provider="TestProvider",
            provider_cn="测试提供商",
            model_type="chat",
        )
        assert model.provider_cn == "测试提供商"


class TestFreeModelsDB:
    """FreeModelsDB 数据库类测试"""

    @pytest.fixture
    def sample_db_data(self):
        """示例数据库数据"""
        return {
            "last_updated": "2026-04-25",
            "source": "web scrape",
            "models": [
                {
                    "id": "Qwen/Qwen3-8B",
                    "name": "Qwen3-8B",
                    "provider": "Qwen",
                    "provider_cn": "通义千问",
                    "model_type": "chat",
                    "context_length": 131072,
                    "capabilities": ["chat"],
                },
                {
                    "id": "deepseek-ai/DeepSeek-R1",
                    "name": "DeepSeek-R1",
                    "provider": "deepseek-ai",
                    "model_type": "chat",
                    "context_length": 32768,
                    "capabilities": ["chat", "reasoning"],
                },
                {
                    "id": "BAAI/bge-m3",
                    "name": "bge-m3",
                    "provider": "BAAI",
                    "model_type": "embedding",
                    "context_length": 8192,
                    "capabilities": ["embedding"],
                },
            ],
        }

    def test_get_all_returns_copy(self, sample_db_data, tmp_path):
        """get_all 返回副本，修改不影响原数据"""
        db_file = tmp_path / "test_db.json"
        db_file.write_text(json.dumps(sample_db_data), encoding="utf-8")

        db = FreeModelsDB(db_file)
        models = db.get_all()
        models.clear()

        # 原数据不受影响
        assert len(db.get_all()) == 3

    def test_get_by_id_found(self, sample_db_data, tmp_path):
        """get_by_id 找到模型"""
        db_file = tmp_path / "test_db.json"
        db_file.write_text(json.dumps(sample_db_data), encoding="utf-8")

        db = FreeModelsDB(db_file)
        model = db.get_by_id("Qwen/Qwen3-8B")
        assert model is not None
        assert model.name == "Qwen3-8B"

    def test_get_by_id_not_found(self, sample_db_data, tmp_path):
        """get_by_id 未找到返回 None"""
        db_file = tmp_path / "test_db.json"
        db_file.write_text(json.dumps(sample_db_data), encoding="utf-8")

        db = FreeModelsDB(db_file)
        model = db.get_by_id("nonexistent/model")
        assert model is None

    def test_search_by_id(self, sample_db_data, tmp_path):
        """按 ID 搜索"""
        db_file = tmp_path / "test_db.json"
        db_file.write_text(json.dumps(sample_db_data), encoding="utf-8")

        db = FreeModelsDB(db_file)
        results = db.search("qwen")
        assert len(results) == 1
        assert results[0].id == "Qwen/Qwen3-8B"

    def test_search_by_description(self, sample_db_data, tmp_path):
        """按描述搜索"""
        db_file = tmp_path / "test_db.json"
        db_file.write_text(json.dumps(sample_db_data), encoding="utf-8")

        db = FreeModelsDB(db_file)
        # 测试空描述也能正常工作
        results = db.search("deepseek")
        assert len(results) == 1

    def test_filter_by_provider(self, sample_db_data, tmp_path):
        """按提供商筛选"""
        db_file = tmp_path / "test_db.json"
        db_file.write_text(json.dumps(sample_db_data), encoding="utf-8")

        db = FreeModelsDB(db_file)
        results = db.filter(provider="Qwen")
        assert len(results) == 1
        assert results[0].provider == "Qwen"

    def test_filter_by_model_type(self, sample_db_data, tmp_path):
        """按模型类型筛选"""
        db_file = tmp_path / "test_db.json"
        db_file.write_text(json.dumps(sample_db_data), encoding="utf-8")

        db = FreeModelsDB(db_file)
        results = db.filter(model_type="embedding")
        assert len(results) == 1
        assert results[0].model_type == "embedding"

    def test_filter_by_min_context(self, sample_db_data, tmp_path):
        """按最小上下文长度筛选"""
        db_file = tmp_path / "test_db.json"
        db_file.write_text(json.dumps(sample_db_data), encoding="utf-8")

        db = FreeModelsDB(db_file)
        results = db.filter(min_context=100000)
        assert len(results) == 1
        assert results[0].context_length >= 100000

    def test_filter_by_capability(self, sample_db_data, tmp_path):
        """按能力筛选"""
        db_file = tmp_path / "test_db.json"
        db_file.write_text(json.dumps(sample_db_data), encoding="utf-8")

        db = FreeModelsDB(db_file)
        results = db.filter(capability="reasoning")
        assert len(results) == 1

    def test_filter_combined(self, sample_db_data, tmp_path):
        """组合筛选"""
        db_file = tmp_path / "test_db.json"
        db_file.write_text(json.dumps(sample_db_data), encoding="utf-8")

        db = FreeModelsDB(db_file)
        results = db.filter(provider="deepseek-ai", model_type="chat")
        assert len(results) == 1

    def test_get_providers(self, sample_db_data, tmp_path):
        """获取所有提供商列表"""
        db_file = tmp_path / "test_db.json"
        db_file.write_text(json.dumps(sample_db_data), encoding="utf-8")

        db = FreeModelsDB(db_file)
        providers = db.get_providers()
        assert providers == ["BAAI", "Qwen", "deepseek-ai"]

    def test_get_capabilities(self, sample_db_data, tmp_path):
        """获取所有能力列表"""
        db_file = tmp_path / "test_db.json"
        db_file.write_text(json.dumps(sample_db_data), encoding="utf-8")

        db = FreeModelsDB(db_file)
        caps = db.get_capabilities()
        assert "chat" in caps
        assert "embedding" in caps
        assert "reasoning" in caps

    def test_handles_missing_db_file(self, tmp_path):
        """数据库文件不存在时正常工作"""
        nonexistent = tmp_path / "nonexistent.json"
        db = FreeModelsDB(nonexistent)
        assert db.get_all() == []
        assert db.last_updated == ""

    def test_last_updated_and_source_properties(self, sample_db_data, tmp_path):
        """last_updated 和 source 属性"""
        db_file = tmp_path / "test_db.json"
        db_file.write_text(json.dumps(sample_db_data), encoding="utf-8")

        db = FreeModelsDB(db_file)
        assert db.last_updated == "2026-04-25"
        assert db.source == "web scrape"