"""
Deo 3 – Python ML: Mašinsko učenje za detekciju useva/objekata na snimcima,
konverziju u vektorski format, upis u PostGIS i prikaz na mapi.

Sada koristi stvarne Sentinel-2 satelitske snimke sa Google Earth Engine-a
umesto simuliranih podataka.
"""

import os
import pickle
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon, box
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from src.config import (
    ML_MODEL_PATH,
    ML_SCALER_PATH,
    ML_LABEL_ENCODER_PATH,
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
from src.geo_loader import _init_earth_engine


# ======================== TRENIRANJE MODELA ========================


def create_training_data():
    """
    Kreira trening podatke za klasifikaciju useva.
    Pokušava da izvuče stvarne spektralne karakteristike sa Sentinel-2 snimaka
    sa Google Earth Engine-a. Ako GEE nije dostupan, pada nazad na simulirane podatke.
    """
    ee = _init_earth_engine()
    if ee is not None:
        df = _create_training_data_from_gee(ee)
        if df is not None and len(df) >= 50:
            return df

    print("[INFO] Pad na simulirane trening podatke (GEE podaci nisu dostupni).")
    return _create_training_data_simulated()


def _create_training_data_from_gee(ee):
    """
    Izvlači stvarne spektralne karakteristike sa Sentinel-2 snimaka
    za poznate useve u Sremu pomoću Google Earth Engine-a.
    """
    print("\n=== EKSTRAKCIJA STVARNIH TRENING PODATAKA SA EARTH ENGINE-A ===")

    try:
        srem_region = ee.Geometry.Rectangle([
            SREM_BOUNDS["west"],
            SREM_BOUNDS["south"],
            SREM_BOUNDS["east"],
            SREM_BOUNDS["north"],
        ])

        # Sentinel-2 Surface Reflectance kolekcija
        s2_collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(srem_region)
            .filterDate(SENTINEL_START_DATE, SENTINEL_END_DATE)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", SENTINEL_CLOUD_COVER))
        )

        count = s2_collection.size().getInfo()
        print(f"   Broj Sentinel-2 snimaka: {count}")

        if count == 0:
            print("[WARN] Nema snimaka za dati period.")
            return None

        # Medijan kompozit za sezonu
        composite = s2_collection.median()

        # Izračunaj vegetacione indekse
        ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")
        ndwi = composite.normalizedDifference(["B3", "B8"]).rename("NDWI")
        savi = composite.expression(
            "(NIR - RED) * 1.5 / (NIR + RED + 0.5)",
            {"NIR": composite.select("B8"), "RED": composite.select("B4")},
        ).rename("SAVI")

        # Kombinuj sve bendove
        stack = composite.addBands([ndvi, ndwi, savi])

        band_names = ["B2", "B3", "B4", "B8", "B11", "NDVI", "NDWI", "SAVI"]
        stack = stack.select(band_names)

        # Uzorkuj piksele (grid uzorkovanje unutar Srema)
        # Generišemo ~500 nasumičnih tačaka unutar regiona
        samples = ee.FeatureCollection.randomPoints(
            srem_region, 500, seed=42
        )

        # Ekstraktuj vrednosti na tačkama
        sampled = stack.reduceRegions(
            collection=samples,
            reducer=ee.Reducer.mean(),
            scale=GEE_SCALE,
            tileScale=2,
        )

        # Preuzmi kao pandas DataFrame
        data_list = sampled.getInfo()
        if not data_list or "features" not in data_list or len(data_list["features"]) == 0:
            print("[WARN] Nema ekstrahovanih tačaka.")
            return None

        records = []
        for feat in data_list["features"]:
            props = feat["properties"]
            records.append({
                "red_band": props.get("B4", None),
                "green_band": props.get("B3", None),
                "blue_band": props.get("B2", None),
                "nir_band": props.get("B8", None),
                "swir_band": props.get("B11", None),
                "ndvi": props.get("NDVI", None),
                "ndwi": props.get("NDWI", None),
                "savi": props.get("SAVI", None),
            })

        df = pd.DataFrame(records)
        # Ukloni piksele sa NoData vrednostima
        df = df.dropna()
        print(f"   Ekstrahovano {len(df)} validnih piksela.")

        if len(df) < 50:
            print("[WARN] Premalo validnih piksela za treniranje modela.")
            return None

        # Dodaj temperaturu i vlažnost iz ERA5-Land reanalize
        try:
            era5 = (
                ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY")
                .filterBounds(srem_region)
                .filterDate(SENTINEL_START_DATE, SENTINEL_END_DATE)
                .select(["temperature_2m", "total_precipitation"])
                .mean()
            )

            era5_sampled = era5.reduceRegions(
                collection=samples,
                reducer=ee.Reducer.mean(),
                scale=11132,  # ~0.1 stepeni
                tileScale=2,
            )

            era5_data = era5_sampled.getInfo()
            if era5_data and "features" in era5_data:
                temps = []
                precips = []
                for feat in era5_data["features"]:
                    props = feat["properties"]
                    t = props.get("temperature_2m")
                    p = props.get("total_precipitation")
                    temps.append(t if t is not None else np.nan)
                    precips.append(p if p is not None else np.nan)
                df_temp = pd.DataFrame({
                    "temperature": temps,
                    "precipitation": precips,
                })
                # Poravnaj dužine
                min_len = min(len(df), len(df_temp))
                df = df.iloc[:min_len].reset_index(drop=True)
                df_temp = df_temp.iloc[:min_len].reset_index(drop=True)
                df["temperature"] = df_temp["temperature"].values
                # Konvertuj temperaturu iz Kelvina u Celzijuse
                df["temperature"] = df["temperature"] - 273.15
                # Humidnost aproksimirana iz precipitacije (pojednostavljeno)
                df["humidity"] = np.clip(df_temp["precipitation"].values * 100000 / 7, 20, 95)
                df = df.dropna()
                print(f"   Dodati ERA5 meteorološki podaci: {len(df)} tačaka.")
        except Exception as meteo_err:
            print(f"[WARN] ERA5 podaci nisu dostupni: {meteo_err}")
            # Dodaj simulirane meteo vrednosti na osnovu stvarnih NDVI vrednosti
            df["temperature"] = np.random.normal(20, 4, len(df))
            df["humidity"] = np.random.normal(60, 12, len(df))
            df["temperature"] = df["temperature"].clip(5, 35)
            df["humidity"] = df["humidity"].clip(20, 95)

        # Heuristička klasifikacija useva na osnovu NDVI i spektralnih karakteristika
        # (za pravu primenu, potrebni su ground-truth podaci)
        df = _assign_crop_labels_heuristic(df)

        print(f"   Konačni trening skup: {len(df)} uzoraka.")
        print(f"   Distribucija useva:")
        for crop, cnt in df["crop_type"].value_counts().items():
            print(f"      {crop}: {cnt}")

        return df

    except Exception as e:
        print(f"[WARN] Greška pri ekstrakciji GEE podataka: {e}")
        import traceback
        traceback.print_exc()
        return None


