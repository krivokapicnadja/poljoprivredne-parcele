"""
Deo 2 – Python GEO: Učitavanje i obogaćivanje Geofabrik shapefile podataka
(landuse, buildings, roads, waterways, natural) za područje Srema,
i preuzimanje stvarnog NDVI rastera sa Google Earth Engine (Sentinel-2).
"""

import os
import numpy as np
import geopandas as gpd
import pandas as pd
import urllib.request
from shapely.geometry import box
from src.config import (
    SHP_PATHS,
    RASTER_PATH,
    DATA_DIR,
    CRS_WGS84,
    SREM_BOUNDS,
    GEE_PROJECT,
    GEE_SERVICE_ACCOUNT,
    GEE_KEY_FILE,
    SENTINEL_START_DATE,
    SENTINEL_END_DATE,
    SENTINEL_CLOUD_COVER,
    GEE_SCALE,
)

# ---------------------------------------------------------------------------
# Mapiranje fclass vrednosti na poljoprivredne kategorije za landuse/natural
# ---------------------------------------------------------------------------
AGRICULTURAL_CATEGORIES = {
    "farmland",
    "farmyard",
    "orchard",
    "vineyard",
    "meadow",
    "grass",
    "heath",
    "scrub",
    "grassland",
    "pasture",
}

LANDUSE_CATEGORY_MAP = {
    "forest": "forest",
    "orchard": "orchard",
    "vineyard": "vineyard",
    "farmland": "farmland",
    "farmyard": "farmland",
    "meadow": "meadow",
    "grass": "grass",
    "heath": "heath",
    "scrub": "scrub",
    "residential": "residential",
    "industrial": "industrial",
    "commercial": "commercial",
    "retail": "commercial",
    "quarry": "quarry",
    "military": "industrial",
    "park": "park",
    "recreation_ground": "park",
    "allotments": "farmland",
    "cemetery": "park",
    "landfill": "industrial",
    "village_green": "grass",
    "greenfield": "grass",
    "harbour": "water",
    "nature_reserve": "nature_reserve",
}

NATURAL_CATEGORY_MAP = {
    "wood": "forest",
    "water": "water",
    "wetland": "wetland",
    "scrub": "scrub",
    "heath": "heath",
    "grassland": "grassland",
    "bare_rock": "bare_rock",
    "beach": "beach",
    "sand": "beach",
    "glacier": "bare_rock",
    "cliff": "cliff",
    "scree": "bare_rock",
    "fell": "grassland",
    "mud": "wetland",
    "shingle": "beach",
    "spring": "spring",
    "cave_entrance": "bare_rock",
    "sinkhole": "bare_rock",
    "rock": "bare_rock",
    "reef": "bare_rock",
}


def _init_earth_engine():
    """Inicijalizuje Google Earth Engine autentifikaciju."""
    try:
        import ee

        if GEE_SERVICE_ACCOUNT and GEE_KEY_FILE and os.path.exists(GEE_KEY_FILE):
            credentials = ee.ServiceAccountCredentials(
                GEE_SERVICE_ACCOUNT, GEE_KEY_FILE
            )
            ee.Initialize(credentials, project=GEE_PROJECT)
            print("[OK] Earth Engine inicijalizovan (service account).")
        else:
            ee.Initialize(project=GEE_PROJECT if GEE_PROJECT else None)
            print("[OK] Earth Engine inicijalizovan (default credentials).")
        return ee
    except ImportError:
        print("[WARN] earthengine-api nije instalirana. Koristi se demo NDVI.")
        return None
    except Exception as e:
        print(f"[WARN] Earth Engine nije dostupan: {e}. Koristi se demo NDVI.")
        return None


