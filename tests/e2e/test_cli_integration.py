"""E2E 测试 - CLI 命令集成测试"""
import subprocess
import sys


def run_cli(args: list[str]) -> tuple[int, str, str]:
    """运行 CLI 命令并返回结果"""
    result = subprocess.run(
        [sys.executable, "-m", "siliconflow_query.cli"] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


class TestCLIIntegration:
    """CLI 集成测试"""

    def test_info_command(self):
        """测试 info 命令"""
        code, stdout, stderr = run_cli(["info"])
        assert code == 0
        assert "硅基流动" in stdout

    def test_list_command(self):
        """测试 list 命令"""
        code, stdout, stderr = run_cli(["list"])
        assert code == 0

    def test_list_with_provider_filter(self):
        """测试带提供商过滤的 list 命令"""
        code, stdout, stderr = run_cli(["list", "--provider", "Qwen"])
        assert code == 0

    def test_list_with_type_filter(self):
        """测试带类型过滤的 list 命令"""
        code, stdout, stderr = run_cli(["list", "--type", "chat"])
        assert code == 0

    def test_list_with_context_filter(self):
        """测试带上下文长度过滤的 list 命令"""
        code, stdout, stderr = run_cli(["list", "--min-context", "100000"])
        assert code == 0

    def test_list_with_sort(self):
        """测试带排序的 list 命令"""
        code, stdout, stderr = run_cli(["list", "--sort", "context"])
        assert code == 0

    def test_providers_command(self):
        """测试 providers 命令"""
        code, stdout, stderr = run_cli(["providers"])
        assert code == 0
        assert "提供商" in stdout

    def test_capabilities_command(self):
        """测试 capabilities 命令"""
        code, stdout, stderr = run_cli(["capabilities"])
        assert code == 0

    def test_search_command(self):
        """测试 search 命令"""
        code, stdout, stderr = run_cli(["search", "qwen"])
        assert code == 0

    def test_search_no_results(self):
        """测试搜索无结果"""
        code, stdout, stderr = run_cli(["search", "nonexistentxyz123"])
        assert code == 0
        assert "未找到" in stdout

    def test_show_invalid_model(self):
        """测试显示不存在的模型"""
        code, stdout, stderr = run_cli(["show", "nonexistent/model"])
        assert code == 1

    def test_verify_without_api_key(self):
        """测试无 API Key 时验证"""
        code, stdout, stderr = run_cli(["verify"])
        # 无 API Key 应返回错误
        assert code == 1 or "API Key" in stdout


class TestCLIHelp:
    """CLI 帮助测试"""

    def test_main_help(self):
        """测试主帮助"""
        code, stdout, stderr = run_cli(["--help"])
        assert code == 0
        assert "sfq" in stdout.lower() or "siliconflow" in stdout.lower()

    def test_list_help(self):
        """测试 list 帮助"""
        code, stdout, stderr = run_cli(["list", "--help"])
        assert code == 0
        assert "provider" in stdout.lower() or "type" in stdout.lower()

    def test_scrape_help(self):
        """测试 scrape 帮助"""
        code, stdout, stderr = run_cli(["scrape", "--help"])
        assert code == 0
        assert "headless" in stdout.lower() or "latest" in stdout.lower()
