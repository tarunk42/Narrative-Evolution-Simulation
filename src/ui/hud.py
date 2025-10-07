from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

import pygame
from pygame import Surface

from ..legend import LegendEntry


class HeadsUpDisplay:
    def __init__(self, font: pygame.font.Font, legend: Iterable[LegendEntry]) -> None:
        self.font = font
        self.legend_entries: List[LegendEntry] = list(legend)
        self.padding = 12
        self.line_height = font.get_linesize()
        self.section_gap = max(8, self.line_height // 2)
        self.swatch_size = max(10, self.line_height - 6)
        self.swatch_spacing = 10
        self.text_color = (235, 235, 245)
        self.background_color = (20, 20, 28, 180)
        self.legend_text_surfaces: List[Tuple[LegendEntry, Surface]] = [
            (entry, self.font.render(f"{entry.code} – {entry.name}", True, self.text_color))
            for entry in self.legend_entries
        ]

    def draw(
        self,
        surface: Surface,
        *,
        show_info: bool,
        show_city_metrics: bool,
        show_population_metrics: bool,
        npc_count: int,
        zoom: float,
        paused: bool,
        clock_time: str,
        clock_date: str,
        city_metrics: Sequence[str],
        population_metrics: Sequence[str],
    ) -> None:
        if show_info:
            info_panel = self._build_info_panel(npc_count, zoom, paused, clock_time, clock_date)
            surface.blit(info_panel, (12, 12))

        right_margin = 12
        y_right = 12
        if show_city_metrics:
            city_panel = self._build_metrics_panel("City Metrics", city_metrics)
            surface.blit(
                city_panel,
                (surface.get_width() - city_panel.get_width() - right_margin, y_right),
            )
            y_right += city_panel.get_height() + 12

        if show_population_metrics:
            pop_panel = self._build_metrics_panel("Population Metrics", population_metrics)
            surface.blit(
                pop_panel,
                (surface.get_width() - pop_panel.get_width() - right_margin, y_right),
            )

    def _build_info_panel(
        self,
        npc_count: int,
        zoom: float,
        paused: bool,
        clock_time: str,
        clock_date: str,
    ) -> Surface:
        stats_lines = [
            f"Time: {clock_time}",
            f"Date: {clock_date}",
            f"Active commuters: {npc_count}",
            f"Zoom: {zoom:.2f}x",
            "Drag/scroll to navigate",
            "Space reset camera",
            "O pause · I info · C city · P population",
        ]
        if paused:
            stats_lines.insert(0, "PAUSED")

        stat_surfaces = [self.font.render(line, True, self.text_color) for line in stats_lines]
        stats_width = max((surf.get_width() for surf in stat_surfaces), default=0)

        legend_width = 0
        for _, legend_surface in self.legend_text_surfaces:
            legend_width = max(
                legend_width,
                self.swatch_size + self.swatch_spacing + legend_surface.get_width(),
            )

        panel_width = max(stats_width, legend_width) + self.padding * 2
        panel_height = self.padding * 2 + len(stat_surfaces) * self.line_height
        if self.legend_text_surfaces:
            panel_height += self.section_gap + len(self.legend_text_surfaces) * self.line_height

        panel = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel.fill(self.background_color)

        y = self.padding
        for stat_surface in stat_surfaces:
            panel.blit(stat_surface, (self.padding, y))
            y += self.line_height

        if self.legend_text_surfaces:
            y += self.section_gap
            for entry, legend_surface in self.legend_text_surfaces:
                swatch_top = y + (self.line_height - self.swatch_size) // 2
                swatch_rect = pygame.Rect(self.padding, swatch_top, self.swatch_size, self.swatch_size)
                pygame.draw.rect(panel, entry.color, swatch_rect, border_radius=3)
                pygame.draw.rect(panel, (0, 0, 0, 120), swatch_rect, width=1, border_radius=3)
                text_x = self.padding + self.swatch_size + self.swatch_spacing
                panel.blit(legend_surface, (text_x, y))
                y += self.line_height

        return panel

    def _build_metrics_panel(self, title: str, lines: Sequence[str]) -> Surface:
        if not lines:
            lines = ["No data"]

        header_surface = self.font.render(title, True, self.text_color)
        line_surfaces = [self.font.render(line, True, self.text_color) for line in lines]

        content_width = max((surf.get_width() for surf in line_surfaces), default=0)
        panel_width = max(header_surface.get_width(), content_width) + self.padding * 2
        header_height = header_surface.get_height()
        panel_height = (
            self.padding * 2
            + header_height
            + self.section_gap
            + len(line_surfaces) * self.line_height
        )

        panel = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel.fill(self.background_color)

        y = self.padding
        panel.blit(header_surface, (self.padding, y))
        y += header_height + self.section_gap

        for line_surface in line_surfaces:
            panel.blit(line_surface, (self.padding, y))
            y += self.line_height

        return panel
