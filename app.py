"""
Flask web aplikacija za Evidenciju i Analizu Poljoprivrednih Površina — Srem.

Integriše sva tri dela projekta:
  Deo 1 – PostgreSQL/PostGIS baza, CRUD, JOIN upiti
  Deo 2 – GIS: shapefile slojevi, overlay tehnike, prostorni upiti, raster
  Deo 3 – ML: klasifikacija useva, vektorski izlaz, prostorne analize
"""

import warnings
warnings.filterwarnings("ignore")

import os
import json
import sys
import pandas as pd
import geopandas as gpd
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory,
    redirect,
    url_for,
)

# Dodaj src folder na path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import DATA_DIR, SREM_BOUNDS, SREM_CENTER, CRS_WGS84
from src.db_setup import setup_database, insert_sample_data, get_connection
from src.db_crud_queries import (
    load_all_to_dataframes,
    run_join_queries,
    read_all,
    insert_row,
    update_row,
    delete_row,
)
from src.geo_loader import (
    load_serbia_shapefiles,
    merge_shp_with_db,
    create_ndvi_demo_raster,
    get_ndvi_tile_url
)
from src.geo_overlay import run_all_overlay_demos, summarize_overlay_results
from src.map_viewer import create_interactive_map
from src.ml_crop_detector import (
    train_model,
    detect_crops_on_raster,
    save_detections_to_postgis,
    run_ml_spatial_analysis,
    update_detection_attributes,
    load_trained_model,
)

app = Flask(__name__, template_folder="templates", static_folder="static")

# Globalni keš podataka (osvežava se po potrebi)
CACHE = {
    "db_dataframes": None,
    "slojevi": None,
    "overlay_rezultati": None,
    "ml_gdf": None,
    "ml_analize": None,
    "raster_path": None,
    "merged_df": None,
    "join_results": None,
}


# =============================================================
# POMOĆNE FUNKCIJE
# =============================================================


def _init_all_data():
    """Inicijalizuje sve podatke i kešira ih (samo jednom po pokretanju)."""
    if CACHE.get("_initialized", False):
        return
    CACHE["_initialized"] = True
    
    print("[INIT] Inicijalizacija svih podataka...")

    if CACHE["db_dataframes"] is None:
        try:
            CACHE["db_dataframes"] = load_all_to_dataframes()
            print("[OK] Podaci učitani iz baze.")
        except Exception as e:
            print(f"[WARN] Baza nije dostupna ({e}). Aplikacija radi u demo režimu.")
            CACHE["db_dataframes"] = {}

    if CACHE["slojevi"] is None:
        CACHE["slojevi"] = load_serbia_shapefiles()
        if CACHE["db_dataframes"]:
            try:
                CACHE["merged_df"] = merge_shp_with_db(
                    CACHE["slojevi"], CACHE["db_dataframes"]
                )
            except Exception as e:
                print(f"[WARN] Spajanje sa bazom nije uspelo: {e}")
                CACHE["merged_df"] = None
        else:
            CACHE["merged_df"] = None

    if CACHE["raster_path"] is None:
        CACHE["raster_path"] = create_ndvi_demo_raster()

    if CACHE["overlay_rezultati"] is None:
        CACHE["overlay_rezultati"] = run_all_overlay_demos(CACHE["slojevi"])

    if CACHE["ml_gdf"] is None:
        model, scaler, le = load_trained_model()
        CACHE["ml_gdf"] = detect_crops_on_raster(CACHE["raster_path"])
        try:
            ml_df = save_detections_to_postgis(CACHE["ml_gdf"])
            if isinstance(ml_df, pd.DataFrame):
                CACHE["ml_df"] = ml_df
        except Exception as e:
            print(f"[WARN] ML upis u PostGIS nije uspeo: {e}")
            CACHE["ml_df"] = CACHE["ml_gdf"]

    if CACHE["ml_analize"] is None:
        CACHE["ml_analize"] = run_ml_spatial_analysis(CACHE["ml_gdf"], CACHE["slojevi"])

    if CACHE["join_results"] is None:
        try:
            CACHE["join_results"] = run_join_queries()
            print("[OK] JOIN upiti izvršeni.")
        except Exception as e:
            print(f"[WARN] JOIN upiti nisu uspeli (baza nedostupna): {e}")
            CACHE["join_results"] = {}

    # Generiši interaktivnu mapu
    ndvi_tile_url = get_ndvi_tile_url()
    try:
        create_interactive_map(
            slojevi=CACHE["slojevi"],
            overlay_rezultati=CACHE["overlay_rezultati"],
            ml_vektor=CACHE["ml_gdf"],
            raster_path=CACHE["raster_path"],
            ndvi_tile_url=ndvi_tile_url,
            output_file="data/interactive_map.html",
        )
        print("[OK] Mapa je regenerisana.")
    except Exception as e:
        print(f"[WARN] Mapa nije kreirana: {e}")

    print("[INIT] Inicijalizacija završena.")


