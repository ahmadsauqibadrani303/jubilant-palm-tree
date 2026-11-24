import re
import json
from shapely import wkb
import shapely.geometry
from pyproj import Transformer

print("Checking WKB from SQL vs UTM transformation...")

# 1. Load from SQL
sql_features = {}
with open("database/migrations/002_seed_hara_bogor.sql", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip().startswith("INSERT INTO"):
            # Format: VALUES ('0106...', 1, ...)
            parts = line.split("VALUES (")
            if len(parts) > 1:
                val_str = parts[1].rstrip(");\n")
                # first item is 'HEX_WKB', second is objectid
                tokens = [t.strip().strip("'") for t in val_str.split(", ")]
                hex_wkb = tokens[0]
                obj_id = int(tokens[1])
                geom = wkb.loads(bytes.fromhex(hex_wkb))
                sql_features[obj_id] = (geom, tokens)

print(f"Loaded {len(sql_features)} features from 002_seed_hara_bogor.sql")

# 2. Check feature 1 bounds
geom1 = sql_features[1][0]
print(f"Feature 1 WGS84 bounds: {geom1.bounds}")
print(f"Feature 1 geom type: {geom1.geom_type}")
geojson_geom1 = shapely.geometry.mapping(geom1)
print(f"Feature 1 sample coordinates: {geojson_geom1['coordinates'][0][0][:2]}")
