# skill-ds-websearch

一个仅依赖 Python 标准库的 Codex skill，通过 DeepSeek Search / Fetch API
搜索实时网页内容，或将单个网页抓取为 Markdown。

## 功能

- 搜索实时网页，返回标题、链接、摘要、站点、发布时间和相关性评分
- 支持 `site:`、`lang:`、`after:`、`before:` 等搜索语法
- 按 `rerank_score` 过滤低质量结果
- 抓取指定网页并输出 Markdown
- 输出结构化 JSON，便于其他程序继续处理

## 环境要求

- Python 3.8 或更高版本
- DeepSeek API Key

脚本不需要安装第三方 Python 包。

## 配置密钥

密钥只从进程环境变量读取，不写入源码、配置文件或 Git 仓库。优先使用：

```powershell
$env:DEEPSEEK_API_KEY = "<your-api-key>"
```

也兼容 `DEEPSEEK_KEY` 和 `DEEPSEEK_API_TOKEN`。仓库中的
[.env.example](.env.example) 仅用于说明变量名，脚本不会自动加载 `.env`。
不要在命令行参数、README、Issue 或截图中暴露真实密钥。

## 使用

在仓库根目录运行：

```powershell
python scripts/websearch.py search "DeepSeek 最新版本" --count 5
python scripts/websearch.py search "DeepSeek site:github.com after:2025" --brief
python scripts/websearch.py search "财经新闻" --min-score 1.5
python scripts/websearch.py search "Agent 框架" --json
python scripts/websearch.py fetch "https://example.com/article"
python scripts/websearch.py fetch "https://example.com/article" --out page.md
```

查看完整参数：

```powershell
python scripts/websearch.py --help
python scripts/websearch.py search --help
python scripts/websearch.py fetch --help
```

## 测试

测试只使用本地 mock，不会调用付费 API：

```powershell
python -m unittest discover -s tests -v
```

## 目录结构

```text
.
├── SKILL.md
├── README.md
├── agents/openai.yaml
├── docs/deepseek-search-fetch-api.md
├── references/api.md
├── scripts/websearch.py
└── tests/test_websearch.py
```

## 安全说明

- 源码中只出现环境变量名，不包含真实 API Key。
- `.env`、日志和常见本地输出已加入 `.gitignore`。
- 请求头中的密钥不会被打印或写入输出文件。
- 提交前应运行密钥扫描；如果密钥曾经进入 Git 历史，应立即在 DeepSeek
  控制台吊销并重新生成，而不是只删除当前文件。

## License

[MIT](LICENSE)
