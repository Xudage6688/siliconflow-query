"""测试爬虫模块 - ScrapedModel 和 save_results"""
import json
import pytest
from pathlib import Path
from datetime import datetime

from siliconflow_query.scraper import ScrapedModel, save_results, parse_price, is_free_model


class TestScrapedModel:
    """ScrapedModel 数据类测试"""

    def test_default_values(self):
        """默认值测试"""
        model = ScrapedModel()
        assert model.id == ""
        assert model.name == ""
        assert model.is_free is False
        assert model.is_deprecated is False

    def test_custom_values(self):
        """自定义值测试"""
        model = ScrapedModel(
            id="Qwen/Qwen3-8B",
            name="Qwen3-8B",
            provider="Qwen",
            context_length="128K",
            input_price="0",
            output_price="0",
            is_free=True,
        )
        assert model.id == "Qwen/Qwen3-8B"
        assert model.context_length == "128K"
        assert model.is_free is True

    def test_deprecated_flag(self):
        """废弃标记测试"""
        model = ScrapedModel(id="old/model", is_deprecated=True)
        assert model.is_deprecated is True


class TestSaveResults:
    """save_results 函数测试"""

    def test_save_results_creates_file(self, tmp_path):
        """保存结果创建文件"""
        models = [
            ScrapedModel(id="free/model", name="Free", is_free=True),
            ScrapedModel(id="paid/model", name="Paid", is_free=False),
        ]
        output_file = tmp_path / "output.json"

        save_results(models, output_file)

        assert output_file.exists()

    def test_save_results_structure(self, tmp_path):
        """保存结果结构正确"""
        models = [
            ScrapedModel(
                id="Qwen/Qwen3-8B",
                name="Qwen3-8B",
                provider="Qwen",
                context_length="128K",
                input_price="0",
                output_price="0",
                is_free=True,
            ),
        ]
        output_file = tmp_path / "output.json"

        save_results(models, output_file)

        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        assert "scrape_time" in data
        assert "total_models" in data
        assert "free_models_count" in data
        assert data["total_models"] == 1
        assert data["free_models_count"] == 1
        assert len(data["free_models"]) == 1
        assert data["free_models"][0]["id"] == "Qwen/Qwen3-8B"

    def test_save_results_empty_list(self, tmp_path):
        """保存空列表"""
        output_file = tmp_path / "output.json"

        save_results([], output_file)

        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_models"] == 0
        assert data["free_models_count"] == 0
        assert data["free_models"] == []

    def test_save_results_creates_parent_dirs(self, tmp_path):
        """自动创建父目录"""
        output_file = tmp_path / "subdir" / "nested" / "output.json"

        save_results([], output_file)

        assert output_file.exists()


class TestParsePriceEdgeCases:
    """parse_price 边界情况测试"""

    def test_whitespace_handling(self):
        """空格处理"""
        assert parse_price("  free  ") == 0.0
        assert parse_price("  $ 0.5  ") == 0.5

    def test_case_insensitive(self):
        """大小写不敏感"""
        assert parse_price("FREE") == 0.0
        assert parse_price("Free") == 0.0

    def test_chinese_free(self):
        """中文免费"""
        assert parse_price("免费") == 0.0


class TestIsFreeModelEdgeCases:
    """is_free_model 边界情况测试"""

    def test_both_free_keyword(self):
        """free 关键词"""
        assert is_free_model("free", "free") is True

    def test_mixed_formats(self):
        """混合格式"""
        assert is_free_model("0", "free") is True
        assert is_free_model("free", "0") is True

    def test_one_empty_one_zero(self):
        """一个空一个零"""
        assert is_free_model("", "0") is False
        assert is_free_model("0", "") is False
