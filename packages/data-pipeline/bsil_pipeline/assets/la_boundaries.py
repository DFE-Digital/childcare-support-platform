"""Generate simplified LA boundary GeoJSON from ONS BFC (Boundaries Full Clipped).

Reads the pre-clipped (Mean High Water) LAD boundaries GeoJSON, simplifies with
shapely, and writes a GeoJSON FeatureCollection. Source is already in WGS84.
"""

import json
from pathlib import Path

from dagster import asset, AssetExecutionContext, Config, MetadataValue
from shapely.geometry import shape

SIMPLIFY_TOLERANCE = 0.001  # ~110m at UK latitudes


class LaBoundariesConfig(Config):
    source_dir: str = "/opt/dagster/app/source_data"
    output_dir: str = "/opt/dagster/app/output"


def generate_la_boundaries(source_dir: Path, output_path: Path, log) -> int:
    """Read ONS BFC GeoJSON, simplify geometries, write output."""
    source_dir = Path(source_dir)
    bfc_files = sorted(source_dir.glob("Local_Authority_Districts*BFC*.geojson"))
    if not bfc_files:
        log.error(f"No BFC GeoJSON found in {source_dir}")
        return 0

    bfc_path = bfc_files[0]
    log.info(f"Reading ONS BFC from: {bfc_path}")

    with open(bfc_path) as f:
        source = json.load(f)

    source_features = source.get("features", [])
    log.info(f"Read {len(source_features)} features")

    features = []
    for feat in source_features:
        props = feat.get("properties", {})
        code = props.get("LAD25CD", "")
        name = props.get("LAD25NM", "")
        if not code or not feat.get("geometry"):
            continue

        geom = shape(feat["geometry"])
        geom = geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)

        features.append(
            {
                "type": "Feature",
                "properties": {"LAD25CD": code, "LAD25NM": name},
                "geometry": geom.__geo_interface__,
            }
        )

    geojson = {"type": "FeatureCollection", "features": features}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(geojson, f)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    log.info(f"Wrote {len(features)} features to {output_path} ({size_mb:.1f} MB)")
    return len(features)


@asset(group_name="os")
def la_boundaries(context: AssetExecutionContext, config: LaBoundariesConfig):
    """Generate simplified LA boundary GeoJSON from ONS BFC.

    Reads the ONS Boundaries Full Clipped GeoJSON (pre-clipped to Mean High Water),
    simplifies geometries (0.002° tolerance ≈ 220m), and writes a GeoJSON
    FeatureCollection to output/la_boundaries.geojson.
    """
    source_dir = Path(config.source_dir)
    output_path = Path(config.output_dir) / "la_boundaries.geojson"

    count = generate_la_boundaries(source_dir, output_path, context.log)

    if count == 0:
        return {"error": MetadataValue.text("No boundaries generated")}

    return {
        "features": MetadataValue.int(count),
        "output_path": MetadataValue.path(str(output_path)),
    }
