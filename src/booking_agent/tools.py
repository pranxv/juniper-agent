"""The restaurant's 'backend': three tools the agent can call.

Claude never runs this code. It asks for a tool by name, and agent.py runs it here.
"""

import datetime
import hashlib
import json
from zoneinfo import ZoneInfo

from anthropic.types.beta import BetaToolParam

OPEN_TIMES = [
    "17:00",
    "17:30",
    "18:00",
    "18:30",
    "19:00",
    "19:30",
    "20:00",
    "20:30",
    "21:00",
]
TABLES_PER_SLOT = 3
MAX_PARTY = 8
RESTAURANT_TZ = ZoneInfo("America/Los_Angeles")

BOOKINGS: dict[str, dict] = {}  # booking_id -> booking (in memory: resets every run)


def _parse_date(date: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(date)
    except ValueError as err:
        raise ValueError(
            f"'{date}' is not a date in YYYY-MM-DD format ({err})"
        ) from err


def _require_bookable_date(date: str) -> datetime.date:
    parsed_date = _parse_date(date)
    today = datetime.datetime.now(RESTAURANT_TZ).date()
    if parsed_date < today:
        raise ValueError(
            f"date needs to be today or any day later, given {date} happens in the past and date for today is {today}"
        )
    return parsed_date


def _tables_taken(date: str, time: str) -> int:
    return sum(1 for b in BOOKINGS.values() if b["date"] == date and b["time"] == time)


def _booking_id(name: str, date: str, time: str, party_size: int) -> str:
    """Same request in, same id out. That is what makes book() safe to retry."""
    raw = f"{name.strip().lower()}|{date}|{time}|{party_size}"
    return "bk_" + hashlib.sha256(raw.encode()).hexdigest()[:8]


def check_availability(date: str, party_size: int) -> dict:
    _require_bookable_date(date)
    if not 1 <= party_size <= MAX_PARTY:
        raise ValueError(
            f"party size must be 1-{MAX_PARTY}; larger groups must call the restaurant"
        )
    free = [t for t in OPEN_TIMES if _tables_taken(date, t) < TABLES_PER_SLOT]
    return {"date": date, "party_size": party_size, "available_times": free}


def book(name: str, date: str, time: str, party_size: int) -> dict:
    _require_bookable_date(date)
    booking_id = _booking_id(name, date, time, party_size)
    # TODO 4: idempotency. If `booking_id` is already in BOOKINGS, return that booking
    # (add a "note" saying it already existed) instead of creating a second one.
    if booking_id in BOOKINGS:
        return {**BOOKINGS[booking_id], "note": "Booking already exists"}
    if time not in OPEN_TIMES:
        raise ValueError(f"we only seat at {', '.join(OPEN_TIMES)}")
    if _tables_taken(date, time) >= TABLES_PER_SLOT:
        raise ValueError(f"no tables left at {time} on {date}")
    BOOKINGS[booking_id] = {
        "booking_id": booking_id,
        "name": name,
        "date": date,
        "time": time,
        "party_size": party_size,
    }
    return BOOKINGS[booking_id]


def cancel(booking_id: str) -> dict:
    if booking_id not in BOOKINGS:
        raise ValueError(f"no booking with id {booking_id}")
    return {"cancelled": BOOKINGS.pop(booking_id)}


TOOLS: list[BetaToolParam] = [
    {
        "name": "check_availability",
        "description": "List the open seating times on a date for a party size. Call this before offering or booking any time.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "party_size": {
                    "type": "integer",
                    "description": "Number of guests, 1-8",
                },
            },
            "required": ["date", "party_size"],
            "additionalProperties": False,
        },
    },
    {
        "name": "book",
        "description": "Book a table. Only call after the guest has confirmed name, date, time and party size. Safe to retry: the same details return the same booking.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Guest's name"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "time": {
                    "type": "string",
                    "description": "Seating time in HH:MM, one of the available times",
                },
                "party_size": {
                    "type": "integer",
                    "description": "Number of guests, 1-8",
                },
            },
            "required": ["name", "date", "time", "party_size"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cancel",
        "description": "Cancel a booking by its booking_id (starts with bk_).",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "booking_id": {
                    "type": "string",
                    "description": "The booking_id returned by book",
                }
            },
            "required": ["booking_id"],
            "additionalProperties": False,
        },
    },
]

HANDLERS = {"check_availability": check_availability, "book": book, "cancel": cancel}


def run_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Run one tool. Returns (result_text, is_error). Errors go back to Claude, not up the stack."""
    try:
        result = HANDLERS[name](**tool_input)
        return json.dumps(result), False
    except KeyError:
        return f"Error: unknown tool '{name}'", True
    except (ValueError, TypeError) as e:
        return f"Error: {e}", True
