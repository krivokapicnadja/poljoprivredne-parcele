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

# Geofabrik shapefile putanje (prilagoditi prema preuzetim podacima)
SHP_PATHS = {
    "landuse": "data/serbia_landuse.shp",
    "buildings": "data/serbia_buildings.shp",
    "roads": "data/serbia_roads.shp",
    "waterways": "data/serbia_waterways.shp",
    "natural": "data/serbia_natural.shp",
}

# Raster podloga (Copernicus/NDVI)
RASTER_PATH = "data/ndvi_raster.tif"

# ML model putanja
ML_MODEL_PATH = "models/crop_classifier.pkl"
ML_SCALER_PATH = "models/scaler.pkl"
ML_LABEL_ENCODER_PATH = "models/label_encoder.pkl"

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
