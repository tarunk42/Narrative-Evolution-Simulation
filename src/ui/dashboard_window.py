from __future__ import annotations

from typing import Iterable, List, Dict

import pygame
import pygame.freetype
from pygame._sdl2.video import Window, Renderer, Texture


class DashboardWindow:
    """Auxiliary SDL2 window that presents simulation metrics."""

    def __init__(self, width: int = 420, height: int = 720, *, font_name: str = "Menlo", base_size: int = 16) -> None:
        pygame.freetype.init()
        self.window = Window("City Dashboard", size=(width, height))
        self.renderer = Renderer(self.window)
        self.width = width
        self.height = height
        self.font = pygame.freetype.SysFont(font_name, base_size)
        self.header_font = pygame.freetype.SysFont(font_name, base_size + 4, bold=True)
        self.small_font = pygame.freetype.SysFont(font_name, max(10, base_size - 2))
        self.background = (18, 20, 30, 255)
        self.text_color = (232, 238, 250)

    def close(self) -> None:
        self.window.destroy()

    def update(
        self,
        *,
        time_str: str,
        date_str: str,
        city_metrics: Iterable[str],
        population_metrics: Iterable[str],
        citizens: List[Dict[str, str]],
        events: Iterable[str],
    ) -> None:
        self.renderer.draw_color = self.background
        self.renderer.clear()
        y = 12
        y = self._blit_text(self.header_font, "City Dashboard", 12, y)
        y = self._blit_text(self.font, f"Time: {time_str}", 12, y + 6)
        y = self._blit_text(self.font, f"Date: {date_str}", 12, y + 2)
        y = self._draw_section("City Metrics", city_metrics, y + 10)
        y = self._draw_section("Population", population_metrics, y)
        y = self._draw_citizens(citizens, y)
        self._draw_events(events, y)
        self.renderer.present()

    # --------------------------------------------------------------- helpers
    def _draw_section(self, title: str, lines: Iterable[str], start_y: int) -> int:
        y = self._blit_text(self.header_font, title, 12, start_y)
        for line in lines:
            y = self._blit_text(self.font, line, 12, y + 2)
        return y + 8

    def _draw_citizens(self, citizens: List[Dict[str, str]], start_y: int) -> int:
        y = self._blit_text(self.header_font, "Citizens", 12, start_y)
        for entry in citizens[:14]:
            line = f"{entry['id']:03d} {entry['name']} ({entry['stage']})"
            y = self._blit_text(self.font, line, 12, y + 2)
            detail = f"  {entry['employment']} · {entry['profession']} · {entry['address']}"
            y = self._blit_text(self.small_font, detail, 12, y + 1)
        return y + 8

    def _draw_events(self, events: Iterable[str], start_y: int) -> None:
        y = self._blit_text(self.header_font, "Recent Events", 12, start_y)
        for line in events:
            y = self._blit_text(self.small_font, line, 12, y + 2)

    def _blit_text(self, font: pygame.freetype.Font, text: str, x: int, y: int) -> int:
        surface, _ = font.render(text, self.text_color)
        # Copy to intermediate surface to avoid texture stretching
        tmp = pygame.Surface((self.width, surface.get_height()), pygame.SRCALPHA)
        tmp.fill((0, 0, 0, 0))
        tmp.blit(surface, (x, 0))
        texture = Texture.from_surface(self.renderer, tmp)
        dst = pygame.Rect(0, y, tmp.get_width(), tmp.get_height())
        texture.draw(dst)
        return y + tmp.get_height()
