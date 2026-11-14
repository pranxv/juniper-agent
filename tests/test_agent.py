import datetime

from booking_agent.agent import build_system
from booking_agent.tools import RESTAURANT_TZ


def test_system_prompt_states_todays_date():
    now = datetime.datetime(2026, 11, 8, 21, 30, tzinfo=RESTAURANT_TZ)
    system = build_system(now)

    assert "Sunday, 08 November 2026" in system
    assert "(2026-11-08)" in system
