from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import pygame

Binding = Tuple[str, str]


def _resolve(binding: Binding) -> int:
    device, name = binding
    if device != "keyboard":
        raise ValueError(f"Unsupported device {device}")
    if not hasattr(pygame, name):
        raise AttributeError(f"Unknown pygame constant: {name}")
    return getattr(pygame, name)


@dataclass
class ControlState:
    pan_left: bool = False
    pan_right: bool = False
    pan_up: bool = False
    pan_down: bool = False
    zoom_in: bool = False
    zoom_out: bool = False
    reset_camera: bool = False
    toggle_pause: bool = False
    toggle_info: bool = False
    toggle_city_metrics: bool = False
    toggle_population_metrics: bool = False


class ControlBindings:
    def __init__(self, raw_bindings: Dict[str, Iterable[Binding]]) -> None:
        self.bindings: Dict[str, Tuple[int, ...]] = {
            action: tuple(_resolve(binding) for binding in binding_list)
            for action, binding_list in raw_bindings.items()
        }

    def state_from_keys(self, pressed: Iterable[bool]) -> ControlState:
        state = ControlState()
        for action, keys in self.bindings.items():
            active = any(pressed[key] for key in keys)
            setattr(state, action, active)
        return state

    def keys_for(self, action: str) -> Tuple[int, ...]:
        return self.bindings.get(action, ())
