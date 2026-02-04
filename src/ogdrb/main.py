"""ogdrb."""

from __future__ import annotations

__all__: tuple[str, ...] = ()

import json
import os
from enum import StrEnum
from typing import TYPE_CHECKING, TypedDict

import pycountry
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


US_COUNTRY = "US"
CountrySelection = tuple[frozenset[str], frozenset[str], set[Country]]
US_STATE_FIPS = {
    "01": "Alabama",
    "02": "Alaska",
    "04": "Arizona",
    "05": "Arkansas",
    "06": "California",
    "08": "Colorado",
    "09": "Connecticut",
    "10": "Delaware",
    "11": "District of Columbia",
    "12": "Florida",
    "13": "Georgia",
    "15": "Hawaii",
    "16": "Idaho",
    "17": "Illinois",
    "18": "Indiana",
    "19": "Iowa",
    "20": "Kansas",
    "21": "Kentucky",
    "22": "Louisiana",
    "23": "Maine",
    "24": "Maryland",
    "25": "Massachusetts",
    "26": "Michigan",
    "27": "Minnesota",
    "28": "Mississippi",
    "29": "Missouri",
    "30": "Montana",
    "31": "Nebraska",
    "32": "Nevada",
    "33": "New Hampshire",
    "34": "New Jersey",
    "35": "New Mexico",
    "36": "New York",
    "37": "North Carolina",
    "38": "North Dakota",
    "39": "Ohio",
    "40": "Oklahoma",
    "41": "Oregon",
    "42": "Pennsylvania",
    "44": "Rhode Island",
    "45": "South Carolina",
    "46": "South Dakota",
    "47": "Tennessee",
    "48": "Texas",
    "49": "Utah",
    "50": "Vermont",
    "51": "Virginia",
    "53": "Washington",
    "54": "West Virginia",
    "55": "Wisconsin",
    "56": "Wyoming",
    "60": "American Samoa",
    "66": "Guam",
    "69": "Northern Mariana Islands",
    "72": "Puerto Rico",
    "78": "U.S. Virgin Islands",
}
US_STATES = dict(sorted(US_STATE_FIPS.items(), key=lambda item: item[1]))


def register_map_cluster_assets() -> None:
    """Register Leaflet marker cluster assets."""
    ui.add_head_html(
        """
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css"
        />
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css"
        />
        <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
        """
    )


