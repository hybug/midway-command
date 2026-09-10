# Repository Guidelines

**Midway Command** is a WWII strategy game prototype with a Python/FastAPI backend and a native HTML/CSS/JS frontend.

## Project Structure & Module Organization

```
midway-command/
├── server.py          # FastAPI entry point
├── app.py             # Legacy Streamlit app (predecessor)
├── src/               # Game logic modules (state, NPC, dice, scouting, aircraft, etc.)
│   ├── agents/        # LLM agent logic
│   └── render/        # Rendering helpers
├── static/            # Frontend assets (HTML, CSS, JS, Canvas)
├── tests/             # Pytest test suite
├── docs/
│   ├── design/        # Authoritative design docs (GAME_SPEC.md, UI_DESIGN.md, ART_DIRECTION.md…)
│   ├── plans/         # Feature implementation plans (e.g. ui-replication-plan.md)
│   └── reference/     # Historical notes for state init and NPC prompts
├── plan/              # 10-day MVP iteration plan (status in OVERVIEW.md)
└── assets/svg/        # Game artwork (SVG icons inlined by static/js/svgLoader.js)
```

Source lives in `src/`, tests in `tests/` (one file per module: `test_<module>.py`). Design documents are in `docs/design/`.

## Build, Test, and Development Commands

Activate the virtual environment before running any command:

```bash
source .venv/bin/activate
```

| Command | Purpose |
|---------|---------|
| `uvicorn server:app --reload` | Start the dev server (http://localhost:8000) |
| `pytest tests/` | Run the full test suite |
| `pytest tests/test_dice.py -v` | Run a single test file with verbose output |
| `pip install -r requirements.txt` | Install/update dependencies |

## Coding Style & Naming Conventions

- **Language**: Python 3.10+. Use type hints on public function signatures.
- **Indentation**: 4 spaces (PEP 8).
- **Naming**: `snake_case` for functions and variables; `PascalCase` for classes; `UPPER_SNAKE_CASE` for constants.
- **Models**: Pydantic v2 `BaseModel` for data structures.
- **Simplicity**: Write the minimum code that solves the problem. No speculative abstractions.
- **Surgical edits**: Only touch code relevant to the task. Do not refactor unrelated code.

## Testing Guidelines

- **Framework**: pytest.
- **Naming**: Test files are `test_<module>.py`. Test functions are `test_<behavior_description>`.
- **Test-first**: Write a test that reproduces the bug or validates the feature, then make it pass.
- **Coverage**: 253 tests currently (includes UI replication guard tests in `tests/test_ui_assets.py`, `tests/test_raster_assets.py`, `tests/test_quality_gate.py`). New features require tests. Bug fixes require a regression test.
- **Frontend has no JS test runner**: guard `static/` changes with static-analysis pytest tests (parse CSS/SVG/JS for required tokens, assets, and markup) plus browser screenshot verification.
- **Run**: `pytest tests/` for the full suite, `pytest tests/test_state.py::test_name -v` for a single test.

## Architecture Boundaries

- **GameState is the sole source of truth** (`src/state.py`, Pydantic v2). LLM NPCs never hallucinate state — they read via `query_*` tools and mutate via `set_*`/`launch_*` tools only.
- Two visibility layers: `actual_enemy` is god-view truth and **must never leak through NPC query tools** (this asymmetry is the core game mechanic); `known_enemy` is the filtered view NPCs may see.
- **Model duality (known wart)**: `state.Position/Carrier/TaskForce` (US task forces) vs `entities.Position/Carrier/TaskForce` (`src/entities.py`, enemy fleet + movement math). `GameState.enemy_fleet` is an `entities.TaskForce`; keep both in sync when touching positions.
- `src/pipeline.py` runs ordered `TickStep`s on every `POST /advance`; a failing step is logged and skipped, not fatal.
- NPCs in `src/agents/` are independent LLM sessions (separate `messages` lists); all cross-NPC information flows through the player. Autonomy/tool config lives in `src/npc_config.py`.

## Frontend (static/)

Vanilla JS, no framework, no build step; only `/static` is mounted by FastAPI (servable asset files must live under `static/`). `main.js` orchestrates and binds events, `uiController.js` handles panels/tabs, `mapRenderer.js` draws the Canvas map, `svgLoader.js` turns inline SVG strings into `Image` objects for canvas. Map math is prepared server-side in `src/render/`. The visual target is the mockup sheet `docs/assets/ChatGPT Image 2026年6月17日 10_55_51.png` (15-asset "1942 aged-paper chart" board); implementation plan: `docs/plans/ui-replication-plan.md`. Raster material also lives in `docs/assets/`: a green-screen icon sheet (`Gemini_Generated_Icon_Green.png`), the matting script `extract_icons.py`, and `icons_extracted/` (47 transparent PNGs, mixed quality) — curated into `static/assets/ui/icons/` per the plan's raster phase.

## LLM Provider Gotchas (Kimi Code, not Anthropic)

- `base_url = https://api.kimi.com/coding/v1`, `model = kimi-for-coding`; env var is `MOONSHOT_API_KEY` (legacy naming — the API is Kimi).
- `default_headers = {"User-Agent": "claude-code/1.0"}` is **required** — the API returns 403 without it.
- Tool use is OpenAI format; tool-call assistant messages must include an empty `reasoning_content` field (see `src/llm.py`). Max 10 tool calls per turn; prompt caching unsupported.

## Key Reference Docs

- `docs/design/GAME_SPEC.md` — §1–§9 full system spec (source of truth for game logic)
- `docs/design/UI_DESIGN.md` + `docs/design/ART_DIRECTION.md` — visual design system (design tokens, fonts, layout)
- `docs/reference/HISTORICAL_NOTES.md` — historical facts for state initialization and NPC prompts
- `plan/OVERVIEW.md` — day-by-day MVP progress tracking

## Commit & Pull Request Guidelines

Commit messages follow Conventional Commits:

```
feat: <what was added>
fix: <what was fixed>
docs: <what documentation changed>
```

Examples from history: `feat: 骰子系统接入侦察玩法`, `fix: 经度包裹到 [-180, 180] 范围`.

Pull requests should include a description of what changed and why, link to the relevant day/plan item, and screenshots for UI changes.

## Security & Configuration

- Copy `.env.example` to `.env` and fill in `MOONSHOT_API_KEY`. Never commit `.env`.
- Environment variables are loaded via `python-dotenv` at startup.
