"""ogdrb."""

from __future__ import annotations

__all__: tuple[str, ...] = ()

import json
import os
from enum import StrEnum
from typing import TYPE_CHECKING, Any, TypedDict, cast

import pycountry
import us  # type: ignore[import-untyped]
from haversine import Unit  # type: ignore[import-untyped]
from nicegui import ui
from opengd77.constants import Max
from opengd77.converters import codeplug_to_csvs, csvs_to_zip
from pycountry.db import Country
from pydantic_settings import BaseSettings, SettingsConfigDict
from repeaterbook.models import ExportQuery
from repeaterbook.utils import LatLon, Radius

from ogdrb.organizer import organize
from ogdrb.services import get_repeaters, prepare_local_repeaters

if TYPE_CHECKING:  # pragma: no cover
    from nicegui.elements.aggrid import AgGrid
    from nicegui.elements.leaflet import Leaflet
    from nicegui.events import GenericEventArguments
    from repeaterbook import Repeater


class ExternalURLs(StrEnum):
    """External URLs."""

    REPEATERBOOK = "https://repeaterbook.com"
    REPEATERBOOK_API = "https://repeaterbook.com/wiki/doku.php?id=api"
    REPEATERBOOK_PLUS = "https://repeaterbook.com/index.php/rbplus"
    OPENGD77 = "https://opengd77.com"
    GITHUB = "https://github.com/MicaelJarniac/ogdrb"


class Settings(BaseSettings):
    """Settings for the app."""

    model_config = SettingsConfigDict(env_file=".env")

    storage_secret: str | None = None
    on_air_token: str | None = None


class ZoneRow(TypedDict):
    """ZoneRow class for AG Grid."""

    id: int
    name: str
    lat: float
    lng: float
    radius: float


class AGColumnDef(TypedDict, total=False):
    """AG Grid column definition."""

    field: str
    headerName: str
    editable: bool
    hide: bool


US_COUNTRY = "US"
CountrySelection = tuple[frozenset[str], frozenset[str], set[Country]]
US_STATE_FIPS = list(us.states.STATES) + list(us.states.TERRITORIES) + [us.states.DC]
US_STATES = {
    state.fips: state.name for state in sorted(US_STATE_FIPS, key=lambda s: s.name)
}


