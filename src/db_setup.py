"""
Deo 1 – Python SQL: Kreiranje PostgreSQL/PostGIS baze podataka,
tabela sa primarnim i stranim ključevima, i unos početnih podataka.
"""

import psycopg2
from psycopg2 import sql
import pandas as pd
from src.config import DB_CONFIG


def get_connection():
    """Vraća konekciju na PostgreSQL/PostGIS bazu."""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    return conn


def create_database():
    """Kreira bazu podataka i PostGIS ekstenziju."""
    conn = psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database="postgres",
    )
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s",
        (DB_CONFIG["database"],),
    )
    if not cur.fetchone():
        cur.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_CONFIG["database"]))
        )
        print(f"[OK] Baza '{DB_CONFIG['database']}' je kreirana.")
    else:
        print(f"[INFO] Baza '{DB_CONFIG['database']}' već postoji.")

    cur.close()
    conn.close()

    # Konekcija na novu bazu i omogućavanje PostGIS ekstenzije
    conn = get_connection()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    print("[OK] PostGIS ekstenzija je omogućena.")
    cur.close()
    conn.close()


def drop_tables():
    """Briše sve tabele (za potrebe ponovnog pokretanja)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        DROP TABLE IF EXISTS
            nadzor, usevi, parcele, vlasnici, katastarske_opstine, tipovi_zemljista
        CASCADE;
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("[OK] Sve tabele su obrisane.")


def create_tables():
    """Kreira svih 6 tabela sa primarnim i stranim ključevima."""

    ddl_statements = [
        # Tabela 1: tipovi_zemljista
        """
        CREATE TABLE IF NOT EXISTS tipovi_zemljista (
            id_tip_zemljista   SERIAL PRIMARY KEY,
            naziv              VARCHAR(100) NOT NULL,
            opis               TEXT,
            ph_vrednost        NUMERIC(3,1),
            organic_matter_pct NUMERIC(5,2),
            drenaza            VARCHAR(50),
            pogodnost_za_useve VARCHAR(100),
            boja_zemljista     VARCHAR(50),
            tekstura           VARCHAR(50),
            datum_unosa        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        # Tabela 2: katastarske_opstine
        """
        CREATE TABLE IF NOT EXISTS katastarske_opstine (
            id_kat_opstina  SERIAL PRIMARY KEY,
            naziv           VARCHAR(150) NOT NULL,
            okrug           VARCHAR(100),
            grad            VARCHAR(100),
            povrsina_ha     NUMERIC(10,2),
            broj_parcela    INTEGER,
            sifra_opstine   VARCHAR(20) UNIQUE,
            napomena        TEXT,
            datum_osnivanja DATE,
            aktivan         BOOLEAN DEFAULT TRUE
        );
        """,
        # Tabela 3: vlasnici
        """
        CREATE TABLE IF NOT EXISTS vlasnici (
            id_vlasnika     SERIAL PRIMARY KEY,
            jmbg            VARCHAR(13) UNIQUE,
            ime             VARCHAR(100) NOT NULL,
            prezime         VARCHAR(100) NOT NULL,
            adresa          VARCHAR(200),
            telefon         VARCHAR(30),
            email           VARCHAR(100),
            tip_vlasnika    VARCHAR(30) DEFAULT 'fizicko_lice',
            datum_registracije DATE,
            aktivan         BOOLEAN DEFAULT TRUE
        );
        """,
        # Tabela 4: parcele
        """
        CREATE TABLE IF NOT EXISTS parcele (
            id_parcele          SERIAL PRIMARY KEY,
            broj_parcele        VARCHAR(50) NOT NULL,
            povrsina_ha         NUMERIC(10,4) NOT NULL,
            geom                GEOMETRY(Polygon, 4326),
            id_kat_opstina      INTEGER REFERENCES katastarske_opstine(id_kat_opstina)
                                ON DELETE CASCADE,
            id_vlasnika         INTEGER REFERENCES vlasnici(id_vlasnika)
                                ON DELETE SET NULL,
            id_tip_zemljista    INTEGER REFERENCES tipovi_zemljista(id_tip_zemljista)
                                ON DELETE SET NULL,
            adresa_parcele      VARCHAR(200),
            nadmorska_visina    INTEGER,
            nagib_terena_pct    NUMERIC(5,2),
            datum_upisa         DATE DEFAULT CURRENT_DATE
        );
        """,
        # Tabela 5: usevi
        """
        CREATE TABLE IF NOT EXISTS usevi (
            id_useva            SERIAL PRIMARY KEY,
            id_parcele          INTEGER REFERENCES parcele(id_parcele)
                                ON DELETE CASCADE,
            naziv_useva         VARCHAR(100) NOT NULL,
            sorta               VARCHAR(100),
            datum_setve         DATE,
            datum_zetve         DATE,
            ocekivani_prinos_t  NUMERIC(8,2),
            status              VARCHAR(30) DEFAULT 'aktivan',
            navodnjavanje       BOOLEAN DEFAULT FALSE,
            tip_useva           VARCHAR(50),
            napomena            TEXT
        );
        """,
        # Tabela 6: nadzor
        """
        CREATE TABLE IF NOT EXISTS nadzor (
            id_nadzora          SERIAL PRIMARY KEY,
            id_useva            INTEGER REFERENCES usevi(id_useva)
                                ON DELETE CASCADE,
            datum_nadzora       DATE NOT NULL DEFAULT CURRENT_DATE,
            ndvi_vrednost       NUMERIC(5,4),
            lai_vrednost        NUMERIC(5,2),
            zdravstveno_stanje  VARCHAR(50),
            uoceni_problemi     TEXT,
            tretman             VARCHAR(200),
            izvor_podataka      VARCHAR(100),
            operater            VARCHAR(100),
            geom_tacke          GEOMETRY(Point, 4326)
        );
        """,
    ]

    conn = get_connection()
    cur = conn.cursor()

    for i, ddl in enumerate(ddl_statements):
        cur.execute(ddl)
        print(f"[OK] Tabela {i + 1}/{len(ddl_statements)} je kreirana.")

    conn.commit()
    cur.close()
    conn.close()
    print("[OK] Sve tabele su uspešno kreirane.")


def setup_database():
    """Wrapper za main.py: kreira bazu i tabele."""
    create_database()
    drop_tables()
    create_tables()


def insert_sample_data():
    """Wrapper za main.py: unosi početne podatke."""
    from src.db_crud_queries import insert_initial_data

    insert_initial_data()


if __name__ == "__main__":
    setup_database()
    insert_sample_data()
