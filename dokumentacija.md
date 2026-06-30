# Dokumentacija projekta: Monitoring poljoprivrednih parcela — Srem

## 1. Opis projekta

Ovaj projekat predstavlja **GIS–ML web aplikaciju za evidenciju i analizu poljoprivrednih površina na području Srema**. Aplikacija integriše tri ključne celine:

1. **Baza podataka (PostgreSQL/PostGIS)** – skladištenje podataka o parcelama, vlasnicima, kulturama i agrotehničkim merama, CRUD operacije i složeni JOIN upiti za izveštavanje.
2. **GIS (Geografski Informacioni Sistem)** – učitavanje i obrada vektorskih slojeva (shapefile), prostorne analize (overlay tehnike — buffer, clip, union, intersection, difference, within, intersects, overlaps, distance), rad sa rasterskim podlogama (NDVI) i generisanje interaktivne mape.
3. **Mašinsko učenje (ML)** – treniranje Random Forest klasifikatora za detekciju tipova useva na osnovu multispektralnih karakteristika (NDVI, temperatura, vlažnost, spektralni opsezi), konverzija rezultata u vektorski format, upis u PostGIS i prostorna analiza detektovanih useva.

**Tehnologije**: Python 3.10+, Flask, GeoPandas, Shapely, Folium, Rasterio, scikit-learn, psycopg2, PostgreSQL + PostGIS.

**Oblast istraživanja**: Srem (između Dunava na severu i Save na jugu, zapadno od Beograda). Opštine: Sremska Mitrovica, Ruma, Šid, Inđija, Stara Pazova, Irig, Pećinci.

---

## 2. Struktura projekta

```
ogi_projekat/
├── app.py                    # Glavna Flask web aplikacija (API rute, inicijalizacija)
├── main.py                   # Alternativna ulazna tačka (CLI režim)
├── pyproject.toml            # Konfiguracija projekta i spisak zavisnosti
├── README.md                 # Kratak opis projekta
├── dokumentacija.md          # Ova dokumentacija
├── .gitignore                # Git ignore pravila
├── .python-version           # Verzija Python-a
├── data/                     # Skladište generisanih podataka
│   ├── interactive_map.html  # Generisana interaktivna mapa (Folium)
│   └── ndvi_raster.tif       # Simulirani NDVI raster za Srem
├── models/                   # Sačuvani ML modeli
│   ├── crop_classifier.pkl   # Random Forest klasifikator useva
│   ├── scaler.pkl            # StandardScaler za normalizaciju ulaznih karakteristika
│   └── label_encoder.pkl     # LabelEncoder za mapiranje klasa useva
├── src/                      # Izvorni kod aplikacije
│   ├── config.py             # Konfiguracija (putanje, granice Srema, DB parametri)
│   ├── db_setup.py           # Kreiranje šeme baze i unos demo podataka
│   ├── db_crud_queries.py    # CRUD operacije i složeni JOIN upiti
│   ├── geo_loader.py         # Učitavanje shapefile slojeva i NDVI rastera
│   ├── geo_overlay.py        # Overlay analize i prostorni upiti
│   ├── map_viewer.py         # Generisanje interaktivne Folium mape
│   └── ml_crop_detector.py   # ML model: treniranje, detekcija, upis i analiza
├── static/                   # Statički fajlovi (CSS, JS, slike)
└── templates/
    └── index.html            # HTML šablon za dashboard (Flask + Jinja2)
```

---

## 3. Opis svakog dela (modula)

### 3.1. `src/config.py` — Centralna konfiguracija

Definiše sve globalne parametre aplikacije:

