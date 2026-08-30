"""
MCP Server - Research Tools
============================
بيشغل سيرفر MCP فيه tool اسمه search_web بيدور فعلياً على الإنترنت
(بدون أي API key) باستخدام مكتبة ddgs.

تشغيل السيرفر:
    python search_server.py

هيشتغل على: http://localhost:8000/mcp
"""

from fastmcp import FastMCP
from ddgs import DDGS

mcp = FastMCP("research_tools")


@mcp.tool()
def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    يدور على الإنترنت عن استعلام معين ويرجع أهم النتائج.

    Args:
        query: نص البحث.
        max_results: أقصى عدد نتائج (افتراضي 5).

    Returns:
        list[dict]: كل عنصر فيه title و href و body.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return [{"title": "No results", "href": "", "body": "لم يتم العثور على نتائج لهذا الاستعلام."}]
        return results
    except Exception as e:
        return [{"title": "Search error", "href": "", "body": f"حصل خطأ أثناء البحث: {e}"}]


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp")
