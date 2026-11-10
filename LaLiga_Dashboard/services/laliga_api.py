"""Shared LaLiga data access using ESPN's publicly accessible soccer endpoints.
Endpoints are unofficial and may change without notice."""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import time
import requests

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1"
KST = ZoneInfo("Asia/Seoul")
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "LaLiga-Dashboard/1.0 (educational project)"})

class DataUnavailable(RuntimeError):
    pass

def now_kst():
    return datetime.now(KST)

def _cache_path(key):
    safe = "".join(c for c in key if c.isalnum() or c in "-_")
    return CACHE_DIR / f"{safe}.json"

def fetch_json(path, ttl=300, params=None):
    key = path.replace("/", "_") + "_" + "_".join(f"{k}-{v}" for k,v in sorted((params or {}).items()))
    cache_path = _cache_path(key)
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if time.time() - cached["saved_at"] < ttl:
                return cached["data"], False, datetime.fromtimestamp(cached["saved_at"], KST)
        except Exception:
            pass
    try:
        response = SESSION.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=(4, 12))
        response.raise_for_status()
        data = response.json()
        cache_path.write_text(json.dumps({"saved_at": time.time(), "data": data}, ensure_ascii=False), encoding="utf-8")
        return data, False, now_kst()
    except Exception as exc:
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                return cached["data"], True, datetime.fromtimestamp(cached["saved_at"], KST)
            except Exception:
                pass
        raise DataUnavailable(f"라리가 데이터를 가져오지 못했습니다: {exc}") from exc

def _events_from(data):
    return data.get("events", []) if isinstance(data, dict) else []

def games(date_value=None, days=7):
    """Return match events for a date or a short future window."""
    if date_value is None:
        date_value = now_kst().date()
    if isinstance(date_value, str):
        date_value = datetime.strptime(date_value, "%Y-%m-%d").date()
    start = date_value
    end = start + timedelta(days=max(0, days - 1))
    data, stale, saved = fetch_json("scoreboard", ttl=30, params={
        "dates": f"{start:%Y%m%d}-{end:%Y%m%d}", "limit": 100
    })
    output = []
    for event in _events_from(data):
        comps = event.get("competitions", [])
        comp = comps[0] if comps else {}
        competitors = comp.get("competitors", [])
        home = next((x for x in competitors if x.get("homeAway") == "home"), {})
        away = next((x for x in competitors if x.get("homeAway") == "away"), {})
        status = (comp.get("status") or {}).get("type", {})
        state_name = status.get("name", "STATUS_SCHEDULED")
        state = "final" if status.get("completed") else ("live" if "IN_PROGRESS" in state_name or "HALFTIME" in state_name else "scheduled")
        dt = event.get("date")
        try:
            kickoff = datetime.fromisoformat(dt.replace("Z", "+00:00")).astimezone(KST)
        except Exception:
            kickoff = None
        output.append({
            "id": str(event.get("id", "")),
            "name": event.get("name", "경기 정보"),
            "date": kickoff,
            "state": state,
            "status": status.get("description") or status.get("detail") or "일정",
            "home": (home.get("team") or {}).get("displayName", "홈팀"),
            "away": (away.get("team") or {}).get("displayName", "원정팀"),
            "home_logo": (home.get("team") or {}).get("logo", ""),
            "away_logo": (away.get("team") or {}).get("logo", ""),
            "home_score": home.get("score", "-"),
            "away_score": away.get("score", "-"),
            "venue": (comp.get("venue") or {}).get("fullName", "구장 정보 없음"),
            "broadcast": ", ".join(x.get("name","") for x in comp.get("broadcasts", []) if x.get("name")),
            "stale": stale,
            "saved_at": saved,
        })
    output.sort(key=lambda x: x["date"] or now_kst())
    return output, stale, saved

def _collect_standing_entries(node):
    """Extract standing rows from ESPN's nested standings/group response."""
    found = []
    if isinstance(node, dict):
        entries = node.get("entries")
        if isinstance(entries, list):
            found.extend(x for x in entries if isinstance(x, dict))
        for key in ("standings", "children", "groups", "tables"):
            child = node.get(key)
            if isinstance(child, (dict, list)):
                found.extend(_collect_standing_entries(child))
    elif isinstance(node, list):
        for item in node:
            found.extend(_collect_standing_entries(item))
    # Deduplicate rows by team/id/name while preserving order.
    unique, seen = [], set()
    for row in found:
        team = row.get("team") or {}
        key = str(team.get("id") or row.get("id") or team.get("displayName") or row.get("name") or id(row))
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique

def standings():
    # Soccer standings are served by ESPN's /apis/v2/ route, not /apis/site/v2/.
    url = "https://site.api.espn.com/apis/v2/sports/soccer/esp.1/standings"
    try:
        response = SESSION.get(url, timeout=(4, 12))
        response.raise_for_status()
        data = response.json()
        entries = _collect_standing_entries(data)
        if entries:
            return entries, False, now_kst()
    except Exception:
        pass
    # Alternate ESPN host can help if the primary host is unavailable.
    try:
        response = SESSION.get("https://site.web.api.espn.com/apis/v2/sports/soccer/esp.1/standings", timeout=(4, 12))
        response.raise_for_status()
        data = response.json()
        entries = _collect_standing_entries(data)
        if entries:
            return entries, False, now_kst()
    except Exception:
        pass
    raise DataUnavailable("라리가 순위를 가져오지 못했습니다. 인터넷 연결 또는 ESPN 데이터 응답을 확인해 주세요.")

def teams():
    data, stale, saved = fetch_json("teams", ttl=86400)
    items = []
    try:
        items = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
    except (AttributeError, IndexError, TypeError):
        items = []
    if not items and isinstance(data, dict):
        # Some ESPN responses return the league/team list in a flatter structure.
        items = data.get("teams", [])
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        team = item.get("team", item)
        if isinstance(team, dict) and (team.get("id") or team.get("displayName") or team.get("name")):
            normalized.append(team)
    if not normalized:
        raise DataUnavailable("구단 목록이 비어 있습니다. ESPN 응답을 확인하거나 캐시 삭제 후 다시 시도해 주세요.")
    return normalized, stale, saved

def team_details(team_id):
    return fetch_json(f"teams/{team_id}", ttl=3600)

def news():
    return fetch_json("news", ttl=1800)

def safe_record(record, *names, default="—"):
    stats = record.get("stats", []) if isinstance(record, dict) else []
    lookup = {x.get("name"): x.get("value") for x in stats if isinstance(x, dict)}
    for name in names:
        if name in lookup and lookup[name] is not None:
            return lookup[name]
    return default