- **Putanje do podataka**: `DATA_DIR` (`data/`), `MODELS_DIR` (`models/`).
- **Shapefile putanje** (`SHP_PATHS`): mape koje povezuju nazive slojeva (`landuse`, `buildings`, `roads`, `waterways`, `natural`) sa očekivanim putanjama Geofabrik .shp fajlova. Ako fajlovi ne postoje, aplikacija automatski generiše demo geopodatke.
- **Granice Srema** (`SREM_BOUNDS`): Bounding box definisan koordinatama `west=19.05`, `east=20.35`, `south=44.73`, `north=45.25` (WGS84). Služi za klipovanje svih podataka na područje Srema.
- **Centar Srema** (`SREM_CENTER`): `[44.99, 19.70]` — koristi se za centriranje interaktivne mape.
- **CRS definicije**: `CRS_WGS84 = "EPSG:4326"`, `CRS_UTM34N = "EPSG:32634"` (metarski sistem za tačne prostorne analize).
- **DB konfiguracija** (`DB_CONFIG`): parametri za konekciju na PostgreSQL/PostGIS bazu (host, port, baza, korisnik, lozinka).
- **ML putanje**: `ML_MODEL_PATH`, `ML_SCALER_PATH`, `ML_LABEL_ENCODER_PATH` — lokacije sačuvanih modela u `models/` folderu.

---

### 3.2. `src/db_setup.py` — Inicijalizacija baze podataka (Deo 1)

Upravlja kreiranjem šeme baze i unosom demonstracionih podataka:

- **`setup_database()`**: Kreira PostgreSQL/PostGIS bazu (ako ne postoji) i sve potrebne tabele sa `GEOMETRY` kolonama:
  - `parcele` — poljoprivredne parcele (ID, broj, površina, kultura, geometrija poligona)
  - `vlasnici` — vlasnici parcela (ime, prezime, JMBG, kontakt)
  - `kulture` — šifarnik poljoprivrednih kultura (naziv, sezona, prosečan prinos)
  - `agrotehnicke_mere` — evidencija mera (đubrenje, navodnjavanje, zaštita, datum)
  - `prinosi` — godišnji prinosi po parceli (količina, jedinica mere)
  - `parcele_vlasnici` — više-prema-više veza parcela–vlasnik (sa udelom)
  - `ml_detektovani_usevi` — ML detekcije (ako se koristi automatska detekcija)

- **`insert_sample_data()`**: Popunjava tabele demonstracionim podacima (parcele u Sremu, vlasnici, kulture, agrotehničke mere, prinosi), uključujući `ST_GeomFromText` za geometrijske kolone.

- **`get_connection()`**: Vraća `psycopg2` konekciju na bazu.

---

### 3.3. `src/db_crud_queries.py` — CRUD i JOIN upiti (Deo 1)

Implementira sve CRUD (Create, Read, Update, Delete) operacije i složene upite:

- **`load_all_to_dataframes()`**: Učitava sve tabele iz baze u `pandas.DataFrame` objekte. Vraća rečnik gde je ključ naziv tabele, a vrednost DataFrame.

- **`read_all(table_name)`**: Vraća sve redove iz zadate tabele.

- **`insert_row(table, columns, values)`**: Unosi novi red u tabelu sa zadatim kolonama i vrednostima. Koristi parametrizovane upite (zaštita od SQL injection-a).

- **`update_row(table, set_col, new_val, where_col, where_val)`**: Ažurira vrednost u koloni `set_col` na `new_val` za red gde je `where_col = where_val`.

- **`delete_row(table, where_col, where_val)`**: Briše red iz tabele gde je zadovoljen uslov.

- **`run_join_queries()`**: Izvršava više JOIN upita za analizu podataka:
  - Parcele sa vlasnicima (INNER JOIN preko `parcele_vlasnici`)
  - Parcele sa prinosima i kulturama
  - Agrotehničke mere po parceli i kulturi
  - Ukupni prinosi po vlasniku (agregacija)
  - Parcele bez agrotehničkih mera (LEFT JOIN sa NULL proverom)
  - Vraća rečnik `{naziv_upita: DataFrame}`.

---

### 3.4. `src/geo_loader.py` — Učitavanje GIS podataka (Deo 2)

Zadužen za učitavanje i pripremu geoprostornih podataka:

- **`load_serbia_shapefiles()`**: Učitava OSM (OpenStreetMap) shapefile slojeve sa Geofabrik servera. Ako fajlovi nisu prisutni (putanje definisane u `SHP_PATHS`), automatski kreira **demo geopodatke** unutar granica Srema:
  - **`landuse`** (10 poligona) — poljoprivredne površine: njive, voćnjaci, vinogradi, pašnjaci, livade
  - **`buildings`** (8 tačaka) — poljoprivredni objekti: silosi, hangari, staklenici, farme
  - **`roads`** (5 linija) — lokalni putevi između opština
  - **`waterways`** (3 linije) — Dunav, Sava, Bosut
  - **`natural`** (4 poligona) — prirodne oblasti: Fruška Gora, Obedska bara, Zasavica
  - Svi slojevi su u WGS84 koordinatnom sistemu (EPSG:4326).

