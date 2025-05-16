"""ogdrb."""

from __future__ import annotations

__all__: tuple[str, ...] = ()

from typing import TYPE_CHECKING, TypedDict

import pycountry
from haversine import Unit  # type: ignore[import-untyped]
from nicegui import ui
from opengd77.constants import Max
from opengd77.converters import codeplug_to_csvs, csvs_to_zip
from pydantic_settings import BaseSettings, SettingsConfigDict
from repeaterbook.models import ExportQuery
from repeaterbook.utils import LatLon, Radius

from ogdrb.organizer import organize
from ogdrb.services import get_repeaters

if TYPE_CHECKING:  # pragma: no cover
    from nicegui.events import GenericEventArguments


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


@ui.page("/")
async def index() -> None:  # noqa: C901, PLR0915
    rows: list[ZoneRow] = []

    async def export() -> None:
        countries = {
            pycountry.countries.lookup(country) for country in select_country.value
        }
        if not countries:
            ui.notify("Please select at least one country.", type="warning")
            select_country.props("error")
            return
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
        ui.button("Export", on_click=export).props("icon=save")
        loading = ui.spinner("dots", size="lg", color="red")
        loading.set_visibility(False)

    with ui.footer():
        ui.html(
            "<a href='https://github.com/MicaelJarniac/ogdrb' target='_blank'>"
            "OGDRB by MicaelJarniac</a>"
        ).classes("text-sm")
        ui.html(
            "This app is not affiliated "
            "with <a href='https://opengd77.com/' target='_blank'>OpenGD77</a> "
            "or <a href='https://repeaterbook.com/' target='_blank'>RepeaterBook</a>."
        )

    with ui.dialog() as dialog, ui.card():
        ui.markdown(f"""
                    # OGDRB
                    This app allows you to import repeaters from RepeaterBook to your
                    OpenGD77 radio.
                    You can add zones by drawing circles on the map, and then export the
                    codeplug as CSV files that can be imported into the OpenGD77
                    codeplug editor.

                    ## How to use
                    1. Select the countries you want to include in your codeplug.
                    2. Draw circles on the map to define the zones you want to include
                    (or manually add to the list below).
                    3. Click the "Export" button to download the codeplug as a ZIP file.
                    4. Import the extracted folder into the OpenGD77 codeplug editor.
                    5. Upload the codeplug to your OpenGD77 radio.

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
                    """)
        ui.button("Close", on_click=dialog.close)

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
        ui.button(on_click=dialog.open, icon="contact_support").props("fab")

    await m.initialized()
    await sync_circles()


if __name__ in {"__main__", "__mp_main__"}:
    settings = Settings()
    ui.run(
        title="OGDRB",
        favicon="📡",
        storage_secret=settings.storage_secret,
        dark=True,
        on_air=settings.on_air_token,
    )