def load_serbia_shapefiles():
    """
    Učitava sve Geofabrik shapefile slojeve za Srem.
    Obogaćuje podatke sa category kolonom za dalju analizu.
    Ako fajlovi ne postoje, vraća prazne slojeve.
    """
    print("\n=== UČITAVANJE GEOFABRIK SHAPEFILE PODATAKA ZA SREM ===")

    slojevi = {}
    srem_bbox = box(
        SREM_BOUNDS["west"],
        SREM_BOUNDS["south"],
        SREM_BOUNDS["east"],
        SREM_BOUNDS["north"],
    )

    for naziv, putanja in SHP_PATHS.items():
        if not os.path.exists(putanja):
            print(f"[WARN] {putanja} ne postoji – preskačem sloj '{naziv}'.")
            continue

        try:
            gdf = gpd.read_file(putanja)
            print(f"[OK] Učitan {naziv}: {len(gdf)} elemenata, CRS={gdf.crs}, "
                  f"kolone: {list(gdf.columns[:6])}...")

            # Provera i konverzija CRS-a
            if gdf.crs is None:
                gdf = gdf.set_crs(CRS_WGS84)
            elif gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(CRS_WGS84)

            # Filtriranje na region Srema
            gdf_srem = gdf[gdf.geometry.intersects(srem_bbox)].copy()
            print(f"   → {len(gdf_srem)} elemenata u regionu Srema.")

            if len(gdf_srem) > 0:
                # Obogaćivanje podataka (dodavanje category kolone)
                gdf_srem = _enrich_layer(naziv, gdf_srem)
                slojevi[naziv] = gdf_srem
                print(f"   → Obogaćen sloj '{naziv}': {len(gdf_srem)} elemenata.")
            else:
                print(f"   [WARN] Nema podataka za sloj '{naziv}' na području Srema.")

        except Exception as e:
            print(f"[ERROR] Neuspešno učitavanje '{naziv}' iz {putanja}: {e}")

    print(f"\n[OK] Učitano {len(slojevi)} slojeva za Srem: {list(slojevi.keys())}")
    return slojevi


def _enrich_layer(naziv, gdf):
    """
    Obogaćuje GeoDataFrame sa dodatnim kolonama za kompatibilnost
    sa ostatkom aplikacije.
    """
    gdf = gdf.copy()

    if naziv == "landuse":
        gdf["type"] = gdf["fclass"]
        gdf["category"] = gdf["fclass"].map(LANDUSE_CATEGORY_MAP).fillna(gdf["fclass"])

    elif naziv == "natural":
        gdf["type"] = gdf["fclass"]
        gdf["category"] = gdf["fclass"].map(NATURAL_CATEGORY_MAP).fillna(gdf["fclass"])

    elif naziv == "buildings":
        gdf["category"] = "building"

    elif naziv == "roads":
        gdf["type"] = gdf["fclass"]
        gdf["category"] = "road"
        gdf["highway"] = gdf["fclass"]

    elif naziv == "waterways":
        gdf["type"] = gdf["fclass"]
        gdf["category"] = "waterway"

    return gdf


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


def _create_demo_ndvi_raster():
    """Kreira simuliran NDVI raster za područje Srema (fallback)."""
    rastername = os.path.join(DATA_DIR, "ndvi_raster.tif")
    if os.path.exists(rastername):
        return rastername

    try:
        import rasterio
        from rasterio.transform import from_bounds

        width, height = 500, 400
        ndvi_array = np.random.uniform(0.1, 0.9, (height, width)).astype(np.float32)
        ndvi_array[100:300, 150:350] += 0.2
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


