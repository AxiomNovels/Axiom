"""Print the vendored analytics map JSON from Natural Earth 5.1.2 (public domain).

Coordinates use the same 1000x500 equirectangular projection as the bubble map.
Simplification and rounding keep the asset small without runtime dependencies.
"""
import json
import math
import urllib.request

SOURCE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_50m_admin_0_countries.geojson"


def simplify(points, tolerance=0.18):
    if len(points) <= 2:
        return points
    x, y = points[0]
    dx, dy = points[-1][0] - x, points[-1][1] - y
    length = dx * dx + dy * dy
    def distance(point):
        t = max(0, min(1, ((point[0] - x) * dx + (point[1] - y) * dy) / length)) if length else 0
        return math.hypot(point[0] - x - t * dx, point[1] - y - t * dy)
    index = max(range(1, len(points) - 1), key=lambda i: distance(points[i]))
    if distance(points[index]) <= tolerance:
        return [points[0], points[-1]]
    return simplify(points[:index + 1], tolerance)[:-1] + simplify(points[index:], tolerance)


def project(point):
    return [round((point[0] + 180) / 360 * 1000, 2), round((90 - point[1]) / 180 * 500, 2)]


def main():
    with urllib.request.urlopen(SOURCE, timeout=30) as response:
        source = json.load(response)
    countries = []
    for feature in source["features"]:
        properties, geometry = feature["properties"], feature["geometry"]
        code = properties["ISO_A2_EH"]
        if code == "-99":
            code = properties["ISO_A2"]
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        paths = []
        for polygon in polygons:
            for ring in polygon:
                points = simplify(ring)
                if len(points) < 4:
                    continue
                paths.append("M" + "L".join(",".join(map(str, project(point))) for point in points) + "Z")
        countries.append({"code": code, "continent": properties["CONTINENT"],
                          "point": project([properties["LABEL_X"], properties["LABEL_Y"]]), "path": "".join(paths)})
    print(json.dumps({"source": "Natural Earth 5.1.2, public domain", "countries": countries}, separators=(",", ":")))


if __name__ == "__main__":
    main()
