from __future__ import annotations

from astrbot.core.star.filter.command import GreedyStr

FORMAT_ALIASES = {
    "原图": "raw",
    "raw": "raw",
    "jpg": "jpg",
    "jpeg": "jpg",
    "png": "png",
    "pdf": "pdf",
}

RANK_ALIASES = {
    "month": "month",
    "week": "week",
    "day": "day",
    "月": "month",
    "周": "week",
    "日": "day",
}


def normalize_format_name(value: str) -> str:
    key = (value or "").strip().lower()
    return FORMAT_ALIASES.get(key, key)


def normalize_rank_name(value: str) -> str:
    key = (value or "").strip().lower()
    return RANK_ALIASES.get(key, key)


__all__ = ["GreedyStr", "normalize_format_name", "normalize_rank_name"]
