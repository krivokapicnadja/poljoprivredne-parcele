"""
Deo 2 – Map Viewer: Interaktivna mapa sa uključivanjem/isključivanjem slojeva,
promenom simbologije (stil, boje), raster podlogom i vektorskim podacima.
"""

import os
import folium
from folium import LayerControl, FeatureGroup, TileLayer
import geopandas as gpd
from branca.colormap import LinearColormap
from src.config import DATA_DIR, CRS_WGS84, SREM_CENTER


def create_interactive_map(
    slojevi=None,
    overlay_rezultati=None,
    ml_vektor=None,
    raster_path=None,
    output_file="data/interactive_map.html",
):
    """
    Kreira interaktivnu mapu sa:
    - Raster podlogom (NDVI)
    - Vektorskim slojevima sa mogućnošću uključivanja/isključivanja
    - Prilagođenom simbologijom (boje, ikone, debljine)
    - ML detektovanim objektima kao poseban sloj
    """

    # Centar mape: Srem
    m = folium.Map(location=SREM_CENTER, zoom_start=10, tiles="CartoDB positron")

    # ==== RASTER PODLOGA (NDVI) ====
    if raster_path and os.path.exists(raster_path):
        try:
            import rasterio
            import numpy as np
            from rasterio.warp import transform_bounds

            with rasterio.open(raster_path) as src:
                bounds = transform_bounds(src.crs, CRS_WGS84, *src.bounds)
                ndvi = src.read(1)
                # Normalizuj za prikaz
                ndvi_normalized = np.clip(ndvi, 0, 1)

                # Kreiraj overlay sliku kao PNG
                from io import BytesIO
                import base64
                from matplotlib import cm

                # Jednostavan prikaz bez PIL (koristi folium image overlay sa colormap)
                ndvi_overlay = folium.raster_layers.ImageOverlay(
                    image=ndvi_normalized,
                    bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
                    colormap=lambda x: (0, int(x * 255), 0, 1),
                    name="NDVI Raster",
                    overlay=True,
                    control=True,
                )
                ndvi_overlay.add_to(m)
                print("[OK] NDVI raster dodat na mapu.")
        except Exception as e:
            print(f"[WARN] Raster nije učitan: {e}. Koristi se samo vektorska podloga.")

    # ==== VEKTORSKI SLOJEVI ====
    if slojevi:
        # Paleta boja za slojeve
        sloj_styles = {
            "landuse": {
                "color": "#228B22",  # Tamno zelena
                "fillOpacity": 0.4,
                "weight": 1,
                "name": "Poljoprivredne površine (Landuse)",
            },
            "buildings": {
                "color": "#FF4500",  # Crvena
                "icon": "home",
                "prefix": "fa",
                "name": "Objekti (Buildings)",
            },
            "roads": {
                "color": "#FFD700",  # Zlatna
                "weight": 3,
                "name": "Putevi (Roads)",
            },
            "waterways": {
                "color": "#1E90FF",  # Plava
                "weight": 3,
                "name": "Vodotokovi (Waterways)",
            },
            "natural": {
                "color": "#32CD32",  # Svetlo zelena
                "fillOpacity": 0.3,
                "weight": 1,
                "name": "Prirodne oblasti (Natural)",
            },
        }

        for naziv, gdf in slojevi.items():
            style = sloj_styles.get(
                naziv, {"color": "#888", "weight": 2, "name": naziv}
            )

            fg = FeatureGroup(name=style.get("name", naziv), show=True)

            if naziv in ("landuse", "natural"):
                # Poligonski sloj
                folium.GeoJson(
                    gdf.to_json(),
                    style_function=lambda feature, s=style: {
                        "color": s["color"],
                        "fillColor": s["color"],
                        "fillOpacity": s.get("fillOpacity", 0.3),
                        "weight": s.get("weight", 1),
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=["name", "type"] if "name" in gdf.columns else ["type"],
                    ),
                ).add_to(fg)

            elif naziv in ("roads", "waterways"):
                # Linijski sloj
                folium.GeoJson(
                    gdf.to_json(),
                    style_function=lambda feature, s=style: {
                        "color": s["color"],
                        "weight": s.get("weight", 2),
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=["name"] if "name" in gdf.columns else None,
                    ),
                ).add_to(fg)

            elif naziv == "buildings":
                # Tačkasti sloj
                for _, row in gdf.iterrows():
                    color_map = {
                        "#FF0000": "red",
                        "#3388FF": "blue",
                        "#FF8C00": "orange",
                        "#228B22": "darkgreen",
                        "#800080": "purple",
                        "#A52A2A": "darkred",
                        "#006400": "darkgreen",
                        "#0066CC": "darkblue",
                        "#FFD700": "orange",
                        "#808080": "gray",
                    }
                    raw_color = style.get("color", "red")
                    icon_color = color_map.get(raw_color, "red")
                    folium.Marker(
                        location=[row.geometry.y, row.geometry.x],
                        popup=f"{row.get('name', '')} ({row.get('type', '')})",
                        icon=folium.Icon(
                            color=icon_color,
                            icon=style.get("icon", "info-sign"),
                        ),
                    ).add_to(fg)

            fg.add_to(m)

    # ==== OVERLAY REZULTATI ====
    if overlay_rezultati:
        overlay_colors = {
            "buffer_putevi_200m": "#FF8C00",
            "buffer_objekti_500m": "#FF6347",
            "clip_landuse_putevi": "#8B0000",
            "union_landuse_natural": "#4B0082",
            "intersection_landuse_putevi": "#00CED1",
            "difference_landuse_van_putevi": "#556B2F",
            "intersects_landuse_natural": "#BDB76B",
            "overlap_landuse": "#DC143C",
            "udaljenost_objekata_voda": "#4682B4",
            "objekti_within_landuse": "#FF69B4",
        }

        for naziv, gdf in overlay_rezultati.items():
            if len(gdf) == 0:
                continue
            col = overlay_colors.get(naziv, "#999")
            fg = FeatureGroup(name=f"Analiza: {naziv}", show=False)
            try:
                folium.GeoJson(
                    gdf.to_json(),
                    style_function=lambda feature, c=col: {
                        "color": c,
                        "fillColor": c,
                        "fillOpacity": 0.4,
                        "weight": 2,
                    },
                ).add_to(fg)
                fg.add_to(m)
            except Exception:
                pass

    # ==== ML DETEKTOVANI OBJEKTI ====
    if ml_vektor is not None and len(ml_vektor) > 0:
        fg_ml = FeatureGroup(name="ML: Detektovani usevi", show=True)
        try:
            if hasattr(ml_vektor, "to_json"):
                folium.GeoJson(
                    ml_vektor.to_json(),
                    style_function=lambda feature: {
                        "color": feature.get("properties", {}).get("color", "#FF0000"),
                        "fillColor": feature.get("properties", {}).get(
                            "color", "#FF0000"
                        ),
                        "fillOpacity": 0.5,
                        "weight": 2,
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=["crop_type", "confidence", "ndvi_mean"]
                    ),
                    popup=folium.GeoJsonPopup(
                        fields=[
                            "crop_type",
                            "confidence",
                            "area_ha",
                            "ndvi_mean",
                            "detection_method",
                        ]
                    ),
                ).add_to(fg_ml)
            else:
                for _, row in ml_vektor.iterrows():
                    folium.Marker(
                        location=[row["latitude"], row["longitude"]],
                        popup=f"Usev: {row.get('crop_type', 'Nepoznat')}<br>"
                        f"Pouzdanost: {row.get('confidence', 'N/A')}%",
                        icon=folium.Icon(color="red", icon="leaf", prefix="fa"),
                    ).add_to(fg_ml)
        except Exception as e:
            print(f"[WARN] ML sloj nije dodat: {e}")
        fg_ml.add_to(m)

    # ==== KONTROLA SLOJEVA ====
    LayerControl(collapsed=False).add_to(m)

    # ==== ČUVANJE ====
    m.save(output_file)
    print(f"\n[OK] Mapa je sačuvana: {os.path.abspath(output_file)}")
    return m


if __name__ == "__main__":
    from src.geo_loader import load_serbia_shapefiles, create_ndvi_demo_raster
    from src.geo_overlay import run_all_overlay_demos

    slojevi = load_serbia_shapefiles()
    raster_path = create_ndvi_demo_raster()
    overlay_rez = run_all_overlay_demos(slojevi)

    create_interactive_map(
        slojevi=slojevi,
        overlay_rezultati=overlay_rez,
        raster_path=raster_path,
        output_file="data/interactive_map.html",
    )