- **`merge_shp_with_db(gdf_slojevi, db_dataframes)`**: Prostorno spaja (spatial join) sloj `landuse` sa parcelama iz baze (`parcele` tabela). Koristi `gpd.sjoin` sa `predicate="intersects"` — pronalazi koje parcele iz baze se preklapaju sa landuse poligonima. Geometrija iz baze se prvo konvertuje iz WKB formata pomoću `shapely.wkb.loads`.

- **`create_ndvi_demo_raster()`**: Generiše simulirani NDVI (Normalized Difference Vegetation Index) raster u GeoTIFF formatu za područje Srema:
  - Rezolucija: 500×400 piksela
  - Vrednosti NDVI: 0.0–1.0 (nasumične sa pojačanim vrednostima u centralnom delu — poljoprivredne površine — i na Fruškoj Gori — šuma)
  - Čuva se kao `data/ndvi_raster.tif`
  - Ako fajl već postoji, ne regeneriše se.

---

### 3.5. `src/geo_overlay.py` — Overlay tehnike i prostorni upiti (Deo 2)

Implementira 9 GIS overlay i prostornih analiza nad slojevima:

1. **Buffer (zaštitni pojas)**:
   - Buffer od 200 m oko puteva (`buffer_putevi_200m`)
   - Buffer od 500 m oko objekata (`buffer_objekti_500m`)
   - Pre buffera se vrši reprojekcija u UTM 34N (EPSG:32634) radi metarske preciznosti.

2. **Clip (isecanje)**: Iseca landuse poligone unutar unije svih buffer zona puteva. Rezultat: `clip_landuse_putevi`.

3. **Union (unija)**: Spaja sve landuse i natural poligone u jedinstvenu geometriju (`union_landuse_natural`). Računa ukupnu površinu.

4. **Intersection (presek)**: Presek landuse sloja sa buffer zonama puteva (`intersection_landuse_putevi`). Koristi `gpd.overlay(how="intersection")`.

5. **Difference (razlika/erase)**: Landuse poligoni koji su **van** zone puteva (`difference_landuse_van_putevi`). Koristi `gpd.overlay(how="difference")`.

6. **Within (unutar)**: Proverava koji objekti (tačke) se nalaze **unutar** landuse poligona. Dodaje kolonu `within_landuse` sa boolean vrednostima.

7. **Intersects (presecanje)**: Pronalazi landuse poligone koji **presecaju** prirodne oblasti. Za svaki par računa geometriju preseka.

8. **Overlaps (preklapanje)**: Detektuje landuse poligone koji se međusobno **preklapaju**. Iterira kroz sve parove poligona (O(n²)).

9. **Distance (udaljenost)**: Računa **minimalnu udaljenost** svakog objekta od najbližeg vodotoka (u metrima), koristeći UTM projekciju.

Rezultati se vraćaju kao rečnik `{naziv_analize: GeoDataFrame}` i koriste se za prikaz na interaktivnoj mapi i u web API-ju.

---

### 3.6. `src/map_viewer.py` — Interaktivna mapa (Deo 2)

Generiše interaktivnu HTML mapu koristeći biblioteku **Folium**:

- **Raster podloga (NDVI)**: Prikazuje NDVI raster kao `ImageOverlay` sloj sa zelenom kolornom mapom. Koristi `rasterio` za čitanje GeoTIFF-a.

- **Vektorski slojevi** — svaki sa prilagođenom simbologijom:
  - **Landuse** (poligoni): tamno zelena (`#228B22`), 40% providnost, tooltip sa nazivom i tipom
  - **Buildings** (tačke): markeri sa `fa-home` ikonom u crvenoj boji, popup sa nazivom i tipom
  - **Roads** (linije): zlatna boja (`#FFD700`), debljina 3, tooltip sa nazivom puta
  - **Waterways** (linije): plava boja (`#1E90FF`), debljina 3
  - **Natural** (poligoni): svetlo zelena (`#32CD32`), 30% providnost

