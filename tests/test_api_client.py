"""测试 API 客户端模块"""
import pytest
from unittest.mock import Mock, patch

from siliconflow_query.api_client import SiliconFlowClient


class TestSiliconFlowClient:
    """SiliconFlowClient 测试"""

    def test_init_with_explicit_api_key(self):
        """使用显式 API Key 初始化"""
        client = SiliconFlowClient(api_key="explicit-key")
        assert client.api_key == "explicit-key"

    def test_init_uses_config_api_key(self, monkeypatch):
        """使用 Config.API_KEY 初始化"""
        monkeypatch.setattr("siliconflow_query.api_client.Config.API_KEY", "config-key")
        client = SiliconFlowClient()
        assert client.api_key == "config-key"

    def test_get_headers_contains_authorization(self):
        """请求头包含 Authorization"""
        client = SiliconFlowClient(api_key="test-key")
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"

    def test_list_models_returns_empty_without_api_key(self):
        """无 API Key 时返回空列表"""
        client = SiliconFlowClient(api_key="")
        result = client.list_models()
        assert result == []

    def test_list_models_success(self, monkeypatch):
        """成功获取模型列表"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"id": "Qwen/Qwen3-8B", "type": "chat"},
                {"id": "BAAI/bge-m3", "type": "embedding"},
            ]
        }
        mock_response.raise_for_status = Mock()

        mock_get = Mock(return_value=mock_response)
        monkeypatch.setattr("requests.get", mock_get)

        client = SiliconFlowClient(api_key="test-key")
        result = client.list_models()

        assert len(result) == 2
        assert result[0]["id"] == "Qwen/Qwen3-8B"

    def test_list_models_with_type_filter(self, monkeypatch):
        """带类型过滤获取模型列表"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": [{"id": "model-1"}]}
        mock_response.raise_for_status = Mock()

        mock_get = Mock(return_value=mock_response)
        monkeypatch.setattr("requests.get", mock_get)

        client = SiliconFlowClient(api_key="test-key")
        client.list_models(model_type="chat", sub_type="reasoning")

        # 验证 params 被正确传递
        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs["params"]["type"] == "chat"
        assert call_kwargs.kwargs["params"]["sub_type"] == "reasoning"

    def test_list_models_handles_request_exception(self, monkeypatch):
        """请求异常时返回空列表"""
        import requests
        mock_get = Mock(side_effect=requests.RequestException("Network error"))
        monkeypatch.setattr("requests.get", mock_get)

        client = SiliconFlowClient(api_key="test-key")
        result = client.list_models()

        assert result == []

    def test_verify_model_returns_true_when_found(self, monkeypatch):
        """验证模型存在时返回 True"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [{"id": "Qwen/Qwen3-8B"}, {"id": "BAAI/bge-m3"}]
        }
        mock_response.raise_for_status = Mock()

        mock_get = Mock(return_value=mock_response)
        monkeypatch.setattr("requests.get", mock_get)

        client = SiliconFlowClient(api_key="test-key")
        assert client.verify_model("Qwen/Qwen3-8B") is True

    def test_verify_model_returns_false_when_not_found(self, monkeypatch):
        """验证模型不存在时返回 False"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": [{"id": "other-model"}]}
        mock_response.raise_for_status = Mock()

        mock_get = Mock(return_value=mock_response)
        monkeypatch.setattr("requests.get", mock_get)

        client = SiliconFlowClient(api_key="test-key")
        assert client.verify_model("nonexistent/model") is False

    def test_verify_model_returns_false_without_api_key(self):
        """无 API Key 时验证返回 False"""
        client = SiliconFlowClient(api_key="")
        assert client.verify_model("any/model") is False

    def test_get_model_ids_returns_ids(self, monkeypatch):
        """获取所有模型 ID 列表"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [{"id": "model-1"}, {"id": "model-2"}, {"name": "no-id-model"}]
        }
        mock_response.raise_for_status = Mock()

        mock_get = Mock(return_value=mock_response)
        monkeypatch.setattr("requests.get", mock_get)

        client = SiliconFlowClient(api_key="test-key")
        ids = client.get_model_ids()

        assert ids == ["model-1", "model-2"]

    def test_get_model_ids_returns_empty_on_error(self, monkeypatch):
        """请求失败时返回空列表"""
        import requests
        mock_get = Mock(side_effect=requests.RequestException())
        monkeypatch.setattr("requests.get", mock_get)

        client = SiliconFlowClient(api_key="test-key")
        ids = client.get_model_ids()

        assert ids == []
