from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WindowConfig:
    size: tuple[int, int] = (1280, 720)
    title: str = "Mini City Simulation"
    target_fps: int = 60


@dataclass(frozen=True)
class WorldConfig:
    tile_size: int = 32
    grid_width: int = 42
    grid_height: int = 32
    npc_count: int = 20


ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"
TILESET_PATH = ASSET_DIR / "tileset.png"


KEY_BINDINGS = {
    "pan_left": (("keyboard", "K_a"), ("keyboard", "K_LEFT")),
    "pan_right": (("keyboard", "K_d"), ("keyboard", "K_RIGHT")),
    "pan_up": (("keyboard", "K_w"), ("keyboard", "K_UP")),
    "pan_down": (("keyboard", "K_s"), ("keyboard", "K_DOWN")),
    "zoom_in": (
        ("keyboard", "K_EQUALS"),
        ("keyboard", "K_RIGHTBRACKET"),
        ("keyboard", "K_KP_PLUS"),
    ),
    "zoom_out": (
        ("keyboard", "K_MINUS"),
        ("keyboard", "K_LEFTBRACKET"),
        ("keyboard", "K_KP_MINUS"),
    ),
    "reset_camera": (("keyboard", "K_SPACE"),),
    "toggle_pause": (("keyboard", "K_o"),),
    "toggle_info": (("keyboard", "K_i"),),
    "toggle_city_metrics": (("keyboard", "K_c"),),
    "toggle_population_metrics": (("keyboard", "K_p"),),
}


WINDOW = WindowConfig()
WORLD = WorldConfig()