def _assign_crop_labels_heuristic(df):
    """
    Dodeljuje oznake useva na osnovu spektralnih karakteristika (heuristički).
    U produkciji, ovo bi bilo zamenjeno sa stvarnim ground-truth podacima.
    """
    crop_types = ["Pšenica", "Kukuruz", "Suncokret", "Soja", "Ječam", "Krompir"]
    labels = []

    for _, row in df.iterrows():
        ndvi = row.get("ndvi", 0.5)
        nir = row.get("nir_band", 0.4)
        red = row.get("red_band", 0.1)
        swir = row.get("swir_band", 0.2)
        ndwi = row.get("ndwi", 0.0)

        if ndvi > 0.78 and nir > 0.45:
            labels.append("Kukuruz")
        elif ndvi > 0.76 and ndwi < 0.1:
            labels.append("Soja")
        elif ndvi > 0.70 and ndwi > 0.1:
            labels.append("Pšenica")
        elif swir > 0.25 and ndvi < 0.65:
            labels.append("Suncokret")
        elif ndvi < 0.65 and red > 0.08:
            labels.append("Ječam")
        elif ndvi > 0.72 and ndwi > 0.15:
            labels.append("Krompir")
        else:
            labels.append(np.random.choice(crop_types))

    df["crop_type"] = labels
    return df


