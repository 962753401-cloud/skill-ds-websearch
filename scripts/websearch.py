#!/usr/bin/env python3
"""Search the web and fetch pages with the DeepSeek Search / Fetch API."""

import argparse
import ipaddress
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://api.deepseek.com"
SEARCH_URL = BASE_URL + "/v1/tools/search"
FETCH_URL = BASE_URL + "/v1/tools/fetch"

REQUEST_TIMEOUT_SECONDS = 60
MAX_QUERY_CHARS = 128
MAX_ORI_QUESTION_CHARS = 128
MAX_URL_CHARS = 8192

# Search / Fetch: 5 CNY per 1,000 successful requests; failures and empty
# results are not billed, so this is the cost of one billed call.
PRICE_PER_CALL = 0.005

KEY_ENV_VARS = ("DEEPSEEK_API_KEY", "DEEPSEEK_KEY", "DEEPSEEK_API_TOKEN")

ERROR_HINTS = {
    400: "请求头或请求体不合法，检查 JSON 与字段取值",
    401: "API Key 缺失或无效，检查 DEEPSEEK_API_KEY",
    402: "账号余额不足，充值后重试",
    403: "Fetch 请求被安全策略拒绝",
    404: "Fetch 拿不到可用网页内容：URL 不可用、被站点拦截、内容类型不支持或无可提取正文",
    408: "读取请求体超时，稍后重试",
    413: "请求体超过大小限制",
    429: "超过 QPS 限制（Search / Fetch 各 5 QPS，按账号计），等待后重试",
    500: "服务器内部错误，稍后重试",
    504: "下游请求超时，稍后重试",
}


def fail(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def resolve_api_key(environ=None):
    env = os.environ if environ is None else environ
    for name in KEY_ENV_VARS:
        value = env.get(name, "").strip()
        if not value:
            continue
        if "\r" in value or "\n" in value:
            fail(f"{name} contains invalid line breaks")
        return value
    return None


def decode_json_object(raw, source):
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"{source} returned invalid JSON: {exc}")
    if not isinstance(payload, dict):
        fail(f"{source} returned JSON that is not an object")
    return payload


def extract_error_message(detail):
    try:
        payload = json.loads(detail)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    message = error.get("message")
    return message if isinstance(message, str) and message else None


def post_json(url, api_key, body):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            return decode_json_object(resp.read(), "API")
    except urllib.error.HTTPError as exc:
        detail = exc.read(8192).decode("utf-8", errors="replace").strip()
        message = extract_error_message(detail)
        hint = ERROR_HINTS.get(exc.code)
        text = f"HTTP {exc.code}: {message or detail or exc.reason}"
        fail(f"{text} ({hint})" if hint else text)
    except urllib.error.URLError as exc:
        fail(f"request failed: {exc.reason}")


def build_search_body(args):
    query = args.query.strip()
    if not query:
        fail("query must not be blank")
    if len(args.query) > MAX_QUERY_CHARS:
        fail(
            f"query is {len(args.query)} characters; the API allows "
            f"{MAX_QUERY_CHARS}. Rewrite it as shorter keywords and move "
            "filters into site:/lang:/after:/before:"
        )
    if not 1 <= args.count <= 50:
        fail(f"count must be 1-50, got {args.count}")
    if args.min_score is not None:
        if not math.isfinite(args.min_score) or not 0 <= args.min_score <= 3:
            fail("min-score must be a finite number from 0 to 3")

    body = {"query": query, "count": args.count, "need_content": args.content}

    if args.ori_question is not None:
        ori_question = args.ori_question.strip()
        if not ori_question:
            fail("ori-question must not be blank when supplied")
        if len(ori_question) > MAX_ORI_QUESTION_CHARS:
            fail(
                f"ori-question is {len(ori_question)} characters; "
                f"the API allows {MAX_ORI_QUESTION_CHARS}"
            )
        body["ori_question"] = ori_question

    if args.localization is not None:
        localization = args.localization.strip()
        if localization:
            try:
                ipaddress.ip_address(localization)
            except ValueError:
                fail("localization must be a valid IPv4 or IPv6 address")
            body["localization"] = localization

    return query, body


def normalize_fetch_url(raw_url):
    url = raw_url.strip()
    if not url:
        fail("url must not be blank")
    if len(url) > MAX_URL_CHARS:
        fail(f"url is {len(url)} characters; the API allows {MAX_URL_CHARS}")

    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError as exc:
        fail(f"url is invalid: {exc}")

    if parsed.scheme.lower() not in ("http", "https"):
        fail("url must be an HTTP/HTTPS URL")
    if not parsed.netloc:
        fail("url must include a host")
    if parsed.username is not None or parsed.password is not None:
        fail("url must not carry a username or password")
    try:
        hostname = parsed.hostname
    except ValueError as exc:
        fail(f"url host is invalid: {exc}")
    if not hostname:
        fail("url must include a host")
    return url


