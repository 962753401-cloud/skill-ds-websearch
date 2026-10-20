---
name: skill-ds-websearch
description: >-
  联网检索与网页抓取工具，基于 DeepSeek Search / Fetch API 搜索实时网络信息并返回结构化结果
  （标题、链接、摘要、站点、发布时间、权威性评分），或抓取单个网页返回 Markdown 正文。
  当用户需要联网搜索、查最新资讯/版本/价格/新闻、事实核对，或需要读取某个网页全文时使用。
  不要用于官方 OpenAI/Codex 文档（走 openai-docs skill），也不要用它做浏览器自动化。
license: MIT
---

# DeepSeek 联网检索

通过 DeepSeek Search / Fetch API 执行联网搜索与网页抓取，返回适合大模型引用的结构化结果。
完整接口规格（参数表、响应 schema、错误码、计费与限速）见
[references/api.md](references/api.md)，仅在排查接口问题或扩展功能时阅读。
网页原文资料整理见 [docs/deepseek-search-fetch-api.md](docs/deepseek-search-fetch-api.md)。

## 前置条件

- 环境变量 `DEEPSEEK_API_KEY`（或 `DEEPSEEK_KEY`、`DEEPSEEK_API_TOKEN`）已设置；
  API Key 从 https://platform.deepseek.com/api_keys 获取，禁止写入源码或配置文件
- 脚本仅依赖 Python 标准库，无需安装包

## 使用方式

在本 skill 目录下运行：

```bash
python scripts/websearch.py search "DeepSeek V4 模型 发布"            # 默认 10 条结果
python scripts/websearch.py search "最新版本" --count 5 --brief        # 只看短摘要
python scripts/websearch.py search "DeepSeek site:github.com after:2025" --content
python scripts/websearch.py search "财经新闻" --ori-question "今天有什么财经大事" --json
python scripts/websearch.py fetch https://example.com/article          # 抓网页正文（Markdown）
python scripts/websearch.py fetch https://example.com/article --out page.md
```

stdout 输出编号结果（标题、站点、发布时间、评分、链接、摘要/正文），stderr 输出本次
调用费用与限流提示。引用搜索结果时保留 `url`、`site_name` 和 `date`。

## 参数要点

### search

- `query` 上限 128 个 Unicode 字符；长问题改写成关键词组合，把限定条件写进 query
- 搜索语法（原样透传，可组合）：`site:`、`-site:`、`-词`、`-"短语"`、`"精确短语"`、
  `lang:zh,en`、`after:2025-01-01`、`before:2026-06-01`
- `--count`：1～50，默认 10
- `--content`：让接口连网页正文一起返回（`need_content`），响应体会明显变大
- `--brief`：打短摘要 `snippet`；默认打长摘要 `summary`（600～800 字符，更适合喂模型）
- `--min-score 1.5`：只保留 `rerank_score >= 1.5` 的优质结果；无意义 query 常返回
  `score≈0.2` 的低质结果，这类结果同样计费，建议先加阈值再引用
- `--ori-question`：附上触发搜索的用户原话，帮助理解搜索意图
- `--localization <IP>`：优先返回该 IP 所在地区的本地化结果

### fetch

- 需要完整网页正文时用 fetch，而不是 search 的 `--content`
- `url` 必须是含 host 的 HTTP/HTTPS 地址、不超过 8192 字符、不能带用户名密码
- 目标站点的反爬策略、内容类型都可能让 Fetch 返回 404
- `--out <文件>` 把 Markdown 正文直接落盘

## 费用与限速

- 计费按请求次数：每 1,000 次**成功**请求 5 元（单次约 0.005 元），与 `count` 无关
- 只有 HTTP 200 且有结果才计费：搜索无结果、抓取拿不到正文、失败或超时都不计费
- Search 与 Fetch 各自独立限速 5 QPS（按账号计），超限返回 HTTP 429

## 错误处理

- HTTP 408 / 429 / 5xx：等待后重试
- HTTP 402：账号余额不足，需先充值
- 其它 4xx：请求本身有问题，改请求再试，不要原样重试

脚本会把常见状态码的中文提示写到 stderr。