class ZoneManager:
    """Manages bidirectional sync between Leaflet map circles and AG Grid rows.

    Instead of deleting all circles and recreating them on every change, this
    class performs targeted updates:

    - Map events only update grid rows (circles are already positioned by Leaflet).
    - Grid events only update the affected circle on the map.
    - Selection changes only update circle colors (single batched JS call).
    """

    def __init__(self, leaflet: Leaflet, grid: AgGrid) -> None:
        self._map_id = leaflet.id
        self._grid = grid
        self._grid_id = grid.id
        self._rows: list[ZoneRow] = grid.options["rowData"]
        self._row_to_leaflet: dict[int, int] = {}
        self._leaflet_to_row: dict[int, int] = {}
        self._next_id = 1
        self._flush_timer: object | None = None

    @property
    def rows(self) -> list[ZoneRow]:
        """The zone rows (same list object shared with AG Grid rowData)."""
        return self._rows

    async def init(self) -> None:
        """Cache the draw FeatureGroup reference and fix circle resize bug."""
        await ui.run_javascript(
            f"""
            (() => {{
                const el = getElement('{self._map_id}');
                if (el && el.map) {{
                    el.map._ogdrb_drawGroup = Object.values(el.map._layers).find(
                        l => l instanceof L.FeatureGroup && !l.id
                    ) || null;
                }}

                // Monkey-patch: NiceGUI's minified Leaflet Draw bundle has a bug
                // where L.Edit.Circle._resize uses an undeclared `radius` variable.
                // The minifier converted `var moveLatLng = ..., radius;` into
                // `var e = ...;` — dropping the `radius` declaration.  Since the
                // bundle is loaded as an ES module (strict mode), the bare
                // `radius = ...` throws a ReferenceError, silently breaking
                // circle resize.  Re-define the method with a proper `var`.
                if (L.Edit && L.Edit.Circle) {{
                    L.Edit.Circle.prototype._resize = function (latlng) {{
                        var moveLatLng = this._moveMarker.getLatLng(),
                            radius;
                        if (L.GeometryUtil.isVersion07x()) {{
                            radius = moveLatLng.distanceTo(latlng);
                        }} else {{
                            radius = this._map.distance(moveLatLng, latlng);
                        }}
                        this._shape.setRadius(radius);
                        if (this._map._editTooltip) {{
                            this._map._editTooltip.updateContent({{
                                text: L.drawLocal.edit.handlers.edit.tooltip.subtext
                                    + '<br />'
                                    + L.drawLocal.edit.handlers.edit.tooltip.text,
                                subtext: L.drawLocal.draw.handlers.circle.radius
                                    + ': '
                                    + L.GeometryUtil.readableDistance(
                                        radius, true,
                                        this.options.feet,
                                        this.options.nautic
                                    ),
                            }});
                        }}
                        this._shape.setRadius(radius);
                        this._map.fire(L.Draw.Event.EDITRESIZE, {{
                            layer: this._shape,
                        }});
                    }};
                }}
            }})();
            """,
            timeout=2.0,
        )

    # -- ID management ----------------------------------------------------------

    def _new_id(self) -> int:
        row_id = self._next_id
        self._next_id += 1
        return row_id

    def _register(self, row_id: int, leaflet_id: int) -> None:
        self._row_to_leaflet[row_id] = leaflet_id
        self._leaflet_to_row[leaflet_id] = row_id

    def _unregister(self, row_id: int) -> None:
        leaflet_id = self._row_to_leaflet.pop(row_id, None)
        if leaflet_id is not None:
            self._leaflet_to_row.pop(leaflet_id, None)

    def _find_row(self, row_id: int) -> ZoneRow | None:
        return next((r for r in self._rows if r["id"] == row_id), None)

    def _resolve_row_id(self, layer: dict[str, Any]) -> int | None:
        """Resolve a row ID from a Leaflet layer dict.

        Tries the leaflet_id mapping first, then the ``_ogdrb_row_id`` stamp.
        """
        leaflet_id = layer.get("_leaflet_id")
        if leaflet_id is not None:
            row_id = self._leaflet_to_row.get(int(leaflet_id))
            if row_id is not None:
                return row_id
        ogdrb_id = layer.get("_ogdrb_row_id")
        return int(ogdrb_id) if ogdrb_id is not None else None

    @staticmethod
    def _iter_event_layers(e: GenericEventArguments) -> list[dict[str, Any]]:
        """Extract individual layer dicts from a draw event."""
        layers = e.args.get("layers")
        if layers and "_layers" in layers:
            return list(layers["_layers"].values())
        layer = e.args.get("layer")
        return [layer] if layer else []

    # -- JS bridge (each method = one run_javascript call) ----------------------

    async def _js_add_circle(
        self,
        lat: float,
        lng: float,
        radius_m: float,
        row_id: int,
        color: str = "blue",
    ) -> int | None:
        """Create a circle in the draw FeatureGroup. Returns its leaflet_id."""
        result = cast(
            "str | int | None",
            await ui.run_javascript(
                f"""
            (() => {{
                try {{
                    const mapEl = getElement('{self._map_id}');
                    const group = mapEl && mapEl.map && mapEl.map._ogdrb_drawGroup;
                    if (!group) return null;
                    const c = L.circle([{lat}, {lng}], {{
                        radius: {radius_m}, color: '{color}'
                    }}).addTo(group);
                    c._ogdrb_row_id = {row_id};
                    c.on('click', () => mapEl.$emit('circle-click', {{
                        row_id: {row_id}
                    }}));
                    return L.stamp(c);
                }} catch (e) {{ console.error('_js_add_circle', e); return null; }}
            }})();
            """,
                timeout=2.0,
            ),
        )
        return int(result) if result is not None else None

    async def _js_remove_circles(self, leaflet_ids: list[int]) -> None:
        """Batch-remove circles from the draw FeatureGroup."""
        if not leaflet_ids:
            return
        ids_json = json.dumps(leaflet_ids)
        await ui.run_javascript(
            f"""
            (() => {{
                try {{
                    const el = getElement('{self._map_id}');
                    const group = el && el.map && el.map._ogdrb_drawGroup;
                    if (!group) return;
                    for (const id of {ids_json}) {{
                        const c = group.getLayer(id);
                        if (c) group.removeLayer(c);
                    }}
                }} catch (e) {{ console.error('_js_remove_circles', e); }}
            }})();
            """,
            timeout=2.0,
        )

    async def _js_update_circle(
        self, leaflet_id: int, lat: float, lng: float, radius_m: float
    ) -> None:
        """Move and resize a single circle."""
        await ui.run_javascript(
            f"""
            (() => {{
                try {{
                    const el = getElement('{self._map_id}');
                    const group = el && el.map && el.map._ogdrb_drawGroup;
                    if (!group) return;
                    const c = group.getLayer({leaflet_id});
                    if (c) {{ c.setLatLng([{lat}, {lng}]); c.setRadius({radius_m}); }}
                }} catch (e) {{ console.error('_js_update_circle', e); }}
            }})();
            """,
            timeout=2.0,
        )

    async def _js_set_circle_colors(self, color_map: dict[int, str]) -> None:
        """Batch-update circle colors. ``color_map``: leaflet_id -> color."""
        if not color_map:
            return
        entries_json = json.dumps({str(k): v for k, v in color_map.items()})
        await ui.run_javascript(
            f"""
            (() => {{
                try {{
                    const el = getElement('{self._map_id}');
                    const group = el && el.map && el.map._ogdrb_drawGroup;
                    if (!group) return;
                    const m = {entries_json};
                    for (const [id, color] of Object.entries(m)) {{
                        const c = group.getLayer(Number(id));
                        if (c) c.setStyle({{ color }});
                    }}
                }} catch (e) {{ console.error('_js_set_circle_colors', e); }}
            }})();
            """,
            timeout=2.0,
        )

    async def _js_setup_circle(self, leaflet_id: int, row_id: int) -> None:
        """Stamp a circle with ``_ogdrb_row_id`` and attach a click handler."""
        await ui.run_javascript(
            f"""
            (() => {{
                try {{
                    const mapEl = getElement('{self._map_id}');
                    const group = mapEl && mapEl.map && mapEl.map._ogdrb_drawGroup;
                    if (!group) return;
                    const c = group.getLayer({leaflet_id});
                    if (!c) return;
                    c._ogdrb_row_id = {row_id};
                    c.on('click', () => mapEl.$emit('circle-click', {{
                        row_id: {row_id}
                    }}));
                }} catch (e) {{ console.error('_js_setup_circle', e); }}
            }})();
            """,
            timeout=2.0,
        )

    async def _js_select_grid_row(self, row_id: int) -> None:
        """Select a single row in the AG Grid by its data id."""
        await ui.run_javascript(
            f"""
            (() => {{
                try {{
                    const gridEl = getElement('{self._grid_id}');
                    if (!gridEl || !gridEl.api) return;
                    gridEl.api.deselectAll();
                    gridEl.api.forEachNode(node => {{
                        if (node.data && node.data.id === {row_id}) {{
                            node.setSelected(true);
                            gridEl.api.ensureNodeVisible(node);
                        }}
                    }});
                }} catch (e) {{ console.error('_js_select_grid_row', e); }}
            }})();
            """,
            timeout=2.0,
        )

    # -- Map event handlers -----------------------------------------------------

    async def handle_draw_created(self, e: GenericEventArguments) -> None:
        """Circle drawn on map -> register mapping + add row."""
        layer = e.args.get("layer")
        if not layer:
            return
        leaflet_id = layer.get("_leaflet_id")
        center = layer["_latlng"]
        radius_m = layer["_mRadius"]

        row_id = self._new_id()
        self._rows.append(
            ZoneRow(
                id=row_id,
                name="New Zone",
                lat=center["lat"],
                lng=center["lng"],
                radius=radius_m / 1000,
            )
        )

        if leaflet_id is not None:
            # NiceGUI already added the circle; just register and set up click handler.
            self._register(row_id, int(leaflet_id))
            await self._js_setup_circle(int(leaflet_id), row_id)
        else:
            # Fallback: create the circle programmatically.
            new_lid = await self._js_add_circle(
                center["lat"], center["lng"], radius_m, row_id
            )
            if new_lid is not None:
                self._register(row_id, new_lid)

    async def handle_draw_edited(self, e: GenericEventArguments) -> None:
        """Circles edited on map (edit completed) -> update rows."""
        self._update_rows_from_layers(self._iter_event_layers(e))

    async def handle_draw_edit_move_or_resize(self, e: GenericEventArguments) -> None:
        """Circle being moved/resized (during edit) -> debounced row update."""
        with self._grid.props.suspend_updates():
            self._update_rows_from_layers(self._iter_event_layers(e))
        self._schedule_grid_flush()

    async def handle_draw_deleted(self, e: GenericEventArguments) -> None:
        """Circles deleted on map -> remove rows."""
        for layer in self._iter_event_layers(e):
            row_id = self._resolve_row_id(layer)
            if row_id is None:
                continue
            if row := self._find_row(row_id):
                self._rows.remove(row)
                self._unregister(row_id)

    # -- Grid event handlers ----------------------------------------------------

    async def handle_cell_value_changed(self, e: GenericEventArguments) -> None:
        """Grid cell edited -> update row + sync circle only if geometry changed."""
        data = e.args["data"]
        row_id = int(data["id"])
        old_row = self._find_row(row_id)

        new_row = ZoneRow(
            id=row_id,
            name=str(data["name"]),
            lat=float(data["lat"]),
            lng=float(data["lng"]),
            radius=float(data["radius"]),
        )
        self._rows[:] = [new_row if r["id"] == row_id else r for r in self._rows]

        if old_row is not None:
            geometry_changed = (
                old_row["lat"] != new_row["lat"]
                or old_row["lng"] != new_row["lng"]
                or old_row["radius"] != new_row["radius"]
            )
            leaflet_id = self._row_to_leaflet.get(row_id)
            if geometry_changed and leaflet_id is not None:
                await self._js_update_circle(
                    leaflet_id,
                    new_row["lat"],
                    new_row["lng"],
                    new_row["radius"] * 1000,
                )

    async def handle_circle_click(self, e: GenericEventArguments) -> None:
        """Circle clicked on map -> select the corresponding row in the grid."""
        row_id = e.args.get("row_id")
        if row_id is None:
            return
        await self._js_select_grid_row(int(row_id))

    async def handle_selection_changed(self, _e: GenericEventArguments) -> None:
        """Grid row selection changed -> batch-update circle colors."""
        selected_rows = cast(
            "list[ZoneRow]",
            await self._grid.get_selected_rows(),  # type: ignore[no-untyped-call]
        )
        selected_ids = {r["id"] for r in selected_rows}
        color_map = {
            lid: "red" if rid in selected_ids else "blue"
            for rid, lid in self._row_to_leaflet.items()
        }
        await self._js_set_circle_colors(color_map)

    async def handle_grid_ready(self, _e: GenericEventArguments) -> None:
        """Grid rebuilt -> reset all circle colors (rebuild clears selection)."""
        color_map = dict.fromkeys(self._leaflet_to_row, "blue")
        await self._js_set_circle_colors(color_map)

    # -- Button actions ---------------------------------------------------------

    async def add_zone(self) -> None:
        """Add a new zone from the 'New zone' button."""
        row_id = self._new_id()
        self._rows.append(
            ZoneRow(id=row_id, name="New Zone", lat=0.0, lng=0.0, radius=1.0)
        )
        leaflet_id = await self._js_add_circle(0.0, 0.0, 1000.0, row_id)
        if leaflet_id is not None:
            self._register(row_id, leaflet_id)

    async def delete_selected(self) -> None:
        """Delete selected zones from grid and map."""
        selected_rows = cast(
            "list[ZoneRow]",
            await self._grid.get_selected_rows(),  # type: ignore[no-untyped-call]
        )
        selected_ids = {r["id"] for r in selected_rows}
        leaflet_ids = [
            self._row_to_leaflet[rid]
            for rid in selected_ids
            if rid in self._row_to_leaflet
        ]
        await self._js_remove_circles(leaflet_ids)
        for row_id in selected_ids:
            self._unregister(row_id)
        self._rows[:] = [r for r in self._rows if r["id"] not in selected_ids]

    # -- Private helpers --------------------------------------------------------

    def _update_rows_from_layers(self, layers: list[dict[str, Any]]) -> None:
        for layer in layers:
            row_id = self._resolve_row_id(layer)
            if row_id is None:
                continue
            if row := self._find_row(row_id):
                center = layer["_latlng"]
                row["lat"] = center["lat"]
                row["lng"] = center["lng"]
                row["radius"] = layer["_mRadius"] / 1000

    def _schedule_grid_flush(self, delay: float = 0.2) -> None:
        """Schedule a single grid rebuild after a short delay (for debouncing)."""
        if self._flush_timer is not None:
            return

        def flush() -> None:
            self._grid.update()
            self._flush_timer = None

        self._flush_timer = ui.timer(delay, flush, once=True, immediate=False)


