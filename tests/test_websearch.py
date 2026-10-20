import io
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import websearch  # noqa: E402


def search_args(**overrides):
    values = {
        "query": "DeepSeek",
        "count": 10,
        "content": False,
        "ori_question": None,
        "localization": None,
        "min_score": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ApiKeyTests(unittest.TestCase):
    def test_primary_key_is_trimmed(self):
        key = websearch.resolve_api_key(
            {"DEEPSEEK_API_KEY": "  primary-key  ", "DEEPSEEK_KEY": "fallback"}
        )
        self.assertEqual(key, "primary-key")

    def test_fallback_key_is_supported(self):
        key = websearch.resolve_api_key({"DEEPSEEK_KEY": "fallback-key"})
        self.assertEqual(key, "fallback-key")

    def test_multiline_key_is_rejected(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            websearch.resolve_api_key({"DEEPSEEK_API_KEY": "bad\r\nkey"})


class SearchValidationTests(unittest.TestCase):
    def test_default_body(self):
        query, body = websearch.build_search_body(search_args())
        self.assertEqual(query, "DeepSeek")
        self.assertEqual(
            body, {"query": "DeepSeek", "count": 10, "need_content": False}
        )

    def test_optional_fields_are_normalized(self):
        query, body = websearch.build_search_body(
            search_args(
                query="  DeepSeek  ",
                ori_question="  user question  ",
                localization=" 127.0.0.1 ",
                min_score=1.5,
            )
        )
        self.assertEqual(query, "DeepSeek")
        self.assertEqual(body["ori_question"], "user question")
        self.assertEqual(body["localization"], "127.0.0.1")

    def test_blank_query_is_rejected(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            websearch.build_search_body(search_args(query="   "))

    def test_count_is_bounded(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            websearch.build_search_body(search_args(count=51))

    def test_invalid_localization_is_rejected(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            websearch.build_search_body(search_args(localization="not-an-ip"))

    def test_invalid_min_score_is_rejected(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            websearch.build_search_body(search_args(min_score=float("nan")))


class FetchUrlTests(unittest.TestCase):
    def test_https_url_is_accepted(self):
        url = "https://example.com/article?q=1"
        self.assertEqual(websearch.normalize_fetch_url(url), url)

    def test_ipv6_url_is_accepted(self):
        url = "http://[::1]:8080/path"
        self.assertEqual(websearch.normalize_fetch_url(url), url)

    def test_userinfo_is_rejected(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            websearch.normalize_fetch_url("https://user:pass@example.com/")

    def test_missing_host_is_rejected(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            websearch.normalize_fetch_url("https:///article")

    def test_non_http_scheme_is_rejected(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            websearch.normalize_fetch_url("file:///etc/passwd")


class CommandTests(unittest.TestCase):
    def test_fetch_writes_markdown(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "page.md"
            args = SimpleNamespace(
                url="https://example.com/article",
                out=str(output),
                json=False,
            )
            payload = {"title": "Example", "content": "Body"}
            with mock.patch.object(websearch, "post_json", return_value=payload):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    websearch.cmd_fetch(args, "test-key")
            self.assertEqual(output.read_text(encoding="utf-8"), "# Example\n\nBody\n")

    def test_http_error_does_not_echo_api_key(self):
        error = urllib.error.HTTPError(
            "https://api.deepseek.com",
            401,
            "Unauthorized",
            {},
            io.BytesIO(
                b'{"error":{"message":"invalid key","type":"authentication_error"}}'
            ),
        )
        stderr = io.StringIO()
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with redirect_stderr(stderr), self.assertRaises(SystemExit):
                websearch.post_json("https://api.deepseek.com", "secret-value", {})
        self.assertIn("HTTP 401", stderr.getvalue())
        self.assertNotIn("secret-value", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
