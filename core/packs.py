"""
캐릭터 팩 로더 (플러그인 구조).

data/packs/<팩이름>/ 폴더를 스캔합니다. 각 폴더에 pack.json 과 characters.json
이 있으면 자동으로 인식됩니다.

어른용을 추가하려면:
    data/packs/adults/pack.json        (audience: "adults", levels: ["basic", ...])
    data/packs/adults/characters.json
    data/levels.json 에 해당 레벨 추가
이렇게 파일만 넣으면 됩니다. 이 파일을 포함해 코드는 수정하지 않습니다.
"""

import json
from functools import lru_cache
from typing import Any

from . import config


def _read_json(path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_levels() -> dict[str, dict]:
    """레벨 id -> 레벨 정의 (파일에 적힌 순서 그대로).

    base 가 있는 레벨은 base 레벨의 rules 뒤에 자기 style 을 붙여서 rules 를
    완성합니다. 공통 규칙(친구처럼, 암묵적 교정, 안전)은 한 곳에만 두고, 레벨마다
    다른 부분(문장 길이, 질문 방식)만 따로 적기 위해서입니다."""
    if not config.LEVELS_PATH.exists():
        return {}
    data = _read_json(config.LEVELS_PATH)
    levels = {lv["id"]: dict(lv) for lv in data.get("levels", [])}
    for lv in levels.values():
        base = levels.get(lv.get("base") or "")
        if base and not lv.get("rules"):
            lv["rules"] = (base.get("rules", "").rstrip() + "\n\n"
                           + lv.get("style", "").strip())
    return levels


@lru_cache(maxsize=1)
def load_packs() -> list[dict]:
    """활성화된 캐릭터 팩 목록. 각 팩에 'characters' 키가 채워집니다."""
    packs: list[dict] = []
    if not config.PACKS_DIR.exists():
        return packs

    for pack_dir in sorted(p for p in config.PACKS_DIR.iterdir() if p.is_dir()):
        pack_file = pack_dir / "pack.json"
        chars_file = pack_dir / "characters.json"
        if not pack_file.exists() or not chars_file.exists():
            continue

        try:
            pack = _read_json(pack_file)
            chars = _read_json(chars_file).get("characters", [])
        except (json.JSONDecodeError, OSError):
            # 팩 하나가 깨져도 앱 전체는 계속 뜨게 합니다.
            continue

        if not pack.get("enabled", True):
            continue

        pack["dir"] = str(pack_dir)
        pack["characters"] = chars
        packs.append(pack)

    return packs


@lru_cache(maxsize=1)
def _character_index() -> dict[str, dict]:
    """캐릭터 id -> 캐릭터 정의 (소속 팩 정보 포함)."""
    index: dict[str, dict] = {}
    for pack in load_packs():
        for ch in pack["characters"]:
            enriched = dict(ch)
            enriched["pack_id"] = pack["id"]
            enriched["audience"] = pack.get("audience", "kids")
            index[ch["id"]] = enriched
    return index


def all_characters() -> list[dict]:
    return list(_character_index().values())


def characters_for_level(level_id: str) -> list[dict]:
    """해당 레벨이 쓸 수 있는 캐릭터만. 팩의 levels 에 레벨이 포함되어야 합니다."""
    allowed_packs = {
        p["id"] for p in load_packs() if level_id in p.get("levels", [])
    }
    return [c for c in all_characters() if c["pack_id"] in allowed_packs]


def get_character(character_id: str) -> dict | None:
    return _character_index().get(character_id)


def get_level(level_id: str) -> dict | None:
    return load_levels().get(level_id)


def default_level_id() -> str:
    levels = load_levels()
    return "kids" if "kids" in levels else (next(iter(levels), "kids"))


def image_path(character: dict):
    """캐릭터 이미지의 절대 경로. 파일이 없으면 None."""
    name = (character.get("stage") or {}).get("image")
    if not name:
        return None
    path = config.ASSETS_DIR / name
    return path if path.exists() else None


def video_paths(character: dict) -> dict[str, Any]:
    """나중에 영상을 넣었을 때 쓰입니다. 지금은 보통 전부 None 입니다."""
    stage = character.get("stage") or {}
    out: dict[str, Any] = {}
    for key in ("idle", "talking"):
        name = stage.get(key)
        if not name:
            out[key] = None
            continue
        path = config.ASSETS_DIR / name
        out[key] = path if path.exists() else None
    return out


def has_video(character: dict) -> bool:
    return any(v is not None for v in video_paths(character).values())


def reload() -> None:
    """캐릭터 파일을 수정한 뒤 캐시를 비우고 다시 읽습니다."""
    load_levels.cache_clear()
    load_packs.cache_clear()
    _character_index.cache_clear()
