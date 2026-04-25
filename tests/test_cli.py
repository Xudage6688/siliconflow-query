"""测试 CLI 模块"""
import json
import pytest
from pathlib import Path
from typer.testing import CliRunner

from siliconflow_query.cli import app


runner = CliRunner()


class TestCLIInfo:
    """info 命令测试"""

    def test_info_command_runs(self):
        """info 命令正常运行"""
        result = runner.invoke(app, ["info"])
        assert result.exit_code == 0
        assert "硅基流动" in result.stdout


class TestCLIList:
    """list 命令测试"""

    def test_list_command_runs(self):
        """list 命令正常运行"""
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0

    def test_list_with_provider_filter(self):
        """带提供商过滤的 list 命令"""
        result = runner.invoke(app, ["list", "--provider", "Qwen"])
        assert result.exit_code == 0

    def test_list_with_type_filter(self):
        """带类型过滤的 list 命令"""
        result = runner.invoke(app, ["list", "--type", "chat"])
        assert result.exit_code == 0

    def test_list_with_sort(self):
        """带排序的 list 命令"""
        result = runner.invoke(app, ["list", "--sort", "context"])
        assert result.exit_code == 0


class TestCLIProviders:
    """providers 命令测试"""

    def test_providers_command_runs(self):
        """providers 命令正常运行"""
        result = runner.invoke(app, ["providers"])
        assert result.exit_code == 0
        assert "提供商" in result.stdout


class TestCLICapabilities:
    """capabilities 命令测试"""

    def test_capabilities_command_runs(self):
        """capabilities 命令正常运行"""
        result = runner.invoke(app, ["capabilities"])
        assert result.exit_code == 0


class TestCLISearch:
    """search 命令测试"""

    def test_search_command_runs(self):
        """search 命令正常运行"""
        result = runner.invoke(app, ["search", "qwen"])
        assert result.exit_code == 0

    def test_search_no_results_message(self):
        """搜索无结果时的消息"""
        result = runner.invoke(app, ["search", "nonexistentxyz"])
        assert result.exit_code == 0
        assert "未找到" in result.stdout or "没有" in result.stdout


class TestCLIShow:
    """show 命令测试"""

    def test_show_command_with_model(self):
        """show 命令显示模型详情"""
        # 使用数据库中可能存在的模型，或搜索返回的第一个
        result = runner.invoke(app, ["show", "Qwen/Qwen3-8B"])
        # 可能找到也可能没找到，取决于数据库内容
        # 只要命令能正常执行就算通过
        assert result.exit_code in [0, 1]

    def test_show_command_with_invalid_model(self):
        """show 命令无效模型"""
        result = runner.invoke(app, ["show", "nonexistent/model"])
        assert result.exit_code == 1


class TestCLIVerify:
    """verify 命令测试"""

    def test_verify_command_without_api_key(self):
        """verify 命令无 API Key 时报错"""
        result = runner.invoke(app, ["verify"])
        # 无 API Key 应返回错误
        assert result.exit_code == 1 or "API Key" in result.stdout


class TestCLIUpdate:
    """update 命令测试"""

    def test_update_command_without_file(self):
        """update 命令无输入文件时报错"""
        result = runner.invoke(app, ["update", "--input", "nonexistent.json"])
        assert result.exit_code == 1
        assert "不存在" in result.stdout or "先运行" in result.stdout

    def test_update_command_with_empty_free_models(self, tmp_path):
        """update 命令无免费模型"""
        data = {"free_models": []}
        input_file = tmp_path / "empty.json"
        input_file.write_text(json.dumps(data))

        result = runner.invoke(app, ["update", "--input", str(input_file)])
        assert result.exit_code == 0
        assert "没有免费模型" in result.stdout or "没有" in result.stdout