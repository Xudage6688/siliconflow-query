"""网页抓取模块 - 从SiliconFlow官网抓取模型定价信息"""
import json
import re
import asyncio
from dataclasses import dataclass, asdict
from typing import List
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright, Page


@dataclass
class ScrapedModel:
    """抓取到的模型信息"""
    id: str = ""
    name: str = ""
    provider: str = ""
    context_length: str = ""
    input_price: str = ""
    output_price: str = ""
    is_free: bool = False
    is_deprecated: bool = False
    description: str = ""
    url: str = ""


LOGIN_URL = "https://cloud.siliconflow.cn"
MODELS_DASHBOARD = "https://cloud.siliconflow.cn/me/models"
PUBLIC_MODELS = "https://www.siliconflow.com/zh/models"

# 调试文件路径
DEBUG_DIR = Path(__file__).parent.parent.parent / "debug"


def parse_price(price_str: str) -> float:
    """解析价格字符串，返回浮点数"""
    if not price_str:
        return -1.0
    s = price_str.strip().lower()

    # 免费标记
    if s in ("free", "$0", "0", "0.0", "0.00", "免费"):
        return 0.0

    # 匹配纯数字 0.xxxxx 格式（如 0.000000）
    if re.match(r'^0\.0+$', s):
        return 0.0

    # 匹配 $0.xx 或 $ 0.xx 格式
    m = re.search(r'\$?\s*([\d.]+)', s)
    if m:
        val = float(m.group(1))
        return val

    return -1.0


def is_free_model(inp: str, out: str) -> bool:
    """判断是否为免费模型：输入和输出价格都为0"""
    input_val = parse_price(inp)
    output_val = parse_price(out)
    return input_val == 0.0 and output_val == 0.0


