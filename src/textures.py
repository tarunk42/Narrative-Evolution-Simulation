from __future__ import annotations

import random
from typing import Dict, Iterable, Tuple
import hashlib

import numpy as np
import pygame
from pygame import Surface

from .constants import ROAD_E, ROAD_N, ROAD_S, ROAD_W

Color = Tuple[int, int, int]


def _seed_value(token: str) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _make_noise_surface(
    size: int,
    base_color: Color,
    variation: int,
    seed: str,
) -> Surface:
    base = np.array(base_color, dtype=np.int16)
    np_rng = np.random.default_rng(_seed_value(f"{seed}-{size}-{base_color}-{variation}"))
    noise = np_rng.integers(-variation, variation + 1, (size, size, 3), dtype=np.int16)
    pixels = np.clip(base + noise, 0, 255).astype(np.uint8)
    surf = pygame.surfarray.make_surface(np.transpose(pixels, (1, 0, 2)))
    return surf.convert()


def _draw_sidewalks(
    surf: Surface,
    mask: int,
    neighbor_types: Dict[str, str | None],
    *,
    size: int,
) -> None:
    sidewalk_color = (170, 170, 176)
    border_color = (210, 210, 215)
    edge = max(3, size // 10)

    def draw_edge(rect: pygame.Rect) -> None:
        pygame.draw.rect(surf, sidewalk_color, rect)
        border = rect.inflate(0, 0)
        pygame.draw.rect(surf, border_color, border, width=1)

    def allow(direction: str) -> bool:
        neighbor = neighbor_types.get(direction)
        return neighbor not in {"R", "S", "W"}

    if allow("N"):
        draw_edge(pygame.Rect(0, 0, size, edge))
    if allow("S"):
        draw_edge(pygame.Rect(0, size - edge, size, edge))
    if allow("W"):
        draw_edge(pygame.Rect(0, 0, edge, size))
    if allow("E"):
        draw_edge(pygame.Rect(size - edge, 0, edge, size))


def _draw_lane_lines(
    surf: Surface,
    mask: int,
    *,
    size: int,
    major: bool,
) -> None:
    center_x = size // 2
    center_y = size // 2
    line_width = max(2, size // 18)
    dash_length = max(6, size // 4)
    gap = dash_length // 2
    yellow = (248, 214, 82)
    white = (235, 235, 235)
    grey = (54, 54, 58)

    if major and (mask & ROAD_E) and (mask & ROAD_W):
        pygame.draw.rect(
            surf,
            grey,
            pygame.Rect(0, center_y - line_width * 3, size, line_width * 6),
        )

    def dash_line(start: Tuple[int, int], end: Tuple[int, int], vertical: bool) -> None:
        total = size if vertical else size
        offset = 0
        color = yellow if major else white
        while offset < total:
            length = min(dash_length, total - offset)
            if vertical:
                rect = pygame.Rect(
                    start[0] - line_width // 2,
                    start[1] + offset,
                    line_width,
                    length,
                )
            else:
                rect = pygame.Rect(
                    start[0] + offset,
                    start[1] - line_width // 2,
                    length,
                    line_width,
                )
            pygame.draw.rect(surf, color, rect)
            offset += dash_length + gap

    if (mask & ROAD_N) and (mask & ROAD_S):
        dash_line((center_x, 0), (center_x, size), vertical=True)
    if (mask & ROAD_E) and (mask & ROAD_W):
        dash_line((0, center_y), (size, center_y), vertical=False)

    intersections = sum(
        1 for flag in (ROAD_N, ROAD_E, ROAD_S, ROAD_W) if mask & flag
    )
    if intersections >= 3:
        cross_size = size // 4
        rect = pygame.Rect(
            center_x - cross_size // 2,
            center_y - cross_size // 2,
            cross_size,
            cross_size,
        )
        pygame.draw.rect(surf, (240, 240, 240), rect, border_radius=3)


def road_tile(
    size: int,
    mask: int,
    *,
    major: bool,
    neighbor_types: Dict[str, str | None],
) -> Surface:
    seed = f"road-{size}-{mask}-{major}-{neighbor_types.get('N')}-{neighbor_types.get('E')}-{neighbor_types.get('S')}-{neighbor_types.get('W')}"
    rng = random.Random(seed)
    base_color = (42, 46, 56) if major else (52, 56, 63)
    surf = _make_noise_surface(size, base_color, 8, seed)
    _draw_sidewalks(surf, mask, neighbor_types, size=size)
    _draw_lane_lines(surf, mask, size=size, major=major)
    return surf


BUILDING_STYLES: Dict[str, Dict[str, Iterable[Color]]] = {
    "H": {
        "base": [
            (196, 205, 214),
            (179, 193, 210),
            (205, 194, 182),
            (185, 174, 200),
        ],
        "windows": [(241, 240, 216), (223, 234, 242)],
        "accents": [(99, 121, 143), (126, 104, 118)],
    },
    "C": {
        "base": [
            (214, 179, 137),
            (205, 152, 142),
            (204, 188, 144),
            (193, 167, 210),
        ],
        "windows": [(250, 243, 173), (255, 214, 152)],
        "accents": [(95, 79, 60), (78, 58, 93)],
    },
    "O": {
        "base": [
            (157, 183, 194),
            (171, 207, 217),
            (143, 172, 198),
        ],
        "windows": [(236, 246, 255), (202, 228, 247)],
        "accents": [(54, 84, 112), (42, 66, 91)],
    },
    "I": {
        "base": [
            (170, 166, 154),
            (183, 169, 145),
            (158, 162, 175),
        ],
        "windows": [(244, 220, 187), (216, 217, 218)],
        "accents": [(96, 86, 76), (88, 93, 102)],
    },
}


def _draw_windows(surf: Surface, color: Color, spacing: int, inset: int) -> None:
    rect = surf.get_rect().inflate(-inset * 2, -inset * 2)
    win_w = max(4, spacing - 2)
    win_h = win_w + 2
    for y in range(rect.top, rect.bottom, spacing):
        for x in range(rect.left, rect.right, spacing):
            pygame.draw.rect(
                surf,
                color,
                pygame.Rect(x, y, win_w, win_h),
                border_radius=2,
            )


def building_tile(size: int, zone: str, seed: Tuple[int, int]) -> Surface:
    style = BUILDING_STYLES[zone]
    rng = random.Random(f"building-{zone}-{seed[0]}-{seed[1]}")
    base_color = rng.choice(list(style["base"]))
    surf = _make_noise_surface(size, base_color, 6, f"building-noise-{zone}-{seed[0]}-{seed[1]}")

    # top/bottom shading to suggest depth
    top_rect = pygame.Rect(0, 0, size, size // 4)
    pygame.draw.rect(
        surf,
        tuple(min(255, c + 18) for c in base_color),
        top_rect,
    )
    bottom_rect = pygame.Rect(0, size - size // 4, size, size // 4)
    pygame.draw.rect(
        surf,
        tuple(max(0, c - 18) for c in base_color),
        bottom_rect,
    )

    accent_color = rng.choice(list(style["accents"]))
    stripe_height = max(3, size // 12)
    pygame.draw.rect(
        surf,
        accent_color,
        pygame.Rect(0, size // 2 - stripe_height // 2, size, stripe_height),
    )

    window_color = rng.choice(list(style["windows"]))
    spacing = max(6, size // 4)
    _draw_windows(surf, window_color, spacing, inset=max(4, size // 8))

    hvac_radius = max(3, size // 8)
    for _ in range(rng.randint(1, 3)):
        cx = rng.randint(hvac_radius, size - hvac_radius)
        cy = rng.randint(hvac_radius, size - hvac_radius)
        pygame.draw.circle(surf, (90, 96, 110), (cx, cy), hvac_radius)
        pygame.draw.circle(surf, (180, 185, 195), (cx, cy), hvac_radius - 2)

    return surf


def park_tile(size: int, seed: Tuple[int, int]) -> Surface:
    rng = random.Random(f"park-{seed[0]}-{seed[1]}")
    surf = _make_noise_surface(size, (74, 138, 88), 12, f"park-noise-{seed[0]}-{seed[1]}")
    for _ in range(6):
        radius = rng.randint(size // 8, size // 5)
        cx = rng.randint(radius, size - radius)
        cy = rng.randint(radius, size - radius)
        pygame.draw.circle(
            surf,
            (81, 156, 97),
            (cx, cy),
            radius,
        )
    for _ in range(3):
        rect = pygame.Rect(0, 0, size // 2, size // 6)
        rect.center = (
            rng.randint(size // 4, size - size // 4),
            rng.randint(size // 4, size - size // 4),
        )
        pygame.draw.rect(surf, (186, 203, 151), rect, border_radius=6)
    return surf


def water_tile(size: int, seed: Tuple[int, int]) -> Surface:
    rng = random.Random(f"water-{seed[0]}-{seed[1]}")
    base = _make_noise_surface(size, (56, 147, 191), 14, f"water-noise-{seed[0]}-{seed[1]}")
    overlay = pygame.Surface((size, size), pygame.SRCALPHA)
    for i in range(6):
        radius = rng.randint(size // 4, size // 3)
        cx = rng.randint(radius, size - radius)
        cy = rng.randint(radius, size - radius)
        pygame.draw.circle(
            overlay,
            (255, 255, 255, max(10, 40 - i * 5)),
            (cx, cy),
            radius,
            width=2,
        )
    base.blit(overlay, (0, 0))
    return base


def plaza_tile(size: int, seed: Tuple[int, int]) -> Surface:
    rng = random.Random(f"plaza-{seed[0]}-{seed[1]}")
    surf = _make_noise_surface(size, (189, 178, 158), 10, f"plaza-noise-{seed[0]}-{seed[1]}")
    grid_color = (168, 156, 140)
    spacing = max(6, size // 5)
    for x in range(0, size, spacing):
        pygame.draw.line(surf, grid_color, (x, 0), (x, size))
    for y in range(0, size, spacing):
        pygame.draw.line(surf, grid_color, (0, y), (size, y))
    fountain_color = (120, 170, 200)
    rect = pygame.Rect(0, 0, size // 2, size // 2)
    rect.center = (size // 2, size // 2)
    pygame.draw.ellipse(surf, fountain_color, rect)
    pygame.draw.ellipse(surf, (215, 230, 240), rect.inflate(-4, -4))
    return surf
