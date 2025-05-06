"""ogdrb."""

from __future__ import annotations

__all__: tuple[str, ...] = ()

from typing import TYPE_CHECKING, TypedDict

from nicegui import ui

if TYPE_CHECKING:  # pragma: no cover
    from nicegui.events import GenericEventArguments


class Circle(TypedDict):
    """Circle class for Leaflet map."""

    id: int
    lat: float
    lng: float
    radius: float


class ZoneRow(TypedDict):
    """ZoneRow class for AG Grid."""

    id: int
    name: str
    lat: float
    lng: float
    radius: float


@ui.page("/")
async def index() -> None:
    rows: list[ZoneRow] = []

    circles_to_zones: dict[int, int] = {}

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

    async def sync_circles() -> None:
        """Sync circles with the map."""
        await delete_all_circles()
        circles_to_zones.clear()
        selected = await aggrid.get_selected_rows()
        selected_ids = [row["id"] for row in selected]
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
                ui.notify(row)
                center = layer["_latlng"]
                radius = layer["_mRadius"]
                ui.notify(radius)
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
        ui.notify("Added row")
        aggrid.update()
        await sync_circles()

    async def handle_cell_value_change(e: GenericEventArguments) -> None:
        new_row: ZoneRow = e.args["data"]
        ui.notify(f"Updated row to: {e.args['data']}")
        rows[:] = [row | new_row if row["id"] == new_row["id"] else row for row in rows]
        aggrid.update()
        await sync_circles()

    async def delete_selected() -> None:
        selected_names = [row["id"] for row in await aggrid.get_selected_rows()]
        rows[:] = [row for row in rows if row["id"] not in selected_names]
        ui.notify(f"Deleted row with ID {selected_names}")
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

    ui.button("Delete selected zones", on_click=delete_selected)
    ui.button("New zone", on_click=add_row)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="ogdrb", storage_secret="ogdrb", dark=True)  # noqa: S106
