"""
GAPPS – Tool 6e – Shape2GCPs: convert GCP files from UTM (or any projected CRS) to WGS84 lon/lat

Since November 2026 the Shape2GCPs tools export the GCPs in WGS84 (EPSG:4326) only. This tool updates
older files, or files exported from Metashape in a projected CRS:

  * GCP tables of Tool 6 (<stem>_gcps.csv, osm_gcps_all.csv): lon/lat recomputed from x_utm/y_utm (with the
    utm_crs column), the UTM columns removed, crs = EPSG::4326
  * other CSV tables (e.g. Metashape "Export Reference" / markers CSV): the X/Easting and Y/Northing columns
    are replaced by lon / lat (give the CRS with --crs if the file does not say it)
  * Metashape XML (File > Export > Export Markers, or a project .xml): marker (and camera) reference
    coordinates converted, chunk reference CRS set to WGS84
  * GeoPackage / shapefile / GeoJSON of points: reprojected to EPSG:4326

Usage
-----
python GAPPS_Tool_06e_GCPs_UTM2WGS84.py file1.csv [file2.xml ...] [--crs EPSG:32735] [--in-place]

Without --in-place the result is written next to the input as <name>_WGS84.<ext>; with --in-place the input
is replaced and a copy of the original is kept as <name>_UTM_backup.<ext>.
Heights (z) are not changed.
"""
import argparse
import csv
import os
import re
import shutil
import sys

UTM_COLUMNS = ("x_utm", "y_utm", "utm_crs")
X_NAMES = ("x_utm", "x", "easting", "east", "e", "x/easting", "x/east", "x_easting", "x/longitude", "x/lon")
Y_NAMES = ("y_utm", "y", "northing", "north", "n", "y/northing", "y/north", "y_northing", "y/latitude", "y/lat")
CRS_NAMES = ("utm_crs", "crs", "epsg", "srs")


def crs_from_comment(lines):
    """CRS named in Metashape's comment lines ('#CoordinateSystem: WGS 84 / UTM zone 35S'), or None."""
    for line in lines:
        m = re.search(r"(?i)utm zone (\d{1,2})\s*([ns])", line)
        if line.startswith("#") and m:
            return f"EPSG:{(32600 if m.group(2).lower() == 'n' else 32700) + int(m.group(1))}"
        m = re.search(r"(?i)epsg::?(\d{4,6})", line)
        if line.startswith("#") and m:
            return f"EPSG:{m.group(1)}"
    return None


def norm_crs(s):
    """'EPSG::32735', 'epsg:32735', '32735' -> 'EPSG:32735' (anything else is returned as given)."""
    s = str(s).strip()
    m = re.fullmatch(r"(?i)(?:epsg\s*:{1,2}\s*)?(\d{4,6})", s)
    return f"EPSG:{m.group(1)}" if m else s


def out_path(path, in_place):
    root, ext = os.path.splitext(path)
    if in_place:
        backup = f"{root}_UTM_backup{ext}"
        shutil.copy2(path, backup)
        return path, backup
    return f"{root}_WGS84{ext}", None


def _transformer(crs):
    from pyproj import CRS, Transformer
    c = CRS.from_user_input(norm_crs(crs))
    if c.is_geographic:
        return None
    return Transformer.from_crs(c, 4326, always_xy=True)


def _key(name):
    return name.strip().lstrip("#").strip().lower()


