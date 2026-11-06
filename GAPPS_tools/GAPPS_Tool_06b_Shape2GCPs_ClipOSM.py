#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GAPPS – Tool 6b – Shape2GCPs: clip OSM to an AOI (run once per area)

One-time extraction of the layers osm_road_gcps.py needs from a Geofabrik
"free" GeoPackage (e.g. congo-democratic-republic.gpkg, ~2.6 GB) for an AOI,
into a small GeoPackage you can reuse for every image of that area.

Output layers
-------------
  roads       road lines (tracks dropped unless --keep-tracks)
  water       water polygons (lakes, reservoirs, river areas) - wetlands dropped
  waterways   river / stream / canal lines

Only features intersecting the AOI (+ buffer) are read: the GeoPackage spatial
index makes this fast even on the country file.

Example
-------
python GAPPS_Tool_06b_Shape2GCPs_ClipOSM.py \
    --gpkg "D:/ADille_Data/GIS/Shapefiles/OpenStreetMap/DRCongo_OpenStreetMap_SHP_2026/congo-democratic-republic.gpkg" \
    --aoi  AOI_large.geojson \
    --out  OSM_AOI_large.gpkg
"""
import argparse
import sys
from pathlib import Path

import geopandas as gpd
import pyogrio

WATER_POLY_KEEP = ["water", "reservoir", "river", "riverbank", "lake", "basin", "dock"]
WATERWAY_KEEP = ["river", "stream", "canal", "drain"]


def find_layer(layers, *keys, avoid=()):
    for l in layers:
        ll = l.lower()
        if all(k in ll for k in keys) and not any(a in ll for a in avoid):
            return l
    return None


def clip_osm_to_aoi(gpkg, aoi, out, buffer=5000.0, keep_tracks=False,
                    water_classes=None, waterway_classes=None):
    """Importable version (used by the Shape2GCPs GUI)."""
    argv = ["--gpkg", str(gpkg), "--aoi", str(aoi), "--out", str(out), "--buffer", str(buffer)]
    if keep_tracks:
        argv.append("--keep-tracks")
    if water_classes:
        argv += ["--water-classes", *water_classes]
    if waterway_classes:
        argv += ["--waterway-classes", *waterway_classes]
    main(argv)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gpkg", required=True, help="Geofabrik *-free GeoPackage (or the unzipped .gpkg)")
    ap.add_argument("--aoi", required=True, help="AOI polygon (any CRS)")
    ap.add_argument("--out", required=True, help="output GeoPackage")
    ap.add_argument("--buffer", type=float, default=5000.0, help="AOI buffer in metres (default 5 km)")
    ap.add_argument("--keep-tracks", action="store_true", help="keep fclass track/track_grade*")
    ap.add_argument("--water-classes", nargs="*", default=WATER_POLY_KEEP)
    ap.add_argument("--waterway-classes", nargs="*", default=WATERWAY_KEEP)
    args = ap.parse_args(argv)

    layers = [str(l[0]) for l in pyogrio.list_layers(args.gpkg)]
    print("layers in input:", ", ".join(layers))
    lay_roads = find_layer(layers, "roads", avoid=("rail",))
    lay_water = find_layer(layers, "water_a") or find_layer(layers, "water", avoid=("waterway",))
    lay_ways = find_layer(layers, "waterways")
    if lay_roads is None:
        sys.exit("No roads layer found.")

    aoi = gpd.read_file(args.aoi)
    if aoi.crs is None:
        aoi = aoi.set_crs(4326)
    utm = aoi.to_crs(4326).estimate_utm_crs()
    area = gpd.GeoSeries([aoi.to_crs(utm).geometry.union_all().buffer(args.buffer)], crs=utm)

    out = Path(args.out)
    if out.exists():
        out.unlink()

    def extract(layer, name, classes=None, drop_prefix=None):
        if layer is None:
            print(f"[{name}] no matching layer, skipped")
            return
        info = pyogrio.read_info(args.gpkg, layer=layer)
        lcrs = info["crs"] or "EPSG:4326"
        bbox = tuple(area.to_crs(lcrs).total_bounds)
        g = gpd.read_file(args.gpkg, layer=layer, bbox=bbox)
        if g.crs is None:
            g = g.set_crs(lcrs)
        n0 = len(g)
        if "fclass" in g.columns:
            if classes is not None:
                g = g[g["fclass"].isin(classes)]
            if drop_prefix:
                g = g[~g["fclass"].astype(str).str.startswith(drop_prefix)]
        # polygons are kept whole (their outline matters, clip edges would be fake shores)
        g = g[g.intersects(area.to_crs(g.crs).iloc[0])]
        if not g.empty:
            g.to_file(out, layer=name, driver="GPKG")
        print(f"[{name}] {layer}: {len(g)} features kept (of {n0} in bbox)")

    extract(lay_roads, "roads", drop_prefix=None if args.keep_tracks else "track")
    extract(lay_water, "water", classes=args.water_classes)
    extract(lay_ways, "waterways", classes=args.waterway_classes)
    print(f"[done] {out}")


if __name__ == "__main__":
    main()
