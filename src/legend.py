from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple


LEGEND_FILE = Path(__file__).resolve().parent / "data" / "legend.json"


@dataclass(frozen=True)
class LegendEntry:
    code: str
    name: str
    color: Tuple[int, int, int]


def _parse_color(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Unsupported color format: {value}")
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    return (r, g, b)


def load_legend() -> List[LegendEntry]:
    if not LEGEND_FILE.exists():
        raise FileNotFoundError(f"Legend file not found at {LEGEND_FILE}")
    with LEGEND_FILE.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    entries: List[LegendEntry] = []
    for code, data in raw.items():
        entries.append(
            LegendEntry(
                code=code,
                name=data["name"],
                color=_parse_color(data["color"]),
            )
        )
    return entries
