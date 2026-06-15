"""
Deo 3 – Python ML: Mašinsko učenje za detekciju useva/objekata na snimcima,
konverziju u vektorski format, upis u PostGIS i prikaz na mapi.
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
)


# ======================== TRENIRANJE MODELA ========================


def create_training_data():
    """
    Kreira simulirane trening podatke za klasifikaciju useva
    na osnovu NDVI, temperature, vlažnosti i spektralnih karakteristika.
    U realnom scenariju, ovi podaci bi dolazili iz Sentinel-2 snimaka.
    """
    np.random.seed(42)
    n_samples = 500

    # Tipovi useva za klasifikaciju
    crop_types = ["Pšenica", "Kukuruz", "Suncokret", "Soja", "Ječam", "Krompir"]

    data = []
    for i in range(n_samples):
        crop = np.random.choice(crop_types)

        # Generiši realne karakteristike za svaki tip useva
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
                "ndwi": np.random.normal(0.15, 0.08),  # Water index
                "savi": np.clip(ndvi * 0.8 + 0.1, 0, 1),  # Soil-adjusted VI
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
    Simulira detekciju useva na satelitskim snimcima.
    U realnom scenariju, ovo bi analiziralo raster (npr. Sentinel-2)
    i segmentiralo poljoprivredne parcele.

    Vraća GeoDataFrame sa detektovanim usevima.
    """
    if raster_path and os.path.exists(raster_path):
        print(f"[INFO] Analiza rastera: {raster_path}")
    else:
        print("[INFO] Nema rastera. Koristim simulirane detekcije.")

    model, scaler, le = load_trained_model()

    np.random.seed(123)
    n_detections = 25

    # Simulirane lokacije detektovanih useva (Vojvodina)
    # Generišemo "snimke" — manje regione unutar parcela
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
        # Simuliraj spektralne karakteristike
        ndvi = np.random.uniform(0.5, 0.9)
        temp = np.random.uniform(10, 30)
        hum = np.random.uniform(30, 80)
        red = np.random.uniform(0.03, 0.15)
        nir = np.random.uniform(0.30, 0.55)
        ndwi = np.random.uniform(0.05, 0.25)
        savi = np.clip(ndvi * 0.8 + np.random.uniform(0.05, 0.15), 0, 1)

        # Predikcija
        features = np.array([[ndvi, temp, hum, red, nir, ndwi, savi]])
        features_scaled = scaler.transform(features)
        pred_class = le.inverse_transform(model.predict(features_scaled))[0]
        proba = model.predict_proba(features_scaled).max()

        # Geografska lokacija u Sremu
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
            "detection_method": "RandomForest",
            "color": crop_colors.get(pred_class, "#999"),
            "geometry": geom,
        }
        detections.append(detection)

    gdf = gpd.GeoDataFrame(detections, crs=CRS_WGS84)
    print(f"\n[OK] Detektovano {len(gdf)} objekata.")

    # Prikaz distribucije detekcija po tipu useva
    print("\nDistribucija detektovanih useva:")
    for crop, count in gdf["crop_type"].value_counts().items():
        print(f"  {crop}: {count}")

    return gdf


# ======================== UPIS U POSTGIS ========================


def save_detections_to_postgis(gdf, table_name="ml_detektovani_usevi"):
    """
    Unosi detektovane useve u PostGIS baz i vraća ih kao DataFrame.
    """
    try:
        import psycopg2
        from src.config import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Kreiranje tabele ako ne postoji
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
                detection_method VARCHAR(50),
                color VARCHAR(10),
                geom GEOMETRY(Polygon, 4326),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Unos podataka
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

        # Učitavanje u DataFrame
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
    Izvršava prostorne analize sa ML rezultatima:
    - Preklapanje detekcija sa katastarskim parcelama
    - Statistike po tipu useva
    - Analiza blizine objekata (silosi, putevi)
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
        # Spaijalni join: koje ML detekcije padaju na landuse poligone
        ml_with_landuse = gpd.sjoin(
            gdf_ml,
            landuse,
            how="left",
            predicate="intersects",
            lsuffix="ml",
            rsuffix="lu",
        )
        preklapa = ml_with_landuse["index_lu"].notna().sum()
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
        print(
            f"   Min: {ml_dist['dist_do_puta_m'].min():.0f}m, "
            f"Max: {ml_dist['dist_do_puta_m'].max():.0f}m, "
            f"Mean: {ml_dist['dist_do_puta_m'].mean():.0f}m"
        )
        rezultati["ml_udaljenost_putevi"] = ml_dist

    return rezultati


# ======================== IZMENA ATRIBUTA ========================


def update_detection_attributes(gdf_ml, index, **kwargs):
    """
    Omogućava izmenu atributa detektovanog objekta.
    """
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
    print("=== Deo 3: Machine Learning — Klasifikacija useva ===\n")

    # Treniranje modela
    model, scaler, le = train_model()

    # Detekcija na simuliranim snimcima
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
    print("\n>>> Demonstracija izmene atributa:")
    gdf_ml = update_detection_attributes(
        gdf_ml, 0, crop_type="Pšenica (ažurirano)", confidence=99.9
    )
    print(gdf_ml.iloc[0][["crop_type", "confidence", "ndvi_mean"]])
