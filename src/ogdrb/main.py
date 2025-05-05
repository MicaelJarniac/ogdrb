"""ogdrb."""

from __future__ import annotations

__all__: tuple[str, ...] = ()

from nicegui import ui


@ui.page("/")
async def index() -> None:
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

    # programmatic circle
    # https://github.com/zauberzeug/nicegui/discussions/4644
    async def add_circle() -> None:
        id_ = await ui.run_javascript(
            f"""
            const out = [];
            const map = getElement('{m.id}').map;
            map.eachLayer(layer => {{
                if (layer instanceof L.FeatureGroup) {{
                    const myCircle = L.circle(
                        [51.49, -0.095], {{ radius: 200 }}
                    ).addTo(layer);
                    out.push(myCircle);
                }}
            }});
            return L.stamp(out[0]);
            """,
            timeout=1.0,
        )
        ui.notify(f"Programmatic circle added (id: {id_})")

    async def list_circles() -> None:
        circles = await ui.run_javascript(
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

    ui.button("Add circle", on_click=add_circle)
    ui.button("List all circles", on_click=list_circles)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="ogdrb")
