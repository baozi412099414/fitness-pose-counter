"""动作库的读写接口（/api/actions）。

这是「新增动作不改代码」在网页上的落地：
新建动作 = 往 `configs/` 写一份 JSON，删除动作 = 删掉那份 JSON。
内置的三个动作（深蹲/俯卧撑/开合跳）不允许删，避免演示时把自己玩坏了。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import action_editor  # noqa: E402
import validate_config  # noqa: E402

CONFIGS = ROOT / "configs"

# 内置动作：可以看、可以练，但不能删
BUILTIN_IDS = {"squat", "pushup", "jumping_jack"}

JOINT_NAMES = {
    (23, 25, 27): "左膝角",
    (24, 26, 28): "右膝角",
    (11, 13, 15): "左肘角",
    (12, 14, 16): "右肘角",
    (13, 11, 23): "左肩角",
    (14, 12, 24): "右肩角",
    (11, 23, 25): "左髋角",
    (12, 24, 26): "右髋角",
    (11, 23, 27): "左体侧线",
    (12, 24, 28): "右体侧线",
}


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _validate(path: Path) -> dict:
    try:
        report = validate_config.validate_file(str(path))
    except Exception as exc:  # noqa: BLE001 - 单个坏文件不该让整个列表 500
        return {"ok": False, "errors": [f"{type(exc).__name__}: {exc}"], "warnings": []}
    return {
        "ok": not report.errors,
        "errors": list(report.errors),
        "warnings": list(report.warns),
    }


def _signal_short(cfg: dict) -> str:
    counter = cfg.get("counter", {})
    conditions = counter.get("conditions")
    if conditions:
        return "多条件"
    signal = counter.get("signal", "angle")
    if signal == "angle":
        return JOINT_NAMES.get(tuple(counter.get("points") or []), "关节角度")
    if signal == "distance":
        return "距离比"
    if signal == "dx":
        return "水平差"
    if signal == "dxs":
        return "带符号水平差"
    if signal == "dy":
        return "高度差"
    return signal


def _signal_kind(cfg: dict) -> str:
    counter = cfg.get("counter", {})
    if counter.get("conditions"):
        return "多条件"
    return "关节角度" if counter.get("signal", "angle") == "angle" else "距离比"


def _thresholds(cfg: dict) -> str:
    counter = cfg.get("counter", {})
    conditions = counter.get("conditions")
    if conditions:
        return f"{len(conditions)} 条件 AND"
    lo, hi = counter.get("lo"), counter.get("hi")
    if lo is None or hi is None:
        return "—"
    if counter.get("first", "lo") == "lo":
        return f"{lo:g}° ↓ · {hi:g}° ↑"
    return f"{hi:g}° ↑ · {lo:g}° ↓"


def _summary(path: Path, cfg: dict) -> dict:
    validation = _validate(path)
    return {
        "id": cfg.get("id", path.stem),
        "name": cfg.get("name", path.stem),
        "camera_side": "front" if cfg.get("camera_side") == "正" else "side",
        "signal": _signal_short(cfg),
        "signal_kind": _signal_kind(cfg),
        "rule_count": len(cfg.get("quality") or []),
        "thresholds": _thresholds(cfg),
        "builtin": cfg.get("id") in BUILTIN_IDS,
        "validation": {
            "ok": validation["ok"],
            "error_count": len(validation["errors"]),
            "warning_count": len(validation["warnings"]),
        },
    }


def _detail(path: Path, cfg: dict) -> dict:
    validation = _validate(path)
    action_id = cfg.get("id", path.stem)
    return {
        "id": action_id,
        "name": cfg.get("name", action_id),
        "camera_side": cfg.get("camera_side", ""),
        "calibrate": bool(cfg.get("calibrate", False)),
        "builtin": action_id in BUILTIN_IDS,
        "counter": cfg.get("counter", {}),
        "quality": cfg.get("quality") or [],
        "file_path": f"configs/{path.name}",
        "last_validated_at": None,
        "validation": validation,
    }


router = APIRouter(prefix="/api/actions", tags=["actions"])


def _all_files() -> list[Path]:
    return sorted(CONFIGS.glob("*.json"))


def _find(action_id: str) -> Path:
    path = CONFIGS / f"{action_id}.json"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"没有这个动作：{action_id}（可用动作见 /api/actions）",
        )
    return path


@router.get("")
def list_actions() -> dict:
    items = []
    for path in _all_files():
        cfg = _load(path)
        if cfg is None:
            continue
        items.append(_summary(path, cfg))
    return {"items": items, "count": len(items)}


@router.get("/{action_id}")
def get_action(action_id: str) -> dict:
    path = _find(action_id)
    cfg = _load(path)
    if cfg is None:
        raise HTTPException(status_code=500, detail=f"{path.name} 不是合法 JSON")
    return _detail(path, cfg)


class RuleDraft(BaseModel):
    enabled: bool = False
    threshold: float = 0
    tip: str = ""
    priority: int = 50


class NewActionDraft(BaseModel):
    name: str
    id: str
    camera_side: str = "侧"
    calibrate: bool = False
    cycles_per_rep: int = 1
    signal: str = "angle"
    points: list[int] = Field(default_factory=list)
    lo: float
    hi: float
    first: str = "lo"
    min_interval: float = 0.4
    enter_hold: float = 0.06
    exit_hold: float = 0.06
    min_active_duration: float = 0.2
    depth: RuleDraft = Field(default_factory=RuleDraft)
    straight: RuleDraft = Field(default_factory=RuleDraft)


def _fail(message: str, field: str | None = None, status: int = 422) -> dict:
    return {"ok": False, "errors": [{"field": field, "message": message} if field
                                    else {"message": message}], "warnings": []}


@router.post("", status_code=201)
def create_action(draft: NewActionDraft) -> dict:
    action_id = (draft.id or "").strip()
    name = (draft.name or "").strip()
    if not name:
        return _fail("动作名称不能为空", "name")
    if not action_id:
        return _fail("动作 ID 不能为空", "id")
    if (CONFIGS / f"{action_id}.json").exists():
        return _fail(f"已经有一个叫「{action_id}」的动作了，换个 ID", "id")

    first_lo = draft.first == "lo"
    cfg = action_editor.build_action_config(
        name=name,
        aid=action_id,
        signal=draft.signal,
        points=draft.points,
        # 界面上 lo/hi 是「小的值 / 大的值」，start/end 是「先到的 / 后到的」
        start_th=draft.lo if first_lo else draft.hi,
        end_th=draft.hi if first_lo else draft.lo,
        first_lo=first_lo,
        cycles=draft.cycles_per_rep,
        camera_side=draft.camera_side,
        calibrate=draft.calibrate,
        depth_check=draft.depth.enabled,
        depth_th=draft.depth.threshold if draft.depth.enabled else None,
        depth_tip=draft.depth.tip,
        straight_check=draft.straight.enabled,
        straight_th=draft.straight.threshold if draft.straight.enabled else None,
        straight_tip=draft.straight.tip,
    )
    # 界面上填的防抖参数允许覆盖默认值
    counter = cfg.get("counter", {})
    counter["min_interval"] = max(0.0, float(draft.min_interval))
    counter["enter_hold"] = max(0.0, float(draft.enter_hold))
    counter["exit_hold"] = max(0.0, float(draft.exit_hold))
    counter["min_active_duration"] = max(0.0, float(draft.min_active_duration))

    ok, message, path = action_editor.validate_and_save(cfg, CONFIGS)
    if not ok or path is None:
        return {
            "ok": False,
            "errors": [{"message": message}],
            "warnings": [],
        }
    saved = _load(path) or cfg
    return {
        "ok": True,
        "errors": [],
        "warnings": _validate(path)["warnings"],
        "message": message,
        "detail": _detail(path, saved),
    }


@router.delete("/{action_id}")
def delete_action(action_id: str) -> dict:
    if action_id in BUILTIN_IDS:
        raise HTTPException(
            status_code=409,
            detail=f"「{action_id}」是内置动作，不能删除（只允许删自己新建的）",
        )
    path = _find(action_id)
    path.unlink()
    return {"ok": True, "message": f"已删除动作「{action_id}」"}


@router.post("/validate")
def validate_actions(payload: dict | None = None) -> dict:
    wanted = (payload or {}).get("id")
    results = []
    for path in _all_files():
        cfg = _load(path)
        if cfg is None:
            continue
        if wanted and cfg.get("id") != wanted:
            continue
        report = _validate(path)
        results.append({
            "action_id": cfg.get("id", path.stem),
            "action_name": cfg.get("name", path.stem),
            "file_path": f"configs/{path.name}",
            "ok": report["ok"],
            "errors": report["errors"],
            "warnings": report["warnings"],
        })
    return {"items": results, "ok": all(r["ok"] for r in results)}
