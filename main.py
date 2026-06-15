"""
AgroSrem — Evidencija i Analiza Poljoprivrednih Površina (Srem)

Glavni ulaz za pokretanje Flask veb aplikacije.
Integriše sva tri dela projekta:
  Deo 1 – PostgreSQL/PostGIS: baza, CRUD, JOIN upiti
  Deo 2 – GIS: shapefile slojevi, overlay tehnike, prostorni upiti, raster
  Deo 3 – ML: klasifikacija useva, vektorski izlaz, prostorne analize

Pokretanje:
  python main.py
  Zatim otvoriti http://localhost:5000 u pretraživaču.
"""

from app import app

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  AgroSrem — Evidencija i Analiza Poljoprivrednih Površina")
    print("  Područje: Srem")
    print("=" * 70)
    print("\n  Pokrećem Flask server na http://localhost:5000")
    print("  Pritisnite Ctrl+C za zaustavljanje.\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
