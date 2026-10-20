# DeepSeek Search / Fetch API 参考

来源：DeepSeek API 文档（https://api-docs.deepseek.com/zh-cn/guides/search）。

## 端点与认证

```
POST https://api.deepseek.com/v1/tools/search
POST https://api.deepseek.com/v1/tools/fetch
Authorization: Bearer <DeepSeek API Key>
Content-Type: application/json
```

Search 与 Fetch 使用同一个 DeepSeek API Key（https://platform.deepseek.com/api_keys）。

## Search 请求参数

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `query` | string | 是 | - | 搜索词，1～128 个 Unicode 字符，不能全为空白，支持搜索语法 |
| `count` | integer | 否 | `10` | 返回条数，1～50 |
| `ori_question` | string | 否 | - | 触发搜索的用户原始问题，1～128 字符，传 `null` 视为未提供 |
| `localization` | string | 否 | `""` | 用于优先返回本地化搜索结果的 IP 地址 |
| `need_content` | boolean | 否 | `false` | 是否在 `content` 返回网页正文；为 false 时恒为空字符串 |

未知字段会被忽略。

## 搜索语法

| 操作符 | 示例 | 说明 |
|---|---|---|
| `site:` | `DeepSeek site:github.com` | 限定站点，多个用空格加 `OR`，如 `site:github.com OR site:huggingface.co` |
| `-site:` | `DeepSeek -site:example.com` | 排除站点，多个用空格分隔 |
| `-` | `DeepSeek -广告` | 排除含指定关键词的网页 |
| `-"..."` | `DeepSeek -"release notes"` | 排除含指定短语的网页 |
| `"..."` | `DeepSeek "精确短语"` | 精确匹配短语 |
| `lang:` | `DeepSeek lang:zh,en` | 限定语言，逗号分隔 |
| `after:` | `DeepSeek after:2025` / `after:2025-01-01` | 限定发布时间之后 |
| `before:` | `DeepSeek before:2026` / `before:2026-06-01` | 限定发布时间之前 |

## Search 响应字段

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `results[]` | object[] | 必填 | 无匹配结果时为空数组 |
| `results[].rerank_score` | number | `<= 3` | 排序分数 0～3，`>= 1.5` 为优质结果 |
| `results[].title` | string | 必填 | 标题 |
| `results[].url` | string | 必填 | 结果链接 |
| `results[].snippet` | string | 必填 | 短摘要，通常 100～200 字符，适合前端展现 |
| `results[].summary` | string | 必填 | 长摘要，通常 600～800 字符，适合给模型阅读 |
| `results[].content` | string | 必填 | 网页正文，`need_content=false` 或正文缺失时为空字符串 |
| `results[].site_name` | string \| null | 可能为 null | 站点名称 |
| `results[].site_icon` | string \| null | 可能为 null | 站点图标 URL |
| `results[].date` | string \| null | 可能为 null | 发布时间，UTC 的 RFC 3339 |
| `results[].authority` | integer | `-1 <= x <= 4` | 网页权威性，`>= 3` 为极权威，`-1` 表示未知 |

## Fetch 请求与响应

请求：`url`（string，必填）——含 host 的 HTTP/HTTPS 地址，不超过 8192 字符，不能带用户名或密码。

响应：

| 字段 | 类型 | 说明 |
|---|---|---|
| `title` | string | 页面标题，缺失时为空字符串 |
| `content` | string | 抓取后的 Markdown 正文 |

Fetch 的结果受目标站点的可用性和访问策略影响。

## 错误

错误响应为 OpenAI 兼容格式，`param` 恒为 `null`：

```json
{"error": {"message": "'count' must be between 1 and 50", "type": "invalid_request_error", "param": null, "code": "invalid_request_error"}}
```

| 状态码 | 含义 |
|---|---|
| 400 | 请求头或请求体不合法（含 JSON 格式错误、字段值无效） |
| 401 | API Key 缺失或无效 |
| 402 | 账号余额不足 |
| 403 | Fetch 被安全策略拒绝 |
| 404 | Fetch 拿不到可用网页内容（URL 不可用、被站点拦截、内容类型不支持、无可提取正文） |
| 408 | 读取请求体超时 |
| 413 | 请求体超过大小限制 |
| 429 | 超过 Search 或 Fetch 的 QPS 限制 |
| 500 | 服务器内部错误 |
| 504 | 下游请求超时 |

408 / 429 / 5xx 等待后重试；402 先充值；其它 4xx 不改请求不要重试。

## 计费与限速

| API | 计费单位 | 价格 | QPS |
|---|---|---|---|
| Search | 每 1,000 次成功请求 | 5 元 | 5 |
| Fetch | 每 1,000 次成功请求 | 5 元 | 5 |

只有 HTTP 200 且产生结果（Search `results` 非空、Fetch 有正文）才计费；`count` 不影响价格。
QPS 按账号粒度计算，与使用哪个 API Key 无关，并与模型并发限制相互独立。Fetch 另有目标域名级 QPS 限制。

DeepSeek Harness / Claude Code / Codex 里通过服务端工具调用访问的 Search/Fetch 目前不计费，
自北京时间 2026-11-01 00:00 起按次收费。
