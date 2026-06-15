"""
Deo 2 – Python GEO: Učitavanje shapefile podataka, GeoDataFrame formiranje,
spajanje sa bazom, upravljanje slojevima i prikaz na mapi.
Podaci ograničeni na područje Srema.
"""

import os
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, box, LineString
from src.config import SHP_PATHS, DATA_DIR, CRS_WGS84, SREM_BOUNDS, SREM_CENTER


def load_serbia_shapefiles():
    """
    Učitava sve Geofabrik shapefile slojeve za Srem.
    Ako fajlovi ne postoje, kreira demo podatke unutar granica Srema.
    """
    slojevi = {}

    missing_files = any(not os.path.exists(p) for p in SHP_PATHS.values())

    if missing_files:
        print(
            "[WARN] Shapefile fajlovi nisu pronađeni. Kreiram demo geopodatke za Srem..."
        )
        slojevi = _create_demo_geodata()
    else:
        for naziv, putanja in SHP_PATHS.items():
            try:
                gdf = gpd.read_file(putanja)
                if gdf.crs is None:
                    gdf.set_crs(CRS_WGS84, inplace=True)
                elif gdf.crs.to_string() != CRS_WGS84:
                    gdf = gdf.to_crs(CRS_WGS84)
                # Klipuj na granice Srema
                srem_bbox = box(
                    SREM_BOUNDS["west"],
                    SREM_BOUNDS["south"],
                    SREM_BOUNDS["east"],
                    SREM_BOUNDS["north"],
                )
                gdf = gdf[gdf.intersects(srem_bbox)].copy()
                slojevi[naziv] = gdf
                print(
                    f"[OK] Učitan sloj '{naziv}': {len(gdf)} objekata u Sremu, "
                    f"kolone: {list(gdf.columns[:5])}..."
                )
            except Exception as e:
                print(f"[ERROR] Neuspešno učitavanje '{naziv}': {e}")

    return slojevi


