# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Midway Command (中途岛指挥官)** — A prototype strategy game: the player, as TF16 Commander Spruance, gives natural-language orders to LLM-driven NPC staff during the Battle of Midway (June 4, 1942, 04:00–08:00, Z+12 / Midway time). Core experience: **information asymmetry × NPC personality × time pressure**.

The 10-day MVP plan lives in `plan/` (status in `plan/OVERVIEW.md`). Core loop (AP/dice), scouting, entity system, multi-NPC, and the FastAPI web frontend are done; combat resolution (Day 9) and playtesting (Day 10) remain. **Don't skip ahead** — each day has a concrete deliverable and cross-day work is prohibited to avoid scope drift. The full system spec is `docs/design/GAME_SPEC.md` (§1–§9); `docs/plans/approval-engine-plan.md` tracked its implementation.

**Tech stack**: Python 3.10+, FastAPI + uvicorn, native HTML/CSS/JS frontend (Canvas), Kimi Code API (OpenAI-compatible), Pydantic v2, OpenAI SDK, pytest.

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
# Run the app — FastAPI backend + static frontend at http://localhost:8000
uvicorn server:app --reload

# Run all tests (以 pytest 实况为准，当前 285 passed)
pytest tests/

# Run a single test
pytest tests/test_state.py::test_name -v

# Validate initial state JSON
python -c "from src.initial_state import build_initial_state; print(build_initial_state().model_dump_json(indent=2))"
```

`app.py` is the **legacy Streamlit app** (predecessor); the current frontend is `static/index.html` served by `server.py`. Keep entry points at the project root.

## High-Level Architecture

### Backend: FastAPI + Tick Pipeline

`server.py` holds module-level global `game_state`, the NPC instances, and the pipeline — a single-user prototype whose state resets on restart. Key endpoints: `/state`, `/npcs`, `/npc/{id}/history`, `/chat`, `/advance`, `/suggestion/{i}/approve|reject`, `/plan-strike`, `/confirm-strike`, `/reject-strike`, `/recall`, `/confirm-contact/{index}`.

`src/pipeline.py` — ordered `TickStep`s run on every `/advance`: clock → positions → spatial index → scouting → pending reports → events → game-over check → AP reset. Each step returns notification strings; a failing step is logged and skipped, not fatal.

### Frontend: static/

`static/index.html` + `static/js/` (vanilla JS, no framework): `main.js` orchestrates, `uiController.js` handles panels/tabs, `mapRenderer.js` draws the Canvas hex map, `svgLoader.js` loads icons. Map data is prepared server-side in `src/render/` — hex coordinate math in `coordinate.py`, chart data + contact-confirm in `chart.py`.

### The State / NPC Wall

**GameState is the sole source of truth** (`src/state.py`, Pydantic v2). All data — fleet positions, aircraft fuel, enemy damage — lives there. LLM NPCs **must never hallucinate state**; they read through `query_*` tools and modify through `set_*` / `launch_*` tools only.

GameState has two visibility layers:
- `actual_enemy` / `enemy_fleet` — god-view truth (e.g. exact Japanese carrier positions at ~30°N 178°W), hidden from NPCs.
- `known_enemy` — filtered view NPCs can access (PBY reports with confidence/source/timestamp).

The `actual_enemy` layer must never leak through query functions. **This is the game's core mechanic** — asymmetric information drives every decision.

**Model duality (known wart):** there are two parallel model families — `state.Position/Carrier/TaskForce` (game-state models, used for the US task forces) and `entities.Position/Carrier/TaskForce` (the entity system in `src/entities.py`, used for the enemy fleet and movement math). `GameState.enemy_fleet` is an `entities.TaskForce`; `entities.update_all_positions` mutates it in place and re-syncs `actual_enemy`. Keep both in sync when touching positions.

### Turn / Time / AP

Turn-based, 15-minute ticks triggered by `POST /advance`. `src/ap.py` — 3 AP (normal) / 5 AP (critical) / 2 AP (emergency) per turn; dialogue and commands consume AP, advancing time resets it. Game ends (`GamePhase.GAME_OVER`) at 08:00 or when all US carriers are sunk.

### Aircraft & Scouting

- `src/state.py` — per-aircraft entities (`Aircraft`) and squadron formations (`AirGroup`) with a full lifecycle (ready → launching → airborne → attacking → returning → refueling/rearming → lost). `src/aircraft.py` implements launch, fuel burn, landing, recall, and damage.
- `src/scouting.py` — full `ScoutMission` lifecycle (preparing → outbound → searching → returning → landed/lost) with the SBD Dauntless fuel model, detection via `src/dice.py` (`roll_scout_check`), and **delayed + distorted reports**: a `PendingReport` stores real vs reported bearing/distance/count and only becomes `known_enemy` after its `arrive_at` time.
- `src/recon_plan.py` + `src/tools.py` — `propose_recon` produces a `PendingSuggestion` for the player to approve; `src/mission.py` plans strikes (intercept kinematics, fuel budget, `MissionPlan`) with `/plan-strike` / `/confirm-strike` endpoints. NPC proposals sit in `state.pending_suggestions` until approved/rejected.
- `src/dice.py` — d100 with five-tier outcomes (大成功/成功/部分成功/失败/大失败), plus `roll_with_npc`, `roll_scout_check`, `roll_attack_check`, `roll_landing_check`, `roll_npc_decision`.

### LLM Provider: Kimi Code via OpenAI SDK

Not Anthropic SDK. Key implications:
- `base_url = https://api.kimi.com/coding/v1`, `model = kimi-for-coding`; the env var is `MOONSHOT_API_KEY` (legacy naming — the API is Kimi, not Moonshot).
- `default_headers = {"User-Agent": "claude-code/1.0"}` is **required** — API returns 403 without it.
- Prompt caching is **not supported** (`cache_read_tokens` always 0, kept for interface compatibility).
- Tool use follows OpenAI format (`role="tool"`, `finish_reason="tool_calls"`); tool-call assistant messages must include an empty `reasoning_content` field (see `src/llm.py`).
- Tool-use loop in `src/llm.py` enforces max 10 tool calls per turn as a safety limit.
- `anthropic` in requirements is legacy/unused.