def convert_csv(path, crs=None, in_place=False):
    """:return: (output path, number of points converted, message)"""
    with open(path, newline="", encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    # Metashape writes comment lines starting with '#', the last of them being the header
    head_i = 0
    while head_i + 1 < len(lines) and lines[head_i].startswith("#") and lines[head_i + 1].startswith("#"):
        head_i += 1
    sample = "\n".join(lines[head_i:head_i + 5])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(lines[head_i:], dialect))
    if not rows:
        return None, 0, "empty file"
    header, data = rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]
    keys = [_key(h) for h in header]
    tool6 = "px_col" in keys and "lon" in keys
    xi = next((keys.index(n) for n in X_NAMES if n in keys), None)
    yi = next((keys.index(n) for n in Y_NAMES if n in keys), None)
    if xi is None or yi is None:
        if "lon" in keys and "lat" in keys:
            return None, 0, "already in lon/lat (no X/Y columns)"
        return None, 0, f"no X/Easting and Y/Northing columns found in {header}"
    ci = next((keys.index(n) for n in CRS_NAMES if n in keys), None)
    src = crs or (data[0][ci] if ci is not None and data and data[0][ci].strip() else None) \
        or crs_from_comment(lines[:head_i])
    vals = [(r[xi], r[yi]) for r in data if len(r) > max(xi, yi) and r[xi].strip() and r[yi].strip()]
    if not vals:
        return None, 0, "no coordinates"
    xs = [float(a) for a, _ in vals]
    ys = [float(b) for _, b in vals]
    if max(map(abs, xs)) <= 180 and max(map(abs, ys)) <= 90 and not tool6:
        return None, 0, "coordinates already look like lon/lat: nothing to do"
    if src is None:
        return None, 0, "CRS of the coordinates unknown: give it with --crs (e.g. EPSG:32735 = UTM 35S)"
    tr = _transformer(src)
    if tr is None:
        return None, 0, f"{src} is already geographic: nothing to do"

    n = 0
    if tool6:
        li, ai = keys.index("lon"), keys.index("lat")
        drop = [i for i, k in enumerate(keys) if k in UTM_COLUMNS or k == "crs"]
        new_header = [h for i, h in enumerate(header) if i not in drop] + ["crs"]
        new_data = []
        for r in data:
            r = r + [""] * (len(header) - len(r))
            if r[xi].strip() and r[yi].strip():
                lon, lat = tr.transform(float(r[xi]), float(r[yi]))
                r[li], r[ai] = f"{lon:.8f}", f"{lat:.8f}"
                n += 1
            new_data.append([v for i, v in enumerate(r) if i not in drop] + ["EPSG::4326"])
    else:
        new_header = list(header)
        if not header[0].startswith("#"):        # plain table: say what the columns now hold
            new_header[xi], new_header[yi] = "lon", "lat"
        if ci is not None:
            new_header[ci] = header[ci]
        new_data = []
        for r in data:
            r = list(r)
            if len(r) > max(xi, yi) and r[xi].strip() and r[yi].strip():
                lon, lat = tr.transform(float(r[xi]), float(r[yi]))
                r[xi], r[yi] = f"{lon:.8f}", f"{lat:.8f}"
                n += 1
            if ci is not None and len(r) > ci:
                r[ci] = "EPSG::4326"
            new_data.append(r)
    dst, backup = out_path(path, in_place)
    with open(dst, "w", newline="", encoding="utf-8") as f:
        for line in lines[:head_i]:
            if re.match(r"(?i)#\s*coordinate ?system", line):
                line = "#CoordinateSystem: WGS 84 (EPSG::4326)"
            f.write(line + "\n")
        wr = csv.writer(f, dialect)
        wr.writerow(new_header)
        wr.writerows(new_data)
    msg = f"{n} points converted from {norm_crs(src)}" + (f" (backup: {os.path.basename(backup)})" if backup else "")
    if not tool6 and header[0].startswith("#"):
        msg += "; in Metashape, import this file with the WGS 84 (EPSG::4326) coordinate system"
    return dst, n, msg


