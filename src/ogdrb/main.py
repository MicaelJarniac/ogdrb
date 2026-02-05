"""ogdrb."""

from __future__ import annotations

__all__: tuple[str, ...] = ()

import json
import os
from enum import StrEnum
from typing import TYPE_CHECKING, TypedDict, cast

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


@ui.page("/", response_timeout=20)
async def index() -> None:  # noqa: C901, PLR0915
    rows: list[ZoneRow] = []
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
        if not rows:
            ui.notify("Please add at least one zone.", type="warning")
            return
        if len(rows) != len({row["name"] for row in rows}):
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
                    for row in rows
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
            "OGDRB by MicaelJarniac</a>"
        ).classes("text-sm")
        ui.html(
            "This app is not affiliated "
            f"with <a href='{ExternalURLs.OPENGD77}' target='_blank'>OpenGD77</a> "
            f"or <a href='{ExternalURLs.REPEATERBOOK}' target='_blank'>"
            "RepeaterBook</a>."
        )
        ui.html(
            "All repeater data is from "
            f"<a href='{ExternalURLs.REPEATERBOOK}' target='_blank'>RepeaterBook</a>, "
            "using their "
            f"<a href='{ExternalURLs.REPEATERBOOK_API}' target='_blank'>"
            "public API</a>."
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

    async def add_circle(
        lat: float,
        lng: float,
        radius: float,
        row_id: int,
        *,
        selected: bool = False,
    ) -> int:
        # https://github.com/zauberzeug/nicegui/discussions/4644
        return cast(
            "int",
            await ui.run_javascript(
                f"""
            try {{
                const out = [];
                const el = getElement('{m.id}');
                const map = el ? el.map : null;
                if (!map) {{
                    return null;
                }}
                const drawGroup = Object.values(map._layers).find(
                    layer => layer instanceof L.FeatureGroup && !layer.id
                );
                if (!drawGroup) {{
                    return null;
                }}
                const myCircle = L.circle(
                    [{lat}, {lng}],
                    {{
                        radius: {radius},
                        color: '{"red" if selected else "blue"}',
                    }}
                ).addTo(drawGroup);
                myCircle._ogdrb_row_id = {row_id};
                out.push(myCircle);
                return out.length ? L.stamp(out[0]) : null;
            }} catch (err) {{
                console.error(err);
                return null;
            }}
            """,
                timeout=1.0,
            ),
        )

    async def delete_all_circles() -> None:
        await ui.run_javascript(
            f"""
            try {{
                const el = getElement('{m.id}');
                const map = el ? el.map : null;
                if (!map) {{
                    return null;
                }}
                const drawGroup = Object.values(map._layers).find(
                    layer => layer instanceof L.FeatureGroup && !layer.id
                );
                if (!drawGroup) {{
                    return null;
                }}
                drawGroup.clearLayers();
                return true;
            }} catch (err) {{
                console.error(err);
                return null;
            }}
            """,
            timeout=1.0,
        )

    circles_to_zones: dict[int, int] = {}

    async def get_selected_rows() -> list[ZoneRow]:
        return cast("list[ZoneRow]", await aggrid.get_selected_rows())  # type: ignore[no-untyped-call]

    def has_client_connection() -> bool:
        client = ui.context.client
        return bool(client and client.has_socket_connection)

    async def get_selected_ids() -> set[int]:
        selected_rows = await get_selected_rows()
        return {row["id"] for row in selected_rows}

    async def sync_circles() -> None:
        if not has_client_connection():
            return
        try:
            await delete_all_circles()
        except TimeoutError:
            return
        circles_to_zones.clear()
        selected_ids = await get_selected_ids()
        for row in rows:
            try:
                circle_id = await add_circle(
                    lat=row["lat"],
                    lng=row["lng"],
                    radius=row["radius"] * 1000,  # convert km to m
                    row_id=row["id"],
                    selected=row["id"] in selected_ids,
                )
            except TimeoutError:
                return
            if circle_id is not None:
                circles_to_zones[circle_id] = row["id"]

    async def draw_created(e: GenericEventArguments) -> None:
        layer = e.args.get("layer")
        if not layer:
            return
        center = layer["_latlng"]
        radius = layer["_mRadius"]
        rows.append(
            ZoneRow(
                id=new_id(),
                name="New Zone",
                lat=center["lat"],
                lng=center["lng"],
                radius=radius / 1000,  # convert m to km
            )
        )
        aggrid.update()
        await sync_circles()

    async def draw_edited(e: GenericEventArguments) -> None:
        layers = e.args.get("layers")
        if not layers:
            return
        for layer in layers["_layers"].values():
            row_id = circles_to_zones.get(layer["_leaflet_id"]) or layer.get(
                "_ogdrb_row_id"
            )
            if not row_id:
                ui.notify(f"Circle with ID {layer['_leaflet_id']} not found")
                continue
            row = next((row for row in rows if row["id"] == row_id), None)
            if row:
                center = layer["_latlng"]
                radius = layer["_mRadius"]
                row["lat"] = center["lat"]
                row["lng"] = center["lng"]
                row["radius"] = radius / 1000
                aggrid.update()
                await sync_circles()

    async def draw_deleted(e: GenericEventArguments) -> None:
        layers = e.args.get("layers")
        if not layers:
            return
        for layer in layers["_layers"].values():
            row_id = circles_to_zones.get(layer["_leaflet_id"]) or layer.get(
                "_ogdrb_row_id"
            )
            if not row_id:
                ui.notify(f"Circle with ID {layer['_leaflet_id']} not found")
                continue
            row = next((row for row in rows if row["id"] == row_id), None)
            if row:
                rows.remove(row)
                aggrid.update()
                await sync_circles()

    m.on("draw:created", draw_created)
    m.on("draw:edited", draw_edited)
    m.on("draw:deleted", draw_deleted)

    def new_id() -> int:
        """Get the next row ID."""
        return max((row["id"] for row in rows), default=0) + 1

    async def add_row() -> None:
        rows.append(ZoneRow(id=new_id(), name="New Zone", lat=0.0, lng=0.0, radius=1.0))
        aggrid.update()
        await sync_circles()

    async def handle_cell_value_change(e: GenericEventArguments) -> None:
        new_row: ZoneRow = e.args["data"]
        rows[:] = [row | new_row if row["id"] == new_row["id"] else row for row in rows]
        aggrid.update()
        await sync_circles()

    async def delete_selected() -> None:
        selected_ids = await get_selected_ids()
        rows[:] = [row for row in rows if row["id"] not in selected_ids]
        aggrid.update()
        await sync_circles()

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
            "rowData": rows,
            "rowSelection": "multiple",
            "stopEditingWhenCellsLoseFocus": True,
        },
        theme="balham-dark",
    )
    aggrid.on("cellValueChanged", handle_cell_value_change)
    aggrid.on("rowSelected", sync_circles)

    with ui.row():
        ui.button("New zone", on_click=add_row).props(
            "icon=add color=green",
        )
        ui.button("Delete selected zones", on_click=delete_selected).props(
            "icon=delete color=red",
        )

    with ui.page_sticky(position="bottom-right", x_offset=20, y_offset=20):
        ui.button(on_click=dialog_help.open, icon="contact_support").props("fab")

    await m.initialized(timeout=20)


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
