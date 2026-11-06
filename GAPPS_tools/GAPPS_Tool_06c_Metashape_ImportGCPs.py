"""
GAPPS – Tool 6c – Shape2GCPs: import the GCP table into Agisoft Metashape
(metashape_import_osm_gcps.py)

Run INSIDE Agisoft Metashape (Tools > Run Script..., or the Python console).
Reads the <stem>_gcps.csv produced by GAPPS_Tool_06_Shape2GCPs.py / the Shape2GCPs GUI and, in the active
chunk, creates one marker per GCP with:
  * its projection on the camera (image pixel position), and
  * its reference coordinates, expressed in the chunk coordinate system.

Projections are created *unpinned* (blue flags) by default: open the image,
check each marker and drag it onto the exact feature (that pins it, green
flag). Use --pinned to create them as green flags directly.

The CSV can be a single-image table (<stem>_gcps.csv) or the combined
osm_gcps_all.csv: rows of cameras not in the active chunk are skipped, and
re-running updates existing markers instead of duplicating them.

Arguments (type them in the "Arguments" box of Tools > Run Script):
    <path/to/gcps.csv> [--only LABEL1,LABEL2] [--camera LABEL] [--pinned] [--default-z 1500]
                            [--acc-z 50] [--disable] [--utm-crs EPSG::32735]
                            [--set-chunk-crs EPSG::32735]

Coordinates and "unsupported datum transformation"
--------------------------------------------------
The CSV holds WGS84 lon/lat and UTM (WGS84 datum) coordinates. To avoid any
datum/geoid conversion inside Metashape the script writes them DIRECTLY when
the chunk CRS is based on WGS84:
  * chunk CRS geographic WGS84 (incl. "WGS 84 + EGM96/EGM2008 height") -> lon, lat
  * chunk CRS = the CSV UTM zone (incl. "+ EGM96 height" variants)      -> x_utm, y_utm
  * chunk CRS "Local Coordinates (m)" (default for non-georeferenced
    projects such as scans): the chunk is switched to the CSV UTM zone
Heights are written as given (DEM heights are orthometric, which matches the
"+ EGM height" systems; vs a pure ellipsoidal system the difference is the
geoid undulation, ~ -15 to -20 m around Lake Kivu: negligible for seed GCPs).
Only for other chunk CRSs is Metashape's conversion used; if that fails
(missing geoid grid, local datum...), either install the geoid in Metashape or
rerun with --set-chunk-crs EPSG::32735 (or EPSG::4326). Note: changing the
chunk CRS does NOT reproject reference values already in the chunk, so only
do it if cameras/markers have no reference coordinates yet (typical for scans).
"""
import csv
import math
import os
import sys

import Metashape

SCRIPT_VERSION = "2026-11-06d (multi-image CSV, local-coords + marker_crs aware)"


def parse_args(argv):
    opts = dict(csv=None, camera=None, pinned=False, default_z=None, acc_z=50.0,
                disable=False, utm_crs=None, set_chunk_crs=None, only=None)
    it = iter(argv)
    for a in it:
        if a == "--camera":
            opts["camera"] = next(it)
        elif a == "--pinned":
            opts["pinned"] = True
        elif a == "--default-z":
            opts["default_z"] = float(next(it))
        elif a == "--acc-z":
            opts["acc_z"] = float(next(it))
        elif a == "--disable":
            opts["disable"] = True
        elif a == "--utm-crs":
            opts["utm_crs"] = next(it)
        elif a == "--only":
            opts["only"] = set(next(it).split(","))
        elif a == "--set-chunk-crs":
            opts["set_chunk_crs"] = next(it)
        elif opts["csv"] is None:
            opts["csv"] = a
    return opts


def find_camera(chunk, label):
    for cam in chunk.cameras:
        if cam.label == label:
            return cam
    for cam in chunk.cameras:          # fall back on file name
        if cam.photo and os.path.splitext(os.path.basename(cam.photo.path))[0] == label:
            return cam
    return None


def _wkt(crs):
    for attr in ("wkt", "wkt2"):
        try:
            v = getattr(crs, attr)
            if v:
                return str(v)
        except Exception:  # noqa
            pass
    return ""


def is_local(crs):
    name = str(getattr(crs, "name", "") or "")
    return name.lower().startswith("local") or "LOCAL_CS[" in _wkt(crs).upper()


def crs_mode(chunk_crs, utm_auth):
    """'lonlat' / 'utm' when coordinates can be written as-is, else 'convert'."""
    auth = ""
    try:
        auth = (chunk_crs.authority or "").upper()
    except Exception:  # noqa
        pass
    if auth == "EPSG::4326":
        return "lonlat"
    if utm_auth and auth == utm_auth.upper():
        return "utm"
    w = _wkt(chunk_crs).upper().replace("_", " ")
    wgs84_datum = ("WGS 1984" in w or "WGS 84" in w or "WGS84" in w) and "ITRF" not in w
    if not wgs84_datum:
        return "convert"
    is_proj = "PROJCS[" in w or "PROJCRS[" in w
    if not is_proj:
        return "lonlat"                 # geographic WGS84, possibly + geoid height
    if utm_auth:
        code = utm_auth.split("::")[-1]          # e.g. 32735 -> zone 35, S
        if len(code) == 5 and code.startswith("32"):
            zone, hemi = int(code[3:]), "S" if code[2] == "7" else "N"
            if ("UTM ZONE %d%s" % (zone, hemi)) in w:
                return "utm"
    return "convert"