def _create_demo_geodata():
    """
    Kreira demo GeoDataFrames za područje Srema.
    Srem je između Dunava (sever) i Save (jug), zapadno od Beograda.
    Opštine: Sremska Mitrovica, Ruma, Šid, Inđija, Stara Pazova, Irig, Pećinci.
    """
    b = SREM_BOUNDS
    slojevi = {}

    # 1. landuse (poljoprivredne površine) - 10 poligona unutar Srema
    landuse_data = {
        "name": [
            "Njiva Mitrovica 1",
            "Njiva Ruma 1",
            "Voćnjak Irig",
            "Vinograd Fruška Gora",
            "Pašnjak Pećinci",
            "Povrtnjak Inđija",
            "Njiva Šid 1",
            "Njiva Stara Pazova",
            "Voćnjak Ruma",
            "Livada Fruška Gora",
        ],
        "type": [
            "farmland",
            "farmland",
            "orchard",
            "vineyard",
            "pasture",
            "farmland",
            "farmland",
            "farmland",
            "orchard",
            "meadow",
        ],
    }
    polys = [
        box(19.60, 44.96, 19.64, 44.99),  # S. Mitrovica
        box(19.82, 44.98, 19.86, 45.01),  # Ruma
        box(19.85, 45.12, 19.88, 45.15),  # Irig (Fruška Gora)
        box(19.68, 45.16, 19.72, 45.19),  # Fruška Gora vinogradi
        box(19.90, 44.88, 19.94, 44.91),  # Pećinci
        box(20.08, 45.04, 20.12, 45.07),  # Inđija
        box(19.10, 45.02, 19.14, 45.05),  # Šid
        box(20.18, 44.98, 20.22, 45.01),  # Stara Pazova
        box(19.78, 44.95, 19.82, 44.98),  # Ruma voćnjak
        box(19.75, 45.20, 19.79, 45.23),  # Fruška Gora livada
    ]
    slojevi["landuse"] = gpd.GeoDataFrame(landuse_data, geometry=polys, crs=CRS_WGS84)
    print(
        f"[OK] Kreiran demo sloj 'landuse': {len(slojevi['landuse'])} poligona (Srem)."
    )

    # 2. buildings (poljoprivredni objekti) - 8 tačaka u Sremu
    buildings_data = {
        "name": [
            "Silos Mitrovica",
            "Hangar Ruma",
            "Staklenik Inđija",
            "Skladište Šid",
            "Farma Pećinci",
            "Silos Stara Pazova",
            "Objekat Irig",
            "Silos Ruma",
        ],
        "type": [
            "agricultural",
            "agricultural",
            "greenhouse",
            "warehouse",
            "farm",
            "agricultural",
            "farm_auxiliary",
            "agricultural",
        ],
    }
    build_points = [
        Point(19.62, 44.97),  # S. Mitrovica
        Point(19.84, 44.99),  # Ruma
        Point(20.10, 45.05),  # Inđija
        Point(19.12, 45.03),  # Šid
        Point(19.92, 44.89),  # Pećinci
        Point(20.20, 44.99),  # Stara Pazova
        Point(19.87, 45.13),  # Irig
        Point(19.80, 44.96),  # Ruma 2
    ]
    slojevi["buildings"] = gpd.GeoDataFrame(
        buildings_data, geometry=build_points, crs=CRS_WGS84
    )
    print(
        f"[OK] Kreiran demo sloj 'buildings': {len(slojevi['buildings'])} tačaka (Srem)."
    )

    # 3. roads (lokalni putevi u Sremu) - 5 linija
    roads_data = {
        "name": [
            "Put Mitrovica–Ruma",
            "Put Ruma–Inđija",
            "Put Šid–Mitrovica",
            "Put Inđija–Stara Pazova",
            "Put Irig–Ruma",
        ],
        "highway": ["primary", "primary", "primary", "secondary", "secondary"],
    }
    road_lines = [
        LineString([(19.62, 44.97), (19.83, 44.99)]),  # S.Mitrovica → Ruma
        LineString([(19.83, 44.99), (20.09, 45.04)]),  # Ruma → Inđija
        LineString([(19.12, 45.03), (19.62, 44.97)]),  # Šid → S.Mitrovica
        LineString([(20.09, 45.04), (20.19, 44.99)]),  # Inđija → Stara Pazova
        LineString([(19.86, 45.14), (19.83, 44.99)]),  # Irig → Ruma
    ]
    slojevi["roads"] = gpd.GeoDataFrame(roads_data, geometry=road_lines, crs=CRS_WGS84)
    print(f"[OK] Kreiran demo sloj 'roads': {len(slojevi['roads'])} linija (Srem).")

    # 4. waterways (Dunav i Sava — granice Srema) - 3 reke
    waterways_data = {
        "name": ["Dunav (severna granica)", "Sava (južna granica)", "Bosut"],
        "type": ["river", "river", "canal"],
    }
    water_lines = [
        LineString([(19.00, 45.18), (20.35, 45.25)]),  # Dunav — sever Srema
        LineString([(19.00, 44.82), (20.30, 44.78)]),  # Sava — jug Srema
        LineString([(19.05, 45.00), (19.45, 44.98)]),  # Bosut
    ]
    slojevi["waterways"] = gpd.GeoDataFrame(
        waterways_data, geometry=water_lines, crs=CRS_WGS84
    )
    print(
        f"[OK] Kreiran demo sloj 'waterways': {len(slojevi['waterways'])} linija (Srem)."
    )

    # 5. natural (prirodne oblasti) — Fruška Gora, Obedska bara, Zasavica
    natural_data = {
        "name": [
            "Fruška Gora",
            "Obedska bara",
            "Zasavica",
            "Fruškogorski vinogradi",
        ],
        "type": ["forest", "wetland", "wetland", "forest"],
    }
    natural_polys = [
        box(19.70, 45.10, 20.00, 45.24),  # Fruška Gora
        box(19.95, 44.73, 20.05, 44.78),  # Obedska bara
        box(19.50, 44.93, 19.60, 44.98),  # Zasavica
        box(19.70, 45.15, 19.85, 45.22),  # Vinogradi zone
    ]
    slojevi["natural"] = gpd.GeoDataFrame(
        natural_data, geometry=natural_polys, crs=CRS_WGS84
    )
    print(
        f"[OK] Kreiran demo sloj 'natural': {len(slojevi['natural'])} poligona (Srem)."
    )

    return slojevi


