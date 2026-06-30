"""
Deo 1 – Python SQL: CRUD operacije, JOIN upiti i upravljanje podacima.
"""

import psycopg2
import pandas as pd
from src.config import DB_CONFIG


def get_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    return conn


# ======================== UNOS POČETNIH PODATAKA ========================


def insert_initial_data():
    """Unosi najmanje 5 redova u svaku tabelu (INSERT)."""
    conn = get_connection()
    cur = conn.cursor()

    # 1. tipovi_zemljista (6 redova)
    tipovi_zemljista = [
        (
            "Černozem",
            "Plodno crno zemljište",
            6.8,
            3.50,
            "Dobra",
            "Žitarice, povrće",
            "Crna",
            "Ilovača",
        ),
        (
            "Aluvijum",
            "Rečno naneseno zemljište",
            7.0,
            2.80,
            "Umerena",
            "Povrće, voće",
            "Smeđa",
            "Peskovita ilovača",
        ),
        (
            "Gajnjača",
            "Šumsko zemljište",
            5.5,
            4.00,
            "Dobra",
            "Voćnjaci, vinogradi",
            "Mrka",
            "Glinovita ilovača",
        ),
        (
            "Smonica",
            "Teško glinovito zemljište",
            6.2,
            2.10,
            "Slaba",
            "Pšenica, suncokret",
            "Tamno siva",
            "Glina",
        ),
        (
            "Rendzina",
            "Zemljište na krečnjaku",
            7.5,
            3.00,
            "Odlična",
            "Vinova loza, duvan",
            "Svetlo siva",
            "Ilovača",
        ),
        (
            "Pseudoglej",
            "Zemljište sa vodoležom",
            5.0,
            1.80,
            "Slaba",
            "Livade, pašnjaci",
            "Svetlo smeđa",
            "Glinuša",
        ),
    ]
    cur.executemany(
        """INSERT INTO tipovi_zemljista (naziv, opis, ph_vrednost, organic_matter_pct, drenaza, pogodnost_za_useve, boja_zemljista, tekstura)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        tipovi_zemljista,
    )
    print("[OK] tipovi_zemljista — uneto 6 redova.")

    # 2. katastarske_opstine (6 redova)
    kat_opstine = [
        (
            "KO Sremska Mitrovica",
            "Sremski",
            "Sremska Mitrovica",
            7628.40,
            4100,
            "SM-001",
            "Administrativni centar Srema",
            "1945-03-01",
            True,
        ),
        (
            "KO Ruma",
            "Sremski",
            "Ruma",
            5820.00,
            2950,
            "RU-001",
            "Opština",
            "1952-06-15",
            True,
        ),
        (
            "KO Šid",
            "Sremski",
            "Šid",
            4960.75,
            2200,
            "SI-001",
            "Granična opština prema Hrvatskoj",
            "1950-04-20",
            True,
        ),
        (
            "KO Inđija",
            "Sremski",
            "Inđija",
            3830.30,
            2600,
            "IN-001",
            "Opština",
            "1955-09-10",
            True,
        ),
        (
            "KO Stara Pazova",
            "Sremski",
            "Stara Pazova",
            3540.80,
            3200,
            "SP-001",
            "Industrijska zona Srema",
            "1948-11-05",
            True,
        ),
        (
            "KO Irig",
            "Sremski",
            "Irig",
            2810.20,
            1400,
            "IR-001",
            "Podnožje Fruške Gore — vinogradi",
            "1960-07-25",
            True,
        ),
    ]
    cur.executemany(
        """INSERT INTO katastarske_opstine (naziv, okrug, grad, povrsina_ha, broj_parcela, sifra_opstine, napomena, datum_osnivanja, aktivan)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        kat_opstine,
    )
    print("[OK] katastarske_opstine — uneto 6 redova.")

    # 3. vlasnici (6 redova)
    vlasnici = [
        (
            "1234567890123",
            "Milan",
            "Petrović",
            "Ulica 1, Novi Sad",
            "+38164111222",
            "milan@email.com",
            "fizicko_lice",
            "2020-01-15",
            True,
        ),
        (
            "2345678901234",
            "Jelena",
            "Jovanović",
            "Ulica 2, Zrenjanin",
            "+38164222333",
            "jelena@email.com",
            "fizicko_lice",
            "2019-06-20",
            True,
        ),
        (
            "3456789012345",
            "Agro Plus d.o.o.",
            "",
            "Ulica 3, Subotica",
            "+38164333444",
            "agro@email.com",
            "pravno_lice",
            "2018-03-10",
            True,
        ),
        (
            "4567890123456",
            "Dragan",
            "Marković",
            "Ulica 4, Kragujevac",
            "+38164444555",
            "dragan@email.com",
            "fizicko_lice",
            "2021-09-01",
            True,
        ),
        (
            "5678901234567",
            "Vesna",
            "Nikolić",
            "Ulica 5, Niš",
            "+38164555666",
            "vesna@email.com",
            "fizicko_lice",
            "2017-11-30",
            True,
        ),
        (
            "6789012345678",
            "Zelena Farm d.o.o.",
            "",
            "Ulica 6, Čačak",
            "+38164666777",
            "zelena@email.com",
            "pravno_lice",
            "2016-05-15",
            True,
        ),
    ]
    cur.executemany(
        """INSERT INTO vlasnici (jmbg, ime, prezime, adresa, telefon, email, tip_vlasnika, datum_registracije, aktivan)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        vlasnici,
    )
    print("[OK] vlasnici — uneto 6 redova.")

    # 4. parcele (6 redova) — koristi dummy geometriju (mali kvadrati oko gradova)
    from psycopg2.extensions import adapt, register_adapter, AsIs
    import binascii

    # Funkcija za kreiranje WKB za jednostavan poligon
    def create_bbox_polygon_wkt(lon, lat, dx=0.01, dy=0.01):
        import struct

        # Kreiraj polygon WKB (little-endian, EPSG:4326)
        # Polygon: ndr=1 (little-endian), type=3 (polygon), numRings=1, numPoints=5
        coords = [
            (lon, lat),
            (lon + dx, lat),
            (lon + dx, lat + dy),
            (lon, lat + dy),
            (lon, lat),
        ]
        # WKB polygon, little-endian
        wkb = struct.pack("<bI", 1, 3)  # byteOrder=1, type=3 (Polygon)
        wkb += struct.pack("<I", 1)  # numRings=1
        wkb += struct.pack("<I", 5)  # numPoints=5 (zatvoren prsten)
        for x, y in coords:
            wkb += struct.pack("<dd", x, y)  # 5 pointova
        return wkb

    parcele = [
        (
            "P-001",
            3.55,
            create_bbox_polygon_wkt(19.85, 45.26),
            1,
            1,
            1,
            "Temerinski put bb, Novi Sad",
            80,
            1.5,
        ),
        (
            "P-002",
            5.20,
            create_bbox_polygon_wkt(20.40, 45.38),
            2,
            2,
            2,
            "Mihajlovački put, Zrenjanin",
            75,
            0.8,
        ),
        (
            "P-003",
            2.80,
            create_bbox_polygon_wkt(19.67, 46.10),
            3,
            3,
            3,
            "Kelebijski put, Subotica",
            105,
            2.0,
        ),
        (
            "P-004",
            4.10,
            create_bbox_polygon_wkt(20.92, 44.02),
            4,
            4,
            4,
            "Kraljevački put, Kragujevac",
            200,
            3.5,
        ),
        (
            "P-005",
            6.75,
            create_bbox_polygon_wkt(21.90, 43.32),
            5,
            5,
            1,
            "Niški put, Niš",
            180,
            1.2,
        ),
        (
            "P-006",
            3.30,
            create_bbox_polygon_wkt(20.35, 43.89),
            6,
            6,
            5,
            "Ljubićki put, Čačak",
            250,
            4.0,
        ),
    ]
    for p in parcele:
        cur.execute(
            """INSERT INTO parcele (broj_parcele, povrsina_ha, geom, id_kat_opstina, id_vlasnika, id_tip_zemljista, adresa_parcele, nadmorska_visina, nagib_terena_pct)
               VALUES (%s, %s, ST_GeomFromWKB(%s, 4326), %s, %s, %s, %s, %s, %s)""",
            (p[0], p[1], psycopg2.Binary(p[2]), p[3], p[4], p[5], p[6], p[7], p[8]),
        )
    print("[OK] parcele — uneto 6 redova.")

    # 5. usevi (6 redova)
    usevi = [
        (
            1,
            "Pšenica",
            "NS-40S",
            "2024-10-15",
            "2025-06-20",
            6.50,
            "aktivan",
            False,
            "ozimi",
            "Dobar usev",
        ),
        (
            2,
            "Kukuruz",
            "ZP-606",
            "2025-04-10",
            "2025-09-15",
            9.00,
            "aktivan",
            True,
            "jari",
            "Hibrid",
        ),
        (
            3,
            "Suncokret",
            "NS-H-111",
            "2025-04-01",
            "2025-08-25",
            3.20,
            "aktivan",
            False,
            "jari",
            "Uljani tip",
        ),
        (
            4,
            "Soja",
            "NS-F-10",
            "2025-04-20",
            "2025-09-10",
            4.00,
            "aktivan",
            True,
            "jari",
            "Proteinski usev",
        ),
        (
            5,
            "Ječam",
            "NS-525",
            "2024-10-20",
            "2025-06-01",
            5.50,
            "zavrsen",
            False,
            "ozimi",
            "Pivski ječam",
        ),
        (
            6,
            "Krompir",
            "Desiree",
            "2025-03-15",
            "2025-07-30",
            25.00,
            "aktivan",
            True,
            "povrće",
            "Konzumni",
        ),
    ]
    cur.executemany(
        """INSERT INTO usevi (id_parcele, naziv_useva, sorta, datum_setve, datum_zetve, ocekivani_prinos_t, status, navodnjavanje, tip_useva, napomena)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        usevi,
    )
    print("[OK] usevi — uneto 6 redova.")

    # 6. nadzor (6 redova)
    nadzor = [
        (
            1,
            "2025-03-15",
            0.75,
            3.5,
            "Dobro",
            "Nema problema",
            "Prihrana",
            "Sentinel-2",
            "Petar P.",
            None,
        ),
        (2, "2025-05-10", 0.82, 4.1, "Odlično", "—", "—", "Sentinel-2", "Ana M.", None),
        (
            3,
            "2025-05-15",
            0.68,
            3.0,
            "Osrednje",
            "Blaga pegavost",
            "Fungicid",
            "Copernicus",
            "Petar P.",
            None,
        ),
        (
            4,
            "2025-06-01",
            0.88,
            4.8,
            "Odlično",
            "—",
            "Navodnjavanje",
            "Landsat-8",
            "Jovan S.",
            None,
        ),
        (
            5,
            "2025-04-01",
            0.70,
            3.2,
            "Dobro",
            "Kasniji razvoj",
            "—",
            "Sentinel-2",
            "Ana M.",
            None,
        ),
        (
            5,
            "2025-05-20",
            0.60,
            2.8,
            "Loše",
            "Suša",
            "Hitno navodnjavanje",
            "Copernicus",
            "Jovan S.",
            None,
        ),
    ]
    cur.executemany(
        """INSERT INTO nadzor (id_useva, datum_nadzora, ndvi_vrednost, lai_vrednost, zdravstveno_stanje, uoceni_problemi, tretman, izvor_podataka, operater, geom_tacke)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        nadzor,
    )
    print("[OK] nadzor — uneto 6 redova.")

    conn.commit()
    cur.close()
    conn.close()
    print("\n[OK] Svi početni podaci su uneseni.\n")


# ======================== CRUD OPERACIJE ========================


def read_all(table_name):
    """Čitanje svih redova iz tabele i vraćanje kao pandas DataFrame."""
    conn = get_connection()
    query = f"SELECT * FROM {table_name};"
    df = pd.read_sql(query, conn)
    conn.close()
    print(f"\n=== {table_name} ({len(df)} redova) ===")
    print(df.to_string(max_rows=10))
    return df


def insert_row(table_name, columns, values):
    """Unos novog reda u tabelu."""
    conn = get_connection()
    cur = conn.cursor()
    placeholders = ", ".join(["%s"] * len(values))
    cols = ", ".join(columns)
    cur.execute(
        f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders});",
        values,
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"[OK] Novi red unet u {table_name}.")


def update_row(table_name, set_column, new_value, where_column, where_value):
    """Ažuriranje reda u tabeli."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE {table_name} SET {set_column} = %s WHERE {where_column} = %s;",
        (new_value, where_value),
    )
    rows = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    print(f"[OK] Ažurirano {rows} redova u {table_name}.")


