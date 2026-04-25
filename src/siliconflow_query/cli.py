"""硅基流动免费模型筛选工具 CLI"""
import json
import re
from datetime import datetime
from pathlib import Path
import asyncio
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Optional
from .models import FreeModelsDB
from .api_client import SiliconFlowClient
from .config import Config
from .scraper import run_scrape, run_scrape_latest, save_results

app = typer.Typer(
    name="sfq",
    help="硅基流动免费模型筛选工具 - SiliconFlow Free Models Query",
)
console = Console()

# Lazy load database to avoid errors at module import time
_DB: Optional[FreeModelsDB] = None


def get_db() -> FreeModelsDB:
    """获取数据库实例（延迟加载）"""
    global _DB
    if _DB is None:
        _DB = FreeModelsDB()
    return _DB


def format_context(length: int) -> str:
    if length >= 1024:
        return f"{length // 1024}K"
    return str(length)


@app.command()
def list(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="按提供商筛选"),
    model_type: Optional[str] = typer.Option(None, "--type", "-t", help="按模型类型筛选"),
    min_context: Optional[int] = typer.Option(None, "--min-context", "-c", help="最小上下文长度"),
    capability: Optional[str] = typer.Option(None, "--capability", "--cap", help="按能力筛选"),
    sort_by: str = typer.Option("name", "--sort", "-s", help="排序字段: name, context, params"),
):
    """列出所有免费模型"""
    db = get_db()
    models = db.filter(
        provider=provider,
        model_type=model_type,
        min_context=min_context,
        capability=capability,
    )

    if sort_by == "context":
        models = sorted(models, key=lambda m: m.context_length, reverse=True)
    elif sort_by == "params":
        models = sorted(models, key=lambda m: m.parameters)
    else:
        models = sorted(models, key=lambda m: m.name)

    if not models:
        console.print("[yellow]没有找到匹配的模型[/yellow]")
        return

    table = Table(title=f"免费模型列表 (共 {len(models)} 个)")
    table.add_column("模型名称", style="cyan")
    table.add_column("提供商", style="green")
    table.add_column("参数量", justify="right")
    table.add_column("上下文", justify="right")
    table.add_column("简介")

    for m in models:
        table.add_row(
            m.name,
            m.provider_cn or m.provider,
            m.parameters,
            format_context(m.context_length),
            m.description[:25] + "..." if len(m.description) > 25 else m.description,
        )

    console.print(table)
    console.print(f"\n[dim]数据更新: {get_db().last_updated} | 来源: {get_db().source}[/dim]")


@app.command()
def show(model_id: str):
    """显示模型详情"""
    model = get_db().get_by_id(model_id)
    if not model:
        models = get_db().search(model_id)
        if models:
            model = models[0]
        else:
            console.print(f"[red]未找到模型: {model_id}[/red]")
            raise typer.Exit(1)

    cap_text = "\n".join(f"- {cap}" for cap in model.capabilities) if model.capabilities else "无"

    content = f"""[bold]ID:[/bold] {model.id}
[bold]提供商:[/bold] {model.provider_cn} ({model.provider})
[bold]类型:[/bold] {model.model_type}
[bold]参数量:[/bold] {model.parameters}
[bold]上下文长度:[/bold] {model.context_length:,} tokens
[bold]最大输出:[/bold] {model.max_output:,} tokens
[bold]定价:[/bold] [green]免费[/green]

[bold]简介:[/bold]
{model.description}

[bold]能力:[/bold]
{cap_text}

[bold]数据来源:[/bold] {model.source}
[bold]数据库更新:[/bold] {get_db().last_updated}"""

    panel = Panel(content, title=f"[bold cyan]{model.name}[/bold cyan]", border_style="cyan")
    console.print(panel)