def merge_shp_with_db(gdf_slojevi, db_dataframes):
    """
    Spaja GeoDataFrame-ove (iz shapefile-ova) sa tabelama iz baze
    (pandas DataFrame-ovi) na osnovu prostorne bliskosti ili ključeva.
    """
    if "landuse" not in gdf_slojevi or "parcele" not in db_dataframes:
        print("[WARN] Nema podataka za spajanje.")
        return None

    landuse = gdf_slojevi["landuse"].copy()
    parcele = db_dataframes["parcele"].copy()

    print(
        f"[INFO] Prostorno spajanje landuse ({len(landuse)}) i parcela ({len(parcele)})..."
    )

    if "geom" in parcele.columns:
        from shapely import wkb

        parcele["geometry"] = parcele["geom"].apply(
            lambda x: wkb.loads(x, hex=False) if x is not None else None
        )
        parcele_gdf = gpd.GeoDataFrame(
            parcele.dropna(subset=["geometry"]), geometry="geometry", crs=CRS_WGS84
        )
        if len(parcele_gdf) > 0:
            merged = gpd.sjoin(
                landuse,
                parcele_gdf,
                how="inner",
                predicate="intersects",
                lsuffix="landuse",
                rsuffix="parcela",
            )
            print(f"[OK] Prostorno spojeno: {len(merged)} redova.")
            return merged
    print("[WARN] Nije moguće izvršiti prostorno spajanje.")
    return None


def create_ndvi_demo_raster():
    """Kreira simuliran NDVI raster za područje Srema (TIF format)."""
    import numpy as np

    rastername = os.path.join(DATA_DIR, "ndvi_raster.tif")
    if os.path.exists(rastername):
        return rastername

    try:
        import rasterio
        from rasterio.transform import from_bounds

        # NDVI raster za Srem: 19.05E–20.35E, 44.80N–45.25N
        width, height = 500, 400
        ndvi_array = np.random.uniform(0.1, 0.9, (height, width)).astype(np.float32)

        # Viši NDVI u centralnom delu (poljoprivredne površine oko Rume/Mitrovice)
        ndvi_array[100:300, 150:350] += 0.2
        # Fruška Gora — viši NDVI (šuma)
        ndvi_array[0:80, 200:400] += 0.15
        ndvi_array = np.clip(ndvi_array, 0.0, 1.0)

        transform = from_bounds(
            SREM_BOUNDS["west"],
            SREM_BOUNDS["south"],
            SREM_BOUNDS["east"],
            SREM_BOUNDS["north"],
            width,
            height,
        )

        with rasterio.open(
            rastername,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype="float32",
            crs=CRS_WGS84,
            transform=transform,
        ) as dst:
            dst.write(ndvi_array, 1)
        print(f"[OK] Kreiran demo NDVI raster za Srem: {rastername}")
    except ImportError:
        print("[WARN] rasterio nije dostupan. NDVI raster nije kreiran.")
        return None

    return rastername


if __name__ == "__main__":
    print("=== Deo 2: Učitavanje Geo podataka (Srem) ===")
    slojevi = load_serbia_shapefiles()
    print(f"\nUčitani slojevi: {list(slojevi.keys())}")
    for name, gdf in slojevi.items():
        print(f"  - {name}: {len(gdf)} objekata, CRS={gdf.crs}")

    create_ndvi_demo_raster()