@ui.page("/", response_timeout=20)
async def index() -> None:  # noqa: C901, PLR0915
    repeater_cluster = None

    def selected_filters() -> CountrySelection:
        selected_country_codes = frozenset(select_country.value or ())
        selected_us_states = frozenset(select_us_state.value or ())
        countries = {
            pycountry.countries.lookup(country) for country in selected_country_codes
        }
        return selected_country_codes, selected_us_states, countries

    def validate_filters() -> CountrySelection | None:
        selected_country_codes, selected_us_states, countries = selected_filters()
        if not countries:
            ui.notify("Please select at least one country.", type="warning")
            select_country.props("error")
            return None
        us_selected = US_COUNTRY in selected_country_codes
        if us_selected and not selected_us_states:
            ui.notify("Please select at least one US state.", type="warning")
            select_us_state.props("error")
            return None
        return selected_country_codes, selected_us_states, countries

    async def sync_repeater_markers(repeaters: list[Repeater]) -> None:
        if repeater_cluster is None:
            return
        m.run_layer_method(repeater_cluster.id, "clearLayers")

        chunk_size = 250
        for i in range(0, len(repeaters), chunk_size):
            chunk = repeaters[i : i + chunk_size]
            markers = []
            for repeater in chunk:
                lat = float(repeater.latitude)
                lng = float(repeater.longitude)
                callsign = repeater.callsign or "Unknown"
                city = repeater.location_nearest_city
                state = repeater.state or ""
                country = repeater.country or ""
                frequency = str(repeater.frequency)
                title = f"{callsign} ({frequency} MHz)"
                popup = (
                    f"<b>{callsign}</b><br>"
                    f"{city}, {state}<br>"
                    f"{country}<br>"
                    f"{frequency} MHz"
                )
                marker = (
                    "L.marker(["
                    f"{lat}, {lng}"
                    f"], {{title: {json.dumps(title)}}})"
                    f".bindPopup({json.dumps(popup)})"
                )
                markers.append(marker)
            markers_expr = f"[{', '.join(markers)}]"
            m.run_layer_method(repeater_cluster.id, ":addLayers", markers_expr)

    async def populate_repeaters() -> None:
        filters = validate_filters()
        if not filters:
            return
        _, selected_us_states, countries = filters
        loading.set_visibility(True)
        try:
            repeaters = await prepare_local_repeaters(
                export=ExportQuery(countries=frozenset(countries)),
                us_state_ids=selected_us_states,
            )
            await sync_repeater_markers(repeaters)
        except ValueError as e:
            ui.notify(f"Error: {e}", type="negative")
            return
        finally:
            loading.set_visibility(False)
        ui.notify(f"Loaded {len(repeaters)} repeaters.", type="positive")

    async def export() -> None:
        filters = validate_filters()
        if not filters:
            return
        _, selected_us_states, countries = filters
        zone_rows = zm.rows
        if not zone_rows:
            ui.notify("Please add at least one zone.", type="warning")
            return
        if len(zone_rows) != len({row["name"] for row in zone_rows}):
            ui.notify("Duplicate zone names found.", type="warning")
            return

        loading.set_visibility(True)
        try:
            repeaters_by_zone = await get_repeaters(
                export=ExportQuery(countries=frozenset(countries)),
                zones={
                    row["name"]: Radius(
                        origin=LatLon(row["lat"], row["lng"]),
                        distance=row["radius"],
                        unit=Unit.KILOMETERS,
                    )
                    for row in zone_rows
                },
                us_state_ids=selected_us_states,
            )
            codeplug = organize(repeaters_by_zone)
        except ValueError as e:
            ui.notify(f"Error: {e}", type="negative")
            return
        finally:
            loading.set_visibility(False)
        csvs = codeplug_to_csvs(codeplug)
        zip_file = csvs_to_zip(csvs)
        ui.download.content(
            content=zip_file,
            filename="ogdrb.zip",
            media_type="application/zip",
        )

    #' with ui.left_drawer() as drawer:
    #'     pass

    with ui.header():
        #' ui.button(icon="menu", on_click=drawer.toggle)
        ui.label("OGDRB").classes("text-2xl")
        select_country = ui.select(
            label="Select countries",
            with_input=True,
            multiple=True,
            clearable=True,
            options={country.alpha_2: country.name for country in pycountry.countries},
        ).classes("w-1/3")
        select_us_state = ui.select(
            label="Select US states",
            with_input=True,
            multiple=True,
            clearable=True,
            options=US_STATES,
        ).classes("w-1/3")
        select_us_state.set_visibility(False)

        def sync_us_states_visibility() -> None:
            us_selected = US_COUNTRY in set(select_country.value or ())
            select_us_state.set_visibility(us_selected)
            if not us_selected:
                select_us_state.set_value([])

        select_country.on_value_change(lambda _: sync_us_states_visibility())

        ui.button("Load Repeaters", on_click=populate_repeaters).props(
            "icon=cloud_download"
        )
        ui.button("Export", on_click=export).props("icon=save")
        loading = ui.spinner("dots", size="lg", color="red")
        loading.set_visibility(False)

    with ui.footer():
        ui.html(
            f"<a href='{ExternalURLs.GITHUB}' target='_blank'>"
            "OGDRB by MicaelJarniac</a>",
            sanitize=False,
        ).classes("text-sm")
        ui.html(
            "This app is not affiliated "
            f"with <a href='{ExternalURLs.OPENGD77}' target='_blank'>OpenGD77</a> "
            f"or <a href='{ExternalURLs.REPEATERBOOK}' target='_blank'>"
            "RepeaterBook</a>.",
            sanitize=False,
        )
        ui.html(
            "All repeater data is from "
            f"<a href='{ExternalURLs.REPEATERBOOK}' target='_blank'>RepeaterBook</a>, "
            "using their "
            f"<a href='{ExternalURLs.REPEATERBOOK_API}' target='_blank'>"
            "public API</a>.",
            sanitize=False,
        )

    with ui.dialog() as dialog_help, ui.card():
        ui.markdown(f"""
                    # OGDRB
                    This app allows you to import repeaters from [RepeaterBook][rb] to
                    your [OpenGD77][ogd] radio.
                    You can add zones by drawing circles on the map, and then export the
                    codeplug as CSV files that can be imported into the OpenGD77
                    codeplug editor.

                    ## How to use
                    1. Select the countries you want to include in your codeplug.
                    If you select United States, also choose one or more states.
                    2. Click "Load Repeaters" to cache repeaters and display markers.
                    3. Draw circles on the map to define the zones you want to include
                    (or manually add to the list below).
                    4. Click the "Export" button to download the codeplug as a ZIP file.
                    5. Import the extracted folder into the OpenGD77 codeplug editor.
                    6. Upload the codeplug to your OpenGD77 radio.

                    ## Notes
                    - The circles you draw on the map define the zones for your
                    codeplug.
                    - You can edit the name, latitude, longitude, and radius of each
                    zone in the table by double-clicking on the cells.
                    - You can delete zones by selecting them in the table and clicking
                    the "Delete" button.
                    - You can add new zones by clicking the "New zone" button.
                    - You can select multiple zones by holding down the Ctrl key while
                    clicking on them.

                    ## Limits
                    Going beyond these limits may truncate the data, or result in
                    errors.
                    | Field               | Limit                    |
                    |---------------------|--------------------------|
                    | Zones               | {Max.ZONES}              |
                    | Channels            | {Max.CHANNELS}           |
                    | Channels Per Zone   | {Max.CHANNELS_PER_ZONE}  |
                    | Zone Name Length    | {Max.CHARS_ZONE_NAME}    |
                    | Channel Name Length | {Max.CHARS_CHANNEL_NAME} |

                    ## RepeaterBook
                    This app uses the [RepeaterBook API][rb_api] to fetch repeater data.
                    The API is free to use, but please consider donating or
                    [subscribing][rb_plus] to [RepeaterBook][rb] to support their work.

                    [rb]: {ExternalURLs.REPEATERBOOK}
                    [rb_api]: {ExternalURLs.REPEATERBOOK_API}
                    [rb_plus]: {ExternalURLs.REPEATERBOOK_PLUS}
                    [ogd]: {ExternalURLs.OPENGD77}
                    """)
        ui.button("Close", on_click=dialog_help.close)

    # Leaflet map with circle-only draw toolbar
    m = ui.leaflet(
        center=(0.0, 0.0),
        zoom=2,
        draw_control={
            "draw": {
                "circle": True,
                # disable all other shapes
                "marker": False,
                "polygon": False,
                "polyline": False,
                "rectangle": False,
                "circlemarker": False,
            },
            "edit": {"edit": True, "remove": True},
        },
        additional_resources=[
            "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css",
            "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css",
            "https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js",
        ],
    ).classes("w-full h-96")
    repeater_cluster = m.generic_layer(
        name="markerClusterGroup",
        args=[
            {
                "chunkedLoading": True,
                "showCoverageOnHover": False,
                "maxClusterRadius": 60,
            }
        ],
    )

    columns = [
        AGColumnDef(field="name", headerName="Name", editable=True),
        AGColumnDef(field="lat", headerName="Latitude", editable=True),
        AGColumnDef(field="lng", headerName="Longitude", editable=True),
        AGColumnDef(field="radius", headerName="Radius (km)", editable=True),
        AGColumnDef(field="id", headerName="ID", hide=True),
    ]

    aggrid = ui.aggrid(
        {
            "defaultColDef": {
                "sortable": False,
            },
            "columnDefs": columns,
            "rowData": [],
            "rowSelection": {"mode": "multiRow"},
            "stopEditingWhenCellsLoseFocus": True,
        },
        theme="balham",
    )

    zm = ZoneManager(m, aggrid)

    m.on("draw:created", zm.handle_draw_created)
    m.on("draw:edited", zm.handle_draw_edited)
    m.on("draw:editmove", zm.handle_draw_edit_move_or_resize)
    m.on("draw:editresize", zm.handle_draw_edit_move_or_resize)
    m.on("draw:deleted", zm.handle_draw_deleted)
    m.on("circle-click", zm.handle_circle_click)
    aggrid.on("cellValueChanged", zm.handle_cell_value_changed)
    aggrid.on("rowSelected", zm.handle_selection_changed)
    aggrid.on("gridReady", zm.handle_grid_ready)

    with ui.row():
        ui.button("New zone", on_click=zm.add_zone).props(
            "icon=add color=green",
        )
        ui.button("Delete selected zones", on_click=zm.delete_selected).props(
            "icon=delete color=red",
        )

    with ui.page_sticky(position="bottom-right", x_offset=20, y_offset=20):
        ui.button(on_click=dialog_help.open, icon="contact_support").props("fab")

    await m.initialized()
    await zm.init()


if __name__ in {"__main__", "__mp_main__"}:
    settings = Settings()
    ui.run(
        title="OGDRB",
        favicon="📡",
        storage_secret=settings.storage_secret,
        dark=True,
        on_air=settings.on_air_token,
        reconnect_timeout=20,
        reload="FLY_ALLOC_ID" not in os.environ,
    )