async def scrape_dashboard(page: Page) -> List[ScrapedModel]:
    """从登录后的模型仪表板抓取所有模型和价格"""
    models: List[ScrapedModel] = []

    print("  正在加载模型仪表板...")
    try:
        await page.goto(MODELS_DASHBOARD, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
    except Exception as e:
        print(f"  导航到仪表板失败: {e}")
        return models

    # 滚动加载所有模型
    for i in range(20):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(800)
        if i % 5 == 0:
            print(f"  滚动加载中... ({i+1}/20)")

    # 保存调试信息
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    html = await page.content()
    with open(DEBUG_DIR / "dashboard_html.txt", "w", encoding="utf-8") as f:
        f.write(html)

    body_text = await page.evaluate("() => document.body.innerText")
    with open(DEBUG_DIR / "dashboard_text.txt", "w", encoding="utf-8") as f:
        f.write(body_text)

    print(f"  调试信息已保存到: {DEBUG_DIR}")

    # 从HTML中解析模型数据
    # 由于HTML中数据有转义引号，使用更宽松的匹配

    # 动态提取 providers：从HTML中找出所有 Provider/Model-Name 格式
    providers_match = re.findall(r'([a-zA-Z][a-zA-Z0-9_-]+)/[a-zA-Z0-9_.-]+', html)
    providers = list(set(providers_match))
    # 过滤掉明显不是provider的字符串
    providers = [p for p in providers if len(p) <= 20 and not p.startswith(('http', 'www'))]

    free_ids = set()
    idx = 0
    while True:
        idx = html.find('(Free)', idx)
        if idx == -1:
            break

        # 往前找最近的模型ID
        prefix = html[max(0, idx - 800):idx]
        for prov in providers:
            matches = re.findall(rf'{re.escape(prov)}/[a-zA-Z0-9_.-]+', prefix)
            if matches:
                free_ids.add(matches[-1])
                break

        idx += 1

    print(f"  通过 DisplayName (Free) 找到 {len(free_ids)} 个免费模型")

    # 方法2: 找所有模型ID（用于后续详情页检查）
    # 从页面文本提取模型ID格式，同时检测 Deprecated 标签
    lines = body_text.split('\n')
    deprecated_ids = set()
    all_model_ids = set()

    for i, line in enumerate(lines):
        line = line.strip()
        # 检测 Deprecated 标签（出现在模型ID之前的行）
        if line == 'Deprecated':
            # 下一行可能是模型ID，标记为废弃
            continue

        # 匹配 Provider/Model-Name 格式
        if '/' in line and not line.startswith(('http', 'www', '查看', '点击')):
            for prov in providers:
                if line.startswith(prov + '/') or line.startswith(prov.lower() + '/'):
                    # 验证格式
                    if re.match(rf'^{prov}/[a-zA-Z0-9_.-]+$', line) or \
                       re.match(rf'^{prov.lower()}/[a-zA-Z0-9_.-]+$', line):
                        all_model_ids.add(line)
                        # 检查前一行是否是 Deprecated
                        if i > 0 and lines[i-1].strip() == 'Deprecated':
                            deprecated_ids.add(line)
                        break

    print(f"  从页面文本提取到 {len(all_model_ids)} 个模型ID")
    print(f"  其中废弃模型: {len(deprecated_ids)} 个")

    # 创建模型对象
    for model_id in all_model_ids:
        model = ScrapedModel(id=model_id)
        if "/" in model_id:
            model.provider = model_id.split("/")[0]

        model.is_free = model_id in free_ids
        if model.is_free:
            model.input_price = "0"
            model.output_price = "0"

        # 标记废弃模型
        if model_id in deprecated_ids:
            model.is_deprecated = True

        models.append(model)

    print(f"  仪表板共发现 {len(models)} 个模型")
    free_count = sum(1 for m in models if m.is_free)
    print(f"  其中明确免费: {free_count} 个")

    return models


async def collect_slugs_from_public(page: Page) -> List[str]:
    """从公开模型页收集slug列表"""
    await page.goto(PUBLIC_MODELS, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(3000)

    # 滚动加载
    for _ in range(15):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(600)

    html = await page.content()
    # 提取模型链接
    slugs = list(set(re.findall(r'/models/([\w-]+)', html)))
    # 过滤非模型链接
    invalid = {'audio', 'video', 'image', 'featured', 'serverless', 'llm', 'vision', 'embeddings', 'rerank'}
    slugs = [s for s in slugs if s not in invalid and not s.startswith('api-')]
    return sorted(slugs)


async def scrape_model_detail(page: Page, slug: str) -> ScrapedModel:
    """抓取公开模型详情页"""
    url = f"{PUBLIC_MODELS}/{slug}"
    model = ScrapedModel(id=slug, url=url)

    try:
        await page.goto(url, wait_until="networkidle", timeout=15000)
        await page.wait_for_timeout(1500)
    except:
        return model

    body_text = await page.evaluate("() => document.body.innerText")

    # 提取名称
    try:
        h1 = await page.query_selector("h1")
        if h1:
            model.name = (await h1.inner_text()).strip()
    except:
        pass

    # 提取价格 - 格式: $ 0.06 / M Tokens
    prices = re.findall(r'\$\s*([\d.]+)\s*/\s*M\s*Tokens?', body_text, re.IGNORECASE)
    if len(prices) >= 2:
        model.input_price = prices[0]
        model.output_price = prices[1]
    elif len(prices) == 1:
        model.input_price = prices[0]
        model.output_price = prices[0]

    # 检测免费标记: 0.000000k/token
    if re.search(r'0\.0+\s*k\s*/\s*token', body_text, re.IGNORECASE):
        model.input_price = "0"
        model.output_price = "0"

    # 上下文长度
    m = re.search(r'(?:上下文长度|Context Length|Total Context|上下文)[:\s]*(\d+[\d,Kk]*)', body_text, re.IGNORECASE)
    if m:
        model.context_length = m.group(1)

    # 提供商
    m = re.search(r'(?:提供者|Provider)[:\s]*(\S+)', body_text, re.IGNORECASE)
    if m:
        model.provider = m.group(1)

    model.is_free = is_free_model(model.input_price, model.output_price)
    return model


async def check_model_pricing_in_dashboard(page: Page, model_id: str) -> ScrapedModel:
    """在登录后的仪表板中点击模型卡片检查价格

    价格信息在点击卡片后的侧边栏中显示，格式如 ¥0.000000/ K Tokens
    """
    model = ScrapedModel(id=model_id)

    try:
        # 确保在仪表板页面
        current_url = page.url
        if not current_url.startswith(MODELS_DASHBOARD):
            await page.goto(MODELS_DASHBOARD, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

        # 查找包含模型ID的元素并点击
        selector = f'text="{model_id}"'
        element = await page.query_selector(selector)

        if element:
            # 点击进入详情侧边栏
            await element.click()
            await page.wait_for_timeout(1500)

            # 获取侧边栏内容
            body_text = await page.evaluate("() => document.body.innerText")

            # 检测免费价格格式: ¥0.000000/ K Tokens
            if re.search(r'¥?\s*0\.0+\s*/\s*K?\s*Tokens?', body_text, re.IGNORECASE):
                model.input_price = "0"
                model.output_price = "0"
                model.is_free = True
            elif re.search(r'free-text-model\.online', body_text, re.IGNORECASE):
                model.input_price = "0"
                model.output_price = "0"
                model.is_free = True
            else:
                # 尝试解析其他价格格式
                prices = re.findall(r'¥\s*([\d.]+)\s*/\s*K?\s*Tokens?', body_text, re.IGNORECASE)
                if len(prices) >= 2:
                    model.input_price = prices[0]
                    model.output_price = prices[1]
                    model.is_free = is_free_model(model.input_price, model.output_price)
                elif len(prices) == 1:
                    model.input_price = prices[0]
                    model.output_price = prices[0]
                    model.is_free = is_free_model(model.input_price, model.output_price)

            # 关闭侧边栏
            try:
                close_btn = await page.query_selector('[class*="close"], [aria-label="Close"], button.close, .ant-drawer-close')
                if close_btn:
                    await close_btn.click()
                else:
                    await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
            except:
                await page.reload(wait_until="networkidle", timeout=15000)
                await page.wait_for_timeout(1000)

    except Exception as e:
        print(f"    [WARN] 检查 {model_id} 价格时出错: {type(e).__name__}: {e}")

    if "/" in model_id:
        model.provider = model_id.split("/")[0]

    return model


async def run_scrape(
    headless: bool = False,
    max_models: int = 0,
    need_login: bool = True,
    check_details: bool = True,
) -> List[ScrapedModel]:
    """执行抓取

    Args:
        headless: 无头模式
        max_models: 最大抓取数量
        need_login: 是否需要登录
        check_details: 是否检查详情页价格（用于发现没有Free标签但实际免费的模型）
    """
    all_models: List[ScrapedModel] = []
    seen_ids = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        ctx = await browser.new_context(viewport={"width": 1400, "height": 900}, locale="zh-CN")
        page = await ctx.new_page()

        if need_login:
            print("\n正在打开登录页面...")
            print("请在浏览器中完成登录，登录成功后回到终端按回车继续。")
            await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, input, "\n>>> 登录完成后按回车继续 <<<\n")

            # 登录后等待一下确保session生效
            await page.wait_for_timeout(2000)

        # Step 1: 从登录后的仪表板抓取（含定价信息）
        print("\n[1/3] 从模型仪表板抓取...")
        dashboard_models = await scrape_dashboard(page)
        for m in dashboard_models:
            if m.id and m.id not in seen_ids:
                seen_ids.add(m.id)
                all_models.append(m)

        # Step 2: 检查仪表板模型的详情页价格（仅对非免费、非废弃模型）
        if check_details and need_login:
            # 过滤掉已废弃的模型（废弃模型不需要检查）
            non_free_models = [m for m in all_models if not m.is_free and not m.is_deprecated]
            if non_free_models:
                print(f"\n[2/3] 检查 {len(non_free_models)} 个非免费模型的详情页价格...")
                # 限制检查数量，避免太慢
                check_limit = min(len(non_free_models), 50)
                found_free = 0

                for i, model in enumerate(non_free_models[:check_limit]):
                    try:
                        detail = await check_model_pricing_in_dashboard(page, model.id)
                        if detail.is_free:
                            model.is_free = True
                            model.input_price = "0"
                            model.output_price = "0"
                            found_free += 1
                            print(f"  [{i+1}/{check_limit}] {model.id} -> 发现免费!")
                        else:
                            print(f"  [{i+1}/{check_limit}] {model.id}")
                    except Exception as e:
                        print(f"  [{i+1}/{check_limit}] {model.id} 检查失败")

                    await page.wait_for_timeout(300)

                print(f"  通过详情页发现 {found_free} 个免费模型")

        # Step 3: 从公开页面补充模型
        print("\n[3/3] 从公开模型页补充...")
        try:
            slugs = await collect_slugs_from_public(page)
            new_slugs = [s for s in slugs if s not in seen_ids]

            if max_models > 0:
                new_slugs = new_slugs[:max_models]

            if new_slugs:
                print(f"  发现 {len(new_slugs)} 个新模型，抓取详情...")
                for i, slug in enumerate(new_slugs):
                    try:
                        model = await scrape_model_detail(page, slug)
                        if model.id not in seen_ids:
                            seen_ids.add(model.id)
                            all_models.append(model)
                        label = " [FREE!]" if model.is_free else ""
                        print(f"  [{i+1}/{len(new_slugs)}] {slug}{label}")
                    except:
                        print(f"  [{i+1}/{len(new_slugs)}] {slug} ERROR")
                    await page.wait_for_timeout(300)
            else:
                print("  无新模型")
        except Exception as e:
            print(f"  补充抓取失败: {e}")

        await browser.close()

    return all_models


def save_results(models: List[ScrapedModel], output_path: Path) -> None:
    """保存结果"""
    free = [m for m in models if m.is_free]
    no_price = [m for m in models if not m.input_price]
    data = {
        "scrape_time": datetime.now().isoformat(),
        "total_models": len(models),
        "free_models_count": len(free),
        "no_price_count": len(no_price),
        "free_models": [asdict(m) for m in free],
        "all_models": [asdict(m) for m in models],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
