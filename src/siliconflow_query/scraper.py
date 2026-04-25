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

# 滚动配置
MAX_SCROLLS_FULL = 8      # 全量抓取最大滚动次数
MAX_SCROLLS_LATEST = 5    # 增量抓取最大滚动次数

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
    """从登录后的模型仪表板抓取所有模型和价格

    使用结构化 HTML 解析直接从模型卡片提取信息：
    - Model ID (Provider/Model-Name 格式)
    - Provider
    - Description
    - Context Length (如 256K)
    - 废弃状态 (Deprecated 标签 + <del> 元素)
    - 限免状态 (紫色背景标签)
    """
    models: List[ScrapedModel] = []

    print("  正在加载模型仪表板...")
    try:
        await page.goto(MODELS_DASHBOARD, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
    except Exception as e:
        print(f"  导航到仪表板失败: {e}")
        return models

    # 滚动加载所有模型（智能滚动：检测高度不变就停）
    prev_height = 0
    for i in range(MAX_SCROLLS_FULL):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(300)
        # 检测滚动高度是否变化
        curr_height = await page.evaluate("document.body.scrollHeight")
        if curr_height == prev_height:
            print(f"  滚动完成（{i+1}次，高度不再变化）")
            break
        prev_height = curr_height
        if i % 2 == 0:
            print(f"  滚动加载中... ({i+1}/{MAX_SCROLLS_FULL})")

    # 保存调试信息
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    html = await page.content()
    with open(DEBUG_DIR / "dashboard_html.txt", "w", encoding="utf-8") as f:
        f.write(html)

    body_text = await page.evaluate("() => document.body.innerText")
    with open(DEBUG_DIR / "dashboard_text.txt", "w", encoding="utf-8") as f:
        f.write(body_text)

    print(f"  调试信息已保存到: {DEBUG_DIR}")

    # ===== 结构化解析：直接从模型卡片提取 =====

    # 查找所有模型卡片容器
    # 卡片结构: <div class="relative flex cursor-pointer flex-col justify-between overflow-hidden rounded-lg border">
    card_selector = 'div.relative.flex.cursor-pointer'
    cards = await page.query_selector_all(card_selector)

    print(f"  找到 {len(cards)} 个候选卡片元素")

    free_ids_from_tags = set()  # 从 DisplayName (Free) 标签识别的免费模型
    deprecated_ids = set()      # 废弃模型
    context_len_map = {}        # 从 JSON 提取的 contextLen 映射

    # ===== 从 JSON 数据提取免费模型 ID 和 contextLen =====
    # HTML 中 JSON 格式使用转义引号：\"DisplayName\":\"ModelName (Free)\"
    # 匹配：ModelName (Free) 然后往前找最近的 id 字段

    idx = 0
    while True:
        idx = html.find('(Free)', idx)
        if idx == -1:
            break
        # 往前找 JSON 块（最多 1000 字符）
        block_start = max(0, idx - 1000)
        block = html[block_start:idx + 200]

        # 优先从 JSON 的 id 字段直接提取（更精确）
        id_match = re.search(r'\\"id\\":\\"([^"\\\\]+)\\"', block)
        if id_match and '/' in id_match.group(1):
            free_ids_from_tags.add(id_match.group(1))
        else:
            # 回退：从文本中提取模型 ID
            id_matches = re.findall(r'([a-zA-Z0-9][a-zA-Z0-9_-]*/[a-zA-Z0-9_.-]+)', block)
            valid_ids = [m for m in id_matches
                         if not any(x in m for x in ['Model_LOGO', 'svg', 'oss-cn', 'aliyuncs'])
                         and len(m.split('/')[0]) <= 25
                         and len(m.split('/')[-1]) >= 3]
            if valid_ids:
                free_ids_from_tags.add(valid_ids[-1])

        idx += 1

    # 提取所有模型的 contextLen（从 JSON 数据）
    for match in re.finditer(r'\\"contextLen\\":(\d+)', html):
        ctx_val = match.group(1)
        # 往前找最近的模型 ID
        block = html[max(0, match.start() - 500):match.start()]
        id_match = re.search(r'\\"id\\":\\"([^"\\\\]+)\\"', block)
        if id_match and '/' in id_match.group(1):
            model_id = id_match.group(1)
        else:
            id_matches = re.findall(r'([a-zA-Z0-9][a-zA-Z0-9_-]*/[a-zA-Z0-9_.-]+)', block)
            valid_ids = [m for m in id_matches
                         if not any(x in m for x in ['Model_LOGO', 'svg', 'oss-cn'])
                         and len(m.split('/')[0]) <= 25]
            if valid_ids:
                model_id = valid_ids[-1]
            else:
                continue
        # 转换为 K 格式
        ctx_int = int(ctx_val)
        if ctx_int >= 1024:
            ctx_str = f"{ctx_int // 1024}K"
        else:
            ctx_str = str(ctx_int)
        context_len_map[model_id] = ctx_str

    print(f"  通过 DisplayName (Free) 标签找到 {len(free_ids_from_tags)} 个免费模型")
    print(f"  从 JSON 提取 {len(context_len_map)} 个模型的 contextLen")

    # 从每个卡片提取详细信息
    for card in cards:
        try:
            card_html = await card.inner_html()

            # 检测废弃状态: 有 Deprecated 标签 或 <del> 元素
            is_deprecated = 'Deprecated' in card_html or '<del>' in card_html

            # 检测限免状态
            is_limited_free = '限免' in card_html

            # 提取模型 ID
            # 格式: Provider/Model-Name 在 text-base 的 div 中
            # 废弃模型: <del>Provider/Model-Name</del>
            model_id = ""

            # 优先从 <del> 标签提取（废弃模型）
            del_elem = await card.query_selector('del')
            if del_elem:
                del_text = await del_elem.inner_text()
                del_text = del_text.strip()
                if '/' in del_text and re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*/[a-zA-Z0-9_.-]+$', del_text):
                    if not any(x in del_text for x in ['Model_LOGO', 'svg', 'oss-cn', '.com']):
                        model_id = del_text

            # 否则从 text-base div 提取
            if not model_id:
                id_elem = await card.query_selector('div.text-base, div.w-full.truncate')
                if id_elem:
                    id_text = await id_elem.inner_text()
                    id_text = id_text.strip()
                    # 移除可能的 "Deprecated" 前缀
                    if id_text.startswith('Deprecated'):
                        id_text = id_text.replace('Deprecated', '').strip()
                    # 验证是模型 ID 格式，排除 URL 片段
                    if '/' in id_text and re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*/[a-zA-Z0-9_.-]+$', id_text):
                        if not any(x in id_text for x in ['Model_LOGO', 'svg', 'oss-cn', '.com']):
                            model_id = id_text

            # 如果没找到，从卡片 HTML 正则提取
            if not model_id:
                m = re.search(r'([a-zA-Z0-9][a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)', card_html)
                if m:
                    candidate = f"{m.group(1)}/{m.group(2)}"
                    # 过滤非模型 ID
                    if not any(x in candidate for x in ['Model_LOGO', 'svg', 'oss-cn', '.com']):
                        model_id = candidate

            if not model_id:
                continue

            # 提取 Provider (在 span.truncate 中，通常是模型 ID 的第一部分)
            provider = model_id.split('/')[0] if '/' in model_id else ""

            # 提取 Provider 显示名称 (可能不同于 ID 中的)
            provider_elem = await card.query_selector('span.truncate')
            if provider_elem:
                provider_text = await provider_elem.inner_text()
                provider_text = provider_text.strip()
                if provider_text and len(provider_text) <= 20:
                    # 保存显示名称（可能用于 description 补充）
                    pass

            # 提取描述 (line-clamp-2 的 div)
            description = ""
            desc_elem = await card.query_selector('div.line-clamp-2, div.ant-typography.line-clamp-2')
            if desc_elem:
                desc_text = await desc_elem.inner_text()
                description = desc_text.strip()[:200]

            # 提取上下文长度
            # 优先使用从 JSON 提取的 contextLen，其次从卡片 badge 提取
            context_length = context_len_map.get(model_id, "")
            if not context_length:
                # 从卡片 badge 提取（如 256K, 128K 等数字+K 的 badge）
                badges = await card.query_selector_all('div.flex.items-center.rounded')
                for badge in badges:
                    badge_text = await badge.inner_text()
                    badge_text = badge_text.strip()
                    # 匹配上下文长度格式: 数字 + K 或 M
                    if re.match(r'^\d+[KM]$', badge_text, re.IGNORECASE):
                        context_length = badge_text
                        break

                # 如果没找到，从卡片 HTML 正则提取
                if not context_length:
                    m = re.search(r'>(\d+[KM])<', card_html, re.IGNORECASE)
                    if m:
                        context_length = m.group(1)

            # 判断是否免费
            is_free = model_id in free_ids_from_tags or is_limited_free

            # 创建模型对象
            model = ScrapedModel(
                id=model_id,
                name=model_id.split('/')[-1] if '/' in model_id else model_id,
                provider=provider,
                context_length=context_length,
                description=description,
                is_free=is_free,
                is_deprecated=is_deprecated,
                input_price="0" if is_free else "",
                output_price="0" if is_free else "",
            )

            if is_deprecated:
                deprecated_ids.add(model_id)

            models.append(model)

        except Exception as e:
            print(f"  [WARN] 解析卡片失败: {type(e).__name__}")
            continue

    # 去重
    seen_ids = set()
    unique_models = []
    for m in models:
        if m.id and m.id not in seen_ids:
            seen_ids.add(m.id)
            unique_models.append(m)
    models = unique_models

    print(f"  结构化解析发现 {len(models)} 个模型")
    free_count = sum(1 for m in models if m.is_free)
    deprecated_count = sum(1 for m in models if m.is_deprecated)
    print(f"  其中免费模型: {free_count} 个")
    print(f"  废弃模型: {deprecated_count} 个")

    # 有描述的模型数量
    with_desc = sum(1 for m in models if m.description)
    with_ctx = sum(1 for m in models if m.context_length)
    print(f"  有描述: {with_desc} 个, 有上下文长度: {with_ctx} 个")

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
    except Exception:
        # 页面加载失败时返回空模型对象
        return model

    body_text = await page.evaluate("() => document.body.innerText")

    # 提取名称
    try:
        h1 = await page.query_selector("h1")
        if h1:
            model.name = (await h1.inner_text()).strip()
    except Exception:
        # 提取失败时忽略，名称保持为空
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
            # 点击进入详情侧边栏（优化：减少等待时间）
            await element.click()
            await page.wait_for_timeout(500)  # 优化：800ms -> 500ms

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

            # 提取上下文长度
            ctx_match = re.search(r'(?:上下文|Context|Total Context)[:\s]*(\d+[\d,Kk]*)', body_text, re.IGNORECASE)
            if ctx_match:
                model.context_length = ctx_match.group(1)

            # 提取描述
            desc_match = re.search(r'(?:简介|Description|模型简介)[:\s]*([^\n]+)', body_text, re.IGNORECASE)
            if desc_match:
                model.description = desc_match.group(1).strip()[:100]

            # 关闭侧边栏（优化：减少等待）
            try:
                close_btn = await page.query_selector('[class*="close"], [aria-label="Close"], button.close, .ant-drawer-close')
                if close_btn:
                    await close_btn.click()
                else:
                    await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)
            except Exception:
                # 关闭按钮查找失败，尝试键盘关闭
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)

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

        # Step 2: 全量检查仪表板模型的详情页价格（仅对非免费、非废弃模型）
        if check_details and need_login:
            # 过滤掉已废弃的模型（废弃模型不需要检查）
            non_free_models = [m for m in all_models if not m.is_free and not m.is_deprecated]
            if non_free_models:
                print(f"\n[2/3] 全量检查非免费模型价格（{len(non_free_models)}个）...")
                found_free = 0

                for i, model in enumerate(non_free_models):
                    try:
                        detail = await check_model_pricing_in_dashboard(page, model.id)
                        if detail.is_free:
                            model.is_free = True
                            model.input_price = "0"
                            model.output_price = "0"
                            if detail.context_length:
                                model.context_length = detail.context_length
                            if detail.description:
                                model.description = detail.description
                            found_free += 1
                            print(f"  [{i+1}/{len(non_free_models)}] {model.id} -> FREE!")
                        else:
                            print(f"  [{i+1}/{len(non_free_models)}] {model.id}")
                    except Exception as e:
                        print(f"  [{i+1}/{len(non_free_models)}] {model.id} ERROR")

                    await page.wait_for_timeout(150)  # 优化：200ms -> 150ms

                print(f"  通过详情页发现 {found_free} 个免费模型")

        await browser.close()

    return all_models


