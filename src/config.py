"""
Centralna konfiguracija za aplikaciju Monitoring poljoprivrednih parcela.
"""

from dotenv import load_dotenv
import os


load_dotenv()
# PostgreSQL/PostGIS konekcioni parametri
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": 5432,
    "database": "postgres",
    "user": "postgres.awrrylgebnnjpwxzokmt",
    "password": os.getenv("DB_PASSWORD"),
    "sslmode": "require",
}
# Putanje do podataka
DATA_DIR = "data"
MODELS_DIR = "models"

# Geofabrik shapefile putanje (stvarni preuzeti fajlovi)
SHP_PATHS = {
    "landuse": "data/gis_osm_landuse_a_free_1.shp",
    "buildings": "data/gis_osm_buildings_a_free_1.shp",
    "roads": "data/gis_osm_roads_free_1.shp",
    "waterways": "data/gis_osm_waterways_free_1.shp",
    "natural": "data/gis_osm_natural_a_free_1.shp",
}

# Raster podloga (Copernicus/NDVI)
RASTER_PATH = "data/ndvi_raster.tif"

# ML model putanja
ML_MODEL_PATH = "models/crop_classifier.pkl"
ML_SCALER_PATH = "models/scaler.pkl"
ML_LABEL_ENCODER_PATH = "models/label_encoder.pkl"

# Google Earth Engine podešavanja
GEE_PROJECT = os.getenv("GEE_PROJECT", "")
GEE_SERVICE_ACCOUNT = os.getenv("GEE_SERVICE_ACCOUNT", "")
GEE_KEY_FILE = os.getenv("GEE_KEY_FILE", "")

# Sentinel-2 podešavanja za NDVI i snimke
SENTINEL_START_DATE = "2025-04-01"
SENTINEL_END_DATE = "2025-09-30"
SENTINEL_CLOUD_COVER = 20
GEE_SCALE = 10  # metara po pikselu (Sentinel-2 rezolucija)

# Koordinatni referentni sistem Srbije
CRS_SERBIA = "EPSG:6316"  # ETRS89 / UTM zone 34N
CRS_WGS84 = "EPSG:4326"

# Granice regije Srem (između Dunava i Save)
SREM_BOUNDS = {
    "west": 19.05,  # granica sa Hrvatskom (Šid)
    "east": 20.35,  # Stara Pazova / Zemun
    "south": 44.73,  # Sava (Obedska bara)
    "north": 45.25,  # Dunav
}
SREM_CENTER = [44.99, 19.70]  # centar Srema (okvirno — između Rume i S. Mitrovice)