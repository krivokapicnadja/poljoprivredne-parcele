# Monitoring poljoprivrednih parcela - Srem 🌾

Aplikacija za evidenciju i analizu poljoprivrednih površina na području Srema, integrišući GIS tehnologije, raster podatke, mašinsko učenje i web interfejs.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.0+-336791.svg)](https://postgis.net/)
[![Licenca](https://img.shields.io/badge/Licenca-MIT-yellow.svg)](LICENSE)

---

## Sadržaj

1. [Opis projekta](#opis-projekta)
2. [Struktura projekta](#struktura-projekta)
3. [Tehnologije](#tehnologije)
4. [Instalacija i pokretanje](#instalacija-i-pokretanje)
5. [Web aplikacija](#web-aplikacija)
6. [Komponente sistema](#komponente-sistema)
7. [API endpoint‑i](#api-endpointi)
8. [Primeri izlaza](#primeri-izlaza)
9. [Planirana unapređenja](#planirana-unapređenja)
10. [Licenca](#licenca)

---

## Opis projekta

Sistem objedinjuje tri celine u jedinstvenu web aplikaciju:

- **Bazu podataka (PostgreSQL/PostGIS)** - upravljanje parcelama, usevima, vlasnicima i nadzorom kroz CRUD operacije i složene SQL upite.
- **GIS prostorne analize** - rad sa vektorskim slojevima (shapefile), stvarnim Sentinel‑2 NDVI rasterskim podacima sa Google Earth Engine‑a, overlay tehnike i mapiranje rezultata.
- **Mašinsko učenje** - klasifikacija useva Random Forest klasifikatorom na **stvarnim Sentinel‑2 satelitskim snimcima** (preko GEE), sa ERA5 meteorološkim podacima, detekcija objekata i prostorna analiza detekcija.

Flask web interfejs omogućava interaktivni pregled podataka, CRUD operacije, vizuelizaciju mapa i API pristup svim komponentama sistema.

---

## Struktura projekta

```
ogi_projekat/
├── src/
│   ├── config.py              # Konfiguracija: DB konekcija, putanje, CRS konstante, granice Srema, GEE podešavanja
│   ├── db_setup.py            # Deo 1: Kreiranje 6 tabela, PK/FK (CASCADE/SET NULL), INSERT podataka
│   ├── db_crud_queries.py     # Deo 1: CRUD operacije + 7 JOIN upita sa WHERE/ORDER BY/GROUP BY/HAVING
│   ├── geo_loader.py          # Deo 2: Učitavanje SHP podataka, stvarni Sentinel‑2 NDVI sa GEE‑a
│   ├── geo_overlay.py         # Deo 2: 9 overlay tehnika i prostornih upita
│   ├── map_viewer.py          # Deo 2: Interaktivna Folium mapa sa LayerControl, NDVI, simbologijom
│   └── ml_crop_detector.py    # Deo 3: RandomForest klasifikacija na stvarnim Sentinel‑2 podacima (GEE)
│
├── app.py                     # Flask web aplikacija (dashboard, API endpoint‑i)
├── main.py                    # Glavni orkestrator - pokreće ceo pipeline iz komandne linije
├── templates/
│   └── index.html             # HTML/JS frontend - interaktivni dashboard
├── data/                      # Generisani podaci (raster, HTML mapa)
├── models/                    # Sačuvani ML modeli (pickle)
├── .env                       # Promenljive okruženja (DB konekcija, GEE projekat)
├── pyproject.toml             # Zavisnosti i metapodaci projekta
├── .gitignore
├── .python-version
└── README.md
```

---

## Tehnologije

| Sloj                | Biblioteka                                            |
| ------------------- | ----------------------------------------------------- |
| Baza podataka       | PostgreSQL / PostGIS, `psycopg2-binary`               |
| Web server          | `Flask`                                               |
| Obrada podataka     | `pandas`                                              |
| GIS / Vektori       | `geopandas`, `shapely`, `fiona`                       |
| Raster              | `rasterio`                                            |
| Satelitski snimci   | `earthengine-api` (Google Earth Engine, Sentinel‑2)   |
| Vizuelizacija       | `folium`, `branca`, `matplotlib`                      |
| Mašinsko učenje     | `scikit-learn` (RandomForest)                         |
| Serijalizacija      | `pickle`, `json`                                      |
| Numerika            | `numpy`                                               |
| Autentifikacija     | `google-auth`, `google-api-python-client`             |

---

## Instalacija i pokretanje

### 1. Kloniraj repozitorijum

```bash
git clone https://github.com/krivokapicnadja/poljoprivredne-parcele.git
cd poljoprivredne-parcele
```

### 2. Kreiraj i aktiviraj virtuelno okruženje

```bash
python -m venv .venv
source .venv/Scripts/activate     # Git Bash / WSL / Linux
.venv\Scripts\activate            # PowerShell / cmd
```

### 3. Instaliraj zavisnosti

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

Sve zavisnosti su definisane u `pyproject.toml`. Opciono, možeš ih instalirati i pojedinačno ručno.

### 3.1 Podešavanje Google Earth Engine‑a

Da bi ML koristio **stvarne Sentinel‑2 satelitske snimke**, potrebno je podesiti GEE:

```bash
# 1. Instaliraj GEE paket (ako već nije instaliran)
python -m pip install earthengine-api

# 2. Autentifikuj se (otvara browser za Google login)
python -c "import ee; ee.Authenticate()"
```

Zatim kreiraj Google Cloud projekat, omogući **Earth Engine API** i registruj projekat za Earth Engine. Upiši Project ID u `.env`:

```ini
# .env
DB_PASSWORD = tvoja_sifra
DB_HOST = tvoj_host
GEE_PROJECT = tvoj-gee-projekt-id
```

> **Napomena:** Ako GEE nije podešen, sistem automatski pada nazad na **simulirane podatke** za ML i demo NDVI raster. Za punu funkcionalnost potrebna je i PostgreSQL baza sa PostGIS ekstenzijom.

### 4. Pokreni aplikaciju

**Web aplikacija (preporučeno):**

```bash
python app.py
```

Otvori [http://localhost:5000](http://localhost:5000) u browseru za pristup interaktivnom dashboard‑u.

**Komandna linija (pipeline):**

```bash
python main.py
```

Izlaz:

- Kreiranje baze, tabela i unos podataka (Deo 1)
- Učitavanje GIS slojeva, preuzimanje NDVI rastera i izvršavanje prostornih analiza (Deo 2)
- Detekcija useva pomoću ML modela i prostorne analize detekcija (Deo 3)
- **Interaktivna mapa** → `data/interactive_map.html` (otvoriti u browseru)

Alternativno, Deo 1 (baza) se može pokrenuti nezavisno:

```bash
python -m src.db_setup
python -m src.db_crud_queries
```

---

## Web aplikacija

Flask aplikacija (`app.py`) pruža:

- **Dashboard** - pregled svih tabela, broj rekorda, ML statistike, GIS slojevi (ruta `/`)
- **Interaktivna mapa** - slojevi, overlay rezultati, ML detekcije (`/map`)
- **CRUD operacije** - unos, ažuriranje i brisanje podataka kroz web interfejs
- **REST API** - JSON endpoint‑i za sve komponente sistema (vidi [API endpoint‑i](#api-endpointi))
- **Inicijalizacija baze** - kreiranje tabela i punjenje demo podacima jednim klikom

### Korišćenje

1. Pokreni `python app.py`
2. Otvori [http://localhost:5000](http://localhost:5000)
3. Klikni na **„Inicijalizuj bazu”** da kreiraš tabele i popuniš demo podacima
4. Pregledaj podatke po tabelama, izvršavaj JOIN upite, modifikuj ML detekcije
5. Otvori `/map` za interaktivnu mapu sa svim slojevima

---

## Komponente sistema

### Deo 1 - Python SQL (`db_setup.py`, `db_crud_queries.py`)

- **6 tabela** sa primarnim i stranim ključevima:
  - `tipovi_zemljista` - šifarnik tipova zemljišta (pH, sadržaj organske materije, drenaža, pogodnost za useve)
  - `katastarske_opstine` - katastarske opštine Srema (površina, broj parcela, šifra opštine)
  - `vlasnici` - fizička i pravna lica koja poseduju parcele
  - `parcele` - geometrija i atributi parcela (FK → `katastarske_opstine` **CASCADE**, → `vlasnici` **SET NULL**, → `tipovi_zemljista` **SET NULL**)
  - `usevi` - usevi zasejani na parcelama, sa datumima setve/žetve i statusom (FK → `parcele` **CASCADE**)
  - `nadzor` - evidencija satelitskog nadzora useva, NDVI/LAI, zdravstveno stanje (FK → `usevi` **CASCADE**)
- **6 redova** ručno unetih u svaku tabelu (`insert_initial_data`)
- **Pandas DataFrame** učitavanje svih tabela
- **CRUD operacije**: prikaz (`read_all`), unos (`insert_row`), ažuriranje (`update_row`), brisanje (`delete_row`) - parametrizovani upiti (zaštita od SQL injekcije)
- **7 JOIN upita** (`run_join_queries`) sa WHERE filtriranjem, ORDER BY, GROUP BY, HAVING - uključujući INNER i LEFT JOIN, agregaciju (COUNT/SUM) i spajanje do 4 tabele u jednom upitu

### Deo 2 - Python GEO (`geo_loader.py`, `geo_overlay.py`, `map_viewer.py`)

- Učitavanje SHP slojeva sa **Geofabrik‑a** za područje Srema (filtrirano po granicama regiona)
- Geopandas `GeoDataFrame` sa prostornim podacima, obogaćeni kategorijama
- NDVI **raster** (.tif) - **stvarni Sentinel‑2** sa Google Earth Engine‑a (medijan/najmanje oblačan snimak, april-septembar, <20% oblaka), ili demo fallback ako GEE/shapefile‑ovi nisu dostupni
- **9 prostornih analiza**:

  | Tehnika        | Opis                                               |
  | -------------- | -------------------------------------------------- |
  | `buffer`       | Zaštitni pojas oko puteva (200m) i objekata (500m) |
  | `clip`         | Isecanje landuse poligona unutar zone puteva       |
  | `union`        | Unija landuse i prirodnih područja                 |
  | `intersection` | Presek landuse i buffer‑a puteva                   |
  | `difference`   | Landuse van zone puteva                            |
  | `within`       | Objekti unutar landuse poligona                    |
  | `intersects`   | Parcele koje presecaju prirodne oblasti            |
  | `overlaps`     | Preklapajući landuse poligoni                      |
  | `distance`     | Udaljenost objekata od vodotokova                  |

- **Interaktivna Folium mapa** sa:
  - NDVI raster podlogom
  - Slojevima (landuse, buildings, roads, waterways, natural)
  - Rezultatima overlay analiza - glavni slojevi (`buffer_putevi_200m`, `clip_landuse_putevi`, `intersection_landuse_putevi`, `difference_landuse_van_putevi`) prikazani po default‑u, ostali dostupni preko `LayerControl`‑a
  - ML detektovanim usevima
  - `LayerControl` za paljenje/gašenje slojeva
  - Prilagođenom simbologijom (boje, debljine linija, ikone)

### Deo 3 - Python ML (`ml_crop_detector.py`)

- **Random Forest klasifikator** sa 150 stabala, max depth 12
- 6 klasa useva: _Ječam, Krompir, Kukuruz, Pšenica, Soja, Suncokret_
- Feature inženjering: NDVI, SAVI, NDWI, red band (B4), NIR band (B8), SWIR (B11), temperatura, vlažnost
- **Trening na stvarnim podacima**: piksele ekstrahovane sa Sentinel‑2 snimaka putem GEE‑a, ERA5 meteorološki podaci (temperatura, precipitacija), heurističke oznake useva
- **Fallback**: simulirani trening podaci kada GEE nije dostupan
- Evaluacija: accuracy, precision, recall, f1‑score, feature importance
- **Detekcija**: 200 objekata nad stvarnim Sentinel‑2 mozaikom (GEE), ili manji broj simuliranih objekata u demo režimu
- **Prostorna analiza detekcija**: statistike po tipu useva, spatial join sa landuse slojem (broji jedinstvene detekcije koje se preklapaju), udaljenost od puteva
- **CRUD nad atributima** detekcije: izmena `crop_type`, `confidence`, `area_ha`, NDVI srednje vrednosti
- Detektovani objekti u `GeoDataFrame` sa Polygon geometrijom → spremni za PostGIS INSERT
- Model i enkoderi sačuvani u `models/` (pickle)

---

## API endpoint‑i

| Metod  | Ruta                 | Opis                                           |
| ------ | --------------------- | ---------------------------------------------- |
| `GET`  | `/api/tables`        | Spisak svih tabela sa brojem redova i kolonama |
| `GET`  | `/api/tables/<name>` | Podaci iz određene tabele                      |
| `POST` | `/api/crud`          | CRUD operacije (insert, update, delete)        |
| `GET`  | `/api/joins`         | Rezultati svih JOIN upita                      |
| `GET`  | `/api/overlays`      | Rezultati overlay prostornih analiza           |
| `GET`  | `/api/slojevi`       | Informacije o GIS slojevima                    |
| `GET`  | `/api/ml/stats`      | ML statistike i sve detekcije                  |
| `POST` | `/api/ml/update`     | Ažuriranje atributa detekcije                  |
| `GET`  | `/api/ml/spatial`    | Prostorne analize ML podataka                  |
| `POST` | `/api/init`          | Inicijalizacija baze i podataka                |
| `GET`  | `/api/config`        | Konfiguracija (granice Srema, centar, CRS)     |
| `GET`  | `/api/dashboard`     | Sumarni podaci za dashboard                    |
| `GET`  | `/map`               | Interaktivna Folium mapa                       |

### Primer CRUD poziva

```json
POST /api/crud
{
  "action": "insert",
  "table": "vlasnici",
  "columns": ["ime", "prezime", "adresa", "tip_vlasnika"],
  "values": ["Zoran", "Ilić", "Sremska 15, Sremska Mitrovica", "fizicko_lice"]
}
```

---

## Primeri izlaza

### Tačnost ML modela (stvarni Sentinel‑2 podaci)

```
=== EKSTRAKCIJA STVARNIH TRENING PODATAKA SA EARTH ENGINE-A ===
   Broj Sentinel-2 snimaka: 184
   Ekstrahovano 500 validnih piksela.
   Dodati ERA5 meteorološki podaci.

Tačnost modela: 0.9400 (94.00%)

Značaj karakteristika:
  ndvi:         0.328
  savi:         0.286
  ndwi:         0.194
  red_band:     0.115
  nir_band:     0.064
  temperature:  0.017
  humidity:     0.000
```

### Detekcija useva (distribucija, stvarni snimci)

```
[OK] Detektovano 200 objekata sa stvarnih Sentinel-2 snimaka.

Suncokret:  140
Kukuruz:    49
Soja:       10
Pšenica:     1
```

> Napomena: tačne brojke variraju iz pokretanja u pokretanje jer zavise od trenutno dostupnih Sentinel‑2 snimaka i nasumičnog uzorkovanja piksela.

### Prostorne analize (stvarni Geofabrik podaci)

```
buffer_putevi_200m:          500 zona (uzorak)
clip_landuse_putevi:         4029 poligona
intersection_landuse_putevi: 5269 preseka
difference_landuse_van_putevi: 27479 poligona
within (objekti):            7/500 unutar landuse‑a (uzorak)
udaljenost od voda:          min 0m, max 4009m, mean 770m
```

> Napomena: broj rezultata zavisi od toga da li su Geofabrik shapefile‑ovi učitani (stvarni podaci, veliki brojevi kao iznad) ili je aktivan demo fallback (mnogo manji, ilustrativni skup podataka).

---

## Planirana unapređenja

- [x] Povezivanje sa stvarnom PostgreSQL/PostGIS instancom (Supabase)
- [x] Preuzimanje stvarnih Sentinel‑2 snimaka sa Google Earth Engine‑a
- [ ] Deep learning model (CNN) za precizniju klasifikaciju useva
- [ ] Proširenje web interfejsa (vizuelizacija vremenskih serija, grafikoni prinosa)
- [ ] Docker kontejnerizacija za lako postavljanje
- [ ] Autentifikacija i korisničke role u web aplikaciji

---

## Licenca

MIT License. Slobodno koristite, menjajte i distribuirajte.