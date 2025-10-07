from __future__ import annotations

import itertools
import random
from collections import Counter
from typing import Dict, List, Optional, Tuple

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


class PopulationManager:
    """Creates citizens, households, and manages their visible agent state."""

    RESIDENTIAL_CAPACITY_PER_TILE = 6

    def __init__(self, city: City, target_population: int = 150, rng_seed: int = 1337) -> None:
        self.city = city
        self.rng = random.Random(rng_seed)
        self.target_population = max(1, target_population)

        self.citizens: Dict[int, Citizen] = {}
        self.households: Dict[int, Household] = {}
        self.households_by_tile: Dict[Tuple[int, int], List[int]] = {}
        self.job_capacity: Dict[Tuple[int, int], int] = {}
        self.job_assignments: Dict[Tuple[int, int], List[int]] = {}
        self.student_capacity: Dict[Tuple[int, int], int] = {}
        self.student_assignments: Dict[Tuple[int, int], List[int]] = {}

        self._citizen_stage: Dict[int, DailyStage] = {}
        self._active_sprites: Dict[int, NPC] = {}
        self.agents = pygame.sprite.Group()

        self._gender_cycle = itertools.cycle([Gender.MALE, Gender.FEMALE])
        self._name_cycle = itertools.cycle(_FIRST_NAMES)

        self._build_population()

    # ------------------------------------------------------------------ setup
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

        citizen_id = 1
        household_id = 1
        zone_house_counter: Dict[str, int] = {}
        for tile in residential_tiles:
            if citizen_id > self.target_population:
                break
            members: List[int] = []
            zone = self.city.zone_label(*tile)
            zone_house_counter.setdefault(zone, 0)
            address = f"{zone}-{zone_house_counter[zone]:03d}"

            adults = self.rng.randint(1, 2)
            for _ in range(adults):
                if citizen_id > self.target_population:
                    break
                gender = next(self._gender_cycle)
                age_group = AgeGroup.ADULT
                if self.rng.random() < 0.15:
                    age_group = AgeGroup.ELDER

                employment_status = EmploymentStatus.UNEMPLOYED
                profession = Profession.NONE
                schedule: Optional[CitizenSchedule] = None
                job_tile = None

                if age_group == AgeGroup.ELDER:
                    employment_status = EmploymentStatus.RETIRED
                elif job_slots:
                    job_tile, profession = job_slots.pop()
                    employment_status = EmploymentStatus.EMPLOYED
                    schedule = _default_schedule_for_profession(profession)
                    self.job_assignments.setdefault(job_tile, []).append(citizen_id)

                zone = self.city.zone_label(*tile)
                zone_house_counter.setdefault(zone, 0)
                address = f"{zone}-{zone_house_counter[zone]:03d}"

                citizen = Citizen(
                    citizen_id=citizen_id,
                    name=next(self._name_cycle),
                    gender=gender,
                    age_group=age_group,
                    employment_status=employment_status,
                    profession=profession,
                    household_id=household_id,
                    home_tile=tile,
                    address=address,
                    job_tile=job_tile,
                    schedule=schedule,
                )
                self.citizens[citizen_id] = citizen
                self._citizen_stage[citizen_id] = DailyStage.HOME
                members.append(citizen_id)
                citizen_id += 1

            if not members:
                continue

            if self.rng.random() < 0.35 and citizen_id <= self.target_population:
                # add a child or teen
                gender = next(self._gender_cycle)
                age_group = AgeGroup.CHILD if self.rng.random() < 0.6 else AgeGroup.TEEN
                employment_status = EmploymentStatus.STUDENT
                profession = Profession.STUDENT
                job_tile = student_slots.pop()[0] if student_slots else None
                schedule = _default_student_schedule()
                if job_tile is not None:
                    self.student_assignments.setdefault(job_tile, []).append(citizen_id)
                citizen = Citizen(
                    citizen_id=citizen_id,
                    name=next(self._name_cycle),
                    gender=gender,
                    age_group=age_group,
                    employment_status=employment_status,
                    profession=profession,
                    household_id=household_id,
                    home_tile=tile,
                    address=address,
                    job_tile=job_tile,
                    schedule=schedule,
                )
                self.citizens[citizen_id] = citizen
                self._citizen_stage[citizen_id] = DailyStage.HOME
                members.append(citizen_id)
                citizen_id += 1

            zone_house_counter[zone] += 1
            household = Household(
                household_id=household_id,
                home_tile=tile,
                member_ids=members,
                address=address,
            )
            self.households[household_id] = household
            self.households_by_tile.setdefault(tile, []).append(household_id)
            household_id += 1

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
