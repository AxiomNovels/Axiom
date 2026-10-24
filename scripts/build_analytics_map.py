"""Rebuild the offline analytics map from Natural Earth's public-domain data."""
import json
from pathlib import Path
from urllib.request import urlopen

SOURCE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_110m_admin_0_countries.geojson"


def main():
    with urlopen(SOURCE, timeout=30) as response:
        data = json.load(response)
    countries = []
    for feature in data["features"]:
        properties = feature["properties"]
        code = properties.get("ISO_A2_EH") or properties.get("ISO_A2")
        if not code or len(code) != 2 or code == "AQ":
            continue
        geometry = feature["geometry"]
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        path = []
        for polygon in polygons:
            for ring in polygon:
                coordinates = [(round((lon+180)*2.5, 1), round((90-lat)*2.5, 1)) for lon, lat, *_ in ring]
                path.append("M" + "L".join(f"{x:g},{y:g}" for x, y in coordinates) + "Z")
        countries.append({"code": code, "name": properties["ADMIN"], "path": "".join(path)})
    destination = Path(__file__).resolve().parents[1]/"frontend/public/assets/analytics-world.json"
    destination.write_text(json.dumps({"source": SOURCE, "license": "Public domain; Natural Earth", "countries": countries}, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(countries)} map features ({destination.stat().st_size:,} bytes).")


if __name__ == "__main__":
    main()