def report_cost(billed, detail):
    if billed:
        print(
            f"cost: {PRICE_PER_CALL:.3f} CNY "
            f"(1 successful {detail}; 5 CNY / 1000)",
            file=sys.stderr,
        )
    else:
        print("cost: 0.000 CNY (no result returned, not billed)", file=sys.stderr)


def print_search_results(query, payload, args):
    results = payload.get("results") or []
    if not isinstance(results, list):
        fail("API returned a non-list results field")
    if any(not isinstance(item, dict) for item in results):
        fail("API returned a malformed search result")
    raw_count = len(results)
    if not results:
        print(f"# {query}")
        print(
            "No results returned. Try other keywords, or loosen "
            "site:/lang:/after:/before: filters."
        )
        return 0
    if args.min_score is not None:
        results = [
            item
            for item in results
            if (item.get("rerank_score") or 0) >= args.min_score
        ]
        if not results:
            print(f"# {query}")
            print(
                f"No results at or above rerank_score {args.min_score} "
                f"({raw_count} returned but all below the threshold). "
                "Rewrite the query or lower --min-score."
            )
            return raw_count
    scores = [
        item["rerank_score"]
        for item in results
        if isinstance(item.get("rerank_score"), (int, float))
    ]
    if scores and max(scores) < 1.5:
        print(
            "note: top rerank_score is below 1.5 (low relevance); "
            "consider rewriting the query or filtering with --min-score 1.5",
            file=sys.stderr,
        )
    print(f"# {query}")
    for index, item in enumerate(results, 1):
        print(f"\n[{index}] {item.get('title', '')}")
        meta = [
            str(value)
            for value in (
                item.get("site_name"),
                item.get("date"),
                None if item.get("rerank_score") is None
                else f"score={item['rerank_score']}",
                None if item.get("authority") is None
                else f"authority={item['authority']}",
            )
            if value
        ]
        if meta:
            print("    " + " | ".join(meta))
        if item.get("url"):
            print(f"    {item['url']}")
        body = item.get("snippet") if args.brief else item.get("summary")
        body = (body or item.get("summary") or item.get("snippet") or "").strip()
        if body:
            print("    " + body)
        content = (item.get("content") or "").strip()
        if content:
            print("\n--- content ---")
            print(content)
    return raw_count


def cmd_search(args, api_key):
    query, body = build_search_body(args)
    payload = post_json(SEARCH_URL, api_key, body)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        found = len(payload.get("results") or [])
    else:
        found = print_search_results(query, payload, args)
    label = "result" if found == 1 else "results"
    report_cost(found, f"search request returning {found} {label}")


def cmd_fetch(args, api_key):
    url = normalize_fetch_url(args.url)
    payload = post_json(FETCH_URL, api_key, {"url": url})
    title = payload.get("title") or ""
    if not isinstance(title, str):
        fail("API returned a non-string title field")
    content = payload.get("content") or ""
    if not isinstance(content, str):
        fail("API returned a non-string content field")
    content = content.strip()

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"# {title or url}")
        print(f"source: {url}")
        print()
        print(content if content else "(no content extracted from this page)")

    if args.out:
        if not content:
            fail("nothing to write: the API returned no content for this page")
        try:
            with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(f"# {title}\n\n" if title else "")
                handle.write(content + "\n")
        except OSError as exc:
            fail(f"could not write output file: {exc}")
        print(f"written: {args.out}", file=sys.stderr)

    report_cost(1 if content else 0, "fetch request")


def main():
    parser = argparse.ArgumentParser(
        description="Search the web or fetch a page via the DeepSeek Search / Fetch API."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search the web")
    search.add_argument("query", help="Search query, 1-128 characters")
    search.add_argument(
        "--count", type=int, default=10, help="Result count, 1-50 (default: 10)"
    )
    search.add_argument(
        "--brief",
        action="store_true",
        help="Print the short snippet instead of the long summary",
    )
    search.add_argument(
        "--content",
        action="store_true",
        help="Ask the API to include page content (need_content=true)",
    )
    search.add_argument(
        "--ori-question",
        help="The user question that triggered this search (improves intent)",
    )
    search.add_argument(
        "--localization",
        help="IP address used to prefer localized results",
    )
    search.add_argument(
        "--min-score",
        type=float,
        help="Only print results with rerank_score >= this value (1.5 = quality)",
    )
    search.add_argument(
        "--json", action="store_true", help="Print the raw JSON response"
    )

    fetch = subparsers.add_parser("fetch", help="Fetch one page as Markdown")
    fetch.add_argument("url", help="HTTP/HTTPS URL to fetch")
    fetch.add_argument("--out", help="Write the Markdown content to this file")
    fetch.add_argument(
        "--json", action="store_true", help="Print the raw JSON response"
    )

    args = parser.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass

    api_key = resolve_api_key()
    if not api_key:
        fail(
            "no API key found; set DEEPSEEK_API_KEY (or DEEPSEEK_KEY, "
            "DEEPSEEK_API_TOKEN). "
            "Get a key at https://platform.deepseek.com/api_keys"
        )

    if args.command == "search":
        cmd_search(args, api_key)
    else:
        cmd_fetch(args, api_key)


if __name__ == "__main__":
    main()