@ui.page("/", response_timeout=20)
async def index() -> None:  # noqa: C901, PLR0915
    register_map_cluster_assets()
    rows: list[ZoneRow] = []

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
        marker_data = [
            {
                "lat": float(repeater.latitude),
                "lng": float(repeater.longitude),
                "callsign": repeater.callsign or "Unknown",
                "city": repeater.location_nearest_city,
                "state": repeater.state or "",
                "country": repeater.country or "",
                "frequency": str(repeater.frequency),
            }
            for repeater in repeaters
        ]
        clustering_enabled = await ui.run_javascript(
            f"""
            return await (async () => {{
                const ensureCluster = async () => {{
                    if (window.L && window.L.markerClusterGroup) {{
                        return true;
                    }}
                    const loadScript = (src) => new Promise((resolve, reject) => {{
                        const script = document.createElement('script');
                        script.src = src;
                        script.async = true;
                        script.onload = () => resolve(true);
                        script.onerror = () =>
                            reject(new Error('Failed to load ' + src));
                        document.head.appendChild(script);
                    }});
                    const loadStyle = (href) => {{
                        if ([...document.styleSheets].some((s) => s.href === href)) {{
                            return;
                        }}
                        const link = document.createElement('link');
                        link.rel = 'stylesheet';
                        link.href = href;
                        document.head.appendChild(link);
                    }};
                    loadStyle('https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css');
                    loadStyle('https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css');
                    try {{
                        await loadScript('https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js');
                    }} catch {{
                        return false;
                    }}
                    return !!(window.L && window.L.markerClusterGroup);
                }};

                const map = getElement('{m.id}').map;
                if (map.__ogdrbRepeaterLayer) {{
                    map.removeLayer(map.__ogdrbRepeaterLayer);
                }}

                const clusteringEnabled = await ensureCluster();
                const repeaterLayer = clusteringEnabled
                    ? L.markerClusterGroup({{
                        chunkedLoading: true,
                        showCoverageOnHover: false,
                        maxClusterRadius: 60,
                    }})
                    : L.layerGroup();
                repeaterLayer.addTo(map);
                const repeaters = {json.dumps(marker_data)};

                const CHUNK_SIZE = 300;
                const addChunk = (index) => {{
                    const end = Math.min(index + CHUNK_SIZE, repeaters.length);
                    for (let i = index; i < end; i++) {{
                        const repeater = repeaters[i];
                        const title = `${{repeater.callsign}} ` +
                            `(${{repeater.frequency}} MHz)`;
                        const marker = L.marker([repeater.lat, repeater.lng], {{
                            title: title,
                        }});
                        marker.bindPopup(
                            `<b>${{repeater.callsign}}</b><br>` +
                            `${{repeater.city}}, ${{repeater.state}}<br>` +
                            `${{repeater.country}}<br>` +
                            `${{repeater.frequency}} MHz`
                        );
                        repeaterLayer.addLayer(marker);
                    }}
                    if (end < repeaters.length) {{
                        requestAnimationFrame(() => addChunk(end));
                    }}
                }};

                if (repeaters.length > 0) {{
                    requestAnimationFrame(() => addChunk(0));
                }}
                map.__ogdrbRepeaterLayer = repeaterLayer;
                return clusteringEnabled;
            }})();
            """,
            timeout=2.0,
        )
        if not clustering_enabled:
            ui.notify(
                "Marker clustering unavailable; falling back to plain markers.",
                type="warning",
            )

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
    ).classes("w-full h-96")

    async def add_circle(
        lat: float, lng: float, radius: float, *, selected: bool = False
    ) -> int:
        # https://github.com/zauberzeug/nicegui/discussions/4644
        id_: int = await ui.run_javascript(
            f"""
            const out = [];
            const map = getElement('{m.id}').map;
            map.eachLayer(layer => {{
                if (layer instanceof L.FeatureGroup) {{
                    const myCircle = L.circle(
                        [{lat}, {lng}],
                        {{
                            radius: {radius},
                            color: '{"red" if selected else "blue"}',
                        }}
                    ).addTo(layer);
                    out.push(myCircle);
                }}
            }});
            return L.stamp(out[0]);
            """,
            timeout=1.0,
        )
        return id_

    async def delete_all_circles() -> None:
        await ui.run_javascript(
            f"""
            getElement('{m.id}').map.eachLayer(layer => {{
                if (layer instanceof L.Circle) {{
                    layer.remove();
                }}
            }});
            return;
            """,
            timeout=1.0,
        )

    circles_to_zones: dict[int, int] = {}

    async def sync_circles() -> None:
        await delete_all_circles()
        circles_to_zones.clear()
        selected_ids = [row["id"] for row in await aggrid.get_selected_rows()]
        for row in rows:
            circles_to_zones[
                await add_circle(
                    lat=row["lat"],
                    lng=row["lng"],
                    radius=row["radius"] * 1000,  # convert km to m
                    selected=row["id"] in selected_ids,
                )
            ] = row["id"]

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
            row_id = circles_to_zones.get(layer["_leaflet_id"])
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
            row_id = circles_to_zones.get(layer["_leaflet_id"])
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
        selected_names = [row["id"] for row in await aggrid.get_selected_rows()]
        rows[:] = [row for row in rows if row["id"] not in selected_names]
        aggrid.update()
        await sync_circles()

    columns = [
        {"field": "name", "headerName": "Name", "editable": True},
        {"field": "lat", "headerName": "Latitude", "editable": True},
        {"field": "lng", "headerName": "Longitude", "editable": True},
        {"field": "radius", "headerName": "Radius (km)", "editable": True},
        {"field": "id", "headerName": "ID", "hide": True},
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
    await sync_circles()


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