def create_ndvi_raster():
    """
    Preuzima stvarni Sentinel-2 NDVI mozaik za Srem sa Google Earth Engine-a.
    Ako GEE nije dostupan, pada nazad na demo raster.
    """
    rastername = os.path.join(DATA_DIR, "ndvi_raster.tif")

    ee = _init_earth_engine()
    if ee is None:
        return _create_demo_ndvi_raster()

    print("\n=== PREUZIMANJE STVARNOG SENTINEL-2 NDVI SA EARTH ENGINE-A ===")

    try:
        # Definiši region Srema kao EE geometriju
        srem_region = ee.Geometry.Rectangle([
            SREM_BOUNDS["west"],
            SREM_BOUNDS["south"],
            SREM_BOUNDS["east"],
            SREM_BOUNDS["north"],
        ])

        # Sentinel-2 Surface Reflectance kolekcija (Harmonized)
        s2_collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(srem_region)
            .filterDate(SENTINEL_START_DATE, SENTINEL_END_DATE)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", SENTINEL_CLOUD_COVER))
        )

        count = s2_collection.size().getInfo()
        print(f"   Broj Sentinel-2 snimaka u periodu: {count}")

        if count == 0:
            print("[WARN] Nema Sentinel-2 snimaka za dati period. Koristi se demo NDVI.")
            return _create_demo_ndvi_raster()

        # Funkcija za izračunavanje NDVI
        def add_ndvi(image):
            ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
            return image.addBands(ndvi)

        # Uzmi samo najmanje oblačan snimak iz perioda (jeftinije računski od medijane 184 snimka)
        s2_collection_sorted = s2_collection.sort("CLOUDY_PIXEL_PERCENTAGE")
        best_image = ee.Image(s2_collection_sorted.first())
        ndvi_composite = add_ndvi(best_image).select("NDVI")

        # Klipuj na validan opseg
        ndvi_composite = ndvi_composite.clamp(-1.0, 1.0)

        # Preuzmi kao GeoTIFF
        print(f"   Preuzimanje NDVI rastera za Srem (rezolucija {GEE_SCALE}m)...")
        url = ndvi_composite.getDownloadURL({
            "name": "ndvi_srem",
            "scale": GEE_SCALE,
            "region": srem_region,
            "crs": "EPSG:4326",
            "format": "GEO_TIFF",
        })

        # Preuzmi fajl
        urllib.request.urlretrieve(url, rastername)
        print(f"[OK] Stvarni Sentinel-2 NDVI sačuvan: {rastername}")

        # Verifikuj raster
        import rasterio
        with rasterio.open(rastername) as src:
            arr = src.read(1)
            print(f"   Raster dimenzije: {src.width}x{src.height}")
            print(f"   NDVI opseg: [{arr.min():.3f}, {arr.max():.3f}]")
            print(f"   CRS: {src.crs}")

        return rastername

    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode()
        except Exception:
            error_body = "(ne mogu da pročitam telo odgovora)"
        print(f"[WARN] HTTP greška {e.code} pri preuzimanju: {error_body}")
        print("[INFO] Pada se nazad na demo NDVI raster.")
        return _create_demo_ndvi_raster()
    except Exception as e:
        print(f"[WARN] Greška pri preuzimanju sa Earth Engine-a: {e}")
        print("[INFO] Pada se nazad na demo NDVI raster.")
        return _create_demo_ndvi_raster()
    
# NOVO - ISPRAVAK GRESKE IZ TERMINALA
def get_ndvi_tile_url():
    """
    Vraća tile URL za NDVI sloj preko Earth Engine getMapId(),
    bez preuzimanja rastera na disk. Koristi se za prikaz na Folium mapi.
    Nema limit veličine jer se tajlovi učitavaju uživo, po zahtevu.
    """
    ee = _init_earth_engine()
    if ee is None:
        return None

    try:
        srem_region = ee.Geometry.Rectangle([
            SREM_BOUNDS["west"],
            SREM_BOUNDS["south"],
            SREM_BOUNDS["east"],
            SREM_BOUNDS["north"],
        ])

        s2_collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(srem_region)
            .filterDate(SENTINEL_START_DATE, SENTINEL_END_DATE)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", SENTINEL_CLOUD_COVER))
        )

        if s2_collection.size().getInfo() == 0:
            return None

        def add_ndvi(image):
            ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
            return image.addBands(ndvi)

        ndvi_composite = (
            s2_collection.map(add_ndvi).select("NDVI").median().clamp(-1.0, 1.0)
        )

        map_id_dict = ndvi_composite.getMapId({
            "min": -1,
            "max": 1,
            "palette": ["blue", "white", "green"],
        })

        print("[OK] NDVI tile URL dobijen preko Earth Engine getMapId().")
        return map_id_dict["tile_fetcher"].url_format

    except Exception as e:
        print(f"[WARN] Ne mogu da dobijem NDVI tile URL: {e}")
        return None


# Alias za kompatibilnost sa starim kodom
create_ndvi_demo_raster = create_ndvi_raster


if __name__ == "__main__":
    print("=== Deo 2: Učitavanje Geo podataka (Srem) ===")
    slojevi = load_serbia_shapefiles()
    print(f"\nUčitani slojevi: {list(slojevi.keys())}")
    for name, gdf in slojevi.items():
        print(f"  - {name}: {len(gdf)} objekata, CRS={gdf.crs}, "
              f"kolone={list(gdf.columns[:8])}")

    create_ndvi_raster()