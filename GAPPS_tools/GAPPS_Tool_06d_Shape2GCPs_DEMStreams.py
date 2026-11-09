#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GAPPS – Tool 6d – Shape2GCPs: river network derived from a DEM

OpenStreetMap only maps the larger rivers in remote areas. This module derives a
stream network from a DEM (e.g. Copernicus GLO-30), used by Shape2GCPs as an
extra reference for the rivers drawn on the photos when the matching with the
OSM rivers fails.

Method
------
1. The DEM is resampled onto a UTM grid (default 60 m) covering the AOI.
2. Flow directions by priority-flood (Barnes et al. 2014): the grid is flooded
   from its edges, from the no-data cells and from the lakes (OSM water
   polygons, treated as outlets, so that no stream runs across a lake); every
   cell drains to the cell from which it was reached, which routes the water
   through pits and across flats.
3. Flow accumulation (contributing area); the cells draining more than
   `min_area_km2` are streams.
4. The streams are chained into lines between channel heads, junctions and
   outlets, and smoothed (D8 directions are quantised to 45 degrees).

Output: GeoPackage, layer "dem_streams" (UTM), attribute area_km2 (contributing
area at the downstream end of each line).

Example
-------
python GAPPS_Tool_06d_Shape2GCPs_DEMStreams.py --dem COPERNICUS_DEM_Kivu_WGS84.tif \\
       --aoi AOI_large.geojson --osm OSM_AOI_large.gpkg --out DEMstreams_AOI_large.gpkg