### NPC Isolation & Config

NPCs in `src/agents/` are **independent LLM sessions** — each `NPCAgent` holds its own `messages` list, so Browning cannot see what the Radio Officer said, and vice versa. All cross-NPC information flows through the player. This is an intentional design choice simulating the real commander's position, not a bug.

`src/npc_config.py` centralizes each NPC's autonomy parameters (0–10: `autonomy`, `risk_tolerance`, `initiative`, `competence`), `info_scope` (which parts of state they may see), and `allowed_tools`. Five NPCs: Browning (参谋长), Murray (企业号舰长), Mitscher (大黄蜂舰长), Radio Officer (通信官), Intel Officer (情报官).

## Conventions

- **Test-first**: write a failing test, then make it pass; new features require tests, bug fixes require a regression test. Tests live in `tests/test_<module>.py`.
- **Commits**: Conventional Commits (`feat:` / `fix:` / `docs:`). Full style and testing guidelines are in `AGENTS.md`.

## Environment

Copy `.env.example` to `.env` and set `MOONSHOT_API_KEY`. The `.env` file is gitignored. `DEV_MODE=true` is read by `src/config.py`.

## Reference Docs

- `docs/design/GAME_SPEC.md` — Full §1–§9 system spec (current source of truth for implementation)
- `docs/design/GAME_DESIGN_V2.md` — Player identity, NPC personalities, decision rhythm, ending conditions
- `docs/design/TECH_ARCH.md` — System architecture with state flow diagrams and module responsibilities
- `docs/reference/HISTORICAL_NOTES.md` — Historical facts for state initialization and NPC prompts (PBY report transcripts, fleet compositions, character bios)
- `plan/` — Day-by-day implementation plans (`OVERVIEW.md` has progress tracking)
