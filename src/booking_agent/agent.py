import datetime
import json
import pathlib
import time

import anthropic
from anthropic.types.beta import BetaMessage
from booking_agent.tools import RESTAURANT_TZ, TOOLS, run_tool

MODEL = "claude-opus-5-5"
MAX_STEPS = 8  # safety rail: never let one guest message loop forever

SYSTEM = """You are the booking assistant for Juniper, a small restaurant.
Today is {today:%A, %d %B %Y} ({today_iso}), restaurant time ({tz}).
- Always check availability before offering or booking a time. Never invent times.
- Before calling book, confirm the guest's name, party size, date and time.
- After booking, tell the guest their booking_id.
- Keep replies to one or two short sentences. They will be spoken aloud later."""

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment


def call_claude(messages: list, system: str) -> BetaMessage:
    return client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=system,
        tools=TOOLS,
        messages=messages,
        output_config={
            "effort": "low"
        },  # chat-style turns: less thinking, lower latency
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # if a safety classifier declines, retry on another model
    )


def build_system(now: datetime.datetime) -> str:
    today = now.date()
    return SYSTEM.format(
        today=today,
        today_iso=today.isoformat(),
        tz=now.tzname(),
    )


def run_turn(messages: list, trace: list, system: str) -> str:
    """Loop until Claude replies to the guest. Appends everything to `messages`."""
    for step in range(MAX_STEPS):
        start = time.perf_counter()
        response = call_claude(messages, system)
        span = {
            "step": step,
            "ms": round((time.perf_counter() - start) * 1000),
            "stop_reason": response.stop_reason,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "tools": [],
        }
        trace.append(span)

        if response.stop_reason == "refusal":
            return "Sorry, I can't help with that one."

        # TODO 1: the API is stateless; `messages` is the agent's only memory.
        # Append Claude's whole reply (every block, not just the text) as an "assistant" message.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    output, is_error = run_tool(block.name, block.input)
                    span["tools"].append(
                        {"name": block.name, "input": block.input, "error": is_error}
                    )
                    # TODO 2: append a tool_result dict to `results`. It needs four keys:
                    # "type" ("tool_result"), "tool_use_id" (which call this answers), "content", "is_error".
                    results.append(
                        {
                            "type": "tool_result",
                            "content": output,
                            "is_error": is_error,
                            "tool_use_id": block.id,
                        }
                    )
            # TODO 3: send ALL the results back to Claude in ONE "user" message.
            messages.append({"role": "user", "content": results})
            continue

        if response.stop_reason == "pause_turn":
            continue  # already appended; send it back so the server can carry on

        # end_turn (or max_tokens): Claude is talking to the guest.
        return "".join(b.text for b in response.content if b.type == "text")

    return "Sorry, I got stuck. Let me get someone from the restaurant to help."


def print_trace(spans: list) -> None:
    for s in spans:
        tools = (
            ", ".join(t["name"] + (" ✗" if t["error"] else "") for t in s["tools"])
            or "-"
        )
        print(
            f"   · step {s['step']}  {s['ms']:>5} ms  in {s['input_tokens']:>5}  out {s['output_tokens']:>4}  {s['stop_reason']:<9} tools: {tools}"
        )


def main() -> None:
    messages: list = []
    trace: list = []
    print("Juniper booking agent. Type 'quit' to exit.")
    system = build_system(datetime.datetime.now(RESTAURANT_TZ))
    while True:
        text = input("\nyou> ").strip()
        if text.lower() in {"quit", "exit"}:
            break
        if not text:
            continue
        messages.append({"role": "user", "content": text})
        before = len(trace)
        reply = run_turn(messages, trace, system)
        print(f"agent> {reply}")
        print_trace(trace[before:])

    out = pathlib.Path("traces") / f"{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    out.parent.mkdir(exist_ok=True)
    out.write_text("".join(json.dumps(s) + "\n" for s in trace))
    print(f"\nSaved {len(trace)} steps to {out}")


if __name__ == "__main__":
    main()
