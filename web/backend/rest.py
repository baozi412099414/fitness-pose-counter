"""网页版的数据接口（REST）。

只做「把 training_manager 里已有的能力翻译成前端要的 JSON」，
统计口径全部复用 `History` / `Goals` / `UserStore`，不在这里重算。

前端 `src/lib/types.ts` 的字段名是契约，改这里之前先看那边。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training_manager import Goals, History, UserStore  # noqa: E402

DATA_ROOT = ROOT / "data" / "users"
GRADE_LINES = ((90, "优秀"), (75, "良好"), (60, "及格"))


def _store() -> UserStore:
    return UserStore(str(DATA_ROOT))


def _action_meta() -> tuple[dict[str, str], dict[str, str]]:
    """configs/*.json → (动作 id→名字, 规则名→提示语)。"""
    names: dict[str, str] = {}
    tips: dict[str, str] = {}
    for path in sorted((ROOT / "configs").glob("*.json")):
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        action_id = cfg.get("id", path.stem)
        names[action_id] = cfg.get("name", action_id)
        for rule in cfg.get("quality", []) or []:
            name = rule.get("name")
            if name:
                tips[name] = rule.get("tip") or name
    return names, tips


def _grade(score: float | None) -> str | None:
    if score is None:
        return None
    for line, label in GRADE_LINES:
        if score >= line:
            return label
    return "待改进"


def _mmdd(date_str: str) -> str:
    return date_str[5:] if len(date_str) >= 10 else date_str


def _fmt_time(iso: str) -> str:
    """'2026-10-27T11:11:30' → '10-27 11:11'。"""
    try:
        dt = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or ""
    return dt.strftime("%m-%d %H:%M")


def _sessions(store: UserStore, user: str) -> list[dict]:
    return History(store, user=user).all_sessions()


def _user_payload(store: UserStore, name: str) -> dict:
    profile = store.profile(name) or {}
    sessions = _sessions(store, name)
    today = datetime.now().strftime("%Y-%m-%d")
    created = profile.get("created_at") or ""
    return {
        "id": name,
        "name": name,
        "initials": (name[:1] or "?").upper(),
        # 没有 profile 的用户（只跑过一次训练）用第一条记录的时间兜底
        "created_at": created[:10] or (sessions[0]["date"] if sessions else ""),
        "height": profile.get("height_cm"),
        "weight": profile.get("weight_kg"),
        "total_sessions": len(sessions),
        "today_sessions": sum(1 for r in sessions if r.get("date") == today),
        "badge": None,
    }


router = APIRouter(prefix="/api")


# ──────────────────────────────────────────────────────────── 用户
@router.get("/users")
def list_users() -> list[dict]:
    """用户列表，**最近练过的排前面**。

    前端在没有记住选择时会默认取第一个，所以顺序决定了「打开就是谁」——
    按名字排会让人看到空数据（最近练的不是字母序第一个），体验很怪。
    """
    store = _store()
    payloads = [_user_payload(store, name) for name in store.list_users()]
    last_active = {
        p["id"]: max((r.get("time") or "" for r in _sessions(store, p["id"])), default="")
        for p in payloads
    }
    payloads.sort(key=lambda p: (last_active[p["id"]], p["created_at"]), reverse=True)
    return payloads


class CreateUserBody(BaseModel):
    name: str
    height: float | None = None
    weight: float | None = None


@router.post("/users")
def create_user(body: CreateUserBody) -> dict:
    store = _store()
    name = (body.name or "").strip()
    if not name:
        return {"ok": False, "errors": [{"field": "name", "message": "用户名不能为空"}]}
    if name in store.list_users():
        return {
            "ok": False,
            "errors": [{"field": "name", "message": f"用户「{name}」已存在"}],
        }
    store.create_user(name, body.height, body.weight)
    return {"ok": True, "errors": [], "user": _user_payload(store, name)}


@router.delete("/users/{name}")
def delete_user(name: str) -> dict:
    store = _store()
    ok, message = store.delete_user(name)
    return {
        "ok": ok,
        "errors": [] if ok else [{"message": message}],
    }


# ──────────────────────────────────────────────────────────── 目标
class GoalBody(BaseModel):
    target: int


@router.put("/goals/{action}")
def set_goal(action: str, body: GoalBody, user: str | None = Query(default=None)) -> dict:
    store = _store()
    name = user or store.current_user()
    Goals(store, user=name).set_goal(action, max(0, int(body.target)))
    return {"ok": True}


@router.delete("/goals/{action}")
def clear_goal(action: str, user: str | None = Query(default=None)) -> dict:
    store = _store()
    name = user or store.current_user()
    Goals(store, user=name).clear_goal(action)
    return {"ok": True}


# ──────────────────────────────────────────────────────────── 历史
@router.get("/history")
def history(
    user: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    store = _store()
    name = user or store.current_user()
    names, tips = _action_meta()
    records = [r for r in _sessions(store, name)
               if not action or r.get("action") == action]
    records.sort(key=lambda r: r.get("time") or "", reverse=True)
    page = records[offset:offset + limit]
    items = []
    for i, r in enumerate(page):
        items.append({
            "id": f"{r.get('time', '')}-{offset + i}",
            "time": _fmt_time(r.get("time")),
            "date": r.get("date"),
            "action_id": r.get("action"),
            "action_name": names.get(r.get("action"), r.get("action")),
            "reps": int(r.get("reps") or 0),
            "sets": int(r.get("sets") or 0),
            "score": r.get("score"),
            "duration": int(round(r.get("duration_sec") or 0)),
            "errors": [tips.get(k, k) for k in (r.get("errors") or {})],
        })
    return {"total": len(records), "items": items}


# ──────────────────────────────────────────────────────────── 总览
@router.get("/overview")
def overview(
    user: str | None = Query(default=None),
    days: int = Query(default=14, ge=1, le=90),
) -> dict:
    store = _store()
    name = user or store.current_user()
    names, tips = _action_meta()
    hist = History(store, user=name)
    goals_api = Goals(store, user=name)
    records = hist.all_sessions()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    def reps_on(date: str) -> int:
        return sum(int(r.get("reps") or 0) for r in records if r.get("date") == date)

    last7 = []
    for i in range(6, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        last7.append({"date": _mmdd(d), "reps": reps_on(d)})

    week_start = (now - timedelta(days=6)).strftime("%Y-%m-%d")
    week_records = [r for r in records if week_start <= (r.get("date") or "") <= today]

    cutoff = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    in_range = [r for r in records if cutoff <= (r.get("date") or "") <= today]
    scores = [r["score"] for r in in_range if r.get("score") is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else None

    progress = goals_api.all_progress(hist)
    goals = [
        {
            "action_id": action,
            "action_name": names.get(action, action),
            "target": int(item.get("target") or 0),
            "done": int(item.get("done") or 0),
        }
        for action, item in progress.items()
    ]

    error_counts = hist.error_summary()
    top_errors = [
        {"tip": tips.get(k, k), "count": int(v)}
        for k, v in list(error_counts.items())[:5]
    ]

    recent = sorted(records, key=lambda r: r.get("time") or "", reverse=True)[:5]
    recent_sessions = [
        {
            "time": _fmt_time(r.get("time")),
            "action_id": r.get("action"),
            "action_name": names.get(r.get("action"), r.get("action")),
            "reps": int(r.get("reps") or 0),
            "score": r.get("score"),
            "errors": len(r.get("errors") or {}),
        }
        for r in recent
    ]

    weekly = [
        {"week_start": _mmdd(item["week_start"]), "reps": int(item["reps"])}
        for item in hist.weekly_trend(weeks=8, now=now)
    ]
    score_trend = [
        {"date": _mmdd(item["date"]), "score": item["score"]}
        for item in hist.score_trend(days=days, now=now)
    ]

    return {
        "today_reps": reps_on(today),
        "yesterday_reps": reps_on(yesterday),
        "daily_goal_target": sum(g["target"] for g in goals),
        "daily_goal_done": sum(g["done"] for g in goals),
        "last_7_days": last7,
        "weekly_trend": weekly,
        "goals": goals,
        "top_errors": top_errors,
        "recent_sessions": recent_sessions,
        "week_reps": sum(int(r.get("reps") or 0) for r in week_records),
        "week_sessions": len(week_records),
        "total_sessions": len(records),
        "avg_score": avg_score,
        "avg_score_grade": _grade(avg_score),
        "score_trend": score_trend,
    }


@router.get("/users/current")
def current_user() -> dict:
    store = _store()
    name = store.current_user_or_none()
    if not name:
        raise HTTPException(status_code=404, detail="还没有用户")
    return _user_payload(store, name)