async def run_scrape_latest(
    headless: bool = False,
    days: int = 90,
) -> List[ScrapedModel]:
    """执行增量抓取 - 只抓取近 N 天新增的免费模型

    通过页面的时间筛选器过滤模型，然后检查价格

    Args:
        headless: 无头模式
        days: 时间范围（天数），默认90天，支持30或90
    """
    all_models: List[ScrapedModel] = []
    seen_ids = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        ctx = await browser.new_context(viewport={"width": 1400, "height": 900}, locale="zh-CN")
        page = await ctx.new_page()

        print("\n正在打开登录页面...")
        print("请在浏览器中完成登录，登录成功后回到终端按回车继续。")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, input, "\n>>> 登录完成后按回车继续 <<<\n")

        # 登录后等待确保 session 生效
        await page.wait_for_timeout(2000)

        print("\n正在加载模型仪表板...")
        await page.goto(MODELS_DASHBOARD, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # 第一步：点击"展开筛选器"按钮
        print("  正在展开筛选器...")
        try:
            # 查找"展开筛选器"按钮
            expand_btn = await page.query_selector('button:has-text("展开筛选器")')
            if expand_btn:
                await expand_btn.click()
                await page.wait_for_timeout(800)
                print("  ✓ 已展开筛选器")
            else:
                # 备用选择器
                expand_btn = await page.query_selector('text="展开筛选器"')
                if expand_btn:
                    await expand_btn.click()
                    await page.wait_for_timeout(800)
                    print("  ✓ 已展开筛选器")
                else:
                    print("  [INFO] 筛选器可能已展开")
        except Exception as e:
            print(f"  [WARN] 展开筛选器失败: {e}")

        # 第二步：应用时间筛选
        print(f"  正在应用「近{days}天」筛选条件...")

        time_filter_applied = False
        filter_text = f"近 {days} 天" if days in [30, 90] else f"近{days}天"

        try:
            # 查找并点击"近 N 天"筛选按钮
            # 结构: div.flex.h-[24px].cursor-pointer 包含 div > "近 90 天"
            filter_btns = await page.query_selector_all('div.flex.h-\\[24px\\].cursor-pointer')
            for btn in filter_btns:
                try:
                    text = await btn.inner_text()
                    if text.strip() == filter_text:
                        await btn.click()
                        await page.wait_for_timeout(800)
                        time_filter_applied = True
                        print(f"  ✓ 已选择「{filter_text}」筛选")
                        break
                except Exception:
                    continue

            if not time_filter_applied:
                # 备用方案：直接用文本选择器
                try:
                    filter_btn = await page.query_selector(f'text="{filter_text}"')
                    if filter_btn:
                        await filter_btn.click()
                        await page.wait_for_timeout(800)
                        time_filter_applied = True
                        print(f"  ✓ 已选择「{filter_text}」筛选（备用方式）")
                except Exception:
                    pass

        except Exception as e:
            print(f"  [WARN] 应用时间筛选失败: {e}")

        if not time_filter_applied:
            print("  [WARN] 未找到时间筛选选项，将使用页面默认排序")

        # 等待页面重新加载
        await page.wait_for_timeout(1500)

        # 滚动加载所有可见模型
        print("  正在滚动加载模型...")
        prev_height = 0
        for i in range(MAX_SCROLLS_LATEST):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(400)
            curr_height = await page.evaluate("document.body.scrollHeight")
            if curr_height == prev_height:
                break
            prev_height = curr_height

        # 获取页面 HTML
        html = await page.content()
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_DIR / "latest_html.txt", "w", encoding="utf-8") as f:
            f.write(html)

        # 查找所有模型卡片并检查价格
        print("  正在检查模型价格...")
        card_selector = 'div.relative.flex.cursor-pointer'
        cards = await page.query_selector_all(card_selector)
        print(f"  找到 {len(cards)} 个候选卡片")

        for i, card in enumerate(cards):
            try:
                card_html = await card.inner_html()
                card_text = await card.inner_text()

                # 提取模型 ID
                model_id = ""
                id_match = re.search(r'([a-zA-Z0-9][a-zA-Z0-9_-]*/[a-zA-Z0-9_.-]+)', card_text)
                if id_match:
                    candidate = id_match.group(1)
                    if not any(x in candidate for x in ['Model_LOGO', 'svg', 'oss-cn', '.com']):
                        model_id = candidate

                if not model_id:
                    print(f"  [{i+1}/{len(cards)}] 跳过（无法提取模型ID）")
                    continue

                # 检查是否废弃
                is_deprecated = 'Deprecated' in card_html or '<del>' in card_html

                print(f"  [{i+1}/{len(cards)}] 检查 {model_id}...")

                # 点击卡片检查价格
                await card.click()
                await page.wait_for_timeout(400)

                # 获取侧边栏内容
                body_text = await page.evaluate("() => document.body.innerText")

                # 检测免费价格
                is_free = False
                if re.search(r'¥?\s*0\.0+\s*/\s*K?\s*Tokens?', body_text, re.IGNORECASE):
                    is_free = True
                elif re.search(r'free-text-model\.online', body_text, re.IGNORECASE):
                    is_free = True

                # 提取上下文长度
                context_length = ""
                ctx_match = re.search(r'(?:上下文|Context|Total Context)[:\s]*(\d+[\d,Kk]*)', body_text, re.IGNORECASE)
                if ctx_match:
                    context_length = ctx_match.group(1)

                # 关闭侧边栏
                try:
                    close_btn = await page.query_selector('[class*="close"], [aria-label="Close"], button.close, .ant-drawer-close')
                    if close_btn:
                        await close_btn.click()
                    else:
                        await page.keyboard.press("Escape")
                    await page.wait_for_timeout(200)
                except Exception:
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(200)

                if is_free and model_id not in seen_ids:
                    seen_ids.add(model_id)
                    model = ScrapedModel(
                        id=model_id,
                        name=model_id.split('/')[-1],
                        provider=model_id.split('/')[0],
                        context_length=context_length,
                        is_free=True,
                        is_deprecated=is_deprecated,
                        input_price="0",
                        output_price="0",
                    )
                    all_models.append(model)
                    print(f"  [{i+1}/{len(cards)}] {model_id} -> FREE!")
                else:
                    print(f"  [{i+1}/{len(cards)}] {model_id} -> 收费")

            except Exception as e:
                print(f"  [{i+1}/{len(cards)}] ERROR: {type(e).__name__}: {e}")
                continue

        await browser.close()

    print(f"\n增量抓取完成! 发现 {len(all_models)} 个免费模型")
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