def delete_row(table_name, where_column, where_value):
    """Brisanje reda iz tabele."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"DELETE FROM {table_name} WHERE {where_column} = %s;",
        (where_value,),
    )
    rows = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    print(f"[OK] Obrisano {rows} redova iz {table_name}.")


# ======================== JOIN UPITI ========================


def run_join_queries():
    """Izvršava 7 složenih JOIN upita sa WHERE filtriranjem."""
    conn = get_connection()
    results = {}

    # Upit 1: Parcele sa tipom zemljišta (JOIN + WHERE)
    q1 = """
        SELECT p.broj_parcele, p.povrsina_ha, tz.naziv AS tip_zemljista, tz.ph_vrednost
        FROM parcele p
        JOIN tipovi_zemljista tz ON p.id_tip_zemljista = tz.id_tip_zemljista
        WHERE tz.ph_vrednost BETWEEN 6.0 AND 7.5
        ORDER BY p.povrsina_ha DESC;
    """
    results["parcele_sa_zemljistem"] = pd.read_sql(q1, conn)

    # Upit 2: Usevi sa parcelama i vlasnicima (trostruki JOIN)
    q2 = """
        SELECT u.naziv_useva, u.sorta, p.broj_parcele, v.ime, v.prezime, v.tip_vlasnika
        FROM usevi u
        JOIN parcele p ON u.id_parcele = p.id_parcele
        JOIN vlasnici v ON p.id_vlasnika = v.id_vlasnika
        WHERE u.status = 'aktivan'
        ORDER BY u.naziv_useva;
    """
    results["usevi_vlasnici"] = pd.read_sql(q2, conn)

    # Upit 3: Nadzor po usevima sa NDVI vrednostima (JOIN + WHERE)
    q3 = """
        SELECT u.naziv_useva, n.datum_nadzora, n.ndvi_vrednost, n.zdravstveno_stanje, n.uoceni_problemi
        FROM nadzor n
        JOIN usevi u ON n.id_useva = u.id_useva
        WHERE n.ndvi_vrednost < 0.75
        ORDER BY n.ndvi_vrednost ASC;
    """
    results["nadzor_niski_ndvi"] = pd.read_sql(q3, conn)

    # Upit 4: Parcele sa katastarskom opštinom i usevima
    q4 = """
        SELECT ko.naziv AS kat_opstina, ko.okrug, p.broj_parcele, u.naziv_useva, u.status
        FROM parcele p
        JOIN katastarske_opstine ko ON p.id_kat_opstina = ko.id_kat_opstina
        LEFT JOIN usevi u ON p.id_parcele = u.id_parcele
        WHERE ko.okrug = 'Sremski'
        ORDER BY ko.naziv;
    """
    results["parcele_katastar"] = pd.read_sql(q4, conn)

    # Upit 5: Vlasnici sa površinom parcela (JOIN + agregacija)
    q5 = """
        SELECT v.ime, v.prezime, v.tip_vlasnika,
               COUNT(p.id_parcele) AS broj_parcela,
               SUM(p.povrsina_ha) AS ukupna_povrsina_ha
        FROM vlasnici v
        JOIN parcele p ON v.id_vlasnika = p.id_vlasnika
        GROUP BY v.id_vlasnika, v.ime, v.prezime, v.tip_vlasnika
        HAVING SUM(p.povrsina_ha) > 3.0
        ORDER BY ukupna_povrsina_ha DESC;
    """
    results["vlasnici_agregacija"] = pd.read_sql(q5, conn)

    # Upit 6: Usevi sa tipom zemljišta i proizvođačem
    q6 = """
        SELECT u.naziv_useva, tz.naziv AS tip_zemljista, tz.drenaza,
               v.ime AS vlasnik, v.email, ko.naziv AS kat_opstina
        FROM usevi u
        JOIN parcele p ON u.id_parcele = p.id_parcele
        JOIN tipovi_zemljista tz ON p.id_tip_zemljista = tz.id_tip_zemljista
        JOIN vlasnici v ON p.id_vlasnika = v.id_vlasnika
        JOIN katastarske_opstine ko ON p.id_kat_opstina = ko.id_kat_opstina
        WHERE u.navodnjavanje = TRUE
        ORDER BY tz.drenaza;
    """
    results["usevi_navodnjavanje"] = pd.read_sql(q6, conn)

    # Upit 7: Nadzor sa usevima i parcelama (višestruki JOIN + WHERE)
    q7 = """
        SELECT n.datum_nadzora, n.operater, n.tretman,
               u.naziv_useva, u.sorta, p.broj_parcele, p.adresa_parcele,
               ko.grad
        FROM nadzor n
        JOIN usevi u ON n.id_useva = u.id_useva
        JOIN parcele p ON u.id_parcele = p.id_parcele
        JOIN katastarske_opstine ko ON p.id_kat_opstina = ko.id_kat_opstina
        WHERE n.tretman IS NOT NULL AND n.tretman != '—'
        ORDER BY n.datum_nadzora DESC;
    """
    results["nadzor_tretmani"] = pd.read_sql(q7, conn)

    conn.close()

    # Ispis rezultata
    for naziv, df in results.items():
        print(f"\n=== {naziv} ({len(df)} redova) ===")
        print(df.to_string(max_rows=10))
        print()

    return results


def load_all_to_dataframes():
    """Učitava sve tabele u pandas DataFrames."""
    conn = get_connection()
    tables = [
        "tipovi_zemljista",
        "katastarske_opstine",
        "vlasnici",
        "parcele",
        "usevi",
        "nadzor",
    ]
    dfs = {}
    for t in tables:
        dfs[t] = pd.read_sql(f"SELECT * FROM {t};", conn)
        print(f"[OK] {t}: {len(dfs[t])} redova učitano u DataFrame.")
    conn.close()
    return dfs


# ======================== DEMO GLAVNA FUNKCIJA ========================


def run_crud_demo():
    """Demonstracija svih CRUD operacija."""
    print("\n" + "=" * 60)
    print("CRUD DEMONSTRACIJA")
    print("=" * 60)

    # READ
    print("\n>>> Čitanje svih podataka iz tabela:")
    tables = [
        "tipovi_zemljista",
        "katastarske_opstine",
        "vlasnici",
        "parcele",
        "usevi",
        "nadzor",
    ]
    for t in tables:
        read_all(t)

    # INSERT
    print("\n>>> Unos novog reda u vlasnici:")
    insert_row(
        "vlasnici",
        [
            "jmbg",
            "ime",
            "prezime",
            "adresa",
            "telefon",
            "email",
            "tip_vlasnika",
            "datum_registracije",
        ],
        [
            "7890123456789",
            "Zoran",
            "Ilić",
            "Ulica 7, Pančevo",
            "+38164777888",
            "zoran@email.com",
            "fizicko_lice",
            "2025-01-10",
        ],
    )
    read_all("vlasnici")

    # UPDATE
    print("\n>>> Ažuriranje telefona vlasnika:")
    update_row("vlasnici", "telefon", "+38164999000", "jmbg", "1234567890123")
    read_all("vlasnici")

    # DELETE
    print("\n>>> Brisanje unetog vlasnika (Zoran Ilić):")
    delete_row("vlasnici", "jmbg", "7890123456789")
    read_all("vlasnici")


# --- Aliasi za main.py kompatibilnost ---
def read_all_tables():
    """Wrapper za main.py: vraća DataFrame-ove svih tabela."""
    return load_all_to_dataframes()


def crud_demo():
    """Wrapper za main.py: demonstracija CRUD operacija."""
    run_crud_demo()


if __name__ == "__main__":
    print("=== Deo 1: Unos podataka i CRUD + JOIN upiti ===")
    insert_initial_data()
    run_crud_demo()
    print("\n=== Deo 1: JOIN upiti ===")
    run_join_queries()
    print("\n=== Deo 1: Učitavanje u DataFrames ===")
    load_all_to_dataframes()
