from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, List, Optional

try:  # pragma: no cover - optional dependency
    from agents import Agent, Runner
    _AGENTS_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    Agent = None  # type: ignore
    Runner = None  # type: ignore
    _AGENTS_AVAILABLE = False


LOGGER = logging.getLogger(__name__)


@dataclass
class PersonaResult:
    name: str
    age_group: str
    temperament: str
    values: List[str]
    gender: str
    summary: str


@dataclass
class ChildPersonaOutput:
    name: str
    gender: str
    age_group: str
    temperament: str
    values: List[str]
    summary: str


@dataclass
class CityLogOutput:
    summary: str
    log_entry: str


class LLMManager:
    """Adapter around the OpenAI Agents SDK for persona generation and city logging."""

    def __init__(self, *, model: str = "gpt-4o-mini", enable_agents: bool = True) -> None:
        self.model = model
        self.persona_agent: Optional[Agent] = None  # type: ignore[assignment]
        self.city_agent: Optional[Agent] = None  # type: ignore[assignment]

        if enable_agents and _AGENTS_AVAILABLE:
            try:
                self.persona_agent = Agent(  # type: ignore[call-arg]
                    name="Citizen Persona Designer",
                    instructions=(
                        "You design concise JSON persona summaries for newborn citizens. "
                        "Blend parental traits, respect cultural context, and return the structured output."
                    ),
                    model=self.model,
                    output_type=ChildPersonaOutput,
                )
                self.city_agent = Agent(  # type: ignore[call-arg]
                    name="City Chronicle",
                    instructions=(
                        "You record concise city narrative log entries. "
                        "Summarize new events and return structured output with 'summary' and 'log_entry'."
                    ),
                    model=self.model,
                    output_type=CityLogOutput,
                )
            except Exception as exc:  # pragma: no cover
                LOGGER.warning("Failed to initialise Agents SDK: %s", exc)
                self.persona_agent = None
                self.city_agent = None

    # ------------------------------------------------------------------ persona
    def generate_child_persona(
        self,
        *,
        city_date: str,
        household_address: str,
        parents: List[dict[str, Any]],
        recent_events: List[str],
    ) -> PersonaResult:
        """Generate a new child persona by delegating to the persona agent when available."""

        if self.persona_agent is not None and Runner is not None:  # pragma: no branch
            prompt = self._build_child_prompt(
                city_date=city_date,
                household_address=household_address,
                parents=parents,
                recent_events=recent_events,
            )
            try:
                result = Runner.run_sync(self.persona_agent, prompt)  # type: ignore[arg-type]
                output = getattr(result, "final_output", None)
                if isinstance(output, ChildPersonaOutput):
                    return PersonaResult(
                        name=output.name,
                        age_group=output.age_group,
                        temperament=output.temperament,
                        values=list(output.values),
                        gender=output.gender,
                        summary=output.summary,
                    )
            except Exception as exc:  # pragma: no cover
                LOGGER.warning("Persona agent failed, using fallback persona: %s", exc)

        # Fallback deterministic persona when the agent is unavailable
        LOGGER.info("Falling back to deterministic child persona generation")
        name = self._default_child_name(parents)
        temperament = "Inquisitive child blending parental traits"
        values = list({value for parent in parents for value in parent.get("values", [])})[:3]
        gender = parents[0].get("gender", "female")
        return PersonaResult(
            name=name,
            age_group="child",
            temperament=temperament,
            values=values,
            gender=gender,
            summary=f"Born on {city_date} at {household_address} to {parents[0]['name']} and {parents[1]['name']}.",
        )

    def _build_child_prompt(
        self,
        *,
        city_date: str,
        household_address: str,
        parents: List[dict[str, Any]],
        recent_events: List[str],
    ) -> str:
        payload = {
            "schema": {
                "name": "string",
                "gender": "male or female",
                "age_group": "child or teen",
                "temperament": "short description",
                "values": "list[str]",
                "summary": "one-sentence narrative summary",
            },
            "date": city_date,
            "address": household_address,
            "parents": parents,
            "recent_events": recent_events,
        }
        prompt = (
            "Create a persona for a newborn citizen. Respond using the structured output fields. "
            "Blend parental traits and keep values concise.\n"
            + json.dumps(payload, indent=2)
        )
        return prompt

    def _default_child_name(self, parents: List[dict[str, Any]]) -> str:
        base_names = [
            "Aiden",
            "Noah",
            "Lia",
            "Riya",
            "Finn",
            "Zoey",
            "Milo",
            "Anya",
        ]
        preferred = parents[0].get("name", "Child").split()[0]
        for candidate in base_names:
            if candidate.lower().startswith(preferred[0].lower()):
                return candidate
        return base_names[0]

    # ------------------------------------------------------------------ city log
    def record_city_event(self, payload: dict[str, Any]) -> Optional[CityLogOutput]:
        if self.city_agent is None or Runner is None:
            return None
        prompt = (
            "Record the following city event. Return structured output with both a summary and log entry.\n"
            + json.dumps(payload, indent=2)
        )
        try:
            result = Runner.run_sync(self.city_agent, prompt)  # type: ignore[arg-type]
            output = getattr(result, "final_output", None)
            if isinstance(output, CityLogOutput):
                return output
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("City log agent failed: %s", exc)
        return None
