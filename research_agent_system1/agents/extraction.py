"""
Extraction Agent - بيستخدم أداة fetch_url (عن طريق MCP) عشان يجيب
المحتوى الفعلي للصفحات، بدل ما يكتفي بالـ snippet القصير من نتيجة البحث.

لو fetch_url فشل لأي سبب (رابط ميت، حظر، timeout)، بيرجع للـ snippet
الأصلي بدل ما يوقف المشروع بالكامل.
"""
import asyncio

from config import AGENT_LIMITS, MAX_DOCUMENTS, MAX_FETCH_CHARS
from state import ResearchState
from agents.base import bump


def make_extraction_agent(fetch_tool):
    async def extraction_agent(state: ResearchState):
        print(f"\n📄 EXTRACTION AGENT (حد أقصى {MAX_DOCUMENTS} مستندات)")

        # ناخد أفضل النتائج اللي عندها رابط حقيقي، ونتجاهل التكرار
        seen_urls = set()
        candidates = []
        for r in state["research_results"]:
            url = r.get("href") if isinstance(r, dict) else None
            if url and url not in seen_urls:
                seen_urls.add(url)
                candidates.append(r)
            if len(candidates) >= MAX_DOCUMENTS:
                break

        async def fetch_one(result: dict) -> dict:
            url = result.get("href", "")
            try:
                fetched = await fetch_tool.ainvoke(
                    {"url": url, "max_chars": MAX_FETCH_CHARS}
                )
            except Exception as e:
                fetched = {"error": str(e), "text": "", "title": None}

            if fetched.get("error") or not fetched.get("text"):
                # fallback: استخدم الـ snippet الأصلي من نتيجة البحث
                return {
                    "title": result.get("title", url),
                    "url": url,
                    "content": result.get("body", ""),
                    "source": "search_snippet_fallback",
                }

            return {
                "title": fetched.get("title") or result.get("title", url),
                "url": url,
                "content": fetched["text"],
                "source": "fetch_url",
            }

        documents = await asyncio.gather(*(fetch_one(c) for c in candidates))

        n_full = sum(1 for d in documents if d["source"] == "fetch_url")
        print(f"   ↳ تم جلب {n_full}/{len(documents)} صفحة بمحتوى كامل (والباقي بالـ snippet).")

        return {
            "documents": list(documents),
            **bump(state, "extraction"),
        }

    return extraction_agent