@app.command()
def search(query: str):
    """搜索模型"""
    models = get_db().search(query)

    if not models:
        console.print(f"[yellow]未找到匹配 '{query}' 的模型[/yellow]")
        return

    console.print(f"[green]找到 {len(models)} 个匹配模型:[/green]\n")

    for m in models:
        console.print(f"  [cyan]{m.id}[/cyan] - {m.name} ({m.parameters})")


@app.command()
def verify():
    """验证模型可用性（需要API Key）"""
    if not Config.has_api_key():
        console.print("[red]错误: 未设置API Key[/red]")
        console.print("请设置环境变量 [cyan]SILICONFLOW_API_KEY[/cyan] 或创建 .env 文件")
        raise typer.Exit(1)

    console.print("[yellow]正在验证免费模型可用性...[/yellow]\n")

    client = SiliconFlowClient()
    available_ids = client.get_model_ids()

    if not available_ids:
        console.print("[red]无法获取API模型列表，请检查API Key是否有效[/red]")
        raise typer.Exit(1)

    available = 0
    unavailable = 0

    for model in get_db().get_all():
        if model.id in available_ids:
            console.print(f"[green][OK][/green] {model.id} - 可用")
            available += 1
        else:
            console.print(f"[red][X][/red] {model.id} - 不可用")
            unavailable += 1

    console.print(f"\n[bold]验证完成:[/bold] {available} 个可用, {unavailable} 个不可用")


@app.command()
def providers():
    """列出所有提供商"""
    providers_list = get_db().get_providers()
    console.print("[bold]可用提供商:[/bold]\n")
    for p in providers_list:
        count = len([m for m in get_db().get_all() if m.provider == p])
        console.print(f"  [cyan]{p}[/cyan] ({count} 个模型)")


@app.command()
def capabilities():
    """列出所有能力标签"""
    caps = get_db().get_capabilities()
    console.print("[bold]可用能力标签:[/bold]\n")
    for c in caps:
        console.print(f"  [cyan]{c}[/cyan]")


@app.command()
def info():
    """显示工具信息"""
    console.print(Panel.fit(
        "[bold cyan]硅基流动免费模型筛选工具[/bold cyan]\n\n"
        f"当前数据库包含 [bold]{len(get_db().get_all())}[/bold] 个免费模型\n"
        f"数据更新时间: {get_db().last_updated}\n"
        f"数据来源: {get_db().source}\n\n"
        "[dim]使用 --help 查看可用命令[/dim]",
        border_style="cyan",
    ))