- **Overlay rezultati**: Svaka overlay analiza dobija svoj `FeatureGroup` sloj sa karakterističnom bojom. Slojevi su inicijalno skriveni (`show=False`).

- **ML detekcije**: Poseban sloj sa detektovanim usevima — `FeatureGroup` sa nazivom "ML: Detektovani usevi". Svaki poligon je obojen prema tipu useva (npr. pšenica = `#F5DEB3`, kukuruz = `#FFD700`). Tooltip i popup prikazuju tip useva, pouzdanost (confidence %), površinu (ha) i NDVI srednju vrednost.

- **LayerControl**: Omogućava korisniku uključivanje/isključivanje svih slojeva.

- Mapa se čuva kao `data/interactive_map.html` i prikazuje se na `/map` ruti.

---

### 3.7. `src/ml_crop_detector.py` — Mašinsko učenje (Deo 3)

Implementira ceo ML pipeline za klasifikaciju useva:

#### Treniranje modela

- **`create_training_data()`**: Generiše 500 simuliranih uzoraka za 6 tipova useva (**Pšenica, Kukuruz, Suncokret, Soja, Ječam, Krompir**). Svaki tip ima realne distribucije za:
  - `ndvi` — vegetacioni indeks
  - `temperature` — temperatura vazduha (°C)
  - `humidity` — vlažnost vazduha (%)
  - `red_band`, `nir_band` — spektralni opsezi (crveni i bliski infracrveni)
  - `ndwi` — indeks vode
  - `savi` — soil-adjusted vegetation index

- **`train_model()`**:
  - Koristi **Random Forest Classifier** sa 150 stabala, max dubinom 12
  - LabelEncoder za kodiranje klasa, StandardScaler za normalizaciju
  - Podela: 80% trening / 20% test (stratifikovana)
  - Evaluacija: accuracy, classification report (precision, recall, f1-score), confusion matrix, feature importance
  - Čuva model, scaler i label encoder u `models/` folder pomoću `pickle`

- **`load_trained_model()`**: Učitava sačuvani model. Ako model ne postoji, automatski poziva `train_model()`.

#### Detekcija useva

- **`detect_crops_on_raster(raster_path)`**: Simulira detekciju 25 poljoprivrednih objekata na satelitskim snimcima:
  - Generiše nasumične multispektralne karakteristike
  - Koristi trenirani model za predikciju tipa useva (sa confidence vrednošću)
  - Kreira poligone (`shapely.geometry.box`) na nasumičnim lokacijama unutar Srema
  - Računa površinu parcele u hektarima (uz kosinusnu korekciju za geografsku širinu)
  - Vraća `GeoDataFrame` sa kolonama: `crop_type`, `confidence`, `ndvi_mean`, `lai_estimate`, `area_ha`, `temperature`, `humidity`, `detection_method`, `color`, `geometry`

#### Upis u bazu

- **`save_detections_to_postgis(gdf, table_name)`**: Upisuje detekcije u PostGIS tabelu `ml_detektovani_usevi`. Kreira tabelu sa `GEOMETRY(Polygon, 4326)` kolonom ako ne postoji. Koristi `ST_GeomFromText` za unos geometrije. Vraća učitan DataFrame iz baze ili originalni GeoDataFrame ako baza nije dostupna.

#### Prostorne analize ML rezultata

- **`run_ml_spatial_analysis(gdf_ml, slojevi)`**:
  1. **Statistike po tipu useva**: broj detekcija, prosečna površina, prosečan NDVI, prosečna pouzdanost, ukupna površina — grupisanjem po `crop_type`
  2. **Preklapanje sa landuse slojem**: `gpd.sjoin` sa `predicate="intersects"` za utvrđivanje koje ML detekcije padaju na postojeće landuse poligone
  3. **Udaljenost od puteva**: računanje distance svake detekcije do najbližeg puta u metrima (koristeći UTM 34N projekciju)

#### Izmena atributa

- **`update_detection_attributes(gdf_ml, index, **kwargs)`\*\*: Omogućava pojedinačnu izmenu atributa detektovanog objekta (npr. ručna korekcija tipa useva, pouzdanosti, površine). Ažurira GeoDataFrame in-place.

