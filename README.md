# Juniper booking agent

A restaurant booking agent with a hand-written tool loop. No framework. Claude decides the next step, this process runs the tools and keeps the transcript. Voice comes later. The repo is private: [github.com/pranxv/juniper-agent](https://github.com/pranxv/juniper-agent).

## What it shows

- **Agent loop**: `tool_use` → code executes it → `tool_result` returned in one message. Step limits (max 8) and refusal handling.
- **Idempotent tools**: Retrying `book` returns the same booking ID with `"note": "Booking already exists"`.
- **Context engineering**: Restaurant-local date (`America/Los_Angeles`) injected into the system prompt, rendered once per conversation.
- **Tracing**: Per-step latency, token counts (input/output), stop reason, and tool calls recorded in JSONL.
- **Production `src`-layout**: Clean separation between application code (`src/booking_agent/`) and test suite (`tests/`).

## A bug it caught

The first version booked "tomorrow" as **2025**-11-07. The model had no clock in its context window and guessed a year from training data.

**Fix**:
1. Date injected into the system prompt via `build_system(now: datetime.datetime)` using dependency injection.
2. Code rejects past dates in `book` using the restaurant's timezone.
*Prompts guide, code enforces.*

Unit test in `tests/test_agent.py` pins time at 21:30 PST (which is already the next day in UTC) to verify timezone correctness without API calls.

## Run

```bash
uv sync
uv run --env-file .env booking-agent
```

`ANTHROPIC_API_KEY` is read from `.env` (gitignored).

## Run checks & tests

```bash
uv run ruff check .
uv run pyright
uv run pytest -q
```

## Layout

```text
src/booking_agent/
  __init__.py     package exports and CLI entrypoint
  agent.py        the hand-written loop and system prompt
  tools.py        availability, book, cancel
tests/
  test_agent.py   system prompt date injection test
  test_tools.py   date validation and idempotency tests
traces/
  *.jsonl         per-session execution traces
```

## Next

Evals over saved traces · latency budget (p50/p95) · payments (spend requests) · voice (Cartesia)
