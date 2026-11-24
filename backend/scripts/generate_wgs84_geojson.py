import json
import os
import shutil
from shapely import wkb
import shapely.geometry

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sql_path = os.path.join(base_dir, "database", "migrations", "002_seed_hara_bogor.sql")
    geojson_path = os.path.join(base_dir, "reference", "data-hara-bogor", "hara-bogor.geojson")
    backup_path = os.path.join(base_dir, "reference", "data-hara-bogor", "hara-bogor-utm-backup.geojson")

    if not os.path.exists(backup_path):
        shutil.copyfile(geojson_path, backup_path)
        print(f"Backed up original UTM geojson to {backup_path}")

    # 1. Parse SQL geometries
    sql_geoms = {}
    with open(sql_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str.startswith("INSERT INTO"):
                parts = line_str.split("VALUES (")
                if len(parts) > 1:
                    val_str = parts[1].rstrip(");\n")
                    # Split safely by ', '
                    tokens = [t.strip().strip("'") for t in val_str.split(", ")]
                    hex_wkb = tokens[0]
                    obj_id = int(tokens[1])
                    geom = wkb.loads(bytes.fromhex(hex_wkb))
                    sql_geoms[obj_id] = geom

    print(f"Extracted {len(sql_geoms)} WGS84 geometries from SQL.")

    # 2. Read existing GeoJSON
    with open(geojson_path, "r", encoding="utf-8") as f:
        raw_geojson = json.load(f)

    all_bounds = []
    updated_features = []
    for feat in raw_geojson.get("features", []):
        props = feat.get("properties", {})
        oid = props.get("OBJECTID") or props.get("id")
        if oid in sql_geoms:
            geom = sql_geoms[oid]
            all_bounds.append(geom.bounds)
            new_geom = shapely.geometry.mapping(geom)
            feat["geometry"] = new_geom
            updated_features.append(feat)
        else:
            print(f"Warning: oid {oid} not found in SQL!")
            updated_features.append(feat)

    raw_geojson["features"] = updated_features
    raw_geojson["crs"] = {
        "type": "name",
        "properties": {
            "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
        }
    }

    # 3. Calculate bounding box
    minx = min(b[0] for b in all_bounds)
    miny = min(b[1] for b in all_bounds)
    maxx = max(b[2] for b in all_bounds)
    maxy = max(b[3] for b in all_bounds)
    center_lon = (minx + maxx) / 2
    center_lat = (miny + maxy) / 2

    print(f"Total features updated: {len(updated_features)}")
    print(f"WGS84 Bounding Box: min_lon={minx:.6f}, min_lat={miny:.6f}, max_lon={maxx:.6f}, max_lat={maxy:.6f}")
    print(f"Center: lon={center_lon:.6f}, lat={center_lat:.6f}")

    # 4. Save updated GeoJSON
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(raw_geojson, f, ensure_ascii=False)

    print(f"Successfully wrote WGS84 GeoJSON to {geojson_path}")

if __name__ == "__main__":
    main()
