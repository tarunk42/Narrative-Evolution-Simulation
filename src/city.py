from __future__ import annotations

import random
from collections import Counter
from typing import Dict, List, Sequence, Tuple

import pygame
from pygame import Surface

from . import settings, textures
from .constants import (
    PLAZA_TYPES,
    ROAD_E,
    ROAD_N,
    ROAD_S,
    ROAD_TYPES,
    ROAD_W,
    PARK_TYPES,
    WATER_TYPES,
)

ZONE_TYPES = ("H", "C", "O", "I")


class City:
    def __init__(self, config: settings.WorldConfig) -> None:
        self.config = config
        self.tile_size = config.tile_size
        self.width = config.grid_width
        self.height = config.grid_height
        self.pixel_size = (self.width * self.tile_size, self.height * self.tile_size)

        self.map = self._build_map()
        self.road_tiles = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if self.map[y][x] in ROAD_TYPES
        ]
        self._zone_column_edges_tiles = self._compute_zone_column_edges_tiles()
        self._zone_row_edges_tiles = self._compute_zone_row_edges_tiles()
        self.zone_labels = self._build_zone_labels()
        self._zone_column_boundaries = [edge * self.tile_size for edge in self._zone_column_edges_tiles]
        self._zone_row_boundaries = [edge * self.tile_size for edge in self._zone_row_edges_tiles]

        self.background = pygame.Surface(self.pixel_size).convert()
        self._render_background()

    def draw(self, surface: Surface) -> None:
        surface.blit(self.background, (0, 0))

    def tile_center(self, tile: Sequence[float]) -> Tuple[float, float]:
        tx, ty = int(tile[0]), int(tile[1])
        return (
            tx * self.tile_size + self.tile_size / 2,
            ty * self.tile_size + self.tile_size / 2,
        )

    def is_within(self, tile: Sequence[float]) -> bool:
        tx, ty = int(tile[0]), int(tile[1])
        return 0 <= tx < self.width and 0 <= ty < self.height

    def is_road(self, tile: Sequence[float]) -> bool:
        if not self.is_within(tile):
            return False
        tx, ty = int(tile[0]), int(tile[1])
        return self.map[ty][tx] in ROAD_TYPES

    def zone_counts(self) -> Counter[str]:
        counts: Counter[str] = Counter()
        for row in self.map:
            counts.update(row)
        return counts

    def zone_label(self, x: int, y: int) -> str:
        x = max(0, min(self.width - 1, x))
        y = max(0, min(self.height - 1, y))
        return self.zone_labels[y][x]

    def create_zone_overlay(self, font: pygame.font.Font) -> Surface:
        overlay = pygame.Surface(self.pixel_size, pygame.SRCALPHA)
        line_color = (255, 255, 255, 60)
        dash_length = 12
        gap = 8

        # Vertical dotted lines
        for x in self._zone_column_boundaries:
            y = 0
            while y < self.pixel_size[1]:
                pygame.draw.line(
                    overlay,
                    line_color,
                    (x, y),
                    (x, min(self.pixel_size[1], y + dash_length)),
                    width=1,
                )
                y += dash_length + gap

        # Horizontal dotted lines
        for y_boundary in self._zone_row_boundaries:
            x = 0
            while x < self.pixel_size[0]:
                pygame.draw.line(
                    overlay,
                    line_color,
                    (x, y_boundary),
                    (min(self.pixel_size[0], x + dash_length), y_boundary),
                    width=1,
                )
                x += dash_length + gap

        zone_letters = [["A", "B", "C"], ["D", "E", "F"]]
        column_edges = [0] + self._zone_column_boundaries + [self.pixel_size[0]]
        row_edges = [0] + self._zone_row_boundaries + [self.pixel_size[1]]
        for row in range(2):
            for col in range(3):
                letter = zone_letters[row][col]
                x_start = column_edges[col]
                x_end = column_edges[col + 1]
                y_start = row_edges[row]
                y_end = row_edges[row + 1]

                text = font.render(letter, True, (255, 255, 255))
                text.set_alpha(40)
                rect = text.get_rect()
                rect.center = (
                    (x_start + x_end) // 2,
                    (y_start + y_end) // 2,
                )
                overlay.blit(text, rect)

        return overlay

    def _build_map(self) -> List[List[str]]:
        rng = random.Random(42)
        grid: List[List[str]] = [["B" for _ in range(self.width)] for _ in range(self.height)]

        for x in range(self.width):
            grid[1][x] = "R"
            grid[self.height - 2][x] = "R"
        for y in range(self.height):
            grid[y][1] = "R"
            grid[y][self.width - 2] = "R"

        for y in range(4, self.height - 4, 6):
            for x in range(1, self.width - 1):
                grid[y][x] = "R"
        for x in range(4, self.width - 4, 7):
            for y in range(1, self.height - 1):
                grid[y][x] = "R"

        for y in range(2, self.height - 2, 9):
            for x in range(1, self.width - 1):
                if grid[y][x] == "B":
                    grid[y][x] = "S"
        for x in range(3, self.width - 3, 9):
            for y in range(1, self.height - 1):
                if grid[y][x] == "B":
                    grid[y][x] = "S"

        for offset in range(-self.height, self.width + self.height):
            x = offset + 6
            y1 = offset // 2 + 5
            y2 = (self.height - 1 - offset) // 2 + self.height // 3
            if 2 <= x < self.width - 2 and 2 <= y1 < self.height - 2:
                if grid[y1][x] == "B":
                    grid[y1][x] = "S"
            if 2 <= x < self.width - 2 and 2 <= y2 < self.height - 2:
                if grid[y2][x] == "B":
                    grid[y2][x] = "S"

        for _ in range(9):
            w = rng.randint(2, 4)
            h = rng.randint(2, 4)
            x0 = rng.randint(2, self.width - w - 3)
            y0 = rng.randint(2, self.height - h - 3)
            for y in range(y0, y0 + h):
                for x in range(x0, x0 + w):
                    if grid[y][x] == "B":
                        grid[y][x] = "P"
            for y in range(y0 - 1, y0 + h + 1):
                for x in range(x0 - 1, x0 + w + 1):
                    if 0 <= x < self.width and 0 <= y < self.height:
                        if grid[y][x] == "B":
                            grid[y][x] = "S"

        for x in range(8, self.width - 8, 12):
            for y in range(2, self.height - 2):
                if grid[y][x] == "B":
                    grid[y][x] = "W"

        self._assign_zones(grid)
        return grid

    def _compute_zone_column_edges_tiles(self) -> List[int]:
        edges: List[int] = []
        for idx in range(1, 3):
            edge = int(round(self.width * idx / 3))
            edge = max(1, min(self.width - 1, edge))
            if edges and edge <= edges[-1]:
                edge = min(self.width - 1, edges[-1] + 1)
            edges.append(edge)
        return edges

    def _compute_zone_row_edges_tiles(self) -> List[int]:
        if self.height <= 1:
            return [1]
        edge = int(round(self.height / 2))
        edge = max(1, min(self.height - 1, edge))
        return [edge]

    def _build_zone_labels(self) -> List[List[str]]:
        letters = [["A", "B", "C"], ["D", "E", "F"]]
        first_col, second_col = self._zone_column_edges_tiles
        first_row = self._zone_row_edges_tiles[0]
        labels: List[List[str]] = []
        for y in range(self.height):
            row_idx = 0 if y < first_row else 1
            row_labels: List[str] = []
            for x in range(self.width):
                if x < first_col:
                    col_idx = 0
                elif x < second_col:
                    col_idx = 1
                else:
                    col_idx = 2
                row_labels.append(letters[row_idx][col_idx])
            labels.append(row_labels)
        return labels

    def _assign_zones(self, grid: List[List[str]]) -> None:
        block_size = 4
        zone_choices = [z for z in ZONE_TYPES]
        zone_weights = [0.42, 0.22, 0.2, 0.16]

        for by in range(0, self.height, block_size):
            for bx in range(0, self.width, block_size):
                rng = random.Random(f"block-{bx}-{by}")
                zone = rng.choices(zone_choices, weights=zone_weights)[0]
                for y in range(by, min(by + block_size, self.height)):
                    for x in range(bx, min(bx + block_size, self.width)):
                        if grid[y][x] == "B":
                            if rng.random() < 0.08:
                                grid[y][x] = "P"
                            else:
                                grid[y][x] = zone

                if rng.random() < 0.12:
                    cx = min(bx + block_size // 2, self.width - 1)
                    cy = min(by + block_size // 2, self.height - 1)
                    if grid[cy][cx] in zone_choices:
                        grid[cy][cx] = "L"

    def _neighbor_types(self, x: int, y: int) -> Dict[str, str | None]:
        return {
            "N": self.map[y - 1][x] if y > 0 else None,
            "E": self.map[y][x + 1] if x < self.width - 1 else None,
            "S": self.map[y + 1][x] if y < self.height - 1 else None,
            "W": self.map[y][x - 1] if x > 0 else None,
        }

    def _road_surface_for(self, x: int, y: int, road_type: str) -> Surface:
        mask = 0
        if y > 0 and self.map[y - 1][x] in ROAD_TYPES:
            mask |= ROAD_N
        if x < self.width - 1 and self.map[y][x + 1] in ROAD_TYPES:
            mask |= ROAD_E
        if y < self.height - 1 and self.map[y + 1][x] in ROAD_TYPES:
            mask |= ROAD_S
        if x > 0 and self.map[y][x - 1] in ROAD_TYPES:
            mask |= ROAD_W

        neighbors = self._neighbor_types(x, y)
        return textures.road_tile(
            self.tile_size,
            mask,
            major=(road_type == "R"),
            neighbor_types=neighbors,
        )

    def _render_background(self) -> None:
        for y in range(self.height):
            for x in range(self.width):
                tile = self.map[y][x]
                top_left = (x * self.tile_size, y * self.tile_size)
                if tile in ROAD_TYPES:
                    surf = self._road_surface_for(x, y, tile)
                elif tile in WATER_TYPES:
                    surf = textures.water_tile(self.tile_size, (x, y))
                elif tile in PARK_TYPES:
                    surf = textures.park_tile(self.tile_size, (x, y))
                elif tile in PLAZA_TYPES:
                    surf = textures.plaza_tile(self.tile_size, (x, y))
                else:
                    surf = textures.building_tile(self.tile_size, tile, (x, y))
                self.background.blit(surf, top_left)
