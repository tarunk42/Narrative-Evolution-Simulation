from __future__ import annotations

from datetime import date, timedelta


class SimulationClock:
    """Accelerated clock that tracks both time of day and calendar date."""

    MINUTES_PER_DAY = 24 * 60

    def __init__(
        self,
        *,
        minutes_per_second: float = 720.0,
        start_date: date | None = None,
        start_minutes: float = 8 * 60,
    ) -> None:
        """
        Args:
            minutes_per_second: How many in-game minutes elapse per real second.
            start_date: Calendar date to begin the simulation (defaults to Jan 1, 2026).
            start_minutes: Minutes since midnight for initial time of day.
        """
        self.minutes_per_second = minutes_per_second
        self.minutes = start_minutes
        self.current_date = start_date or date(2026, 1, 1)

    def update(self, dt_seconds: float) -> None:
        advance = dt_seconds * self.minutes_per_second
        new_minutes = self.minutes + advance
        if new_minutes >= self.MINUTES_PER_DAY:
            days, remaining = divmod(new_minutes, self.MINUTES_PER_DAY)
            self.current_date += timedelta(days=int(days))
            self.minutes = remaining
        else:
            self.minutes = new_minutes

    @property
    def hour(self) -> int:
        return int(self.minutes) // 60

    @property
    def minute(self) -> int:
        return int(self.minutes) % 60

    def formatted_time(self) -> str:
        hour = self.hour
        minute = self.minute
        suffix = "AM" if hour < 12 else "PM"
        display_hour = hour % 12
        if display_hour == 0:
            display_hour = 12
        return f"{display_hour:02d}:{minute:02d} {suffix}"

    def formatted_date(self) -> str:
        return self.current_date.strftime("%b %d, %Y")
