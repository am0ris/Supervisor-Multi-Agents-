"""Tool: fetch_url — يجيب المحتوى الفعلي (النص) لصفحة ويب."""
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ResearchAgentBot/1.0; "
        "+https://example.com/bot)"
    )
}

MAX_CHARS_DEFAULT = 4000


def fetch_url(url: str, max_chars: int = MAX_CHARS_DEFAULT) -> dict:
    """
    يجيب النص الفعلي (الـ body text) من صفحة ويب حقيقية.

    Args:
        url: رابط الصفحة.
        max_chars: أقصى عدد حروف نرجعهم (عشان منغرقش السياق بصفحة ضخمة).

    Returns:
        dict فيه url, title, text, error (لو حصل خطأ).
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")

        # شيل السكريبتات والستايلات عشان النص يطلع نضيف
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else url
        text = " ".join(soup.get_text(separator=" ").split())

        return {
            "url": url,
            "title": title,
            "text": text[:max_chars],
            "truncated": len(text) > max_chars,
            "error": None,
        }
    except Exception as e:
        return {
            "url": url,
            "title": None,
            "text": "",
            "truncated": False,
            "error": f"تعذر جلب الصفحة: {e}",
        }