---

### 3.8. `main.py` — Alternativna ulazna tačka (CLI)

Modul koji pokreće aplikaciju iz komandne linije (za razliku od `app.py` koji je Flask server). Služi za demonstraciju i testiranje svih komponenti bez web interfejsa:

- Inicijalizuje bazu (`setup_database`, `insert_sample_data`)
- Učitava podatke u DataFrame-ove
- Izvršava JOIN upite i prikazuje rezultate
- Učitava GIS slojeve i pokreće overlay analize
- Trenira ML model, vrši detekciju i prostorne analize
- Generiše interaktivnu mapu

---

### 3.9. `app.py` — Flask web aplikacija (glavna ulazna tačka)

Centralni modul koji integriše sve komponente u web aplikaciju sa REST API-jem:

#### Arhitektura

- **Flask server** na portu 5000, dostupan na svim interfejsima (`host="0.0.0.0"`)
- Koristi globalni **keš** (`CACHE` rečnik) za čuvanje učitanih podataka između zahteva
- **`_init_all_data()`**: Lazy-load inicijalizacija — učitava podatke iz baze, GIS slojeve, NDVI raster, overlay rezultate, ML detekcije, ML analize i JOIN rezultate po potrebi. Ako neka komponenta nije dostupna (npr. baza), aplikacija nastavlja rad u demo režimu.
- **`_refresh_cache()`**: Resetuje keš i ponovo učitava sve podatke (koristi se nakon CRUD operacija i inicijalizacije baze)

#### API rute

| Ruta                       | Metod | Opis                                                       |
| -------------------------- | ----- | ---------------------------------------------------------- |
| `/`                        | GET   | Dashboard — glavna stranica (`templates/index.html`)       |
| `/api/init`                | POST  | Inicijalizacija baze i demo podataka                       |
| `/api/tables`              | GET   | Spisak svih tabela sa brojem redova i kolonama             |
| `/api/tables/<table_name>` | GET   | Podaci iz zadate tabele (JSON)                             |
| `/api/crud`                | POST  | CRUD operacije (insert, update, delete)                    |
| `/api/joins`               | GET   | Rezultati JOIN upita                                       |
| `/api/overlays`            | GET   | Rezultati overlay analiza (prvih 5 objekata po analizi)    |
| `/api/ml/stats`            | GET   | ML statistike (detekcije, tipovi useva, agregacije)        |
| `/api/ml/update`           | POST  | Ažuriranje atributa ML detekcije                           |
| `/api/ml/spatial`          | GET   | Prostorne analize ML rezultata                             |
| `/api/slojevi`             | GET   | Informacije o GIS slojevima (broj, CRS, tipovi geometrije) |
| `/api/config`              | GET   | Konfiguracija (granice Srema, centar, CRS)                 |
| `/api/dashboard`           | GET   | Sumarne informacije za dashboard                           |
| `/map`                     | GET   | Prikaz interaktivne Folium mape                            |

#### Pomoćne funkcije

- **`_df_to_dict(df)`**: Konvertuje DataFrame u listu rečnika za JSON serijalizaciju. Uklanja geometrijske kolone, konvertuje datetime u string, obrađuje `NaN` vrednosti.

- **`_get_columns_for_table(table_name)`**: Vraća spisak kolona za CRUD formu (bez ID, geometrije i timestamp kolona).

---

### 3.10. `templates/index.html` — Korisnički interfejs

Frontend dashboard stranica koja komunicira sa Flask API-jem:

- **Sekcije**:
  - Inicijalizacija baze (dugme + status)
  - Pregled tabela (dinamički tabovi sa podacima iz baze)
  - CRUD forma za unos/izmenu/brisanje podataka
  - Rezultati JOIN upita
  - Overlay analize (tabelarni prikaz)
  - ML detekcije i statistike (tabela + grafikoni)
  - Link ka interaktivnoj mapi (`/map`)

- Tehnologije: HTML5, CSS3, JavaScript (vanilla), Fetch API za AJAX pozive

---

### 3.11. `pyproject.toml` — Konfiguracija projekta

Definiše metapodatke projekta i sve Python zavisnosti:

