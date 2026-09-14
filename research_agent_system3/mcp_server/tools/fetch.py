"""Tool: fetch_url — fetches the real content of a web page.

Security: every URL is validated against SSRF (blocks internal/private
addresses) before any request is made, and robots.txt is checked and
honored before fetching. This tool never bypasses authentication,
CAPTCHAs, rate limits, or any other access control — if a page is
disallowed or requires a login, we report that rather than working
around it.
"""
import os
import requests
from bs4 import BeautifulSoup
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

from security.ssrf_guard import validate_url, UnsafeURLError

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ResearchAgentBot/1.0; "
        "+https://example.com/bot)"
    )
}

MAX_CHARS_DEFAULT = 4000
ROBOTS_TIMEOUT = 5
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", 10.0))


def _is_allowed_by_robots(url: str) -> bool:
    """Checks robots.txt for the URL's host. Fails open (allowed) only if
    robots.txt itself can't be fetched/parsed — a missing robots.txt does
    not imply disallowal, per the standard."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        resp = requests.get(robots_url, headers=HEADERS, timeout=ROBOTS_TIMEOUT)
        if resp.status_code >= 400:
            return True  # no robots.txt = no restriction stated
        parser.parse(resp.text.splitlines())
    except requests.RequestException:
        return True  # couldn't check - fail open, standard behavior
    return parser.can_fetch(HEADERS["User-Agent"], url)


def fetch_url(url: str, max_chars: int = MAX_CHARS_DEFAULT) -> dict:
    """
    Fetches the real text content (and raw HTML, for structured-data
    extraction) of a web page.

    Args:
        url: page URL.
        max_chars: max characters of extracted text to return.

    Returns:
        dict with url, title, text, html, truncated, error (if any).
        `html` is included (also capped) so callers can run JSON-LD /
        structured-data extraction on it before falling back to plain text.
    """
    try:
        validate_url(url)
    except UnsafeURLError as e:
        return {
            "url": url, "title": None, "text": "", "html": "",
            "truncated": False, "error": f"Blocked for security reasons: {e}",
        }

    if not _is_allowed_by_robots(url):
        return {
            "url": url, "title": None, "text": "", "html": "",
            "truncated": False, "error": "Disallowed by robots.txt for this URL - not fetched.",
        }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        raw_html = resp.text
        soup = BeautifulSoup(raw_html, "lxml")

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            # Keep JSON-LD <script> tags - callers need them for structured
            # data extraction. Only strip other scripts/styles/nav chrome.
            if tag.name == "script" and tag.get("type") == "application/ld+json":
                continue
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else url
        text = " ".join(soup.get_text(separator=" ").split())

        return {
            "url": url,
            "title": title,
            "text": text[:max_chars],
            "html": raw_html[: max_chars * 4],  # generous cap; JSON-LD blocks can be large
            "truncated": len(text) > max_chars,
            "error": None,
        }
    except requests.RequestException as e:
        return {
            "url": url, "title": None, "text": "", "html": "",
            "truncated": False, "error": f"Could not fetch the page: {e}",
        }
