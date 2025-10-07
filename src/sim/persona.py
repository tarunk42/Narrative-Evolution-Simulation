from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional, Tuple


class Gender(enum.Enum):
    MALE = "male"
    FEMALE = "female"


class AgeGroup(enum.Enum):
    CHILD = "child"
    TEEN = "teen"
    ADULT = "adult"
    ELDER = "elder"


class EmploymentStatus(enum.Enum):
    STUDENT = "student"
    EMPLOYED = "employed"
    UNEMPLOYED = "unemployed"
    RETIRED = "retired"


class Profession(enum.Enum):
    OFFICE = "office"
    RETAIL = "retail"
    INDUSTRIAL = "industrial"
    SERVICE = "service"
    STUDENT = "student"
    NONE = "none"


class DailyStage(enum.Enum):
    HOME = "home"
    COMMUTE_TO_WORK = "commute_to_work"
    WORK = "work"
    COMMUTE_HOME = "commute_home"
    OFF_DUTY = "off_duty"


@dataclass(frozen=True)
class CitizenSchedule:
    commute_to_work_start: int  # minutes since midnight
    work_start: int
    work_end: int
    commute_home_end: int


@dataclass
class Citizen:
    citizen_id: int
    name: str
    gender: Gender
    age_group: AgeGroup
    employment_status: EmploymentStatus
    profession: Profession
    household_id: int
    home_tile: Tuple[int, int]
    address: str
    job_tile: Optional[Tuple[int, int]] = None
    schedule: Optional[CitizenSchedule] = None


@dataclass
class Household:
    household_id: int
    home_tile: Tuple[int, int]
    member_ids: list[int]
    address: str