@app.command()
def scrape(
    headless: bool = typer.Option(False, "--headless", "-h", help="无头模式（不显示浏览器）"),
    max_models: int = typer.Option(0, "--max", "-m", help="最大抓取模型数（0=全部）"),
    output: str = typer.Option("scraped_models.json", "--output", "-o", help="输出文件路径"),
    skip_login: bool = typer.Option(False, "--skip-login", help="跳过登录等待（可能无法获取定价）"),
    skip_detail_check: bool = typer.Option(False, "--skip-detail-check", help="跳过详情页价格检查（更快但不完整）"),
    latest: bool = typer.Option(False, "--latest", "-l", help="增量模式：只抓取近90天的免费模型（更快）"),
    days: int = typer.Option(90, "--days", "-d", help="增量模式的时间范围（天数）"),
):
    """从官网抓取模型定价信息，自动识别免费模型

    使用方法:
        sfq scrape                   # 全量抓取（显示浏览器，等待登录）
        sfq scrape --latest          # 增量抓取（近90天的免费模型）
        sfq scrape --latest --days 30 # 增量抓取（近30天）
        sfq scrape --skip-login      # 跳过登录（可能无法获取完整定价）
        sfq scrape --headless        # 无头模式（需先登录过）
        sfq scrape --skip-detail-check  # 跳过详情页检查，只从列表识别免费模型
    """
    console.print("[bold cyan]开始抓取 SiliconFlow 模型定价信息...[/bold cyan]")

    if latest:
        console.print(f"[yellow]增量模式：抓取近 {days} 天的免费模型[/yellow]")
        console.print("[yellow]请在浏览器中完成登录，然后回到终端按回车继续[/yellow]\n")

        try:
            models = asyncio.run(run_scrape_latest(
                headless=headless,
                days=days,
            ))
        except Exception as e:
            console.print(f"[red]抓取失败: {e}[/red]")
            raise typer.Exit(1)

        free_models = models  # 增量模式只返回免费模型
    else:
        if not headless and not skip_login:
            console.print("[yellow]提示: 浏览器将打开登录页面[/yellow]")
            console.print("[yellow]请在浏览器中完成登录，然后回到终端按回车继续[/yellow]\n")
        elif skip_login:
            console.print("[dim]跳过登录，可能无法获取完整定价信息[/dim]\n")

        try:
            models = asyncio.run(run_scrape(
                headless=headless,
                max_models=max_models,
                need_login=not skip_login,
                check_details=not skip_detail_check,
            ))
        except Exception as e:
            console.print(f"[red]抓取失败: {e}[/red]")
            raise typer.Exit(1)

        free_models = [m for m in models if m.is_free]

    no_price = [m for m in models if not m.input_price] if not latest else []

    # 显示结果
    console.print(f"\n[bold green]抓取完成![/bold green]")
    console.print(f"  总模型数: {len(models)}")
    if not latest:
        console.print(f"  无价格数据: {len(no_price)}")
    console.print(f"  免费模型: [bold]{len(free_models)}[/bold]")

    if free_models:
        console.print("\n[bold]免费模型列表:[/bold]")
        table = Table()
        table.add_column("模型ID", style="cyan")
        table.add_column("名称")
        table.add_column("输入价格")
        table.add_column("输出价格")

        for m in free_models:
            table.add_row(
                m.id,
                m.name or "-",
                m.input_price or "0",
                m.output_price or "0",
            )
        console.print(table)

    # 保存结果
    output_path = Path(output)
    if latest:
        # 增量模式：只保存免费模型
        data = {
            "scrape_time": datetime.now().isoformat(),
            "mode": "latest",
            "days": days,
            "free_models_count": len(free_models),
            "free_models": [{"id": m.id, "name": m.name, "provider": m.provider,
                            "context_length": m.context_length, "is_free": True,
                            "input_price": "0", "output_price": "0"} for m in free_models],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    else:
        save_results(models, output_path)
    console.print(f"\n[dim]结果已保存到: {output_path}[/dim]")

    # 更新本地数据库
    if free_models:
        console.print("\n[yellow]提示: 使用 'sfq update' 将免费模型更新到本地数据库[/yellow]")


@app.command()
def update(
    input_file: str = typer.Option("scraped_models.json", "--input", "-i", help="抓取结果文件"),
):
    """从抓取结果更新本地免费模型数据库"""
    input_path = Path(input_file)
    if not input_path.exists():
        console.print(f"[red]文件不存在: {input_path}[/red]")
        console.print("请先运行 'sfq scrape' 抓取模型信息")
        raise typer.Exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    free_models = data.get("free_models", [])
    if not free_models:
        console.print("[yellow]抓取结果中没有免费模型[/yellow]")
        return

    # 更新本地数据库
    db_path = Path(__file__).parent / "free_models.json"
    db_data = {
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "source": "web scrape",
        "models": []
    }

    # 已知模型的默认上下文长度（当 scraper 未抓取时使用）
    KNOWN_CONTEXT = {
        "THUDM/GLM-4-9B-0414": 131072,
        "THUDM/GLM-Z1-9B-0414": 131072,
        "THUDM/GLM-4.1V-9B-Thinking": 131072,
        "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B": 32768,
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B": 32768,
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B": 32768,
        "Qwen/Qwen2.5-7B-Instruct": 32768,
        "Qwen/Qwen3-8B": 131072,
        "internlm/internlm2_5-7b-chat": 32768,
        "tencent/Hunyuan-MT-7B": 32768,
        "BAAI/bge-m3": 8192,
        "BAAI/bge-large-en-v1.5": 512,
        "BAAI/bge-large-zh-v1.5": 512,
        "BAAI/bge-reranker-v2-m3": 8192,
        "netease-youdao/bce-embedding-base_v1": 512,
    }

    # 已知模型的默认描述
    KNOWN_DESC = {
        "THUDM/GLM-4-9B-0414": "智谱AI GLM-4 9B 模型",
        "THUDM/GLM-Z1-9B-0414": "智谱AI GLM-Z1 9B 思考模型",
        "THUDM/GLM-4.1V-9B-Thinking": "智谱AI GLM-4.1V 9B 视觉思考模型",
        "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B": "DeepSeek R1 推理模型",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B": "DeepSeek R1 蒸馏版",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B": "DeepSeek R1 蒸馏版",
        "Qwen/Qwen3-8B": "通义千问3 8B，支持思考/非思考模式切换",
        "internlm/internlm2_5-7b-chat": "书生浦语 2.5 7B 对话模型",
        "tencent/Hunyuan-MT-7B": "腾讯混元翻译模型",
        "BAAI/bge-m3": "多语言嵌入模型",
        "BAAI/bge-large-en-v1.5": "英文嵌入模型",
        "BAAI/bge-large-zh-v1.5": "中文嵌入模型",
        "BAAI/bge-reranker-v2-m3": "多语言重排序模型",
        "netease-youdao/bce-embedding-base_v1": "网易有道嵌入模型",
    }

    for m in free_models:
        model_id = m.get("id", "")
        id_suffix = model_id.split("/")[-1] if "/" in model_id else model_id

        # 解析参数量 (如 7B, 9B, 1.5B, 8B)
        params_match = re.search(r'(\d+\.?\d*)[Bb]', model_id)
        parameters = params_match.group(0).upper() if params_match else ""

        # 推断模型类型
        model_type = "chat"
        if "bge-" in model_id.lower() or "embedding" in model_id.lower():
            model_type = "embedding"
        elif "rerank" in model_id.lower():
            model_type = "reranker"
        elif "ocr" in model_id.lower() or "vl" in model_id.lower():
            model_type = "vision"

        # 解析上下文长度：优先用抓取数据，否则用已知映射表
        ctx_raw = m.get("context_length", "")
        ctx_str = str(ctx_raw).strip() if ctx_raw else ""
        if "K" in ctx_str:
            context_length = int(ctx_str.replace("K", "").replace(",", "")) * 1024
        elif ctx_str and ctx_str != "0":
            context_length = int(ctx_str.replace(",", ""))
        elif model_id in KNOWN_CONTEXT:
            context_length = KNOWN_CONTEXT[model_id]
        else:
            context_length = 32768 if model_type == "chat" else 512

        # 名称：优先用抓取数据，为空时用 ID 后缀
        name = m.get("name", "") or id_suffix

        # 描述：优先用抓取数据，否则用已知映射表
        description = m.get("description", "") or KNOWN_DESC.get(model_id, "")

        db_data["models"].append({
            "id": model_id,
            "name": name,
            "provider": m.get("provider", "") or model_id.split("/")[0],
            "provider_cn": m.get("provider_cn", "") or m.get("provider", "") or model_id.split("/")[0],
            "model_type": m.get("model_type", "") or model_type,
            "context_length": context_length,
            "max_output": 4096,
            "parameters": parameters,
            "description": description,
            "capabilities": [model_type],
            "pricing_tier": "free",
            "source": "scraped",
        })

    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(db_data, f, ensure_ascii=False, indent=2)

    console.print(f"[green]已更新本地数据库: {db_path}[/green]")
    console.print(f"  更新了 {len(free_models)} 个免费模型")


if __name__ == "__main__":
    app()