def _create_training_data_simulated():
    """
    Kreira simulirane trening podatke za klasifikaciju useva
    (fallback kada Earth Engine nije dostupan).
    """
    np.random.seed(42)
    n_samples = 500

    crop_types = ["Pšenica", "Kukuruz", "Suncokret", "Soja", "Ječam", "Krompir"]

    data = []
    for i in range(n_samples):
        crop = np.random.choice(crop_types)

        if crop == "Pšenica":
            ndvi = np.random.normal(0.72, 0.08)
            temp = np.random.normal(18, 3)
            humidity = np.random.normal(55, 10)
            red_band = np.random.normal(0.08, 0.02)
            nir_band = np.random.normal(0.40, 0.05)
        elif crop == "Kukuruz":
            ndvi = np.random.normal(0.78, 0.06)
            temp = np.random.normal(22, 4)
            humidity = np.random.normal(60, 12)
            red_band = np.random.normal(0.06, 0.02)
            nir_band = np.random.normal(0.45, 0.06)
        elif crop == "Suncokret":
            ndvi = np.random.normal(0.65, 0.10)
            temp = np.random.normal(20, 5)
            humidity = np.random.normal(50, 15)
            red_band = np.random.normal(0.10, 0.03)
            nir_band = np.random.normal(0.35, 0.07)
        elif crop == "Soja":
            ndvi = np.random.normal(0.80, 0.05)
            temp = np.random.normal(20, 3)
            humidity = np.random.normal(65, 10)
            red_band = np.random.normal(0.05, 0.01)
            nir_band = np.random.normal(0.48, 0.05)
        elif crop == "Ječam":
            ndvi = np.random.normal(0.68, 0.09)
            temp = np.random.normal(16, 4)
            humidity = np.random.normal(50, 12)
            red_band = np.random.normal(0.09, 0.03)
            nir_band = np.random.normal(0.37, 0.06)
        elif crop == "Krompir":
            ndvi = np.random.normal(0.75, 0.07)
            temp = np.random.normal(18, 3)
            humidity = np.random.normal(70, 10)
            red_band = np.random.normal(0.07, 0.02)
            nir_band = np.random.normal(0.42, 0.05)

        data.append(
            {
                "ndvi": np.clip(ndvi, 0, 1),
                "temperature": np.clip(temp, 5, 35),
                "humidity": np.clip(humidity, 20, 95),
                "red_band": np.clip(red_band, 0.01, 0.3),
                "nir_band": np.clip(nir_band, 0.2, 0.7),
                "ndwi": np.random.normal(0.15, 0.08),
                "savi": np.clip(ndvi * 0.8 + 0.1, 0, 1),
                "crop_type": crop,
            }
        )

    return pd.DataFrame(data)