Software authorship: Antoine DILLE (RMCA), developed with Anthropic's Claude – 2026-11-09
"""
import argparse
import heapq
import math
import time
from pathlib import Path

import numpy as np


def _read_dem_utm(dem_path, bounds, crs, cell):
    import rasterio
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_origin
    x0, y0, x1, y1 = bounds
    W = int(math.ceil((x1 - x0) / cell))
    H = int(math.ceil((y1 - y0) / cell))
    tr = from_origin(x0, y1, cell, cell)
    z = np.full((H, W), np.nan, np.float32)
    with rasterio.open(dem_path) as src:
        reproject(source=rasterio.band(src, 1), destination=z, src_transform=src.transform, src_crs=src.crs,
                  src_nodata=src.nodata, dst_transform=tr, dst_crs=crs, dst_nodata=np.nan,
                  resampling=Resampling.average)
    return z, tr


def _rasterize(geoms, shape, tr):
    from rasterio.features import rasterize
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    if not geoms:
        return np.zeros(shape, bool)
    return rasterize(((g, 1) for g in geoms), out_shape=shape, transform=tr, fill=0, dtype="uint8").astype(bool)


def flow_priority_flood(z, outlet_mask, progress=None):
    """D8 receivers (flat index, -1 for outlets) and the processing order
    (outlets first, then upstream). z: float array with NaN = no data."""
    H, W = z.shape
    n = H * W
    zf = np.where(np.isfinite(z), z, -1e9).ravel().astype(np.float64)
    seed = outlet_mask.copy()
    seed[0, :] = seed[-1, :] = seed[:, 0] = seed[:, -1] = True
    seed |= ~np.isfinite(z)
    closed = seed.ravel().copy()
    recv = np.full(n, -1, np.int64)
    heap = [(zf[i], k, i) for k, i in enumerate(np.flatnonzero(seed.ravel()))]
    heapq.heapify(heap)
    counter = len(heap)
    order = np.empty(n, np.int64)
    m = 0
    offs = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    zl = zf.tolist()
    cl = closed.tolist()
    rv = recv.tolist()
    t0 = time.time()
    while heap:
        zc, _, i = heapq.heappop(heap)
        order[m] = i
        m += 1
        r, c = divmod(i, W)
        for dr, dc in offs:
            rr, cc = r + dr, c + dc
            if 0 <= rr < H and 0 <= cc < W:
                j = rr * W + cc
                if not cl[j]:
                    cl[j] = True
                    rv[j] = i
                    zj = zl[j]
                    counter += 1
                    heapq.heappush(heap, (zj if zj > zc else zc, counter, j))
        if progress and m % 500000 == 0:
            progress(f"  flow routing {m / n * 100:.0f}% ({time.time() - t0:.0f} s)")
    return np.array(rv, np.int64), order[:m]


def accumulate(recv, order, cell_area):
    acc = np.full(len(recv), cell_area, np.float64).tolist()
    rv = recv.tolist()
    for i in order[::-1].tolist():
        d = rv[i]
        if d >= 0:
            acc[d] += acc[i]
    return np.array(acc)


def chain_streams(recv, stream, W, x0, y1, cell, acc, smooth=2):
    """Lines (UTM coordinates) between channel heads, junctions and outlets."""
    idx = np.flatnonzero(stream)
    down = recv[idx]
    ok = (down >= 0) & stream[np.maximum(down, 0)]
    indeg = np.bincount(down[ok], minlength=len(stream))
    starts = idx[(indeg[idx] == 0) | (indeg[idx] >= 2)]
    rv = recv.tolist()
    st = stream.tolist()
    ind = indeg.tolist()
    lines, areas = [], []
    for s in starts.tolist():
        path = [s]
        c = s
        while True:
            d = rv[c]
            if d < 0 or not st[d]:
                break
            path.append(d)
            if ind[d] >= 2:
                break
            c = d
        if len(path) < 2:
            continue
        p = np.array(path)
        r, cc = np.divmod(p, W)
        xy = np.column_stack([x0 + (cc + 0.5) * cell, y1 - (r + 0.5) * cell])
        if smooth and len(xy) > 2 * smooth + 2:
            k = 2 * smooth + 1
            ker = np.ones(k) / k
            inner = np.column_stack([np.convolve(xy[:, 0], ker, "valid"), np.convolve(xy[:, 1], ker, "valid")])
            xy = np.vstack([xy[:1], inner, xy[-1:]])
        lines.append(xy)
        areas.append(acc[path[-1]] / 1e6)
    return lines, areas


def make_dem_streams(dem, aoi, out, osm=None, cell=60.0, min_area_km2=0.5, buffer=5000.0, crs=None,
                     progress=print):
    """Build the DEM river network of an AOI and write it to `out` (GeoPackage,
    layer 'dem_streams'). Returns the output path."""
    import geopandas as gpd
    from shapely.geometry import LineString
    t_start = time.time()
    aoi_g = gpd.read_file(aoi)
    if aoi_g.crs is None:
        aoi_g = aoi_g.set_crs(4326)
    crs = crs or aoi_g.to_crs(4326).estimate_utm_crs()
    area = aoi_g.to_crs(crs).geometry.union_all().buffer(buffer)
    bounds = area.bounds
    progress(f"[dem streams] DEM -> {cell:.0f} m UTM grid ({crs.to_string() if hasattr(crs, 'to_string') else crs})")
    z, tr = _read_dem_utm(dem, bounds, crs, cell)
    H, W = z.shape
    progress(f"[dem streams] grid {W} x {H} ({W * H / 1e6:.1f} M cells)")
    lakes = np.zeros(z.shape, bool)
    if osm:
        try:
            import pyogrio
            lays = [str(l[0]) for l in pyogrio.list_layers(osm)]
            lay = next((l for l in lays if l.lower() in ("water",) or "water_a" in l.lower()), None)
            if lay:
                wg = gpd.read_file(osm, layer=lay, mask=gpd.GeoSeries([area], crs=crs))
                if wg.crs is None:
                    wg = wg.set_crs(4326)
                wg = wg.to_crs(crs)
                big = wg[wg.geometry.area > 0.05e6]                 # lakes / reservoirs > 5 ha
                lakes = _rasterize(list(big.geometry), z.shape, tr)
                progress(f"[dem streams] {len(big)} lake(s) used as outlets")
        except Exception as e:  # noqa
            progress(f"[dem streams] (lakes not used: {e})")
    recv, order = flow_priority_flood(z, lakes, progress)
    progress(f"[dem streams] flow routing done ({time.time() - t_start:.0f} s)")
    acc = accumulate(recv, order, cell * cell)
    stream = (acc >= min_area_km2 * 1e6) & np.isfinite(z).ravel() & ~lakes.ravel()
    lines, areas = chain_streams(recv, stream, W, tr.c, tr.f, cell, acc)
    g = gpd.GeoDataFrame(dict(area_km2=np.round(areas, 3)), geometry=[LineString(l) for l in lines], crs=crs)
    g = g[g.intersects(area)]
    out = Path(out)
    if out.exists():
        out.unlink()
    g.to_file(out, layer="dem_streams", driver="GPKG")
    progress(f"[dem streams] {len(g)} lines, {g.length.sum() / 1000:.0f} km (catchment >= {min_area_km2} km2) "
             f"-> {out}  ({time.time() - t_start:.0f} s)")
    return str(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dem", required=True)
    ap.add_argument("--aoi", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--osm", default=None, help="OSM extract with a 'water' layer (lakes used as outlets)")
    ap.add_argument("--cell", type=float, default=60.0, help="grid cell (m), default 60")
    ap.add_argument("--min-area", type=float, default=0.5, help="minimum catchment of a stream (km2), default 0.5")
    a = ap.parse_args(argv)
    make_dem_streams(a.dem, a.aoi, a.out, a.osm, a.cell, a.min_area)


if __name__ == "__main__":
    main()
