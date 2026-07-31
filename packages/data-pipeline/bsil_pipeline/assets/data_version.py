from datetime import datetime, timezone
from pathlib import Path

from dagster import asset, AssetExecutionContext, Config, MetadataValue

from bsil_pipeline.automation import PIPELINE_CONDITION


class DataVersionConfig(Config):
    output_dir: str = "/opt/dagster/app/output/app"


@asset(
    group_name="publish",
    deps=["validate_exports"],
    automation_condition=PIPELINE_CONDITION,
)
def data_version(context: AssetExecutionContext, config: DataVersionConfig):
    """Write data_version.txt with git commit and timestamp."""
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stamp_path = Path("/opt/dagster/app/data/.git-commit")
    commit = stamp_path.read_text().strip() if stamp_path.exists() else "unknown"
    if stamp_path.exists():
        stamp_path.unlink()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    version_file = output_dir / "data_version.txt"
    version_file.write_text(f"commit: {commit}\ntimestamp: {timestamp}\n")

    context.log.info(f"Wrote data_version.txt: commit={commit}, timestamp={timestamp}")
    return MetadataValue.text(f"{commit} @ {timestamp}")