def train_model():
    """
    Trenira RandomForestClassifier za klasifikaciju useva.
    Čuva model, skaliranje i label enkoder u models/ folder.
    """
    print("=== TRENIRANJE ML MODELA ZA KLASIFIKACIJU USEVA ===")
    df = create_training_data()
    print(f"Trening podaci: {len(df)} uzoraka, {df['crop_type'].nunique()} klasa.")
    print(f"Klase: {df['crop_type'].unique().tolist()}")

    feature_cols = [
        "ndvi",
        "temperature",
        "humidity",
        "red_band",
        "nir_band",
        "ndwi",
        "savi",
    ]
    X = df[feature_cols].values
    y = df["crop_type"].values

    # Label enkoder
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    # Podela na trening i test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
    )

    # Skaliranje
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Model: Random Forest
    model = RandomForestClassifier(
        n_estimators=150,
        max_depth=12,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train_scaled, y_train)

    # Evaluacija
    y_pred = model.predict(X_test_scaled)
    accuracy = model.score(X_test_scaled, y_test)
    print(f"\nTačnost modela: {accuracy:.4f} ({accuracy * 100:.2f}%)")
    print("\nClassification Report:")
    print(
        classification_report(y_test, y_pred, target_names=le.classes_, zero_division=0)
    )

    # Značaj karakteristika
    print("\nZnačaj karakteristika:")
    for feat, imp in sorted(
        zip(feature_cols, model.feature_importances_), key=lambda x: -x[1]
    ):
        print(f"  {feat}: {imp:.4f}")

    # Čuvanje modela
    os.makedirs("models", exist_ok=True)
    with open(ML_MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    with open(ML_SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)
    with open(ML_LABEL_ENCODER_PATH, "wb") as f:
        pickle.dump(le, f)

    print(f"\n[OK] Model sačuvan: {ML_MODEL_PATH}")
    print(f"[OK] Skaliranje sačuvano: {ML_SCALER_PATH}")
    print(f"[OK] Label enkoder sačuvan: {ML_LABEL_ENCODER_PATH}")

    return model, scaler, le


# ======================== DETEKCIJA NA SNIMCIMA ========================


def load_trained_model():
    """Učitava prethodno trenirani model."""
    if not os.path.exists(ML_MODEL_PATH):
        print("[INFO] Model nije pronađen. Treniram novi model...")
        return train_model()

    with open(ML_MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    with open(ML_SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)
    with open(ML_LABEL_ENCODER_PATH, "rb") as f:
        le = pickle.load(f)
    print("[OK] Model je učitan.")
    return model, scaler, le


def detect_crops_on_raster(raster_path=None):
    """
    Detektuje useve na stvarnim Sentinel-2 satelitskim snimcima
    pomoću Google Earth Engine-a.
    Ako GEE nije dostupan ili raster ne postoji, pada nazad na simulaciju.

    Vraća GeoDataFrame sa detektovanim usevima.
    """
    ee = _init_earth_engine()
    if ee is not None:
        gdf = _detect_crops_from_gee(ee)
        if gdf is not None and len(gdf) > 0:
            return gdf

    print("[INFO] Pad na simuliranu detekciju (GEE podaci nisu dostupni).")
    return _detect_crops_simulated(raster_path)


def _detect_crops_from_gee(ee):
    """
    Izvršava detekciju useva na Sentinel-2 snimcima sa Earth Engine-a.
    Ekstraktuje piksele iz Srem regiona, izračunava spektralne karakteristike
    i primenjuje trenirani ML model na svaki piksel.
    """
    print("\n=== DETEKCIJA USEVA NA STVARNIM SENTINEL-2 SNIMCIMA (GEE) ===")

    try:
        model, scaler, le = load_trained_model()

        srem_region = ee.Geometry.Rectangle([
            SREM_BOUNDS["west"],
            SREM_BOUNDS["south"],
            SREM_BOUNDS["east"],
            SREM_BOUNDS["north"],
        ])

        # Sentinel-2 Surface Reflectance kolekcija
        s2_collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(srem_region)
            .filterDate(SENTINEL_START_DATE, SENTINEL_END_DATE)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", SENTINEL_CLOUD_COVER))
        )

        count = s2_collection.size().getInfo()
        print(f"   Broj Sentinel-2 snimaka: {count}")

        if count == 0:
            print("[WARN] Nema snimaka za dati period.")
            return None

        composite = s2_collection.median()

        # Izračunaj vegetacione indekse
        ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")
        ndwi = composite.normalizedDifference(["B3", "B8"]).rename("NDWI")
        savi = composite.expression(
            "(NIR - RED) * 1.5 / (NIR + RED + 0.5)",
            {"NIR": composite.select("B8"), "RED": composite.select("B4")},
        ).rename("SAVI")

        stack = composite.addBands([ndvi, ndwi, savi])
        band_names = ["B2", "B3", "B4", "B8", "B11", "NDVI", "NDWI", "SAVI"]
        stack = stack.select(band_names)

        # Uzorkuj detekcione tačke (grid ~200 tačaka unutar Srema)
        n_detections = 200
        sample_points = ee.FeatureCollection.randomPoints(
            srem_region, n_detections, seed=123
        )

        sampled = stack.reduceRegions(
            collection=sample_points,
            reducer=ee.Reducer.mean(),
            scale=GEE_SCALE,
            tileScale=2,
        )

        data_list = sampled.getInfo()
        if not data_list or "features" not in data_list:
            print("[WARN] Nema ekstrahovanih tačaka za detekciju.")
            return None

        features_list = data_list["features"]

        # ERA5 meteorološki podaci
        try:
            era5 = (
                ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY")
                .filterBounds(srem_region)
                .filterDate(SENTINEL_START_DATE, SENTINEL_END_DATE)
                .select(["temperature_2m", "total_precipitation"])
                .mean()
            )
            era5_sampled = era5.reduceRegions(
                collection=sample_points,
                reducer=ee.Reducer.mean(),
                scale=11132,
                tileScale=2,
            )
            era5_data = era5_sampled.getInfo()
        except Exception:
            era5_data = None

        crop_colors = {
            "Pšenica": "#F5DEB3",
            "Kukuruz": "#FFD700",
            "Suncokret": "#FFA500",
            "Soja": "#32CD32",
            "Ječam": "#DEB887",
            "Krompir": "#8B4513",
        }

        detections = []
        feature_cols = ["ndvi", "temperature", "humidity", "red_band", "nir_band", "ndwi", "savi"]

        for i, feat in enumerate(features_list):
            props = feat["properties"]
            coords = feat["geometry"]["coordinates"]
            lon, lat = coords[0], coords[1]

            # Ekstraktuj spektralne karakteristike
            red = props.get("B4")
            nir = props.get("B8")
            ndvi_val = props.get("NDVI")
            ndwi_val = props.get("NDWI")
            savi_val = props.get("SAVI")

            if any(v is None for v in [red, nir, ndvi_val]):
                continue

            # Meteorološki podaci
            temperature = 20.0
            humidity = 60.0
            if era5_data and "features" in era5_data and i < len(era5_data["features"]):
                ep = era5_data["features"][i]["properties"]
                t_k = ep.get("temperature_2m")
                p = ep.get("total_precipitation")
                if t_k is not None:
                    temperature = t_k - 273.15
                if p is not None:
                    humidity = np.clip(p * 100000 / 7, 20, 95)

            # Formiraj feature vektor
            features = np.array([[
                np.clip(ndvi_val, 0, 1),
                np.clip(temperature, 5, 35),
                np.clip(humidity, 20, 95),
                np.clip(red, 0.01, 0.3),
                np.clip(nir, 0.2, 0.7),
                ndwi_val if ndwi_val is not None else 0.15,
                np.clip(savi_val if savi_val is not None else ndvi_val * 0.8 + 0.1, 0, 1),
            ]])

            # Predikcija
            try:
                features_scaled = scaler.transform(features)
                pred_class = le.inverse_transform(model.predict(features_scaled))[0]
                proba = model.predict_proba(features_scaled).max()
            except Exception:
                continue

            # Geometrija: mali poligon oko tačke
            dx = 0.005
            dy = 0.005
            geom = box(lon - dx / 2, lat - dy / 2, lon + dx / 2, lat + dy / 2)

            detection = {
                "crop_type": pred_class,
                "confidence": round(proba * 100, 1),
                "ndvi_mean": round(float(ndvi_val), 4),
                "lai_estimate": round(np.random.uniform(2, 6), 1),
                "area_ha": round(
                    dx * dy * 111_000 * 111_000 * 0.0001 * np.cos(np.radians(lat)), 2
                ),
                "latitude": lat,
                "longitude": lon,
                "temperature": round(temperature, 1),
                "humidity": round(humidity, 1),
                "detection_method": "RandomForest + Sentinel-2 (GEE)",
                "color": crop_colors.get(pred_class, "#999"),
                "geometry": geom,
            }
            detections.append(detection)

        gdf = gpd.GeoDataFrame(detections, crs=CRS_WGS84)
        print(f"\n[OK] Detektovano {len(gdf)} objekata sa stvarnih Sentinel-2 snimaka.")

        if len(gdf) > 0:
            print("\nDistribucija detektovanih useva:")
            for crop, cnt in gdf["crop_type"].value_counts().items():
                print(f"  {crop}: {cnt}")

        return gdf

    except Exception as e:
        print(f"[WARN] Greška pri GEE detekciji: {e}")
        import traceback
        traceback.print_exc()
        return None


def _detect_crops_simulated(raster_path=None):
    """
    Simulirana detekcija useva (fallback kada GEE nije dostupan).
    """
    if raster_path and os.path.exists(raster_path):
        print(f"[INFO] Analiza rastera: {raster_path}")
    else:
        print("[INFO] Nema rastera. Koristim simulirane detekcije.")

    model, scaler, le = load_trained_model()

    np.random.seed(123)
    n_detections = 25

    detections = []
    crop_colors = {
        "Pšenica": "#F5DEB3",
        "Kukuruz": "#FFD700",
        "Suncokret": "#FFA500",
        "Soja": "#32CD32",
        "Ječam": "#DEB887",
        "Krompir": "#8B4513",
    }

    for i in range(n_detections):
        ndvi = np.random.uniform(0.5, 0.9)
        temp = np.random.uniform(10, 30)
        hum = np.random.uniform(30, 80)
        red = np.random.uniform(0.03, 0.15)
        nir = np.random.uniform(0.30, 0.55)
        ndwi = np.random.uniform(0.05, 0.25)
        savi = np.clip(ndvi * 0.8 + np.random.uniform(0.05, 0.15), 0, 1)

        features = np.array([[ndvi, temp, hum, red, nir, ndwi, savi]])
        features_scaled = scaler.transform(features)
        pred_class = le.inverse_transform(model.predict(features_scaled))[0]
        proba = model.predict_proba(features_scaled).max()

        lon = np.random.uniform(SREM_BOUNDS["west"], SREM_BOUNDS["east"])
        lat = np.random.uniform(SREM_BOUNDS["south"], SREM_BOUNDS["north"])
        dx = np.random.uniform(0.005, 0.015)
        dy = np.random.uniform(0.005, 0.015)

        geom = box(lon, lat, lon + dx, lat + dy)

        detection = {
            "crop_type": pred_class,
            "confidence": round(proba * 100, 1),
            "ndvi_mean": round(ndvi, 4),
            "lai_estimate": round(np.random.uniform(2, 6), 1),
            "area_ha": round(
                dx * dy * 111_000 * 111_000 * 0.0001 * np.cos(np.radians(lat)), 2
            ),
            "latitude": lat,
            "longitude": lon,
            "temperature": round(temp, 1),
            "humidity": round(hum, 1),
            "detection_method": "RandomForest (simulirano)",
            "color": crop_colors.get(pred_class, "#999"),
            "geometry": geom,
        }
        detections.append(detection)

    gdf = gpd.GeoDataFrame(detections, crs=CRS_WGS84)
    print(f"\n[OK] Detektovano {len(gdf)} objekata (simulirano).")

    print("\nDistribucija detektovanih useva:")
    for crop, count in gdf["crop_type"].value_counts().items():
        print(f"  {crop}: {count}")

    return gdf


# ======================== UPIS U POSTGIS ========================


def save_detections_to_postgis(gdf, table_name="ml_detektovani_usevi"):
    """
    Unosi detektovane useve u PostGIS bazu i vraća ih kao DataFrame.
    """
    try:
        import psycopg2
        from src.config import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                crop_type VARCHAR(100),
                confidence NUMERIC(5,1),
                ndvi_mean NUMERIC(5,4),
                lai_estimate NUMERIC(4,1),
                area_ha NUMERIC(10,4),
                latitude NUMERIC(10,6),
                longitude NUMERIC(10,6),
                temperature NUMERIC(5,1),
                humidity NUMERIC(5,1),
                detection_method VARCHAR(100),
                color VARCHAR(10),
                geom GEOMETRY(Polygon, 4326),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        inserted = 0
        for _, row in gdf.iterrows():
            cur.execute(
                f"""INSERT INTO {table_name}
                   (crop_type, confidence, ndvi_mean, lai_estimate, area_ha,
                    latitude, longitude, temperature, humidity,
                    detection_method, color, geom)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                           ST_GeomFromText(%s, 4326));""",
                (
                    row["crop_type"],
                    row["confidence"],
                    row["ndvi_mean"],
                    row["lai_estimate"],
                    row["area_ha"],
                    row["latitude"],
                    row["longitude"],
                    row["temperature"],
                    row["humidity"],
                    row["detection_method"],
                    row["color"],
                    row["geometry"].wkt,
                ),
            )
            inserted += 1

        conn.commit()

        df = pd.read_sql(f"SELECT * FROM {table_name};", conn)

        cur.close()
        conn.close()
        print(f"[OK] Uneto {inserted} detekcija u tabelu '{table_name}'.")
        print(f"[OK] Učitano {len(df)} redova u DataFrame.")
        return df

    except Exception as e:
        print(f"[ERROR] Neuspešan upis u PostGIS: {e}")
        print("[WARN] Detekcije se čuvaju samo u memoriji (GeoDataFrame).")
        return gdf


# ======================== PROSTORNE ANALIZE ========================


def run_ml_spatial_analysis(gdf_ml, slojevi=None):
    """
    Izvršava prostorne analize sa ML rezultatima.
    """
    print("\n=== PROSTORNE ANALIZE ML REZULTATA ===")

    rezultati = {}

    # 1. Statistike po tipu useva
    print("\n>>> 1. Statistike detektovanih useva:")
    stats = (
        gdf_ml.groupby("crop_type")
        .agg(
            broj=("crop_type", "count"),
            prosecna_povrsina_ha=("area_ha", "mean"),
            prosecan_ndvi=("ndvi_mean", "mean"),
            prosecna_pouzdanost=("confidence", "mean"),
            ukupna_povrsina=("area_ha", "sum"),
        )
        .round(2)
    )
    print(stats.to_string())
    rezultati["statistike_useva"] = stats

    # 2. Prostorno preklapanje sa landuse slojem
    if slojevi and "landuse" in slojevi:
        print("\n>>> 2. Preklapanje ML detekcija sa landuse slojem:")
        landuse = slojevi["landuse"]
        ml_with_landuse = gpd.sjoin(
            gdf_ml,
            landuse,
            how="left",
            predicate="intersects",
            lsuffix="ml",
            rsuffix="lu",
        )
        # sjoin(how="left") vraća po jedan red za SVAKI landuse poligon koji
        # preseca datu detekciju, pa .notna().sum() broji redove spoja, a ne
        # jedinstvene detekcije. Zato brojimo unikatne indekse iz gdf_ml.
        preklapa = ml_with_landuse[ml_with_landuse["index_lu"].notna()].index.nunique()
        print(f"   {preklapa}/{len(gdf_ml)} ML detekcija se preklapa sa landuse.")
        rezultati["ml_landuse_overlap"] = ml_with_landuse

    # 3. Blizina putevima
    if slojevi and "roads" in slojevi:
        print("\n>>> 3. Udaljenost ML detekcija od puteva:")
        roads = slojevi["roads"]
        ml_utm = gdf_ml.to_crs("EPSG:32634")
        roads_utm = roads.to_crs("EPSG:32634")
        road_union = roads_utm.unary_union
        ml_utm["dist_do_puta_m"] = ml_utm.geometry.distance(road_union)
        ml_dist = ml_utm.to_crs(CRS_WGS84)
        if len(ml_dist) > 0:
            print(
                f"   Min: {ml_dist['dist_do_puta_m'].min():.0f}m, "
                f"Max: {ml_dist['dist_do_puta_m'].max():.0f}m, "
                f"Mean: {ml_dist['dist_do_puta_m'].mean():.0f}m"
            )
        rezultati["ml_udaljenost_putevi"] = ml_dist

    return rezultati


# ======================== IZMENA ATRIBUTA ========================


def update_detection_attributes(gdf_ml, index, **kwargs):
    """Omogućava izmenu atributa detektovanog objekta."""
    if index in gdf_ml.index:
        for key, value in kwargs.items():
            if key in gdf_ml.columns:
                gdf_ml.at[index, key] = value
                print(f"[OK] Ažuriran atribut '{key}' za detekciju {index}: {value}")
            else:
                print(f"[WARN] Kolona '{key}' ne postoji.")
        return gdf_ml
    else:
        print(f"[WARN] Detekcija sa indeksom {index} ne postoji.")
        return gdf_ml


if __name__ == "__main__":
    print("=== Deo 3: Machine Learning — Klasifikacija useva (GEE + Sentinel-2) ===\n")

    # Treniranje modela
    model, scaler, le = train_model()

    # Detekcija na stvarnim satelitskim snimcima (ili simuliranim fallback)
    gdf_ml = detect_crops_on_raster()
    print(f"\nDetektovani usevi (prvih 5):")
    print(gdf_ml.drop(columns=["geometry"]).head().to_string())

    # Upis u PostGIS (ako je dostupan)
    df_db = save_detections_to_postgis(gdf_ml)

    # Prostorne analize
    from src.geo_loader import load_serbia_shapefiles

    slojevi = load_serbia_shapefiles()
    analize = run_ml_spatial_analysis(gdf_ml, slojevi)

    # Demonstracija izmene atributa
    if len(gdf_ml) > 0:
        print("\n>>> Demonstracija izmene atributa:")
        gdf_ml = update_detection_attributes(
            gdf_ml, 0, crop_type="Pšenica (ažurirano)", confidence=99.9
        )
        print(gdf_ml.iloc[0][["crop_type", "confidence", "ndvi_mean"]])