# 硅基流动免费模型筛选工具 (SiliconFlow Query)

一个命令行工具，帮助您发现和选择硅基流动(SiliconFlow)平台上的免费模型。

## 功能特性

- 列出所有免费模型及其详细信息
- 按提供商、类型、能力筛选模型
- 搜索模型
- 显示模型详情（上下文长度、参数量、能力等）
- 从官网自动抓取最新免费模型（需登录）
- 验证模型可用性（需要API Key）

## 命令参考

<!-- AUTO-GENERATED -->
| 命令 | 描述 |
|------|------|
| `sfq list` | 列出所有免费模型 |
| `sfq show <model_id>` | 显示模型详情 |
| `sfq search <query>` | 搜索模型 |
| `sfq providers` | 列出所有提供商 |
| `sfq capabilities` | 列出所有能力标签 |
| `sfq scrape` | 从官网抓取模型定价信息 |
| `sfq update` | 从抓取结果更新本地数据库 |
| `sfq verify` | 验证模型可用性（需API Key） |
| `sfq info` | 显示工具信息 |
<!-- /AUTO-GENERATED -->

## 安装

```bash
# 克隆或进入项目目录
cd siliconflow-query

# 安装
pip install -e .
```

## 环境变量

<!-- AUTO-GENERATED -->
| 变量 | 必需 | 描述 | 示例 |
|------|------|------|------|
| `SILICONFLOW_API_KEY` | 可选 | SiliconFlow API密钥，用于 `verify` 命令验证模型可用性 | `sk-xxxxx` |
<!-- /AUTO-GENERATED -->

## 使用方法

### 查看帮助

```bash
sfq --help
```

### 列出所有免费模型

```bash
# 基本列表
sfq list

# 按提供商筛选
sfq list --provider Qwen

# 按模型类型筛选
sfq list --type chat

# 按最小上下文长度筛选
sfq list --min-context 16384

# 按能力筛选
sfq list --capability chinese

# 排序
sfq list --sort context
```

### 显示模型详情

```bash
sfq show Qwen/Qwen2-7B-Instruct
```

### 搜索模型

```bash
sfq search qwen
sfq search glm
```

### 列出提供商

```bash
sfq providers
```

### 列出能力标签

```bash
sfq capabilities
```

### 从官网抓取免费模型

自动登录并从 SiliconFlow 官网抓取最新免费模型信息：

```bash
# 显示浏览器，等待登录后抓取（推荐）
sfq scrape
<img width="392" height="305" alt="image" src="https://github.com/user-attachments/assets/ddab468c-7c93-4c8f-a497-4a9950f4c90c" />


# 无头模式（需先登录过）
sfq scrape --headless

# 跳过登录（可能无法获取完整定价）
sfq scrape --skip-login

# 跳过详情页价格检查（更快但不完整）
sfq scrape --skip-detail-check

# 限制抓取数量
sfq scrape --max 50
```

### 更新本地数据库

将抓取结果更新到本地数据库：

```bash
sfq update
# 或指定输入文件
sfq update --input scraped_models.json
```

### 验证模型可用性

需要先设置API Key：

```bash
# 方法1: 环境变量
export SILICONFLOW_API_KEY=your_api_key_here

# 方法2: 创建 .env 文件
cp .env.example .env
# 编辑 .env 文件填入你的API Key
```

然后运行：

```bash
sfq verify
```

## 当前免费模型

数据库包含 21+ 个免费模型，使用以下命令查看完整列表：

```bash
sfq list
```

部分热门免费模型示例：

| 模型 | 参数 | 提供商 |
|------|------|--------|
| Qwen/Qwen3-8B | 8B | 通义千问 |
| Qwen/Qwen2.5-7B-Instruct | 7B | 通义千问 |
| deepseek-ai/DeepSeek-R1-Distill-Qwen-7B | 7B | DeepSeek |
| THUDM/glm-4-9b-chat | 9B | 智谱AI |
| internlm/internlm2_5-7b-chat | 7B | 书生浦语 |

## 注意事项

- 免费模型有速率限制，请查阅官方文档
- 免费模型列表可能随时调整，以官网最新公告为准
- 免费模型的输入输出可能用于训练
- 建议仅用于开发和测试，生产环境考虑付费模型

## 数据来源

- **官网抓取**：使用 `sfq scrape` 从 SiliconFlow 官网自动抓取
- [SiliconFlow官方模型列表](https://cloud.siliconflow.cn/me/models)

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest
```

## 许可证

MIT
