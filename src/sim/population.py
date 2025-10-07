from __future__ import annotations

import itertools
import random
import logging
import threading
import asyncio
import concurrent.futures
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json

import pygame

from ..city import City
from .clock import SimulationClock
from .npc import NPC
from .persona import (
    AgeGroup,
    Citizen,
    CitizenSchedule,
    DailyStage,
    EmploymentStatus,
    Gender,
    Household,
    Profession,
)
from ..llm.agents import LLMManager, PersonaResult


LOGGER = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    speaker_id: int
    message: str
    timestamp: str


@dataclass
class Conversation:
    conversation_id: str
    participants: List[int]
    turns: List[ConversationTurn] = field(default_factory=list)
    is_active: bool = True
    last_activity: datetime = field(default_factory=datetime.now)


class ConversationManager:
    def __init__(self, llm_manager: Optional[LLMManager], citizens: Dict[int, Citizen], save_callback: Optional[callable] = None):
        self.llm = llm_manager
        self.citizens = citizens
        self.active_conversations: Dict[str, Conversation] = {}
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="conversation")
        self.save_callback = save_callback

    def start_conversation(self, citizen_ids: List[int]) -> None:
        if len(citizen_ids) < 2:
            return
        
        # Check if any participant is already in a conversation
        for conv in self.active_conversations.values():
            if any(cid in conv.participants for cid in citizen_ids):
                return  # Already conversing
        
        conv_id = f"conv_{'_'.join(map(str, sorted(citizen_ids)))}_{random.randint(1000, 9999)}"
        conversation = Conversation(
            conversation_id=conv_id,
            participants=sorted(citizen_ids)
        )
        self.active_conversations[conv_id] = conversation
        LOGGER.info(f"Starting conversation {conv_id} between citizens {citizen_ids}")
        
        # Start conversation thread
        self.executor.submit(self._run_conversation, conversation)

    def _run_conversation(self, conversation: Conversation) -> None:
        try:
            # Initial greeting from first participant
            first_speaker = conversation.participants[0]
            greeting = self._generate_greeting(first_speaker, conversation.participants)
            if greeting:
                turn = ConversationTurn(
                    speaker_id=first_speaker,
                    message=greeting,
                    timestamp=datetime.now().isoformat()
                )
                conversation.turns.append(turn)
                conversation.last_activity = datetime.now()
                LOGGER.info(f"Conversation {conversation.conversation_id}: {self.citizens[first_speaker].name}: {greeting}")
            
            # Continue with turn-based dialogue
            current_turn = 1
            max_turns = 6  # Limit conversation length
            
            while conversation.is_active and current_turn < max_turns:
                time.sleep(2)  # Pause between turns for realism
                
                # Determine next speaker (alternate)
                speaker_idx = current_turn % len(conversation.participants)
                speaker_id = conversation.participants[speaker_idx]
                
                # Generate response
                response = self._generate_response(speaker_id, conversation)
                if response:
                    turn = ConversationTurn(
                        speaker_id=speaker_id,
                        message=response,
                        timestamp=datetime.now().isoformat()
                    )
                    conversation.turns.append(turn)
                    conversation.last_activity = datetime.now()
                    LOGGER.info(f"Conversation {conversation.conversation_id}: {self.citizens[speaker_id].name}: {response}")
                    
                    # Check if conversation should end
                    if self._should_end_conversation(conversation):
                        break
                else:
                    break
                
                current_turn += 1
            
            # End conversation and update personas
            conversation.is_active = False
            self._update_personas_after_conversation(conversation)
            LOGGER.info(f"Conversation {conversation.conversation_id} ended")
            
        except Exception as exc:
            LOGGER.error(f"Error in conversation {conversation.conversation_id}: {exc}")
            conversation.is_active = False

    def _generate_greeting(self, speaker_id: int, participants: List[int]) -> Optional[str]:
        if not self.llm:
            return f"Hello {', '.join(self.citizens[pid].name for pid in participants if pid != speaker_id)}!"
        
        speaker = self.citizens[speaker_id]
        others = [self.citizens[pid] for pid in participants if pid != speaker_id]
        
        context = f"You are {speaker.name}, {speaker.temperament}. You just encountered {', '.join(o.name for o in others)}."
        prompt = f"{context}\n\nGenerate a natural greeting to start a conversation. Keep it brief (1-2 sentences)."
        
        try:
            result = self.llm.generate_response(prompt)
            return result.response if result else None
        except Exception as exc:
            LOGGER.warning(f"Failed to generate greeting: {exc}")
            return f"Hello {', '.join(o.name for o in others)}!"

    def _generate_response(self, speaker_id: int, conversation: Conversation) -> Optional[str]:
        if not self.llm:
            return "That's interesting!"
        
        speaker = self.citizens[speaker_id]
        others = [self.citizens[pid] for pid in conversation.participants if pid != speaker_id]
        
        # Build conversation history
        history = "\n".join([
            f"{self.citizens[turn.speaker_id].name}: {turn.message}"
            for turn in conversation.turns[-3:]  # Last 3 turns for context
        ])
        
        context = f"""You are {speaker.name}, {speaker.temperament}.
Your values: {', '.join(speaker.values)}
Recent memories: {speaker.memories[-2:] if speaker.memories else 'None'}

Conversation with: {', '.join(o.name for o in others)}
Recent conversation:
{history}

Generate a natural response. Keep it brief (1-2 sentences)."""
        
        try:
            result = self.llm.generate_response(context)
            return result.response if result else None
        except Exception as exc:
            LOGGER.warning(f"Failed to generate response: {exc}")
            return "I see."

    def _should_end_conversation(self, conversation: Conversation) -> bool:
        # Simple heuristic: end if last few turns are short or repetitive
        if len(conversation.turns) < 3:
            return False
        
        recent_turns = conversation.turns[-3:]
        avg_length = sum(len(turn.message) for turn in recent_turns) / len(recent_turns)
        return avg_length < 10  # Very short responses indicate conversation winding down

    def _update_personas_after_conversation(self, conversation: Conversation) -> None:
        if not self.llm or len(conversation.turns) < 2:
            return
        
        # Analyze conversation and update personas
        for participant_id in conversation.participants:
            participant = self.citizens[participant_id]
            
            # Simple updates based on conversation
            # In a more advanced system, this could use LLM analysis
            turns_by_participant = [turn for turn in conversation.turns if turn.speaker_id == participant_id]
            
            if len(turns_by_participant) > 1:
                # Participant was engaged - slightly boost relationships
                for other_id in conversation.participants:
                    if other_id != participant_id:
                        # Strengthen relationship
                        rel = next((r for r in participant.relationships if r['citizen_id'] == other_id), None)
                        if rel:
                            rel['strength'] = min(1.0, rel['strength'] + 0.05)
                        else:
                            participant.relationships.append({
                                'citizen_id': other_id,
                                'type': 'acquaintance',
                                'strength': 0.3
                            })
                
                # Add conversation memory (permanent, not expiring)
                conversation_summary = f"Had a conversation with {', '.join(self.citizens[pid].name for pid in conversation.participants if pid != participant_id)}"
                participant.memories.append({
                    "timestamp": datetime.now().isoformat(),
                    "summary": conversation_summary,
                    "severity": "low",
                    "tags": ["conversation", "social"],
                    "expires_at": None,  # Permanent
                    "conversation_id": conversation.conversation_id
                })
        
        # Save updated personas
        if self.save_callback:
            self.save_callback()

    def cleanup_old_conversations(self) -> None:
        # Remove conversations that haven't been active for a while
        cutoff = datetime.now() - timedelta(minutes=10)
        to_remove = [
            conv_id for conv_id, conv in self.active_conversations.items()
            if not conv.is_active and conv.last_activity < cutoff
        ]
        for conv_id in to_remove:
            del self.active_conversations[conv_id]

    def get_active_conversations(self) -> List[Conversation]:
        return list(self.active_conversations.values())


