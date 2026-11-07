import datetime

import pytest

import tools

@pytest.fixture(autouse=True)
def clear_bookings():
    tools.BOOKINGS.clear()

def test_rejects_impossible_date():
    with pytest.raises(ValueError, match="day is out of range"):
        tools.book("Ruari", "2026-02-30", "17:00", 2)

def test_reject_past_date():
    with pytest.raises(ValueError, match="date needs to be today or any day later"):
        tools.book("Ruari", "2026-02-23", "17:00", 2)

def future_date(days: int = 7) -> str:
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()

def test_booking_is_idempotent():
    date = future_date()
    first = tools.book("Ruari",date, "18:00",2)
    second = tools.book("Ruari",date, "18:00",2)
    
    assert second["booking_id"] == first["booking_id"]
    assert len(tools.BOOKINGS) == 1
    assert "note" in second
    assert "note" not in tools.BOOKINGS[first["booking_id"]]    