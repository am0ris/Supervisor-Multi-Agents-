"""Tool: search_web — بحث حقيقي على الإنترنت بدون API key."""
from ddgs import DDGS


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    يدور على الإنترنت عن استعلام معين ويرجع أهم النتائج.

    Args:
        query: نص البحث.
        max_results: أقصى عدد نتائج (افتراضي 5).

    Returns:
        list[dict]: كل عنصر فيه title, href, body.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return [{"title": "No results", "href": "", "body": "لم يتم العثور على نتائج."}]
        return results
    except Exception as e:
        return [{"title": "Search error", "href": "", "body": f"حصل خطأ أثناء البحث: {e}"}]
