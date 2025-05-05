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
    """ZoneRow class for AgGrid."""

    id: int
    name: str
    lat: float
    lng: float
    radius: float


@ui.page("/")
async def index() -> None:
    rows: list[ZoneRow] = []

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

    # Programmatic circle
    # https://github.com/zauberzeug/nicegui/discussions/4644
    async def add_circle(lat: float, lng: float, radius: float) -> None:
        id_ = await ui.run_javascript(
            f"""
            const out = [];
            const map = getElement('{m.id}').map;
            map.eachLayer(layer => {{
                if (layer instanceof L.FeatureGroup) {{
                    const myCircle = L.circle(
                        [{lat}, {lng}], {{ radius: {radius} }}
                    ).addTo(layer);
                    out.push(myCircle);
                }}
            }});
            return L.stamp(out[0]);
            """,
            timeout=1.0,
        )
        ui.notify(f"Programmatic circle added (id: {id_})")

    async def list_circles() -> list[Circle]:
        circles: list[Circle] = await ui.run_javascript(
            f"""
            const out = [];
            getElement('{m.id}').map.eachLayer(layer => {{
                if (layer instanceof L.Circle) {{
                    const c = layer.getLatLng();
                    out.push({{
                        id: L.stamp(layer),
                        lat: c.lat,
                        lng: c.lng,
                        radius: layer.getRadius()
                    }});
                }}
            }});
            return out;
            """,
            timeout=1.0,
        )
        ui.notify(f"All circles: {circles}")
        return circles

    columns = [
        {"field": "name", "headerName": "Name", "editable": True},
        {"field": "lat", "headerName": "Latitude", "editable": True},
        {"field": "lng", "headerName": "Longitude", "editable": True},
        {"field": "radius", "headerName": "Radius", "editable": True},
        {"field": "id", "headerName": "ID"},
    ]

    def add_row() -> None:
        new_id = max((dx["id"] for dx in rows), default=-1) + 1
        rows.append(ZoneRow(id=new_id, name="New zone", lat=0.0, lng=0.0, radius=0.0))
        ui.notify(f"Added row with ID {new_id}")
        aggrid.update()

    def handle_cell_value_change(e: GenericEventArguments) -> None:
        new_row: ZoneRow = e.args["data"]
        ui.notify(f"Updated row to: {e.args['data']}")
        rows[:] = [row | new_row if row["id"] == new_row["id"] else row for row in rows]

    async def delete_selected() -> None:
        selected_id = [row["id"] for row in await aggrid.get_selected_rows()]
        rows[:] = [row for row in rows if row["id"] not in selected_id]
        ui.notify(f"Deleted row with ID {selected_id}")
        aggrid.update()

    aggrid = ui.aggrid(
        {
            "columnDefs": columns,
            "rowData": rows,
            "rowSelection": "multiple",
            "stopEditingWhenCellsLoseFocus": True,
        }
    ).on("cellValueChanged", handle_cell_value_change)

    ui.button("Delete selected zones", on_click=delete_selected)
    ui.button("New zone", on_click=add_row)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="ogdrb")