def _refresh_cache():
    """Osveži sve keširane podatke."""
    for key in CACHE:
        CACHE[key] = None
    CACHE["_initialized"] = False
    _init_all_data()


def _df_to_dict(df):
    """Konvertuje DataFrame u listu rečnika pogodnih za JSON."""
    if df is None or len(df) == 0:
        return []
    df_clean = df.copy()
    # Ukloni geometrijske kolone koje nisu serijalizabilne
    cols_to_drop = [
        c for c in df_clean.columns if c in ("geom", "geometry", "geom_tacke")
    ]
    df_clean.drop(columns=cols_to_drop, errors="ignore", inplace=True)
    # Konvertuj Timestamp/Datetime u string
    for col in df_clean.columns:
        if pd.api.types.is_datetime64_any_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].dt.strftime("%Y-%m-%d %H:%M:%S")
        elif df_clean[col].dtype == "object":
            # Konvertuj sve numpy/int64 u standardne Python tipove
            try:
                # Pokušaj prvo konvertovati u brojeve gde je moguće
                df_clean[col] = df_clean[col].astype(str)
            except Exception:
                pass

    return df_clean.fillna("").to_dict(orient="records")


def _get_columns_for_table(table_name):
    """Vraća kolone za tabelu (osim serijskog/geom)."""
    skip = {"id_" + table_name.rstrip("s")} if table_name.endswith("s") else {"id"}
    skip.add("geom")
    skip.add("geom_tacke")
    skip.add("created_at")
    skip.add("datum_unosa")

    if table_name in CACHE["db_dataframes"]:
        df = CACHE["db_dataframes"][table_name]
        return [c for c in df.columns if c not in skip]
    return []


# =============================================================
# RUTE
# =============================================================


@app.route("/")
def index():
    """Početna stranica — dashboard."""
    _init_all_data()
    return render_template("index.html")


