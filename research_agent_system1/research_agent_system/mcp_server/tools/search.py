"""Tool: search_web — بحث حقيقي على الإنترنت بدون API key."""
from ddgs import DDGS


def search_web(query: str, max_results: int = 5, timelimit: str = "y") -> list[dict]:
    """
    يدور على الإنترنت عن استعلام معين ويرجع أهم النتائج.

    Args:
        query: نص البحث.
        max_results: أقصى عدد نتائج (افتراضي 5).
        timelimit: فلتر الحداثة - "d" (يوم) / "w" (أسبوع) / "m" (شهر) /
            "y" (سنة) / None (من غير فلتر). الافتراضي "y" عشان نتائج
            "آخر تطورات" ماترجعش صفحات قديمة عالية الشهرة بدل الحديثة.

    Returns:
        list[dict]: كل عنصر فيه title, href, body.
    """
    try:
        with DDGS() as ddgs:
            results = list(
                ddgs.text(query, max_results=max_results, timelimit=timelimit or None)
            )
        if not results and timelimit:
            # لو الفلتر الزمني رجّع فاضي، جرب من غيره بدل ما نرجع فاضي بالكامل
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return [{"title": "No results", "href": "", "body": "لم يتم العثور على نتائج."}]
        return results
    except Exception as e:
        return [{"title": "Search error", "href": "", "body": f"حصل خطأ أثناء البحث: {e}"}]