class PopulationManager:
    """Creates citizens, households, and manages their visible agent state."""

    RESIDENTIAL_CAPACITY_PER_TILE = 6

    def __init__(
        self,
        city: City,
        rng_seed: int = 1337,
        llm_manager: Optional[LLMManager] = None,
    ) -> None:
        self.city = city
        self.rng = random.Random(rng_seed)
        self.llm = llm_manager

        # Reset events.json on startup
        events_path = Path(__file__).resolve().parents[2] / "data" / "events.json"
        events_path.write_text("[]")

        self.citizens: Dict[int, Citizen] = {}
        self.households: Dict[int, Household] = {}
        self.households_by_tile: Dict[Tuple[int, int], List[int]] = {}
        self.job_capacity: Dict[Tuple[int, int], int] = {}
        self.job_assignments: Dict[Tuple[int, int], List[int]] = {}
        self.student_capacity: Dict[Tuple[int, int], int] = {}
        self.student_assignments: Dict[Tuple[int, int], List[int]] = {}
        self._unused_job_slots: List[Tuple[Tuple[int, int], Profession]] = []
        self._unused_student_slots: List[Tuple[Tuple[int, int], Profession]] = []

        self._citizen_stage: Dict[int, DailyStage] = {}
        self._active_sprites: Dict[int, NPC] = {}
        self.agents = pygame.sprite.Group()

        self._gender_cycle = itertools.cycle([Gender.MALE, Gender.FEMALE])
        self._name_cycle = itertools.cycle(_FIRST_NAMES)

        self._seed_households = self._load_seed_households()

        self.household_birth_record: Dict[int, date] = {}
        self._last_birth_check_date: Optional[date] = None
        self._recent_birth_events: List[str] = []
        self._next_generated_id: int = 1
        self._next_household_id: int = 1

        # Random city events
        self._next_random_event_time: date = date(2026, 1, 1) + timedelta(days=self.rng.randint(2, 7))
        self._city_events = [
            {"type": "theft", "description": "A theft occurred in the city.", "severity": "medium"},
            {"type": "fire", "description": "A fire broke out in a building.", "severity": "high"},
            {"type": "fair", "description": "A fair is being held in the city.", "severity": "low"},
            {"type": "festival", "description": "A festival is celebrated in the city.", "severity": "low"},
            {"type": "accident", "description": "An accident happened on the streets.", "severity": "medium"},
            {"type": "protest", "description": "Citizens are protesting in the city.", "severity": "medium"},
            {"type": "celebration", "description": "A celebration is taking place.", "severity": "low"},
        ]
        self.events_log: List[Dict[str, Any]] = []
        self.save_events()  # Wipe events.json at start

        self._build_population()
        
        # Initialize conversation manager after citizens are built
        self.conversation_manager = ConversationManager(llm_manager, self.citizens, self.save_to_personas)

    # ------------------------------------------------------------------ setup
    def _load_seed_households(self) -> List[Dict[str, Any]]:
        data_dir = Path(__file__).resolve().parents[2] / "data"
        personas_path = data_dir / "personas.json"
        seed_path = data_dir / "personas_seed.json"
        
        # Always reset personas.json from seed on startup
        if seed_path.exists():
            personas_path.write_text(seed_path.read_text())
            source_path = personas_path
        elif personas_path.exists():
            source_path = personas_path
        else:
            return []

        if not source_path.exists():
            return []
        try:
            data = json.loads(source_path.read_text())
        except Exception as exc:
            LOGGER.warning("Unable to load personas.json: %s", exc)
            return []

        grouped: Dict[str, Dict[str, Any]] = {}
        for entry in data:
            tag = entry.get("household_tag") or f"seed-{entry['citizen_id']}"
            grouped.setdefault(tag, {"tag": tag, "members": []})
            grouped[tag]["members"].append(entry)
        ordered = sorted(grouped.values(), key=lambda item: min(member["citizen_id"] for member in item["members"]))
        return ordered

    def _create_seed_household(
        self,
        tile: Tuple[int, int],
        seed: Dict[str, Any],
        household_id: int,
        zone_house_counter: Dict[str, int],
        job_slots: List[Tuple[Tuple[int, int], Profession]],
        student_slots: List[Tuple[Tuple[int, int], Profession]],
    ) -> int:
        zone = self.city.zone_label(*tile)
        zone_house_counter.setdefault(zone, 0)
        address = f"{zone}-{zone_house_counter[zone]:03d}"
        member_ids: List[int] = []

        for entry in sorted(seed["members"], key=lambda m: m["citizen_id"]):
            citizen_id = entry["citizen_id"]
            gender = Gender(entry.get("gender", "female"))
            age_group = AgeGroup(entry.get("age_group", "adult"))
            employment_status = EmploymentStatus(entry.get("employment_status", "unemployed"))
            profession = Profession(entry.get("profession", "none"))
            job_tile = None
            schedule = None
            if employment_status == EmploymentStatus.EMPLOYED:
                job_tile = self._assign_job_tile(profession, job_slots)
                schedule = _default_schedule_for_profession(profession)
                if job_tile is not None:
                    self.job_assignments.setdefault(job_tile, []).append(citizen_id)
            elif employment_status == EmploymentStatus.STUDENT:
                job_tile = self._assign_student_slot(student_slots)
                schedule = _default_student_schedule()
                if job_tile is not None:
                    self.student_assignments.setdefault(job_tile, []).append(citizen_id)

            citizen = Citizen(
                citizen_id=citizen_id,
                name=entry["name"],
                gender=gender,
                age_group=age_group,
                employment_status=employment_status,
                profession=profession,
                household_id=household_id,
                home_tile=tile,
                address=entry.get("address", address),
                job_tile=job_tile,
                schedule=schedule,
                temperament=entry.get("temperament", ""),
                values=entry.get("values", []),
                relationships=entry.get("relationships", []),
                system_prompt=entry.get("system_prompt", ""),
                memories=entry.get("memories", []),
                traits=entry.get("traits", {}),
            )
            self.citizens[citizen_id] = citizen
            self._citizen_stage[citizen_id] = DailyStage.HOME
            member_ids.append(citizen_id)

        household = Household(
            household_id=household_id,
            home_tile=tile,
            member_ids=member_ids,
            address=address,
        )
        self.households[household_id] = household
        self.households_by_tile.setdefault(tile, []).append(household_id)
        zone_house_counter[zone] += 1
        if member_ids:
            self.household_birth_record[household_id] = date(2026, 1, 1) - timedelta(days=90)
        return household_id + 1

    def _build_population(self) -> None:
        residential_tiles = [
            (x, y)
            for y in range(self.city.height)
            for x in range(self.city.width)
            if self.city.map[y][x] == "H"
        ]
        if not residential_tiles:
            return

        self.rng.shuffle(residential_tiles)

        job_slots = self._make_job_slots()
        student_slots = self._make_student_slots()

        zone_house_counter: Dict[str, int] = {}

        tiles_iter = iter(residential_tiles)
        household_id = 1

        # seed households first
        for seed in self._seed_households:
            try:
                tile = next(tiles_iter)
            except StopIteration:
                LOGGER.warning("Not enough residential tiles for all seed households")
                break
            household_id = self._create_seed_household(
                tile=tile,
                seed=seed,
                household_id=household_id,
                zone_house_counter=zone_house_counter,
                job_slots=job_slots,
                student_slots=student_slots,
            )

        if self.citizens:
            self._next_generated_id = max(self.citizens) + 1
        else:
            self._next_generated_id = 1
        if self.households:
            self._next_household_id = max(self.households) + 1
        else:
            self._next_household_id = 1

        self._unused_job_slots = job_slots
        self._unused_student_slots = student_slots

    def _make_job_slots(self) -> List[Tuple[Tuple[int, int], Profession]]:
        slots: List[Tuple[Tuple[int, int], Profession]] = []
        office_tiles: List[Tuple[int, int]] = []
        for y in range(self.city.height):
            for x in range(self.city.width):
                tile = self.city.map[y][x]
                pos = (x, y)
                if tile == "O":
                    office_tiles.append(pos)
                    slots.extend([(pos, Profession.OFFICE)] * 4)
                    self.job_capacity[pos] = self.job_capacity.get(pos, 0) + 4
                elif tile == "C":
                    slots.extend([(pos, Profession.RETAIL)] * 3)
                    self.job_capacity[pos] = self.job_capacity.get(pos, 0) + 3
                elif tile == "I":
                    slots.extend([(pos, Profession.INDUSTRIAL)] * 5)
                    self.job_capacity[pos] = self.job_capacity.get(pos, 0) + 5

        for idx, pos in enumerate(office_tiles):
            if idx % 6 == 0:
                slots.extend([(pos, Profession.SERVICE)] * 3)
                self.job_capacity[pos] = self.job_capacity.get(pos, 0) + 3
        self.rng.shuffle(slots)
        return slots

    def _make_student_slots(self) -> List[Tuple[Tuple[int, int], Profession]]:
        school_tiles = [
            (x, y)
            for y in range(self.city.height)
            for x in range(self.city.width)
            if self.city.map[y][x] in {"C", "O"}
            and (x + y) % 7 == 0
        ]
        slots: List[Tuple[Tuple[int, int], Profession]] = []
        for tile in school_tiles:
            slots.extend([(tile, Profession.STUDENT)] * 8)
            self.student_capacity[tile] = self.student_capacity.get(tile, 0) + 8
        self.rng.shuffle(slots)
        return slots

    def _assign_job_tile(
        self, profession: Profession, job_slots: List[Tuple[Tuple[int, int], Profession]]
    ) -> Optional[Tuple[int, int]]:
        for idx, (slot_tile, slot_profession) in enumerate(job_slots):
            if slot_profession == profession:
                job_slots.pop(idx)
                return slot_tile
        return None

    def _pop_job_slot(
        self, job_slots: List[Tuple[Tuple[int, int], Profession]]
    ) -> Tuple[Optional[Tuple[int, int]], Profession]:
        if not job_slots:
            return None, Profession.NONE
        slot_tile, slot_profession = job_slots.pop()
        return slot_tile, slot_profession

    def _assign_student_slot(
        self, student_slots: List[Tuple[Tuple[int, int], Profession]]
    ) -> Optional[Tuple[int, int]]:
        if not student_slots:
            return None
        slot_tile, _ = student_slots.pop()
        return slot_tile

    def _find_available_student_tile(self) -> Optional[Tuple[int, int]]:
        for tile, capacity in self.student_capacity.items():
            assigned = len(self.student_assignments.get(tile, []))
            if assigned < capacity:
                return tile
        if self._unused_student_slots:
            tile, _ = self._unused_student_slots.pop()
            self.student_capacity[tile] = self.student_capacity.get(tile, 0) + 1
            return tile
        return None

    # ------------------------------------------------------------------ update
    def update(self, clock: SimulationClock, dt: float) -> None:
        minute = int(clock.minutes)
        for citizen_id, citizen in self.citizens.items():
            stage = self._determine_stage(citizen, minute)
            if self._citizen_stage[citizen_id] == stage:
                continue
            self._citizen_stage[citizen_id] = stage

            if stage in (DailyStage.COMMUTE_TO_WORK, DailyStage.COMMUTE_HOME):
                if citizen_id not in self._active_sprites:
                    npc = NPC(self.city, citizen, stage)
                    self.agents.add(npc)
                    self._active_sprites[citizen_id] = npc
                else:
                    self._active_sprites[citizen_id].set_stage(stage)
            else:
                sprite = self._active_sprites.pop(citizen_id, None)
                if sprite:
                    sprite.kill()

        self.agents.update(dt)
        self._check_interactions()
        self._handle_births(clock)
        self._handle_random_city_events(clock)
        self._clean_expired_memories(clock)
        self.conversation_manager.cleanup_old_conversations()

    def broadcast_event(self, event_summary: str, severity: str, clock: SimulationClock, event_type: str = "") -> None:
        """Broadcast events to all citizens' memories."""
        expires_at = clock.current_date + timedelta(days=7)
        event_id = f"{event_type}_{clock.current_date.isoformat()}_{self.rng.randint(1000, 9999)}"
        memory_entry = {
            "event_id": event_id,
            "timestamp": f"{clock.current_date.isoformat()}T{clock.hour:02d}:{clock.minute:02d}:00",
            "summary": event_summary,
            "severity": severity,
            "tags": ["city_event"],
            "expires_at": expires_at.isoformat(),
        }
        for citizen in self.citizens.values():
            citizen.memories.append(memory_entry)

    def _clean_expired_memories(self, clock: SimulationClock) -> None:
        current_time = clock.current_date
        for citizen in self.citizens.values():
            citizen.memories = [
                memory for memory in citizen.memories
                if memory.get("expires_at") is None or self._parse_expires_date(memory["expires_at"]) > current_time
            ]

    def _parse_expires_date(self, expires_str: str) -> date:
        try:
            return date.fromisoformat(expires_str)
        except ValueError:
            # Try parsing as datetime
            dt = datetime.fromisoformat(expires_str)
            return dt.date()

    def save_events(self) -> None:
        path = Path(__file__).resolve().parents[2] / "data" / "events.json"
        with open(path, 'w') as f:
            json.dump(self.events_log, f, indent=2)

    def save_to_personas(self) -> None:
        data = []
        for citizen in self.citizens.values():
            citizen_dict = {
                "citizen_id": citizen.citizen_id,
                "name": citizen.name,
                "gender": citizen.gender.value,
                "age_group": citizen.age_group.value,
                "employment_status": citizen.employment_status.value,
                "profession": citizen.profession.value,
                "household_tag": f"H{citizen.household_id}",
                "temperament": citizen.temperament,
                "values": citizen.values,
                "relationships": citizen.relationships,
                "system_prompt": citizen.system_prompt,
                "memories": citizen.memories,
            }
            data.append(citizen_dict)
        path = Path(__file__).resolve().parents[2] / "data" / "personas.json"
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def _check_interactions(self) -> None:
        active_npcs = list(self._active_sprites.values())
        for i, npc1 in enumerate(active_npcs):
            for npc2 in active_npcs[i+1:]:
                dx = npc1.rect.centerx - npc2.rect.centerx
                dy = npc1.rect.centery - npc2.rect.centery
                dist = (dx**2 + dy**2)**0.5
                if dist < 50:  # proximity threshold
                    # Start conversation if not already active
                    LOGGER.info(f"Citizens {npc1.citizen_id} and {npc2.citizen_id} are close (dist: {dist:.1f}), starting conversation")
                    self.conversation_manager.start_conversation([npc1.citizen_id, npc2.citizen_id])

    def _handle_births(self, clock: SimulationClock) -> None:
        if not self.llm:
            return
        current_date = clock.current_date
        if self._last_birth_check_date == current_date:
            return
        self._last_birth_check_date = current_date

        for household_id, household in list(self.households.items()):
            if not self._household_can_have_child(household):
                continue
            last_birth = self.household_birth_record.get(household_id)
            if last_birth and (current_date - last_birth).days < 120:
                continue
            if self._home_capacity_remaining(household) <= 0:
                continue
            try:
                self._spawn_child_for_household(household, current_date)
            except Exception as exc:
                LOGGER.warning("Failed to spawn child for household %s: %s", household_id, exc)

    def _handle_random_city_events(self, clock: SimulationClock) -> None:
        current_date = clock.current_date
        if current_date < self._next_random_event_time:
            return
        if self.llm:
            event = self.rng.choice(self._city_events)
            event_payload = {
                "event_type": event["type"],
                "date": current_date.isoformat(),
                "location": "city-wide",
                "description": event["description"],
                "severity": event["severity"],
                "involved_citizens": [],
            }
            city_log = self.llm.record_city_event(event_payload)
            if city_log:
                LOGGER.info("City event (%s): %s", event["type"], city_log.log_entry)
                self.broadcast_event(city_log.summary, event["severity"], clock, event["type"])
                # Log to events.json
                self.events_log.append({
                    "date": current_date.isoformat(),
                    "type": event["type"],
                    "description": event["description"],
                    "severity": event["severity"],
                    "log_entry": city_log.log_entry,
                })
                self.save_events()
                self.save_to_personas()
        # Schedule next event
        self._next_random_event_time = current_date + timedelta(days=self.rng.randint(2, 7))

    def _determine_stage(self, citizen: Citizen, minute: int) -> DailyStage:
        if citizen.schedule is None:
            return DailyStage.HOME
        schedule = citizen.schedule
        minute_mod = minute % (24 * 60)
        if minute_mod < schedule.commute_to_work_start:
            return DailyStage.HOME
        if schedule.commute_to_work_start <= minute_mod < schedule.work_start:
            return DailyStage.COMMUTE_TO_WORK
        if schedule.work_start <= minute_mod < schedule.work_end:
            return DailyStage.WORK
        if schedule.work_end <= minute_mod < schedule.commute_home_end:
            return DailyStage.COMMUTE_HOME
        return DailyStage.OFF_DUTY

    # ---------------------------------------------------------------- metrics
    def population_count(self) -> int:
        return len(self.citizens)

    def employment_breakdown(self) -> Counter[EmploymentStatus]:
        counts: Counter[EmploymentStatus] = Counter()
        for citizen in self.citizens.values():
            counts[citizen.employment_status] += 1
        return counts

    def active_commuters(self) -> int:
        return len(self._active_sprites)

    def households_count(self) -> int:
        return len(self.households)

    def tile_report(self, tile: Tuple[int, int]) -> Optional[Dict[str, object]]:
        x, y = tile
        if not self.city.is_within(tile):
            return None
        tile_type = self.city.map[y][x]
        zone = self.city.zone_label(x, y)
        report: Dict[str, object] = {
            "tile": tile,
            "zone": zone,
            "terrain": tile_type,
        }

        if tile_type == "H":
            households = [
                self.households[hid]
                for hid in self.households_by_tile.get(tile, [])
            ]
            occupants = []
            for household in households:
                for member_id in household.member_ids:
                    citizen = self.citizens[member_id]
                    occupants.append(
                        {
                            "id": citizen.citizen_id,
                            "name": citizen.name,
                            "gender": citizen.gender.value,
                            "age": citizen.age_group.value,
                            "employment": citizen.employment_status.value,
                        }
                    )
            report.update(
                {
                    "category": "Residential",
                    "capacity": self.RESIDENTIAL_CAPACITY_PER_TILE,
                    "occupant_count": len(occupants),
                    "households": [
                        {
                            "household_id": household.household_id,
                            "address": household.address,
                            "members": [self.citizens[mid].name for mid in household.member_ids],
                        }
                        for household in households
                    ],
                    "occupants": occupants,
                }
            )
        elif tile_type in {"O", "C", "I"}:
            employees = [
                self.citizens[cid]
                for cid in self.job_assignments.get(tile, [])
            ]
            capacity = self.job_capacity.get(tile, 0)
            report.update(
                {
                    "category": "Workplace",
                    "capacity": capacity,
                    "occupant_count": len(employees),
                    "employees": [
                        {
                            "id": emp.citizen_id,
                            "name": emp.name,
                            "profession": emp.profession.value,
                            "address": emp.address,
                        }
                        for emp in employees
                    ],
                }
            )
        elif tile_type == "P":
            report.update({"category": "Park"})
        elif tile_type == "L":
            report.update({"category": "Plaza"})
        elif tile_type == "W":
            report.update({"category": "Water"})
        elif tile_type in {"R", "S"}:
            report.update({"category": "Road"})
        else:
            report.update({"category": "Building"})

        return report

    def citizen_report(self, citizen_id: int) -> Optional[Dict[str, object]]:
        citizen = self.citizens.get(citizen_id)
        if not citizen:
            return None
        household = self.households.get(citizen.household_id)
        relatives = []
        if household:
            for member_id in household.member_ids:
                if member_id == citizen_id:
                    continue
                relative = self.citizens[member_id]
                relatives.append(
                    {
                        "id": relative.citizen_id,
                        "name": relative.name,
                        "relationship": "Household member",
                        "gender": relative.gender.value,
                        "age": relative.age_group.value,
                    }
                )

        stage = self._citizen_stage.get(citizen_id, DailyStage.HOME)
        job_zone = None
        if citizen.job_tile:
            job_zone = self.city.zone_label(*citizen.job_tile)

        return {
            "id": citizen.citizen_id,
            "name": citizen.name,
            "gender": citizen.gender.value,
            "age_group": citizen.age_group.value,
            "employment_status": citizen.employment_status.value,
            "profession": citizen.profession.value,
            "address": citizen.address,
            "home_tile": citizen.home_tile,
            "job_tile": citizen.job_tile,
            "job_zone": job_zone,
            "stage": stage.value,
            "relatives": relatives,
        }

    def citizen_summaries(self) -> List[Dict[str, object]]:
        summaries: List[Dict[str, object]] = []
        for citizen_id in sorted(self.citizens):
            citizen = self.citizens[citizen_id]
            summaries.append(
                {
                    "id": citizen.citizen_id,
                    "name": citizen.name,
                    "gender": citizen.gender.value,
                    "age_group": citizen.age_group.value,
                    "employment": citizen.employment_status.value,
                    "profession": citizen.profession.value,
                    "address": citizen.address,
                    "stage": self._citizen_stage.get(citizen_id, DailyStage.HOME).value,
                }
            )
        return summaries

    def recent_birth_logs(self) -> List[str]:
        return list(self._recent_birth_events)

    # ---------------------------------------------------------------- births
    def _household_can_have_child(self, household: Household) -> bool:
        adults = [
            self.citizens[mid]
            for mid in household.member_ids
            if self.citizens[mid].age_group == AgeGroup.ADULT
        ]
        male = any(c.gender == Gender.MALE for c in adults)
        female = any(c.gender == Gender.FEMALE for c in adults)
        return male and female

    def _home_capacity_remaining(self, household: Household) -> int:
        capacity = self.RESIDENTIAL_CAPACITY_PER_TILE
        occupants = len(household.member_ids)
        return capacity - occupants

    def _spawn_child_for_household(self, household: Household, current_date: date) -> None:
        parent_ids = [
            mid
            for mid in household.member_ids
            if self.citizens[mid].age_group in {AgeGroup.ADULT, AgeGroup.ELDER}
        ]
        if len(parent_ids) < 2:
            return
        parents = [self.citizens[parent_ids[0]], self.citizens[parent_ids[1]]]
        parent_payload = [
            {
                "id": parent.citizen_id,
                "name": parent.name,
                "gender": parent.gender.value,
                "temperament": parent.temperament,
                "values": parent.values,
                "memories": parent.memories[-3:],
            }
            for parent in parents
        ]
        persona = self.llm.generate_child_persona(
            city_date=current_date.isoformat(),
            household_address=household.address,
            parents=parent_payload,
            recent_events=self._recent_birth_events[-5:],
        )

        citizen_id = self._next_generated_id
        self._next_generated_id += 1

        gender = Gender(persona.gender.lower()) if persona.gender.lower() in {"male", "female"} else Gender.FEMALE
        age_group = AgeGroup(persona.age_group.lower()) if persona.age_group.lower() in {"child", "teen"} else AgeGroup.CHILD

        employment_status = EmploymentStatus.STUDENT
        profession = Profession.STUDENT
        job_tile = self._find_available_student_tile()
        schedule = _default_student_schedule()

        child = Citizen(
            citizen_id=citizen_id,
            name=persona.name,
            gender=gender,
            age_group=age_group,
            employment_status=employment_status,
            profession=profession,
            household_id=household.household_id,
            home_tile=household.home_tile,
            address=household.address,
            job_tile=job_tile,
            schedule=schedule,
            temperament=persona.temperament,
            values=persona.values,
            relationships=[
                {"citizen_id": parents[0].citizen_id, "type": "parent", "strength": 0.8},
                {"citizen_id": parents[1].citizen_id, "type": "parent", "strength": 0.8},
            ],
            system_prompt=(
                "You are "
                + persona.name
                + ", a new child in the city. Remember family context and stay concise."
            ),
            memories=[
                {
                    "timestamp": f"{current_date.isoformat()}T08:00:00",
                    "summary": persona.summary,
                    "severity": "low",
                    "tags": ["birth", "family"],
                    "expires_at": None,
                }
            ],
            traits={},
        )
        self.citizens[citizen_id] = child
        self._citizen_stage[citizen_id] = DailyStage.HOME
        household.member_ids.append(citizen_id)
        if job_tile is not None:
            self.student_assignments.setdefault(job_tile, []).append(citizen_id)

        for parent in parents:
            parent.relationships.append({"citizen_id": citizen_id, "type": "child", "strength": 0.8})
            parent.memories.append(
                {
                    "timestamp": f"{current_date.isoformat()}T08:00:00",
                    "summary": f"Welcomed {persona.name} into the family.",
                    "severity": "medium",
                    "tags": ["birth", "family"],
                    "expires_at": None,
                }
            )

        self.household_birth_record[household.household_id] = current_date
        log_entry = f"{current_date.isoformat()}: {persona.name} was born at {household.address}."
        self._recent_birth_events.append(log_entry)
        if len(self._recent_birth_events) > 20:
            self._recent_birth_events.pop(0)

        # Log to city narrative
        if self.llm:
            event_payload = {
                "event_type": "birth",
                "date": current_date.isoformat(),
                "location": household.address,
                "description": f"A new citizen, {persona.name}, was born to {parents[0]['name']} and {parents[1]['name']}.",
                "severity": "low",
                "involved_citizens": [parents[0]["id"], parents[1]["id"], citizen_id],
            }
            city_log = self.llm.record_city_event(event_payload)
            if city_log:
                LOGGER.info("City log: %s", city_log.log_entry)
                # For demo, assume births are low severity, no broadcast



