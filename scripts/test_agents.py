#!/usr/bin/env python
"""Quick smoke test for the OpenAI Agents SDK integration."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm.agents import LLMManager  # type: ignore  # noqa: E402


def main() -> None:
    manager = LLMManager(enable_agents=True)
    persona = manager.generate_child_persona(
        city_date="2026-01-15",
        household_address="B-001",
        parents=[
            {
                "id": 1,
                "name": "Maya Patel",
                "gender": "female",
                "temperament": "Organized and caring",
                "values": ["community", "innovation"],
                "memories": [],
            },
            {
                "id": 2,
                "name": "Arjun Patel",
                "gender": "male",
                "temperament": "Analytical and calm",
                "values": ["family", "stability"],
                "memories": [],
            },
        ],
        recent_events=["2026-01-10: Household received energy-efficiency grant."],
    )
    print("Generated child persona:")
    print(persona)

    log = manager.record_city_event(
        {
            "timestamp": "2026-01-15T09:00:00",
            "event": "Birth",
            "details": persona.summary,
        }
    )
    print("City log response:")
    print(log)


if __name__ == "__main__":
    main()
