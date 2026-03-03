# CHANGELOG


## v0.6.0 (2026-03-03)

### Bug Fixes

- Harden i18n storage access and browser language parsing
  ([`57cb4e8`](https://github.com/MicaelJarniac/ogdrb/commit/57cb4e8465f3493537721c366b71f9872eed66b1))

- Add _current_lang_code() helper to DRY up duplicated storage access - Fix territory_name() None
  guard (replace type:ignore with proper check) - Fix quasar_html() and selector() crashes outside
  request context - Fix browser_language Accept-Language parsing to strip quality values - Add tests
  for _flag_emoji, _discover_languages, _current_lang_code, t(), territory_name, and LanguageManager

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-opencode)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

### Build System

- Add babel runtime dep and i18n build config
  ([`3f2afad`](https://github.com/MicaelJarniac/ogdrb/commit/3f2afadbd307871edde0655483193bc213a7d488))

- Move babel from optional i18n group to runtime dependencies - Update babel extraction config
  (keywords, mapping, output path) - Add .gitignore negation patterns to track locale files (*.pot,
  *.mo) - Ignore .nicegui directory

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-opencode)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- Add nox sessions for i18n workflow
  ([`706403b`](https://github.com/MicaelJarniac/ogdrb/commit/706403ba3ed17559348f71ddf1e81130b6c4c4ec))

Add four nox sessions for managing translations: - i18n_extract: extract strings to POT template -
  i18n_init: initialize new language catalog - i18n_update: update existing catalogs from POT -
  i18n_compile: compile PO to binary MO files

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-opencode)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- Fill POT metadata in i18n_extract nox session
  ([`5d23b6e`](https://github.com/MicaelJarniac/ogdrb/commit/5d23b6e007de3dda4888d90ae4d01fbdac2849e1))

Pass --version (read dynamically from pyproject.toml), --copyright-holder, and --msgid-bugs-address
  to pybabel extract so the POT header is fully populated.

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-opencode)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

### Chores

- Exclude .po/.pot from end-of-file and trailing-whitespace hooks
  ([`240c343`](https://github.com/MicaelJarniac/ogdrb/commit/240c343d471f3de9a9b381ecc95ee4872189a8b1))

Gettext catalog files have their own formatting conventions that conflict with these pre-commit
  hooks.

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-opencode)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- I18n WIP
  ([`a479b51`](https://github.com/MicaelJarniac/ogdrb/commit/a479b516106015597d51fe1159b01605782f6242))

- Regenerate locale files with updated translations
  ([`766508a`](https://github.com/MicaelJarniac/ogdrb/commit/766508a58c213948a4d398c015db865fda0ecf5f))

- Regenerate POT template (no URLs, split help text, individual table headers) - Rewrite pt_BR PO
  with all new translations, remove fuzzy/obsolete entries - Recompile MO binary

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-opencode)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- Remove unused babel extract_messages config
  ([`bea8a71`](https://github.com/MicaelJarniac/ogdrb/commit/bea8a71264f85cd7cdf12a6dc4ca66440e2025f4))

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-opencode)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- Translations sync
  ([`356bca0`](https://github.com/MicaelJarniac/ogdrb/commit/356bca0c085cf8d8d560a8a0a101c96884502a7c))

- Update all dependencies and remove circle-resize monkeypatch
  ([#11](https://github.com/MicaelJarniac/ogdrb/pull/11),
  [`5ce08ef`](https://github.com/MicaelJarniac/ogdrb/commit/5ce08ef44277a328b85c150b20a706085cb822ce))

Bump all dependency minimum versions to match currently installed packages (including NiceGUI 3.8.0,
  sqlmodel 0.0.37, pycountry 26.2.16, us 3.2.0, and many others). Also removes the
  L.Edit.Circle._resize monkeypatch that worked around a Leaflet Draw minification bug, which is
  fixed in NiceGUI 3.8.0.

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

- Update translations
  ([`32e6440`](https://github.com/MicaelJarniac/ogdrb/commit/32e6440b5db8d09a804540c9870078d8b531d478))

### Features

- Add i18n support with gettext for all UI strings
  ([`95d0e21`](https://github.com/MicaelJarniac/ogdrb/commit/95d0e21e68ae7e20341457ab74ee7a201692c565))

- Add pt_BR locale catalog
  ([`e4151dc`](https://github.com/MicaelJarniac/ogdrb/commit/e4151dc95f8f4236f74dfb5edc81752d3df25395))

- Extract 35 translatable strings to ogdrb.pot template - Initialize and fully translate pt_BR
  catalog (ogdrb.po) - Compile binary message catalog (ogdrb.mo)

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-opencode)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- Auto-detect supported locales from directory
  ([`c7ad8fc`](https://github.com/MicaelJarniac/ogdrb/commit/c7ad8fc27cecff9919a9ff64cb3dda7e6f861589))

Scan LOCALE_DIR for subdirectories containing compiled .mo files and build Language objects
  dynamically using Babel's Locale.parse() for display names and Unicode regional indicators for
  flag emoji.

Adding a new language now requires only a locale directory (pybabel init + translate + compile) — no
  Python code changes needed.

Also provides an EMOJI_OVERRIDES dict for edge cases (e.g. locales without a country code).

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-opencode)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- Implement per-user gettext translations
  ([`5c62361`](https://github.com/MicaelJarniac/ogdrb/commit/5c6236109d102cd41377c35a59b61073861fa79a))

- Replace module-level singleton t() with per-user function that reads from app.storage.user,
  enabling per-session language switching - Add PT_BR language with cached GNUTranslations lookup -
  Fix browser_language variable shadowing bug (inner loop vs set comprehension) - Fix selector label
  collision: use language_name instead of display_name to avoid 'English (United States)'
  conflicting with country selector - Seed user storage before bind_value to prevent spurious reload
  on load

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-opencode)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- Localize country names in selector by user language
  ([`7d2d3b6`](https://github.com/MicaelJarniac/ogdrb/commit/7d2d3b6764cc1b1752bca2051c74871ebd6e3b4f))

Add territory_name() helper that returns localized country names via Babel's Locale.territories. The
  country selector now displays names in the user's chosen language (e.g. 'Estados Unidos' for
  pt-BR) while keeping alpha-2 codes as values for the backend API.

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-opencode)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- Parse Accept-Language header with RFC 7231 quality values
  ([`2aa601f`](https://github.com/MicaelJarniac/ogdrb/commit/2aa601f4003179d7b525429e9484dcb561f01fcb))

Replace naive comma+semicolon split with _parse_accept_languages() that extracts q-values and sorts
  by priority, so browser_language matches the user's highest-quality supported locale instead of
  the first one in header order.

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-opencode)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- Quasar lang
  ([`13b8b13`](https://github.com/MicaelJarniac/ogdrb/commit/13b8b132f3e51fb6a83f48ca3148a07938488f36))

### Refactoring

- Move ExternalURLs to module scope and split help text
  ([`ccfc81b`](https://github.com/MicaelJarniac/ogdrb/commit/ccfc81baa11615ec033d3654e88177d802719045))

- Move ExternalURLs enum out of index() to avoid wrapping URLs in t() - Split monolithic help text
  into 5 translatable sections - Fix leading space in INCOMPATIBLE badge - Fix 'New Zone' button
  text casing in test

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-opencode)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>


## v0.5.0 (2026-02-25)

### Bug Fixes

- Address code review findings
  ([`a1a329b`](https://github.com/MicaelJarniac/ogdrb/commit/a1a329bc35e986fb4db09559df8ebd067c5adc5f))

- Remove dead _rows_by_id dict from ZoneManager (write-only, never read) - Add empty-DB guard in
  export flow to warn when repeaters not loaded - Convert CountrySelection to NamedTuple for
  self-documenting fields - Move Country import to TYPE_CHECKING block - Convert f-string loggers to
  loguru lazy format (7 occurrences) - Remove inconsistent @pytest.mark.anyio marker

- Address code review findings for PR #8
  ([`f8f0808`](https://github.com/MicaelJarniac/ogdrb/commit/f8f08080cb0a6b525f2410ec42f2a0ebd2c5ac7e))

- Escape external API data in marker popups to prevent XSS - Fix race condition in
  prepare_local_repeaters (dict keyed by index instead of concurrent list.append) - Extract
  duplicated country/state SQL filter logic into _country_state_filters helper - Document _find_row
  O(n) design decision (AG Grid shares list ref)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- Address code review findings for PR #8
  ([`3b903af`](https://github.com/MicaelJarniac/ogdrb/commit/3b903af3df07e8df984f21fd67c9629fbea54f1f))

- Fix race condition in prepare_local_repeaters: collect download results into separate lists
  instead of concurrent .extend() on a shared list - Restore country/state filters in export path
  (get_repeaters now accepts country_names and us_state_ids to avoid returning unrelated repeaters)
  - Remove async from get_repeaters and get_compatible_repeaters (purely synchronous SQLModel
  queries) - Extract duplicated JS draw-group lookup into window._ogdrb_ctx() helper - Filter out
  territories with None FIPS codes from US_STATES dict - Fix no-op test assertion (>= 0 → == 1) and
  remove unused variable

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- Extract enum values
  ([`f60efcc`](https://github.com/MicaelJarniac/ogdrb/commit/f60efcc04988bd2b8892b8b062eef9282fd16988))

- Include digital-only repeaters and show compatibility on map
  ([`f79fc32`](https://github.com/MicaelJarniac/ogdrb/commit/f79fc3210a98e67b1747e657880431743201bcd1))

- Fix fm_bandwidth filter to allow NULL (digital-only repeaters) - Add visual indicators: blue
  markers (compatible), red dots (incompatible) - Eliminate code duplication by using SQL filters as
  single source of truth - Query repeaters twice on map load: all + compatible for O(1) color lookup
  - Ensure map display and export use identical compatibility logic

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Kinda better?
  ([`ffd346d`](https://github.com/MicaelJarniac/ogdrb/commit/ffd346dc1634493bcd0b4d34188cbd7a3cbaedbb))

- Mostly works
  ([`6eba761`](https://github.com/MicaelJarniac/ogdrb/commit/6eba761636b938ec09e84315ae28cd066cd3253d))

- Patch NiceGUI's broken circle resize in Leaflet Draw
  ([`566d8f9`](https://github.com/MicaelJarniac/ogdrb/commit/566d8f9ad41da7d66b1f718e3f3866bf56f78730))

The minified Leaflet Draw bundle shipped with NiceGUI 3.x has a bug: L.Edit.Circle._resize uses an
  undeclared `radius` variable (the minifier dropped it from `var moveLatLng = ..., radius;`). Since
  the bundle is loaded as an ES module (strict mode), the bare assignment throws a ReferenceError,
  silently killing circle resize.

Monkey-patch the method on init with a corrected version.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- Reset circle colors when grid rebuilds clearing selection
  ([`a4f42ad`](https://github.com/MicaelJarniac/ogdrb/commit/a4f42add9ea10a3040f7aca2b5f47568b4708227))

Listen for AG Grid's gridReady event (fires after every rebuild) to reset all circle colors to blue,
  since the rebuild silently clears row selection without firing rowSelected events.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- Split non-US country queries to avoid API result truncation
  ([`2c254d1`](https://github.com/MicaelJarniac/ogdrb/commit/2c254d1c599bbb1f31a5db21cf235ac511070337))

Each non-US country now gets its own ExportQuery, matching the existing per-state splitting for US.
  This prevents multi-country ROW requests from exceeding RepeaterBook's ~3500 result cap and
  silently losing repeaters.

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-opencode)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- Use US FIPS state ids for filtering
  ([`a666bd1`](https://github.com/MicaelJarniac/ogdrb/commit/a666bd18281d3e4a859069fd53451c80ed5579c8))

### Build System

- **deps**: Update Nox
  ([`8716ba5`](https://github.com/MicaelJarniac/ogdrb/commit/8716ba51293a885921ce0e7615cd8034851d1790))

### Chores

- Better texts
  ([`e0438f0`](https://github.com/MicaelJarniac/ogdrb/commit/e0438f0ce4239450168a1f2eb0130b822b769200))

- Fix typing
  ([`bf237b3`](https://github.com/MicaelJarniac/ogdrb/commit/bf237b3d76dc1687dbc8de2411f9bfb4364b61e2))

- Fixes
  ([`97a5823`](https://github.com/MicaelJarniac/ogdrb/commit/97a58230a538bbe63a340c02e2b857edc4ad690a))

- Format
  ([`c44c1c0`](https://github.com/MicaelJarniac/ogdrb/commit/c44c1c0468403c46773c060189d0a5f603294fda))

- Lint & small refactor
  ([`28ff0d9`](https://github.com/MicaelJarniac/ogdrb/commit/28ff0d963ced1c8291a37c4ce3c0af2d3ebf3aff))

- Remove empty line
  ([`8aa38eb`](https://github.com/MicaelJarniac/ogdrb/commit/8aa38eb2aed6038ff91e27c16383e1f0b0216a81))

- Remove pragma no covers
  ([`4627c95`](https://github.com/MicaelJarniac/ogdrb/commit/4627c95f4481e720027e96dbf1f48824fd91291b))

- Small DRY
  ([`b256be2`](https://github.com/MicaelJarniac/ogdrb/commit/b256be2a0c71dc3b9d7361862f395fafb88e3a73))

- Tests typing
  ([`ba53d17`](https://github.com/MicaelJarniac/ogdrb/commit/ba53d174b0e32d71314823ffeb36a58ba9ec815b))

- Tiny refactor
  ([`fc423f7`](https://github.com/MicaelJarniac/ogdrb/commit/fc423f7e81e130b161853737b4a0cdc33f114ca7))

- Typing
  ([`f16c199`](https://github.com/MicaelJarniac/ogdrb/commit/f16c199ee62aab6f8242623f9a230a756ecb6c30))

- Upgrade all deps and migrate to NiceGUI 3.x
  ([`36b28b6`](https://github.com/MicaelJarniac/ogdrb/commit/36b28b64992b9401ea25840f54e7f371a0a8f4c0))

- Upgrade all dependencies (110 packages), notably NiceGUI 2.17→3.7.1 - Fix AG Grid data binding:
  use grid's ObservableList instead of disconnected plain list; remove explicit grid.update() calls
  - Update rowSelection to object format for AG Grid 34 - Add sanitize=False to footer ui.html()
  calls (new default in 3.0) - Fix removed APIs: initialized() timeout param, balham-dark theme

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- Upgrade Python from 3.13 to 3.14
  ([`4f47491`](https://github.com/MicaelJarniac/ogdrb/commit/4f47491e2d303ebd9179f31e5518334ff1de90d7))

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- Use repeaterbook>=0.2.2 (drop local path)
  ([`56c6314`](https://github.com/MicaelJarniac/ogdrb/commit/56c63147372694670aef019f61e4f6bf8ad6a10a))

- Use us package for FIPS state codes
  ([`2162f9b`](https://github.com/MicaelJarniac/ogdrb/commit/2162f9b8e161416409b2a73400d40627581d0d67))

- **wordlist**: Add packages
  ([`bde6737`](https://github.com/MicaelJarniac/ogdrb/commit/bde6737d3daa5adbd5928aecc21c4200d0b7ca3e))

### Features

- Better layout
  ([`2769aac`](https://github.com/MicaelJarniac/ogdrb/commit/2769aac473098fa6e6a2d165759da28e4dc27555))

- Bidirectional selection — clicking a circle selects the grid row
  ([`5b6103b`](https://github.com/MicaelJarniac/ogdrb/commit/5b6103bb95c1e921fa0be913931e74ef351f0de0))

Adds click handlers to map circles that emit a custom 'circle-click' event, which selects and
  scrolls to the corresponding AG Grid row.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- Enable leaflet marker clustering
  ([`7dde792`](https://github.com/MicaelJarniac/ogdrb/commit/7dde7920cdebb7dbe73ecef5c648821200130c4a))

- Preload repeaters and map markers
  ([`5f7a9f8`](https://github.com/MicaelJarniac/ogdrb/commit/5f7a9f84d12ea28eb21be87587c1c583bb0619d4))

- Timestamp on filename
  ([`55d6e3c`](https://github.com/MicaelJarniac/ogdrb/commit/55d6e3c776835065962bc009611d5559ae877e1a))

### Refactoring

- Address code review items for PR #8
  ([`5901388`](https://github.com/MicaelJarniac/ogdrb/commit/5901388a23ba11992fd23ab349f00af470c079bc))

Services refactoring: - Add module-level RepeaterBook service instances for reuse - Implement
  parallel downloads for US state queries using anyio - Add US_COUNTRY_CODE and US_COUNTRY_NAME
  constants - Fix re-download bug by removing prepare_local_repeaters from get_repeaters - Change
  build_export_queries to raise ValueError when US selected without states

ZoneManager improvements: - Add factory method create() for proper async initialization - Add
  dynamic draw group lookup with fallback for robust Leaflet initialization - Implement _rows_by_id
  index for O(1) row lookups (maintained but using _find_row) - Fix AGColumnDef TypedDict with
  NotRequired for optional fields - Add type annotations and sanitize=False comments

Tests: - Add test_main.py with 6 ZoneManager unit tests - Add test_services.py with 3 new async
  tests for services module - All tests passing with full coverage

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Replace nuke-and-rebuild Leaflet<->AG Grid sync with ZoneManager
  ([`ba22909`](https://github.com/MicaelJarniac/ogdrb/commit/ba229093eefb26e341b27408f415bdf10cab79f9))

The old approach deleted all map circles and recreated them from scratch on every interaction (draw,
  edit, delete, select, grid edit). This caused visual flashing, stale ID mappings, and race
  conditions.

ZoneManager performs targeted updates instead: - Map events only update grid rows (circles already
  positioned by Leaflet) - Grid events only update the affected circle (skip if only name changed) -
  Selection changes batch-update circle colors in a single JS call - Stable bidirectional row_id <->
  leaflet_id mappings

Also fixes type coercion for AG Grid cell edits (string -> float/int).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

### Testing

- Add UI tests for web app using NiceGUI User simulation
  ([`d57dbea`](https://github.com/MicaelJarniac/ogdrb/commit/d57dbea835f703cf210dec09bf8ffba6dd91540b))

Add 8 new tests covering page elements, country/state selection, validation notifications, help
  dialog, and footer content. Mock ui.run_javascript so ZoneManager initializes fully in the
  simulation.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>


## v0.4.3 (2025-05-16)

### Bug Fixes

- Bigger map load timeout
  ([`90767fb`](https://github.com/MicaelJarniac/ogdrb/commit/90767fb2a8c964d7dee511e708f31fa0e157aa4e))


## v0.4.2 (2025-05-16)

### Bug Fixes

- No auto-reload when in Fly
  ([`812da05`](https://github.com/MicaelJarniac/ogdrb/commit/812da0572efca9fad039891f82632e867d63360b))


## v0.4.1 (2025-05-16)

### Bug Fixes

- Bigger timeouts
  ([`c2c8938`](https://github.com/MicaelJarniac/ogdrb/commit/c2c89387f8fbd582891319dc6c1f1f354f5bf055))

This is a temporary fix. I should probably make repeaterbook local DB async.


## v0.4.0 (2025-05-16)

### Build System

- Dockerfile
  ([`1d41665`](https://github.com/MicaelJarniac/ogdrb/commit/1d416652b9183374d73075168d7eb9059d07067e))

### Features

- Spinner
  ([`054dbe0`](https://github.com/MicaelJarniac/ogdrb/commit/054dbe010aff52af73a5ee2e111540fcf8a00a43))


## v0.3.0 (2025-05-14)

### Build System

- **deps**: Update NiceGUI
  ([`2d51d78`](https://github.com/MicaelJarniac/ogdrb/commit/2d51d78c65d214ffac5f7bf1f3d6d3b577bb1333))

### Features

- Better UX, errors, info about limits, favicon
  ([`8c1da6a`](https://github.com/MicaelJarniac/ogdrb/commit/8c1da6aaac88b7dbea803cbe55d29b04b4e17103))


## v0.2.0 (2025-05-13)

### Bug Fixes

- Typo
  ([`aff2331`](https://github.com/MicaelJarniac/ogdrb/commit/aff2331cebf88ec5e25380fcb9e280ed7acbee13))

### Chores

- Hide sidebar
  ([`00bf23f`](https://github.com/MicaelJarniac/ogdrb/commit/00bf23f23f0576e5c3a0caa4447e17fe781c4687))

### Features

- Add circle
  ([`a2b44e5`](https://github.com/MicaelJarniac/ogdrb/commit/a2b44e53ea74e1eca44c9ad91d43322cb27624ef))

- Almost export
  ([`209b46a`](https://github.com/MicaelJarniac/ogdrb/commit/209b46a572c164014d7818643a36e275c001adb1))

- Basic functionality finished
  ([`64402a4`](https://github.com/MicaelJarniac/ogdrb/commit/64402a4b486d2ebefc49288c246df6c3d9a60ea8))

- Filter bandwidth
  ([`2b0b041`](https://github.com/MicaelJarniac/ogdrb/commit/2b0b041052558e606fa928fe5077388c1a3659b4))

- Settings
  ([`b554924`](https://github.com/MicaelJarniac/ogdrb/commit/b554924bd9b4207f47b8aec126835bf740d75a92))

- Sync map and table
  ([`19f8a54`](https://github.com/MicaelJarniac/ogdrb/commit/19f8a54d0d6093fc238571f056210da5400a194e))

- Sync table and map the other way around
  ([`c7737e0`](https://github.com/MicaelJarniac/ogdrb/commit/c7737e0369477ae544efa3c018e398866fbd84f6))

- Table
  ([`1d34aff`](https://github.com/MicaelJarniac/ogdrb/commit/1d34affc6e57d935a8e16b4d4807b62d39b5b76c))

- Ux improvements
  ([`820a4a4`](https://github.com/MicaelJarniac/ogdrb/commit/820a4a4b7a613011b95f8ef4cdb79af91d47165e))


## v0.1.0 (2025-04-16)

### Features

- Initial release
  ([`bc19f21`](https://github.com/MicaelJarniac/ogdrb/commit/bc19f21529486449006a653b4c8dbdd552362382))


## v0.0.1 (2025-04-09)

### Bug Fixes

- Bandwidth
  ([`e445232`](https://github.com/MicaelJarniac/ogdrb/commit/e445232932f49b06dc191490ff7e0f29a240f91e))


## v0.0.0 (2025-04-09)

### Documentation

- **readme**: Links
  ([`ea90b19`](https://github.com/MicaelJarniac/ogdrb/commit/ea90b1981c231cd180fc848aebe7bf63a91e89f3))
