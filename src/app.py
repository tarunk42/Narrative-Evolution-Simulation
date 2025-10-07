from __future__ import annotations

from typing import Dict, List, Optional

import pygame
from pygame.math import Vector2

from . import settings
from .city import City
from .legend import load_legend
from .sim.camera import Camera
from .sim.clock import SimulationClock
from .sim.persona import EmploymentStatus
from .sim.population import PopulationManager
from .ui.controls import ControlBindings
from .ui.hud import HeadsUpDisplay
from .ui.dashboard_window import DashboardWindow
from .llm.agents import LLMManager


class Application:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(settings.WINDOW.title)
        self.screen = pygame.display.set_mode(settings.WINDOW.size)
        self.clock = pygame.time.Clock()

        self.city = City(settings.WORLD)
        self.world_surface = pygame.Surface(self.city.pixel_size).convert()
        self.camera = Camera(self.city.pixel_size, settings.WINDOW.size)
        self.sim_clock = SimulationClock(minutes_per_second=30.0)

        self.bindings = ControlBindings(settings.KEY_BINDINGS)
        legend_entries = load_legend()
        self.legend_lookup = {entry.code: entry.name for entry in legend_entries}
        self.info_font = pygame.font.SysFont("Menlo", 16)
        self.hud = HeadsUpDisplay(self.info_font, legend_entries)

        overlay_font = pygame.font.SysFont("Menlo", max(72, settings.WORLD.tile_size * 3))
        self.zone_overlay = self.city.create_zone_overlay(overlay_font)
        self.inspect_font = pygame.font.SysFont("Menlo", 14)
        self.dashboard_window = DashboardWindow(width=420, height=400)

        self.llm_manager = LLMManager()
        self.population = PopulationManager(
            self.city,
            llm_manager=self.llm_manager,
        )

        self.show_info_panel = True
        self.show_city_metrics = False
        self.show_population_metrics = False

        self.running = True
        self.paused = False

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(settings.WINDOW.target_fps) / 1000.0
            self._handle_events()
            self._update(dt)
            self._draw()

        self.dashboard_window.close()
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                if event.key in self.bindings.keys_for("zoom_in"):
                    self.camera.apply_zoom(+1, focus=pygame.mouse.get_pos())
                if event.key in self.bindings.keys_for("zoom_out"):
                    self.camera.apply_zoom(-1, focus=pygame.mouse.get_pos())
                if event.key in self.bindings.keys_for("reset_camera"):
                    self.camera.reset()
                if event.key in self.bindings.keys_for("toggle_pause"):
                    self.paused = not self.paused
                if event.key in self.bindings.keys_for("toggle_info"):
                    self.show_info_panel = not self.show_info_panel
                if event.key in self.bindings.keys_for("toggle_city_metrics"):
                    self.show_city_metrics = not self.show_city_metrics
                if event.key in self.bindings.keys_for("toggle_population_metrics"):
                    self.show_population_metrics = not self.show_population_metrics
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button in (2, 3) or (event.button == 1 and pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    self.camera.start_drag(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button in (1, 2, 3):
                    self.camera.end_drag()
            elif event.type == pygame.MOUSEMOTION:
                if self.camera.dragging:
                    self.camera.drag_to(event.pos)
            elif event.type == pygame.MOUSEWHEEL:
                focus = pygame.mouse.get_pos()
                steps = int(event.y)
                if steps == 0 and hasattr(event, "precise_y"):
                    steps = int(round(event.precise_y))
                self.camera.apply_zoom(steps, focus=focus)

    def _update(self, dt: float) -> None:
        pressed = pygame.key.get_pressed()
        control_state = self.bindings.state_from_keys(pressed)
        direction = Vector2(
            (1 if control_state.pan_right else 0) - (1 if control_state.pan_left else 0),
            (1 if control_state.pan_down else 0) - (1 if control_state.pan_up else 0),
        )
        if direction.length_squared() > 0:
            self.camera.move(direction, dt)

        if not self.camera.dragging:
            self.camera.edge_pan(pygame.mouse.get_pos(), dt)

        if not self.paused:
            self.sim_clock.update(dt)
            self.population.update(self.sim_clock, dt)
        else:
            # Still update sprites so they remain responsive to toggles
            self.population.agents.update(0.0)

    def _draw(self) -> None:
        self.world_surface.blit(self.city.background, (0, 0))
        if self.zone_overlay:
            self.world_surface.blit(self.zone_overlay, (0, 0))
        self.population.agents.draw(self.world_surface)

        view = self.camera.render(self.world_surface)
        self.screen.blit(view, (0, 0))

        city_metrics = self._build_city_metrics_lines()
        population_metrics = self._build_population_metrics_lines()
        time_str = self.sim_clock.formatted_time()
        date_str = self.sim_clock.formatted_date()

        inspection = self._gather_inspection()
        if inspection:
            self._draw_inspection(inspection)

        self.hud.draw(
            self.screen,
            show_info=self.show_info_panel,
            show_city_metrics=self.show_city_metrics,
            show_population_metrics=self.show_population_metrics,
            npc_count=self.population.active_commuters(),
            zoom=self.camera.zoom,
            paused=self.paused,
            clock_time=time_str,
            clock_date=date_str,
            city_metrics=city_metrics,
            population_metrics=population_metrics,
        )
        self.dashboard_window.update(
            time_str=time_str,
            date_str=date_str,
            city_metrics=city_metrics,
            population_metrics=population_metrics,
            citizens=self.population.citizen_summaries(),
            events=self.population.recent_birth_logs(),
        )
        pygame.display.flip()

    def _build_city_metrics_lines(self) -> List[str]:
        counts = self.city.zone_counts()
        total_tiles = self.city.width * self.city.height
        lines: List[str] = [f"Tiles: {total_tiles}"]

        if total_tiles:
            road_tiles = sum(counts.get(code, 0) for code in ("R", "S"))
            water_tiles = counts.get("W", 0)
            park_tiles = counts.get("P", 0)
            plaza_tiles = counts.get("L", 0)
            lines.append(f"Road coverage: {road_tiles} ({road_tiles / total_tiles:.1%})")
            lines.append(f"Water: {water_tiles} ({water_tiles / total_tiles:.1%})")
            lines.append(f"Parks: {park_tiles} ({park_tiles / total_tiles:.1%})")
            if plaza_tiles:
                lines.append(f"Plazas: {plaza_tiles} ({plaza_tiles / total_tiles:.1%})")
        else:
            lines.append("Road coverage: 0")

        for code in ("H", "C", "O", "I"):
            count = counts.get(code, 0)
            name = self.legend_lookup.get(code, code)
            if total_tiles:
                lines.append(f"{name}: {count} ({count / total_tiles:.1%})")
            else:
                lines.append(f"{name}: {count}")

        return lines

    def _build_population_metrics_lines(self) -> List[str]:
        total = self.population.population_count()
        breakdown = self.population.employment_breakdown()
        lines: List[str] = [f"Citizens: {total}", f"Households: {self.population.households_count()}"]

        if total:
            employed = breakdown.get(EmploymentStatus.EMPLOYED, 0)
            unemployed = breakdown.get(EmploymentStatus.UNEMPLOYED, 0)
            students = breakdown.get(EmploymentStatus.STUDENT, 0)
            retired = breakdown.get(EmploymentStatus.RETIRED, 0)
            lines.append(f"Employed: {employed} ({employed / total:.1%})")
            lines.append(f"Unemployed: {unemployed} ({unemployed / total:.1%})")
            lines.append(f"Students: {students} ({students / total:.1%})")
            lines.append(f"Retired: {retired} ({retired / total:.1%})")
        active = self.population.active_commuters()
        lines.append(f"Active commuters: {active}")
        lines.append(f"Simulation: {'paused' if self.paused else 'running'}")
        return lines

    def _gather_inspection(self) -> Optional[Dict[str, object]]:
        mouse_pos = pygame.mouse.get_pos()
        world_pos = self.camera.screen_to_world(Vector2(mouse_pos))
        tile_x = int(world_pos.x // self.city.tile_size)
        tile_y = int(world_pos.y // self.city.tile_size)

        tile_info = None
        tile_rect = None
        if 0 <= tile_x < self.city.width and 0 <= tile_y < self.city.height:
            tile_info = self.population.tile_report((tile_x, tile_y))
            world_rect = pygame.Rect(
                tile_x * self.city.tile_size,
                tile_y * self.city.tile_size,
                self.city.tile_size,
                self.city.tile_size,
            )
            tile_rect = self.camera.world_rect_to_screen(world_rect)

        npc_info = None
        npc_rect = None
        for sprite in self.population.agents.sprites():
            screen_rect = self.camera.world_rect_to_screen(sprite.rect)
            if screen_rect.collidepoint(mouse_pos):
                npc_info = self.population.citizen_report(sprite.citizen_id)
                npc_rect = screen_rect
                break

        if not tile_info and not npc_info:
            return None

        return {
            "mouse": mouse_pos,
            "tile": tile_info,
            "tile_rect": tile_rect,
            "npc": npc_info,
            "npc_rect": npc_rect,
        }

    def _draw_inspection(self, info: Dict[str, object]) -> None:
        highlight_color = (255, 255, 0)
        if info.get("tile_rect") and not info.get("npc_rect"):
            pygame.draw.rect(self.screen, highlight_color, info["tile_rect"], width=2)
        if info.get("npc_rect"):
            pygame.draw.rect(self.screen, (255, 160, 0), info["npc_rect"], width=2)

        lines: List[str] = []
        npc_info = info.get("npc")
        if npc_info:
            lines.append(f"Citizen {npc_info['name']} (ID {npc_info['id']})")
            lines.append(
                f"Gender: {npc_info['gender']} · Age: {npc_info['age_group']}"
            )
            lines.append(
                f"Employment: {npc_info['employment_status']} ({npc_info['profession']})"
            )
            lines.append(f"Address: {npc_info['address']}")
            if npc_info.get("job_tile"):
                lines.append(
                    f"Workplace: {npc_info['job_tile']} (Zone {npc_info['job_zone']})"
                )
            lines.append(f"Status: {npc_info['stage']}")
            relatives = npc_info.get("relatives", [])
            if relatives:
                lines.append("Relatives:")
                for rel in relatives:
                    lines.append(
                        f"  - {rel['name']} ({rel['relationship']}, {rel['gender']}, {rel['age']})"
                    )
            lines.append("")

        tile_info = info.get("tile")
        if tile_info and npc_info is None:
            lines.append(f"Tile {tile_info['tile']} · Zone {tile_info['zone']}")
            lines.append(
                f"Type: {tile_info.get('category', tile_info.get('terrain'))} ({tile_info.get('terrain')})"
            )
            if "capacity" in tile_info:
                lines.append(
                    f"Capacity: {tile_info['occupant_count']} / {tile_info['capacity']}"
                )
            if tile_info.get("households"):
                lines.append("Households:")
                for household in tile_info["households"]:
                    member_summary = ", ".join(household["members"])
                    lines.append(
                        f"  - {household['address']} ({member_summary})"
                    )
            if tile_info.get("employees"):
                lines.append("Employees:")
                for emp in tile_info["employees"]:
                    lines.append(
                        f"  - {emp['name']} ({emp['profession']})"
                    )

        if not lines:
            return

        padding = 8
        line_surfaces = [
            self.inspect_font.render(line, True, (245, 245, 245)) for line in lines
        ]
        width = max(s.get_width() for s in line_surfaces)
        height = len(line_surfaces) * self.inspect_font.get_linesize()
        panel = pygame.Surface((width + padding * 2, height + padding * 2), pygame.SRCALPHA)
        panel.fill((20, 20, 30, 210))

        y = padding
        for surf in line_surfaces:
            panel.blit(surf, (padding, y))
            y += self.inspect_font.get_linesize()

        mouse_x, mouse_y = info["mouse"]
        panel_rect = panel.get_rect()
        panel_rect.topleft = (mouse_x + 18, mouse_y + 18)
        screen_w, screen_h = self.screen.get_size()
        if panel_rect.right > screen_w:
            panel_rect.right = screen_w - 10
        if panel_rect.bottom > screen_h:
            panel_rect.bottom = screen_h - 10

        self.screen.blit(panel, panel_rect)


def main() -> None:
    Application().run()