def convert_metashape_xml(path, crs=None, in_place=False):
    """Marker (and camera) reference coordinates of a Metashape XML converted to lon/lat."""
    import xml.etree.ElementTree as ET
    from pyproj import CRS
    tree = ET.parse(path)
    root = tree.getroot()
    chunk = root.find("chunk") if root.tag == "document" else root
    if chunk is None:
        chunk = root
    ref_el = chunk.find("reference")
    pts = [(float(el.get("x")), float(el.get("y"))) for el in chunk.iter("reference")
           if el is not ref_el and el.get("x") is not None and el.get("y") is not None]
    if not pts:
        return None, 0, "no reference coordinates in this file"
    if crs is None and max(abs(x) for x, _ in pts) <= 180 and max(abs(y) for _, y in pts) <= 90:
        return None, 0, "the coordinates already look like lon/lat: nothing to do"
    wkt = (ref_el.text or "").strip() if ref_el is not None else ""
    if crs is None:
        if not wkt or wkt.upper().startswith("LOCAL_CS"):
            return None, 0, "the chunk CRS is local or missing: give the CRS of the coordinates with --crs"
        src = CRS.from_wkt(wkt)
    else:
        src = CRS.from_user_input(norm_crs(crs))
    if src.is_geographic:
        return None, 0, "the coordinates are already geographic: nothing to do"
    tr = _transformer(src.to_wkt())
    n = 0
    for el in chunk.iter("reference"):
        if el is ref_el or el.get("x") is None or el.get("y") is None:
            continue
        lon, lat = tr.transform(float(el.get("x")), float(el.get("y")))
        el.set("x", f"{lon:.10f}")
        el.set("y", f"{lat:.10f}")
        n += 1
    if ref_el is not None:
        ref_el.text = CRS.from_epsg(4326).to_wkt("WKT1_GDAL")
    dst, backup = out_path(path, in_place)
    tree.write(dst, encoding="UTF-8", xml_declaration=True)
    return dst, n, (f"{n} reference positions converted from {src.name}"
                    + (f" (backup: {os.path.basename(backup)})" if backup else ""))


def convert_vector(path, crs=None, in_place=False):
    import geopandas as gpd
    import pyogrio
    layers = [l[0] for l in pyogrio.list_layers(path)]
    dst, backup = out_path(path, in_place)
    n, done = 0, []
    frames = {}
    for lay in layers:
        g = gpd.read_file(path, layer=lay)
        if g.crs is None:
            if crs is None:
                return None, 0, f"layer {lay} has no CRS: give it with --crs"
            g = g.set_crs(norm_crs(crs))
        frames[lay] = g.to_crs(4326)
        n += len(g)
        done.append(lay)
    if in_place and os.path.splitext(path)[1].lower() == ".gpkg":
        os.remove(path)
    for i, (lay, g) in enumerate(frames.items()):
        kw = dict(layer=lay) if os.path.splitext(dst)[1].lower() == ".gpkg" else {}
        g.to_file(dst, **kw)
    return dst, n, f"{n} features of {len(done)} layer(s) reprojected to EPSG:4326" + (
        f" (backup: {os.path.basename(backup)})" if backup else "")


def convert_file(path, crs=None, in_place=False):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".csv", ".txt"):
        return convert_csv(path, crs, in_place)
    if ext == ".xml":
        return convert_metashape_xml(path, crs, in_place)
    if ext in (".gpkg", ".shp", ".geojson", ".json"):
        return convert_vector(path, crs, in_place)
    return None, 0, f"unsupported file type {ext}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--crs", default=None, help="CRS of the input coordinates if the file does not say it "
                                                 "(e.g. EPSG:32735 = WGS 84 / UTM 35S)")
    ap.add_argument("--in-place", action="store_true", help="replace the input (a _UTM_backup copy is kept)")
    a = ap.parse_args(argv)
    ok = True
    for p in a.files:
        try:
            dst, n, msg = convert_file(p, a.crs, a.in_place)
        except Exception as e:  # noqa
            dst, n, msg = None, 0, f"{type(e).__name__}: {e}"
        print(f"{p}: {msg}" + (f"\n   -> {dst}" if dst else ""))
        ok = ok and dst is not None
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
