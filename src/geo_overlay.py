"""
Deo 2 – Python GEO: Overlay tehnike i prostorni upiti
(clip, union, intersection, buffer, within, overlaps...)
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, LineString, box, mapping
from src.config import CRS_WGS84


def run_all_overlay_demos(slojevi):
    """
    Izvršava pet+ overlay tehnika i prostorne upite nad slojevima.
    Vraća rečnik sa rezultatima.
    """
    rezultati = {}

    # Provera da li postoji landuse sloj
    if "landuse" not in slojevi:
        print("[ERROR] Nema 'landuse' sloja. Nije moguće izvršiti overlay analize.")
        return rezultati

    landuse = slojevi["landuse"].copy()
    buildings = slojevi.get("buildings")
    roads = slojevi.get("roads")
    waterways = slojevi.get("waterways")
    natural = slojevi.get("natural")

    MAX_SAMPLE = 500  # Ograničenje za overlay operacije nad velikim skupovima

    # ===== 1. BUFFER =====
    print("\n>>> 1. BUFFER: Kreiranje zaštitnog pojasa oko puteva (200m)")
    if roads is not None and len(roads) > 0:
        # Uzmi uzorak za performanse
        roads_sample = roads.sample(n=min(len(roads), MAX_SAMPLE), random_state=42)
        roads_utm = roads_sample.to_crs("EPSG:32634")  # UTM zone 34N
        roads_utm["buffer_200m"] = roads_utm.geometry.buffer(200)
        roads_buf = roads_utm.set_geometry("buffer_200m").to_crs(CRS_WGS84)
        rezultati["buffer_putevi_200m"] = roads_buf
        print(f"   Kreirano {len(roads_buf)} buffer zona oko puteva (uzorak {MAX_SAMPLE}).")

        # Buffer oko objekata
        if buildings is not None and len(buildings) > 0:
            bld_sample = buildings.sample(n=min(len(buildings), MAX_SAMPLE), random_state=42)
            bld_utm = bld_sample.to_crs("EPSG:32634")
            bld_utm["buffer_500m"] = bld_utm.geometry.buffer(500)
            bld_buf = bld_utm.set_geometry("buffer_500m").to_crs(CRS_WGS84)
            rezultati["buffer_objekti_500m"] = bld_buf
            print(f"   Kreirano {len(bld_buf)} buffer zona oko objekata (500m, uzorak).")
    else:
        print("   Nema sloja puteva.")

    # ===== 2. CLIP (isecanje) =====
    print("\n>>> 2. CLIP: Isecanje landuse u okviru pojasa puteva")
    if "buffer_putevi_200m" in rezultati and roads is not None:
        try:
            # Unija svih buffer zona kao jedan poligon
            from shapely.ops import unary_union

            road_union = unary_union(rezultati["buffer_putevi_200m"].geometry)
            clipped = landuse.copy()
            clipped["geometry"] = landuse.geometry.apply(
                lambda geom: (
                    geom.intersection(road_union)
                    if geom.intersects(road_union)
                    else None
                )
            )
            clipped = clipped.dropna(subset=["geometry"])
            if not clipped.is_empty.any():
                rezultati["clip_landuse_putevi"] = clipped
                print(f"   Isečeno {len(clipped)} landuse poligona unutar zone puteva.")
            else:
                print("   Nema preklapanja — clip je prazan.")
        except Exception as e:
            print(f"   Clip nije uspeo: {e}")
    else:
        print("   Nema buffer podataka za clip.")

    # ===== 3. UNION (unija) =====
    print("\n>>> 3. UNION: Unija landuse sa prirodnim područjima")
    if natural is not None and len(natural) > 0:
        try:
            # Pojednostavi za uniju — unija svih geometrija
            landuse_union = landuse.unary_union
            natural_union = natural.unary_union
            total_union = landuse_union.union(natural_union)
            union_gdf = gpd.GeoDataFrame(
                {"name": ["Ukupna_unija"], "type": ["union"]},
                geometry=[total_union],
                crs=CRS_WGS84,
            )
            rezultati["union_landuse_natural"] = union_gdf
            print(
                f"   Kreirana unija landuse i natural slojeva. Površina: {total_union.area:.6f} stepeni²"
            )
        except Exception as e:
            print(f"   Union nije uspeo: {e}")
    else:
        print("   Nema natural sloja.")

    # ===== 4. INTERSECTION (presek) =====
    print("\n>>> 4. INTERSECTION: Presek landuse sa bufferom puteva")
    if "buffer_putevi_200m" in rezultati:
        try:
            buffs = rezultati["buffer_putevi_200m"].copy()
            intersection_gdf = gpd.overlay(landuse, buffs, how="intersection")
            rezultati["intersection_landuse_putevi"] = intersection_gdf
            print(f"   Presečeno {len(intersection_gdf)} poligona.")
        except Exception as e:
            print(f"   Intersection nije uspeo: {e}")
    else:
        print("   Nema buffer podataka.")

    # ===== 5. ERASE (difference) =====
    print("\n>>> 5. DIFFERENCE (Izuzimanje): Landuse izvan zone puteva")
    if "buffer_putevi_200m" in rezultati:
        try:
            buffs = rezultati["buffer_putevi_200m"].copy()
            difference_gdf = gpd.overlay(landuse, buffs, how="difference")
            rezultati["difference_landuse_van_putevi"] = difference_gdf
            print(f"   Landuse van zone puteva: {len(difference_gdf)} poligona.")
        except Exception as e:
            print(f"   Difference nije uspeo: {e}")

    # ===== PROSTORNI UPITI =====

    # 6. WITHIN (unutar) - koristi uzorak za performanse
    print("\n>>> 6. Prostorni upit: Objekti UNUTAR landuse poligona (WITHIN)")
    if buildings is not None and len(buildings) > 0:
        bld_sample = buildings.sample(n=min(len(buildings), MAX_SAMPLE), random_state=42)
        landuse_sample = landuse.sample(n=min(len(landuse), MAX_SAMPLE), random_state=42)
        landuse_union = landuse_sample.unary_union
        bld_sample["within_landuse"] = bld_sample.geometry.apply(
            lambda g: g.within(landuse_union)
        )
        within_count = bld_sample["within_landuse"].sum()
        print(f"   {within_count}/{len(bld_sample)} objekata unutar landuse područja (uzorak {MAX_SAMPLE}).")
        rezultati["objekti_within_landuse"] = bld_sample[
            bld_sample["within_landuse"]
        ].copy()

    # 7. INTERSECTS (seče) - uzorak za performanse
    print(
        "\n>>> 7. Prostorni upit: Parcele koje PRESECAJU prirodne oblasti (INTERSECTS)"
    )
    if natural is not None and len(natural) > 0:
        landuse_sample = landuse.sample(n=min(len(landuse), MAX_SAMPLE), random_state=42)
        intersects_list = []
        for i, land_row in landuse_sample.iterrows():
            for j, nat_row in natural.iterrows():
                try:
                    if land_row.geometry.intersects(nat_row.geometry):
                        intersects_list.append(
                            {
                                "landuse_name": land_row.get("name", f"parcela_{i}"),
                                "natural_name": nat_row.get("name", f"natural_{j}"),
                                "geometry": land_row.geometry.intersection(
                                    nat_row.geometry
                                ),
                            }
                        )
                except Exception:
                    pass
        if intersects_list:
            intersects_gdf = gpd.GeoDataFrame(intersects_list, crs=CRS_WGS84)
            rezultati["intersects_landuse_natural"] = intersects_gdf
            print(f"   Pronađeno {len(intersects_gdf)} preseka (uzorak {MAX_SAMPLE} x {len(natural)}).")
        else:
            print("   Nema preseka.")

    # 8. OVERLAPS (preklapanje) - uzorak za performanse
    print("\n>>> 8. Prostorni upit: Landuse poligoni koji se PREKLAPAJU (OVERLAPS)")
    SAMPLE_N = min(len(landuse), 200)
    landuse_sample = landuse.sample(n=SAMPLE_N, random_state=42).reset_index(drop=True)
    overlap_count = 0
    overlap_geoms = []
    for i in range(SAMPLE_N):
        for j in range(i + 1, SAMPLE_N):
            try:
                if landuse_sample.iloc[i].geometry.overlaps(landuse_sample.iloc[j].geometry):
                    overlap_count += 1
                    overlap_geoms.append(
                        landuse_sample.iloc[i].geometry.intersection(landuse_sample.iloc[j].geometry)
                    )
            except Exception:
                pass
    print(f"   Broj preklapajućih landuse poligona: {overlap_count} (uzorak {SAMPLE_N})")
    if overlap_geoms:
        rezultati["overlap_landuse"] = gpd.GeoDataFrame(
            {"type": ["overlap"] * len(overlap_geoms)},
            geometry=overlap_geoms,
            crs=CRS_WGS84,
        )

    # 9. DISTANCE (blizina) - uzorak za performanse
    print("\n>>> 9. Prostorni upit: Udaljenost objekata od vodotokova (DISTANCE)")
    if (
        buildings is not None
        and waterways is not None
        and len(buildings) > 0
        and len(waterways) > 0
    ):
        bld_sample = buildings.sample(n=min(len(buildings), MAX_SAMPLE), random_state=42)
        bld_utm = bld_sample.to_crs("EPSG:32634")
        wat_utm = waterways.to_crs("EPSG:32634")
        wat_union = wat_utm.unary_union
        bld_utm["dist_do_vode_m"] = bld_utm.geometry.distance(wat_union)
        bld_dist = bld_utm.to_crs(CRS_WGS84)
        rezultati["udaljenost_objekata_voda"] = bld_dist
        print(
            f"   Min: {bld_dist['dist_do_vode_m'].min():.0f}m, "
            f"Max: {bld_dist['dist_do_vode_m'].max():.0f}m, "
            f"Mean: {bld_dist['dist_do_vode_m'].mean():.0f}m "
            f"(uzorak {MAX_SAMPLE} objekata)"
        )

    print("\n[OK] Sve overlay i prostorne analize su završene.")
    return rezultati


def summarize_overlay_results(rezultati):
    """Sumira rezultate overlay analiza."""
    print("\n" + "=" * 60)
    print("REZULTATI OVERLAY I PROSTORNIH UPITA")
    print("=" * 60)
    for naziv, gdf in rezultati.items():
        geom_type = gdf.geometry.geom_type.unique()
        print(f"\n{naziv}:")
        print(f"  - Broj geometrija: {len(gdf)}")
        print(f"  - Tip geometrije: {', '.join(geom_type)}")
        if hasattr(gdf, "crs") and gdf.crs:
            print(f"  - CRS: {gdf.crs}")
    print("=" * 60)


if __name__ == "__main__":
    from src.geo_loader import load_serbia_shapefiles

    slojevi = load_serbia_shapefiles()
    rez = run_all_overlay_demos(slojevi)
    summarize_overlay_results(rez)
