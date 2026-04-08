# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-08
**Commit:** 69705a9
**Branch:** main

## OVERVIEW

NiceGUI web app that imports repeaters from RepeaterBook into OpenGD77 radio codeplugs. Users upload CSV exports, draw zones on a Leaflet map, and export ZIP'd CSV codeplugs. Python 3.14+, deployed on Fly.io.

## STRUCTURE

```
ogdrb/
├── src/ogdrb/          # All source — 8 modules
│   ├── main.py         # UI entry point (1048 lines) — NiceGUI page, ZoneManager, Settings
│   ├── services.py     # RepeaterBook API + SQLModel DB — per-user temp dirs
│   ├── organizer.py    # Repeaters → Codeplug (zones, channels)
│   ├── converters.py   # Repeater → AnalogChannel / DigitalChannel
│   ├── i18n.py         # Babel + gettext — auto-discovers locales from .mo files
│   ├── utils.py        # normalize_string(), MakeUnique (collision-free channel names)
│   └── locales/        # pt_BR translation + .pot template
├── tests/              # pytest — 49 tests (10 async UI, 39 sync unit)
├── playground/         # Dev scripts (circle resize bug repro, examples)
├── benchmarks/         # ASV performance benchmarks
├── docs/               # Sphinx (ReadTheDocs)
├── noxfile.py          # All automation sessions
├── Dockerfile          # Multi-stage build for Fly.io
└── fly.toml            # Fly.io deployment (gig region, 1GB RAM)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add UI elements | `src/ogdrb/main.py` `index()` | Single-page app, all UI in one async function |
| Map/grid sync | `src/ogdrb/main.py` `ZoneManager` | Bidirectional Leaflet ↔ AG Grid sync via JS bridge |
| Repeater queries | `src/ogdrb/services.py` | `_compatibility_filters()` defines what's "compatible" |
| Export pipeline | `services.get_repeaters()` → `organizer.organize()` → `opengd77.codeplug_to_csvs()` |
| Channel naming | `converters.make_name()` → `utils.MakeUnique` | Truncation + dedup to fit OpenGD77 limits |
| Add a language | `nox -s i18n_init -- <locale>` then translate `.po`, then `nox -s i18n_compile` |
| Deployment | `Dockerfile` → `fly deploy` | Multi-stage, `python app/src/ogdrb/main.py` |
| Run app locally | `uv sync && python src/ogdrb/main.py` | Reads `.env` for `storage_secret`, `on_air_token` |

## CONVENTIONS

- **src-layout** with `hatchling` build backend
- **`from __future__ import annotations`** in every file
- **`__all__`** tuple declared in every module
- **Google-style docstrings** — enforced by ruff `pydocstyle.convention = "google"`
- **Ruff ALL rules** selected — suppress with `# noqa: XXXX` only when justified
- **MyPy strict** — `type: ignore[code]` requires specific error code
- **`TYPE_CHECKING` guards** for import-time-only types
- **Conventional Commits** — `feat:`, `fix:`, `chore:`, `test:`, `refactor:` prefixes
- **`attrs` for immutable domain objects** (`@frozen`) — `UniRepeater` in services.py
- **`TypedDict` for grid row shapes** — `ZoneRow`, `AGColumnDef` in main.py
- **`NamedTuple` for value objects** — `RepeaterId`, `CountrySelection`, `Language`
- **i18n via `t()` function** — wraps gettext, reads user language from NiceGUI storage
- **Per-user isolation** — each session gets a temp dir + SQLite via `create_repeater_db()`
- **No conftest.py** — fixtures from NiceGUI plugin (`user: User`) or inline mocks

## ANTI-PATTERNS (THIS PROJECT)

- **`index()` is 512 lines** (noqa: C901, PLR0915) — known tech debt, all UI in one function
- **`contextlib.suppress(Exception)`** in `i18n.py` — intentional for non-request-context fallback
- **`ignore_errors=True`** in `cleanup_repeater_db()` — silent cleanup failure on disconnect
- **Several `# type: ignore[no-untyped-call]`** — upstream libs (`us`, `haversine`, NiceGUI methods) lack stubs
- **API access disabled** — country selector + "Load Repeaters" button hidden; CSV upload is the current flow
- **5 skipped tests** in `test_app.py` — correspond to disabled API-based features

## UNIQUE STYLES

- **JS bridge pattern** — `ZoneManager._js_*` methods inject raw JavaScript via `ui.run_javascript()` with `_ogdrb_ctx()` global helper for Leaflet access
- **`_ogdrb_row_id` stamp** — circles carry a custom property linking back to grid row IDs
- **Debounced grid flush** — `_schedule_grid_flush()` uses `ui.timer` to batch rapid edit events
- **Parallel API downloads** — `anyio.create_task_group()` for concurrent RepeaterBook queries
- **Dynamic Nox CI** — `nox --json -l | jq` generates GitHub Actions matrix dynamically
- **OIDC auth for Codecov** — no secrets, uses GitHub OIDC token
- **`builtins-ignorelist = ["id", "type"]`** — ruff allows shadowing `id` and `type` builtins

## COMMANDS

```bash
# Dev setup
uv sync

# Run locally
python src/ogdrb/main.py          # or: uv run python src/ogdrb/main.py

# Test
uv run pytest                      # quick
nox -s test_code                   # full (multi-python)

# Lint + format
uv run ruff check . --fix
uv run ruff format

# Type check
uv run mypy

# i18n workflow
nox -s i18n_extract                # extract strings → .pot
nox -s i18n_update                 # merge .pot → .po catalogs
nox -s i18n_compile                # compile .po → .mo

# All nox sessions
nox -s pre_commit lint_files format_files type_check_code test_code
```

## NOTES

- **Python 3.14 required** — `requires-python = ">=3.14"` in pyproject.toml
- **`.env` file** — `storage_secret` (NiceGUI session storage) + `on_air_token` (NiceGUI On Air)
- **`__mp_main__` guard** — `if __name__ in {"__main__", "__mp_main__"}` handles NiceGUI multiprocessing
- **`reload` disabled on Fly.io** — checks `FLY_ALLOC_ID` env var to skip file watching in prod
- **OpenGD77 limits** — `Max.ZONES`, `Max.CHANNELS`, `Max.CHANNELS_PER_ZONE`, `Max.CHARS_*` from `opengd77.constants`
- **Channel name format** — `CALL_City` (analog `~`, digital `_`) truncated to `Max.CHARS_CHANNEL_NAME`
- **Zone splitting** — each zone becomes two: `"Zone [D]"` (digital) + `"Zone [A]"` (analog)
- **Repeater compatibility** — must be DMR/analog, On-air, Open use, 2m/70cm band, valid bandwidth
- **Template origin** — scaffolded from [MicaelJarniac/crustypy](https://github.com/MicaelJarniac/crustypy)
- **Related libs** — `repeaterbook` and `opengd77` are author's own packages