- **Naziv**: `ogi-projekat`
- **Python**: `>=3.10`
- **Ključne zavisnosti**:
  - `psycopg2-binary` — PostgreSQL adapter
  - `pandas`, `geopandas` — obrada podataka i geoprostornih podataka
  - `shapely`, `fiona` — geometrijske operacije
  - `matplotlib` — vizuelizacija
  - `folium` — interaktivne mape (Leaflet.js wrapper)
  - `rasterio` — rad sa rasterskim podacima (GeoTIFF)
  - `scikit-learn` — mašinsko učenje (RandomForest)
  - `opencv-python` — obrada slika
  - `numpy` — numeričke operacije
  - `contextily`, `descartes` — dodatne GIS vizuelizacije

---

## 4. Arhitektura i tok podataka

```
┌─────────────────────────────────────────────────────────┐
│                    app.py (Flask API)                    │
│  - REST API rute                                        │
│  - Globalni keš (CACHE)                                 │
│  - Inicijalizacija svih komponenti                      │
└──────────┬──────────────────────────────────────────────┘
           │
    ┌──────┼──────────────────────────────────┐
    │      │                                  │
    ▼      ▼                                  ▼
┌───────────────┐  ┌───────────────────┐  ┌──────────────────┐
│  Deo 1: Baza  │  │  Deo 2: GIS       │  │  Deo 3: ML       │
│               │  │                   │  │                  │
│ db_setup.py   │  │ geo_loader.py     │  │ ml_crop_detector │
│ db_crud_      │  │ geo_overlay.py    │  │  .py             │
│  queries.py   │  │ map_viewer.py     │  │                  │
└───────┬───────┘  └────────┬──────────┘  └────────┬─────────┘
        │                   │                      │
        ▼                   ▼                      ▼
┌───────────────┐  ┌───────────────────┐  ┌──────────────────┐
│ PostgreSQL +  │  │ Shapefile / Demo  │  │ Random Forest    │
│ PostGIS       │  │ geopodaci        │  │ model (.pkl)     │
│               │  │ NDVI raster (.tif)│  │                  │
│ Tabele:       │  │ Interaktivna mapa │  │ Detekcije →      │
│ - parcele     │  │ (Folium HTML)     │  │ PostGIS tabela   │
│ - vlasnici    │  │                   │  │ + GeoDataFrame   │
│ - kulture     │  │ Overlay analize:  │  │                  │
│ - agro_mere   │  │ buffer, clip,     │  │ Prostorne        │
│ - prinosi     │  │ union, intersect, │  │ analize ML       │
│ - veze        │  │ difference,       │  │ rezultata        │
│               │  │ within, overlaps, │  │                  │
│               │  │ distance          │  │                  │
└───────────────┘  └───────────────────┘  └──────────────────┘
```

---

## 5. Pokretanje aplikacije

1. **Instalacija zavisnosti**:

   ```bash
   pip install -e .
   ```

2. **PostgreSQL + PostGIS**: Potrebno je imati pokrenutu PostgreSQL instancu sa PostGIS ekstenzijom. Parametri se podešavaju u `src/config.py` (`DB_CONFIG`).

3. **Pokretanje web aplikacije**:

   ```bash
   python app.py
   ```

   Aplikacija je dostupna na `http://localhost:5000`.

4. **Pokretanje iz komandne linije** (bez web interfejsa):

   ```bash
   python main.py
   ```

5. **Inicijalizacija baze**: Klikom na dugme "Inicijalizuj bazu" u web interfejsu ili pozivom `POST /api/init`.

6. **Interaktivna mapa**: Dostupna na `http://localhost:5000/map`.

---

## 6. Napomene

- Ako **shapefile fajlovi nisu prisutni** (definisani u `SHP_PATHS`), aplikacija automatski koristi **demo geopodatke** za Srem, tako da sve funkcionalnosti rade i bez eksternih izvora podataka.
- Ako **PostgreSQL baza nije dostupna**, aplikacija radi u **demo režimu** — svi podaci se čuvaju samo u memoriji (pandas/geopandas DataFrame-ovi), a CRUD operacije i JOIN upiti će prijaviti grešku.
- **ML model** se trenira samo jednom i čuva u `models/` folderu. Pri svakom sledećem pokretanju koristi se sačuvani model.
