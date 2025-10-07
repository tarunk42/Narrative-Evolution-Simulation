from __future__ import annotations

import random
from typing import List, Tuple

import pygame
from pygame.math import Vector2

from ..city import City
from .persona import Citizen, DailyStage, Gender, Profession

PROFESSION_COLORS = {
    Profession.OFFICE: (96, 205, 255),
    Profession.RETAIL: (255, 189, 89),
    Profession.INDUSTRIAL: (255, 120, 120),
    Profession.SERVICE: (156, 225, 120),
    Profession.STUDENT: (212, 167, 255),
    Profession.NONE: (200, 200, 200),
}

GENDER_OUTLINES = {
    Gender.MALE: (30, 50, 120),
    Gender.FEMALE: (140, 40, 90),
}


class NPC(pygame.sprite.Sprite):
    def __init__(self, city: City, citizen: Citizen, stage: DailyStage) -> None:
        super().__init__()
        self.city = city
        self.citizen = citizen
        self.citizen_id = citizen.citizen_id
        self.speed = random.uniform(65.0, 100.0)
        self.stage = stage
        fill_color = PROFESSION_COLORS.get(citizen.profession, (200, 200, 200))
        outline = GENDER_OUTLINES.get(citizen.gender, (20, 20, 30))

        radius = max(4, city.tile_size // 3)
        self.image = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, fill_color, (radius, radius), radius)
        pygame.draw.circle(self.image, outline, (radius, radius), radius, width=3)
        self.rect = self.image.get_rect()

        spawn_tile = self._choose_spawn_tile(stage)
        self.grid_pos = Vector2(spawn_tile)
        self.pos = Vector2(self.city.tile_center(spawn_tile))
        self.rect.center = self.pos
        self.direction: Tuple[int, int] | None = None
        self.target_tile: Vector2 | None = None
        self._choose_new_direction(initial=True)

    def update(self, dt: float) -> None:
        if not self.target_tile:
            return
        target_center = Vector2(self.city.tile_center(self.target_tile))
        to_target = target_center - self.pos
        distance = to_target.length()

        if distance <= self.speed * dt:
            self.pos = target_center
            self.grid_pos = Vector2(self.target_tile)
            self._choose_new_direction()
        elif distance > 0.0:
            step = self.speed * dt
            if step > distance:
                step = distance
            if step > 0:
                move = to_target * (step / distance)
                self.pos += move

        self.rect.center = (round(self.pos.x), round(self.pos.y))

    def set_stage(self, stage: DailyStage) -> None:
        if stage == self.stage:
            return
        self.stage = stage
        spawn_tile = self._choose_spawn_tile(stage)
        self.grid_pos = Vector2(spawn_tile)
        self.pos = Vector2(self.city.tile_center(spawn_tile))
        self.rect.center = self.pos
        self.direction = None
        self.target_tile = None
        self._choose_new_direction(initial=True)

    def _choose_new_direction(self, initial: bool = False) -> None:
        possible: List[Tuple[int, int]] = []
        backtrack: Tuple[int, int] | None = None
        if self.direction is not None:
            backtrack = (-self.direction[0], -self.direction[1])

        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            next_tile = (self.grid_pos.x + dx, self.grid_pos.y + dy)
            if not self.city.is_road(next_tile):
                continue
            if backtrack and (dx, dy) == backtrack and not initial:
                continue
            possible.append((dx, dy))

        if not possible:
            fallbacks = [
                (dx, dy)
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]
                if self.city.is_road((self.grid_pos.x + dx, self.grid_pos.y + dy))
            ]
            if fallbacks:
                possible = fallbacks
            else:
                self.target_tile = None
                return

        self.direction = random.choice(possible)
        target = Vector2(
            self.grid_pos.x + self.direction[0],
            self.grid_pos.y + self.direction[1],
        )
        self.target_tile = target

    def _choose_spawn_tile(self, stage: DailyStage) -> Tuple[int, int]:
        if stage == DailyStage.COMMUTE_TO_WORK:
            base = self.citizen.home_tile
        else:
            base = self.citizen.job_tile or self.citizen.home_tile

        return _nearest_road_tile(self.city, base)


def _nearest_road_tile(city: City, start: Tuple[int, int]) -> Tuple[int, int]:
    if not city.road_tiles:
        return start
    sx, sy = start
    best_tile = city.road_tiles[0]
    best_dist = float("inf")
    for tile in city.road_tiles:
        tx, ty = tile
        dist = abs(tx - sx) + abs(ty - sy)
        if dist < best_dist:
            best_tile = tile
            best_dist = dist
            if dist == 0:
                break
    return best_tile