@app.route("/api/init", methods=["POST"])
def api_init():
    """Inicijalizacija baze i podataka."""
    try:
        setup_database()
        insert_sample_data()
        _refresh_cache()
        return jsonify({"status": "ok", "message": "Baza i podaci su inicijalizovani."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/tables/<table_name>")
def api_table_data(table_name):
    """Vraća podatke za datu tabelu kao JSON."""
    _init_all_data()
    dfs = CACHE["db_dataframes"]
    if table_name in dfs:
        return jsonify(
            {
                "data": _df_to_dict(dfs[table_name]),
                "columns": list(dfs[table_name].columns),
            }
        )
    return jsonify({"error": f"Tabela '{table_name}' ne postoji."}), 404


@app.route("/api/tables", methods=["GET"])
def api_all_tables():
    """Vraća spisak svih tabela."""
    _init_all_data()
    tables = {}
    for name, df in CACHE["db_dataframes"].items():
        tables[name] = {"row_count": len(df), "columns": list(df.columns)}
    return jsonify(tables)


@app.route("/api/crud", methods=["POST"])
def api_crud():
    """CRUD operacije: insert, update, delete."""
    _init_all_data()
    data = request.get_json()
    action = data.get("action")
    table = data.get("table")

    try:
        if action == "insert":
            columns = data.get("columns", [])
            values = data.get("values", [])
            insert_row(table, columns, values)
            message = f"Novi red unet u {table}."

        elif action == "update":
            set_col = data["set_column"]
            new_val = data["new_value"]
            where_col = data["where_column"]
            where_val = data["where_value"]
            update_row(table, set_col, new_val, where_col, where_val)
            message = f"Ažuriran red u {table}."

        elif action == "delete":
            where_col = data["where_column"]
            where_val = data["where_value"]
            delete_row(table, where_col, where_val)
            message = f"Obrisan red iz {table}."

        else:
            return jsonify(
                {"status": "error", "message": f"Nepoznata akcija: {action}"}
            ), 400

        # Osveži keš nakon CRUD operacije
        CACHE["db_dataframes"] = load_all_to_dataframes()
        return jsonify({"status": "ok", "message": message})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/joins")
def api_join_queries():
    """Vraća rezultate JOIN upita."""
    _init_all_data()
    rezultati = {}
    for naziv, df in CACHE["join_results"].items():
        rezultati[naziv] = _df_to_dict(df)
    return jsonify(rezultati)


@app.route("/api/overlays")
def api_overlay_results():
    """Vraća rezultate overlay analiza."""
    _init_all_data()
    rezultati = {}
    for naziv, gdf in CACHE.get("overlay_rezultati", {}).items():
        if gdf is not None and len(gdf) > 0:
            try:
                #rez = _df_to_dict(gdf.drop(columns=["geometry"], errors="ignore"))
                #novo:
                gdf_clean = pd.DataFrame(gdf.drop(columns=[c for c in gdf.columns 
                    if hasattr(gdf[c], 'geom_type') or c == 'geometry'], errors="ignore"))
                rez = _df_to_dict(gdf_clean)

                rezultati[naziv] = {"count": len(gdf), "data": rez[:5]}
            except Exception:
                rezultati[naziv] = {"count": len(gdf), "data": []}
    return jsonify(rezultati)


@app.route("/api/ml/stats")
def api_ml_stats():
    """Vraća ML statistike i podatke."""
    _init_all_data()
    ml_gdf = CACHE.get("ml_gdf")

    if ml_gdf is None or len(ml_gdf) == 0:
        return jsonify({"error": "Nema ML podataka."}), 404

    # Detekcije (bez geometrije za API)
    detections = _df_to_dict(ml_gdf.drop(columns=["geometry"], errors="ignore"))

    # Statistike
    if CACHE.get("ml_analize") and "statistike_useva" in CACHE["ml_analize"]:
        stats_df = CACHE["ml_analize"]["statistike_useva"]
        stats = stats_df.reset_index().to_dict(orient="records")
    else:
        stats = []

    return jsonify(
        {
            "detections": detections,
            "total_count": len(ml_gdf),
            "statistics": stats,
        }
    )


@app.route("/api/ml/update", methods=["POST"])
def api_ml_update():
    """Ažuriranje atributa ML detekcije."""
    _init_all_data()
    data = request.get_json()
    det_index = data.get("index")
    attributes = data.get("attributes", {})

    if det_index is None:
        return jsonify(
            {"status": "error", "message": "Nedostaje indeks detekcije."}
        ), 400

    try:
        idx = int(det_index)
        valid_attrs = {}
        for k, v in attributes.items():
            if k in CACHE["ml_gdf"].columns:
                # Konvertuj tipove gde je potrebno
                if k in (
                    "confidence",
                    "ndvi_mean",
                    "area_ha",
                    "temperature",
                    "humidity",
                    "lai_estimate",
                ):
                    try:
                        valid_attrs[k] = float(v)
                    except ValueError:
                        valid_attrs[k] = v
                else:
                    valid_attrs[k] = v

        CACHE["ml_gdf"] = update_detection_attributes(
            CACHE["ml_gdf"], idx, **valid_attrs
        )
        message = f"Ažurirana detekcija {idx}: {valid_attrs}"

        # Ažuriraj i u bazi ako je moguće
        try:
            df_updated = save_detections_to_postgis(CACHE["ml_gdf"])
            if isinstance(df_updated, pd.DataFrame):
                CACHE["ml_df"] = df_updated
        except Exception as e:
            print(f"[WARN] Ažuriranje PostGIS nije uspelo: {e}")

        # Regeneriši mapu
        ndvi_tile_url = get_ndvi_tile_url()
        create_interactive_map(
            slojevi=CACHE["slojevi"],
            overlay_rezultati=CACHE["overlay_rezultati"],
            ml_vektor=CACHE["ml_gdf"],
            raster_path=CACHE["raster_path"],
            ndvi_tile_url=ndvi_tile_url,
            output_file="data/interactive_map.html",
        )

        return jsonify({"status": "ok", "message": message})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/ml/spatial")
def api_ml_spatial():
    """Vraća rezultate prostornih analiza ML podataka."""
    _init_all_data()
    analize = CACHE.get("ml_analize", {})
    rezultati = {}

    for k, v in analize.items():
        if isinstance(v, pd.DataFrame):
            rezultati[k] = _df_to_dict(v.reset_index())[:10]
        elif isinstance(v, gpd.GeoDataFrame):
            rezultati[k] = _df_to_dict(
                pd.DataFrame(v.drop(columns=["geometry"], errors="ignore"))
            )[:10]

    return jsonify(rezultati)


@app.route("/api/slojevi")
def api_slojevi():
    """Vraća informacije o GIS slojevima."""
    _init_all_data()
    slojevi_info = {}
    for naziv, gdf in CACHE.get("slojevi", {}).items():
        geom_types = list(gdf.geometry.geom_type.unique()) if len(gdf) > 0 else []
        slojevi_info[naziv] = {
            "count": len(gdf),
            "crs": str(gdf.crs),
            "geom_types": [str(g) for g in geom_types],
            "columns": [c for c in gdf.columns if c != "geometry"],
        }
    return jsonify(slojevi_info)


@app.route("/map")
def view_map():
    """Prikazuje interaktivnu mapu."""
    map_path = os.path.join(DATA_DIR, "interactive_map.html")
    if not os.path.exists(map_path):
        _init_all_data()
    return send_from_directory(DATA_DIR, "interactive_map.html")


@app.route("/api/config")
def api_config():
    """Vraća konfiguraciju (granice Srema, centar)."""
    return jsonify(
        {
            "srem_bounds": SREM_BOUNDS,
            "srem_center": SREM_CENTER,
            "crs": CRS_WGS84,
        }
    )


@app.route("/api/dashboard")
def api_dashboard():
    """Vraća sumarne informacije za dashboard."""
    _init_all_data()
    dfs = CACHE["db_dataframes"]
    ml_gdf = CACHE.get("ml_gdf")
    slojevi = CACHE.get("slojevi")

    return jsonify(
        {
            "tables": {name: {"row_count": len(df)} for name, df in dfs.items()},
            "ml_total_detections": len(ml_gdf) if ml_gdf is not None else 0,
            "ml_crop_types": (
                list(ml_gdf["crop_type"].unique())
                if ml_gdf is not None and len(ml_gdf) > 0
                else []
            ),
            "gis_layers": list(slojevi.keys()) if slojevi else [],
            "overlay_count": len(CACHE.get("overlay_rezultati", {})),
            "join_queries_count": len(CACHE.get("join_results", {})),
        }
    )


# =============================================================
# POKRETANJE
# =============================================================


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  Aplikacija za Evidenciju i Analizu Poljoprivrednih Površina")
    print("  Područje: Srem")
    print("=" * 70 + "\n")

    # Inicijalizuj podatke pri pokretanju
    try:
        _init_all_data()
    except Exception as e:
        print(f"[WARN] Inicijalizacija nije u potpunosti uspela: {e}")
        print("[INFO] Aplikacija će se pokrenuti. Kliknite 'Inicijalizuj bazu' u UI.")
    #privremena izmena
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)
