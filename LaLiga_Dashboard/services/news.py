"""News helper for the LaLiga dashboard."""
from .laliga_api import news

def get_news():
    data, stale, saved = news()
    items = data.get("articles", []) if isinstance(data, dict) else []
    output = []
    for item in items:
        output.append({
            "title": item.get("headline") or item.get("title") or "라리가 뉴스",
            "description": item.get("description") or item.get("story") or "",
            "url": item.get("links", {}).get("web", {}).get("href", ""),
            "published": item.get("published") or item.get("lastModified") or "",
            "image": (item.get("images") or [{}])[0].get("url", ""),
        })
    return output, stale, saved
