import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcp_server.tools.fetch as fetch_mod
from mcp_server.tools.fetch import fetch_url


class _FakeResponse:
    def __init__(self, text="", status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"status {self.status_code}")


def test_ssrf_blocked_url_never_reaches_requests():
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)
        return _FakeResponse("<html></html>")

    fetch_mod.requests.get = fake_get
    result = fetch_url("http://127.0.0.1:8000/admin")
    assert result["error"] is not None and "security" in result["error"].lower()
    assert calls == [], "requests.get must never be called for an SSRF-blocked URL"
    print("PASS: test_ssrf_blocked_url_never_reaches_requests")


def test_robots_disallow_blocks_fetch():
    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/robots.txt"):
            return _FakeResponse("User-agent: *\nDisallow: /private/")
        return _FakeResponse("<html><body>secret</body></html>")

    fetch_mod.requests.get = fake_get
    result = fetch_url("https://example.com/private/page")
    assert result["error"] is not None and "robots.txt" in result["error"]
    print("PASS: test_robots_disallow_blocks_fetch")


def test_robots_allow_permits_fetch():
    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/robots.txt"):
            return _FakeResponse("User-agent: *\nAllow: /\n")
        return _FakeResponse("<html><head><title>T</title></head><body>Hello world</body></html>")

    fetch_mod.requests.get = fake_get
    result = fetch_url("https://example.com/page")
    assert result["error"] is None
    assert result["title"] == "T"
    assert "Hello world" in result["text"]
    print("PASS: test_robots_allow_permits_fetch")


def test_missing_robots_txt_fails_open():
    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/robots.txt"):
            return _FakeResponse("", status_code=404)
        return _FakeResponse("<html><head><title>T</title></head><body>content</body></html>")

    fetch_mod.requests.get = fake_get
    result = fetch_url("https://example.com/page")
    assert result["error"] is None, "a missing robots.txt must not block the fetch"
    print("PASS: test_missing_robots_txt_fails_open")


def test_jsonld_script_tag_preserved_in_html_output():
    html_with_jsonld = (
        '<html><head><title>Job</title>'
        '<script type="application/ld+json">{"@type":"JobPosting","title":"AI Engineer"}</script>'
        '</head><body>Some visible text</body></html>'
    )

    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/robots.txt"):
            return _FakeResponse("", status_code=404)
        return _FakeResponse(html_with_jsonld)

    fetch_mod.requests.get = fake_get
    result = fetch_url("https://example.com/jobs/1")
    assert result["error"] is None
    assert "application/ld+json" in result["html"], "JSON-LD script tag must survive into the html field"
    assert "JobPosting" in result["html"]
    print("PASS: test_jsonld_script_tag_preserved_in_html_output")


if __name__ == "__main__":
    test_ssrf_blocked_url_never_reaches_requests()
    test_robots_disallow_blocks_fetch()
    test_robots_allow_permits_fetch()
    test_missing_robots_txt_fails_open()
    test_jsonld_script_tag_preserved_in_html_output()
    print("\n✅ All fetch_url security/robots tests passed")
