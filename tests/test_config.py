"""测试配置模块"""
import pytest

from siliconflow_query.config import Config


class TestConfig:
    """Config 类测试"""

    def test_has_api_key_returns_true_when_key_set(self, monkeypatch):
        """API_KEY 设置时返回 True"""
        monkeypatch.setattr(Config, "API_KEY", "test-key-123")
        assert Config.has_api_key() is True

    def test_has_api_key_returns_false_when_key_empty(self, monkeypatch):
        """API_KEY 为空时返回 False"""
        monkeypatch.setattr(Config, "API_KEY", "")
        assert Config.has_api_key() is False

    def test_has_api_key_returns_false_when_key_whitespace(self, monkeypatch):
        """API_KEY 仅包含空格时返回 False"""
        monkeypatch.setattr(Config, "API_KEY", "   ")
        assert Config.has_api_key() is False

    def test_api_key_class_attribute_exists(self):
        """API_KEY 类属性存在"""
        assert hasattr(Config, "API_KEY")
        assert hasattr(Config, "API_BASE_URL")
        assert hasattr(Config, "TIMEOUT")

    def test_default_timeout_value(self):
        """默认超时值为 30"""
        assert Config.TIMEOUT == 30

    def test_default_api_base_url(self):
        """默认 API 基础 URL"""
        assert Config.API_BASE_URL == "https://api.siliconflow.cn/v1"