# ---------------------------------------------------------------------------
# helpers


def _default_schedule_for_profession(profession: Profession) -> CitizenSchedule:
    start_commute = 7 * 60 + 30
    work_start = 9 * 60
    work_end = 17 * 60
    commute_end = 18 * 60
    if profession == Profession.RETAIL:
        work_start = 10 * 60
        work_end = 19 * 60
        start_commute = 9 * 60
        commute_end = 20 * 60
    elif profession == Profession.INDUSTRIAL:
        work_start = 6 * 60 + 30
        start_commute = 5 * 60 + 30
        work_end = 15 * 60
        commute_end = 16 * 60
    elif profession == Profession.SERVICE:
        work_start = 8 * 60
        work_end = 18 * 60
        commute_end = 19 * 60
    return CitizenSchedule(
        commute_to_work_start=start_commute,
        work_start=work_start,
        work_end=work_end,
        commute_home_end=commute_end,
    )


def _default_student_schedule() -> CitizenSchedule:
    return CitizenSchedule(
        commute_to_work_start=7 * 60 + 15,
        work_start=8 * 60,
        work_end=15 * 60,
        commute_home_end=16 * 60,
    )


_FIRST_NAMES = [
    "Ava",
    "Noah",
    "Liam",
    "Emma",
    "Olivia",
    "Mason",
    "Sophia",
    "Ethan",
    "Isabella",
    "Logan",
    "Mia",
    "Lucas",
    "Charlotte",
    "Amelia",
    "Harper",
    "Evelyn",
    "James",
    "Benjamin",
    "Henry",
    "Grace",
    "Lily",
    "Chloe",
    "Victoria",
    "Aiden",
    "Ella",
    "Scarlett",
    "Natalie",
    "Hannah",
    "Levi",
]
