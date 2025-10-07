from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence, Tuple

import pygame
from pygame import Surface
from pygame.math import Vector2


@dataclass
class ZoomConfig:
    levels: Tuple[float, ...] = (
        0.5,
        0.65,
        0.75,
        1.0,
        1.25,
        1.5,
        1.75,
        2.0,
    )
    scroll_step: int = 1


class Camera:
    def __init__(
        self,
        world_size: Tuple[int, int],
        screen_size: Tuple[int, int],
        zoom_config: ZoomConfig | None = None,
    ) -> None:
        self.world_size = Vector2(world_size)
        self.screen_size = Vector2(screen_size)
        self.zoom_config = zoom_config or ZoomConfig()

        min_zoom = max(
            screen_size[0] / world_size[0],
            screen_size[1] / world_size[1],
        )
        levels = sorted(set(self.zoom_config.levels + (min_zoom,)))
        self.zoom_levels = tuple(levels)
        self.zoom_index = min(
            (i for i, value in enumerate(self.zoom_levels) if value >= 1.0),
            default=len(self.zoom_levels) - 1,
        )
        self.center = Vector2(world_size[0] / 2, world_size[1] / 2)

        self.pan_speed = 520.0
        self.edge_pan_speed = 360.0
        self.dragging = False
        self.drag_origin_screen = Vector2()
        self.drag_origin_center = Vector2()
        self._view_rect: pygame.Rect | None = None
        self._view_zoom: float = self.zoom

    @property
    def zoom(self) -> float:
        return self.zoom_levels[self.zoom_index]

    def render(self, world_surface: Surface) -> Surface:
        rect, zoom = self._current_view()
        self._view_rect = rect
        self._view_zoom = zoom
        cropped = world_surface.subsurface(rect).copy()
        scaled = pygame.transform.smoothscale(
            cropped, (int(self.screen_size.x), int(self.screen_size.y))
        )
        return scaled.convert()

    def move(self, direction: Vector2, dt: float) -> None:
        if direction.length_squared() == 0.0:
            return
        scaled_speed = self.pan_speed * dt / self.zoom
        self.center += direction.normalize() * scaled_speed
        self._clamp_center()

    def edge_pan(self, mouse_pos: Tuple[int, int], dt: float, margin: int = 32) -> None:
        mx, my = mouse_pos
        vx = 0.0
        vy = 0.0
        if mx < margin:
            vx -= 1.0 - mx / margin
        elif mx > self.screen_size.x - margin:
            vx += 1.0 - (self.screen_size.x - mx) / margin
        if my < margin:
            vy -= 1.0 - my / margin
        elif my > self.screen_size.y - margin:
            vy += 1.0 - (self.screen_size.y - my) / margin
        vec = Vector2(vx, vy)
        if vec.length_squared() > 0:
            speed = self.edge_pan_speed * dt / self.zoom
            self.center += vec.normalize() * speed
            self._clamp_center()

    def start_drag(self, screen_pos: Tuple[int, int]) -> None:
        self.dragging = True
        self.drag_origin_screen = Vector2(screen_pos)
        self.drag_origin_center = self.center.copy()

    def drag_to(self, screen_pos: Tuple[int, int]) -> None:
        if not self.dragging:
            return
        delta_screen = Vector2(screen_pos) - self.drag_origin_screen
        self.center = self.drag_origin_center - delta_screen / self.zoom
        self._clamp_center()

    def end_drag(self) -> None:
        self.dragging = False

    def apply_zoom(self, delta_steps: int, focus: Tuple[int, int] | None = None) -> None:
        if delta_steps == 0:
            return
        new_index = self.zoom_index + delta_steps
        new_index = max(0, min(len(self.zoom_levels) - 1, new_index))
        if new_index == self.zoom_index:
            return

        focus_world_before = None
        if focus is not None:
            focus_world_before = self.screen_to_world(Vector2(focus))
        self.zoom_index = new_index
        if focus_world_before is not None:
            focus_world_after = self.screen_to_world(Vector2(focus))
            delta = focus_world_before - focus_world_after
            self.center += delta
            self._clamp_center()

    def reset(self) -> None:
        self.center = Vector2(self.world_size.x / 2, self.world_size.y / 2)
        self.zoom_index = min(
            (i for i, value in enumerate(self.zoom_levels) if value >= 1.0),
            default=len(self.zoom_levels) - 1,
        )
        self._clamp_center()

    def screen_to_world(self, screen_point: Vector2) -> Vector2:
        rect, zoom = self._current_view()
        top_left = Vector2(rect.x, rect.y)
        world_point = top_left + screen_point / zoom
        return world_point

    def world_to_screen(self, world_point: Tuple[float, float]) -> Vector2:
        rect, zoom = self._current_view()
        rel = Vector2(world_point[0] - rect.x, world_point[1] - rect.y)
        return rel * zoom

    def world_rect_to_screen(self, world_rect: pygame.Rect) -> pygame.Rect:
        rect, zoom = self._current_view()
        screen_rect = pygame.Rect(0, 0, 0, 0)
        screen_rect.x = int(round((world_rect.x - rect.x) * zoom))
        screen_rect.y = int(round((world_rect.y - rect.y) * zoom))
        screen_rect.width = int(round(world_rect.width * zoom))
        screen_rect.height = int(round(world_rect.height * zoom))
        return screen_rect

    def _clamp_center(self) -> None:
        zoom = self.zoom
        view_width = min(self.screen_size.x / zoom, self.world_size.x)
        view_height = min(self.screen_size.y / zoom, self.world_size.y)
        half_w = view_width / 2
        half_h = view_height / 2

        if view_width >= self.world_size.x:
            self.center.x = self.world_size.x / 2
        else:
            self.center.x = min(
                self.world_size.x - half_w, max(half_w, self.center.x)
            )

        if view_height >= self.world_size.y:
            self.center.y = self.world_size.y / 2
        else:
            self.center.y = min(
                self.world_size.y - half_h, max(half_h, self.center.y)
            )

    def _current_view(self) -> Tuple[pygame.Rect, float]:
        zoom = self.zoom
        view_width = min(self.screen_size.x / zoom, self.world_size.x)
        view_height = min(self.screen_size.y / zoom, self.world_size.y)
        half_w = view_width / 2
        half_h = view_height / 2

        top_left_x = self.center.x - half_w
        top_left_y = self.center.y - half_h
        max_x = self.world_size.x - view_width
        max_y = self.world_size.y - view_height
        if max_x <= 0:
            top_left_x = max_x / 2
        else:
            top_left_x = max(0, min(max_x, top_left_x))
        if max_y <= 0:
            top_left_y = max_y / 2
        else:
            top_left_y = max(0, min(max_y, top_left_y))

        rect = pygame.Rect(
            int(round(top_left_x)),
            int(round(top_left_y)),
            int(round(view_width)),
            int(round(view_height)),
        )
        return rect, zoom