def main():
    print("metashape_import_osm_gcps.py version", SCRIPT_VERSION)
    opts = parse_args(sys.argv[1:])
    if opts["csv"] is None:
        opts["csv"] = Metashape.app.getOpenFileName("GCP CSV from osm_road_gcps.py", filter="*.csv")
    if not opts["csv"]:
        print("No CSV given.")
        return
    chunk = Metashape.app.document.chunk
    if chunk is None:
        raise RuntimeError("No active chunk.")

    wgs84 = Metashape.CoordinateSystem("EPSG::4326")
    if opts["set_chunk_crs"]:
        chunk.crs = Metashape.CoordinateSystem(opts["set_chunk_crs"])
        print("Chunk CRS set to %s" % opts["set_chunk_crs"])
    elif chunk.crs is None:
        chunk.crs = wgs84
        print("Chunk had no CRS: set to WGS84 (EPSG::4326).")

    with open(opts["csv"], newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("CSV is empty.")
        return

    utm_auth = opts["utm_crs"] or rows[0].get("utm_crs") or "EPSG::32735"
    if not opts["set_chunk_crs"] and is_local(chunk.crs):
        # a local (engineering) frame has no relation to the Earth: nothing can be
        # converted into it, and nothing is lost by switching (it has no datum)
        print("Chunk CRS is '%s' (local frame, not georeferenced): switching chunk to %s."
              % (getattr(chunk.crs, "name", chunk.crs), utm_auth))
        chunk.crs = Metashape.CoordinateSystem(utm_auth)
    # Metashape 2.x: markers may have their own CRS (Reference settings > Marker CRS)
    if hasattr(chunk, "marker_crs") and chunk.marker_crs is not None:
        if opts["set_chunk_crs"] or is_local(chunk.marker_crs):
            print("Marker CRS '%s' -> %s" % (getattr(chunk.marker_crs, "name", ""), chunk.crs.name))
            chunk.marker_crs = chunk.crs
    target_crs = chunk.marker_crs if getattr(chunk, "marker_crs", None) is not None else chunk.crs
    mode = crs_mode(target_crs, utm_auth)
    print("Marker reference CRS: %s -> %s" % (getattr(target_crs, "name", target_crs),
                                   {"lonlat": "writing lon/lat directly",
                                    "utm": "writing %s coordinates directly" % utm_auth,
                                    "convert": "converting with Metashape"}[mode]))
    utm = Metashape.CoordinateSystem(utm_auth) if mode == "convert" else None

    existing = {m.label: m for m in chunk.markers}
    n_new = n_upd = 0
    warned_z = False
    cam_label = None
    missing, flagged, done_cams = set(), set(), set()
    for r in rows:
        cam_label = opts["camera"] or r["camera"]
        if opts["only"] and cam_label not in opts["only"]:
            continue
        cam = find_camera(chunk, cam_label)
        if cam is None:
            if cam_label not in missing:
                print("skip: camera '%s' not in the active chunk" % cam_label)
                missing.add(cam_label)
            continue
        if r.get("flags"):
            if cam_label not in flagged:
                print("WARNING camera %s: matching flagged %s - check before trusting" % (cam_label, r["flags"]))
                flagged.add(cam_label)
        x_px, y_px = float(r["px_col"]), float(r["px_row"])
        if cam.sensor is not None and (x_px < 0 or y_px < 0 or
                                       x_px > cam.sensor.width or y_px > cam.sensor.height):
            print("WARNING %s: pixel (%.0f, %.0f) outside image %dx%d - wrong image resolution?"
                  % (r["label"], x_px, y_px, cam.sensor.width, cam.sensor.height))

        z_txt = r.get("z", "")
        if z_txt not in ("", None) and not math.isnan(float(z_txt)):
            z, acc_z = float(z_txt), opts["acc_z"]
        else:
            z = opts["default_z"] if opts["default_z"] is not None else 0.0
            acc_z = 1000.0
            if not warned_z:
                print("WARNING: no Z in CSV -> Z = %.1f with 1000 m accuracy "
                      "(rerun the matching with a DEM for real heights)" % z)
                warned_z = True

        lon, lat = float(r["lon"]), float(r["lat"])
        if mode == "lonlat":
            loc = Metashape.Vector([lon, lat, z])
        elif mode == "utm":
            loc = Metashape.Vector([float(r["x_utm"]), float(r["y_utm"]), z])
        else:
            loc, err = None, None
            for src, pt in ((wgs84, [lon, lat, z]), (utm, [float(r["x_utm"]), float(r["y_utm"]), z])):
                try:
                    loc = Metashape.CoordinateSystem.transform(Metashape.Vector(pt), src, target_crs)
                    break
                except Exception as e:  # noqa
                    err = e
            if loc is None:
                raise RuntimeError(
                    "Metashape cannot convert to the marker CRS '%s' (%s).\n"
                    "Fix: install the geoid grid used by that CRS in Metashape, or rerun with\n"
                    "     --set-chunk-crs %s   (or EPSG::4326)  if the chunk has no reference "
                    "coordinates yet." % (getattr(target_crs, "name", target_crs), err, utm_auth))

        label = r["label"]
        if label in existing:
            m = existing[label]
            n_upd += 1
        else:
            m = chunk.addMarker()
            m.label = label
            n_new += 1
        m.projections[cam] = Metashape.Marker.Projection(
            Metashape.Vector([x_px, y_px]), opts["pinned"])
        m.reference.location = loc
        acc = float(r.get("acc_xy_m") or 20.0)
        m.reference.accuracy = Metashape.Vector([acc, acc, acc_z])
        m.reference.enabled = not opts["disable"]
        done_cams.add(cam.label)

    print("OSM GCPs: %d markers created, %d updated on %d camera(s): %s"
          % (n_new, n_upd, len(done_cams), ", ".join(sorted(done_cams))))


main()
