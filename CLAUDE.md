# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Midway Command (中途岛指挥官)** — A prototype strategy game: the player, as TF16 Commander Spruance, gives natural-language orders to LLM-driven NPC staff during the Battle of Midway (June 4, 1942, 04:00–08:00). 10-day MVP plan in `plan/day01-skeleton.md` through `day10-iterate.md`. **Do not skip ahead** — each day has a concrete deliverable and cross-day work is prohibited to avoid scope drift.

**Tech stack**: Python 3.10+, Streamlit, Kimi Code API (OpenAI-compatible), Pydantic v2, OpenAI SDK, pytest.

## Behavioral Guidelines

### 1. Think Before Coding

Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist (e.g., "make the search faster" could mean latency, throughput, or perceived speed), present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what the day's plan specifies.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios (e.g., GameState internal invariants).
- If you write 200 lines and it could be 50, rewrite it.

The test: Would a senior engineer say this is overcomplicated? If yes, simplify.

### 3. Surgical Changes

Touch only what you must. Clean up only your own mess.

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request or the day's plan.

### 4. Goal-Driven Execution

Define success criteria. Loop until verified.

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

## Common Commands

All commands assume the virtual environment is activated (`source .venv/bin/activate`):

```bash
# Run the Streamlit app (entry point is in project root, not src/)
streamlit run app.py

# Run all tests
pytest tests/

# Run a single test
pytest tests/test_state.py::test_name -v

# Validate initial state JSON
python -c "from src.initial_state import build_initial_state; print(build_initial_state().model_dump_json(indent=2))"
```

## High-Level Architecture

### The State / NPC Wall

**GameState is the sole source of truth.** All data — fleet positions, aircraft fuel, enemy damage — lives in `GameState` (Pydantic models, `src/state.py`). LLM NPCs **must never hallucinate state**. They read through `query_*` tools and modify through `set_*` / `launch_*` tools only.

GameState has two layers:
- `actual_*` — god-view, hidden from NPCs (e.g. exact Japanese carrier positions at `~30°N 178°W`)
- `known` — filtered view NPCs can access (e.g. PBY reports with confidence/source/timestamp)

The `_hidden_actual_enemy` field must never leak through query functions. **This is the game's core mechanic** — asymmetric information drives every decision.

### LLM Provider: Kimi Code via OpenAI SDK

Not Anthropic SDK. Key implications:
- `base_url = https://api.kimi.
com/coding/v1`, `model = kimi-for-coding`
- `default_headers = {"User-Agent": "claude-code/1.0"}` is **required** — API returns 403 without it
- Prompt caching is **not supported** (`cache_read_tokens` always 0, kept for interface compatibility)
- Tool use follows OpenAI format (`role="tool"`, `finish_reason="tool_calls"`)
- `anthropic` package in requirements is legacy/unused
- Tool-use loop in `src/llm.py` enforces max 10 tool calls per turn as safety limit

### NPC Isolation

NPCs in `src/agents/` are **independent LLM sessions**. They do not share conversation history — Browning cannot see what the Radio Officer said, and vice versa. All cross-NPC information flows through the player. This is an intentional design choice simulating the real commander's position, not a bug.

### Time & Events

Turn-based, not real-time. 15-minute ticks triggered by a player button. `EventScheduler` (`src/events.py`) checks pending events at each tick. Events typically add entries to `state.incoming_messages`. Command delay is handled through **textual description** in NPC responses, not real queues — state changes via write tools take effect immediately.

### Combat Resolution

Combat (`src/combat.py`) is **lookup tables + randomness**, not physics simulation. Input: launch time, air group config, target. Output: `StrikeOutcome` (ships sunk, losses, narrative). Uses `random.Random(seed)` for reproducibility.

### app.py Location

`app.py` **must stay in the project root**. Streamlit's module resolution fails when the entry point is inside `src/` — this was discovered and fixed on Day 1. Don't move it.

## Environment

Copy `.env.example` to `.env` and set `MOONSHOT_API_KEY`. The `.env` file is gitignored. `DEV_MODE=true` enables debug panels in the UI.

## Reference Docs

- `docs/GAME_DESIGN.md` — Player identity, NPC personalities, decision rhythm, ending conditions
- `docs/HISTORICAL_NOTES.md` — Historical facts for state initialization and NPC prompts (PBY report transcripts, fleet compositions, character bios)
- `docs/TECH_ARCH.md` — Full system architecture with state flow diagrams and module responsibilities
