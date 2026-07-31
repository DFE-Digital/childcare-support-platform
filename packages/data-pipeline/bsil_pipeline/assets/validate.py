"""Dagster asset for post-publish Zod validation of providers."""

import json
import os
import subprocess  # nosec B404

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource

SCHEMAS_DIR = "/opt/dagster/app/schemas"
NODE_BIN = os.path.join(SCHEMAS_DIR, "node_modules", ".bin")


def _ensure_node_deps(context):
    """Install schemas package dependencies if node_modules is missing."""
    # Check for the generated Prisma client — the actual artifact we need
    prisma_client = os.path.join(
        SCHEMAS_DIR, "node_modules", ".prisma", "client", "default.js"
    )
    if os.path.exists(prisma_client):
        return

    context.log.info("Installing schemas node dependencies...")
    result = subprocess.run(  # nosec B603 B607
        ["npm", "install", "--omit=dev"],
        capture_output=True,
        text=True,
        cwd=SCHEMAS_DIR,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"npm install failed: {result.stderr}")

    # Generate Prisma client for this platform
    context.log.info("Generating Prisma client...")
    result = subprocess.run(  # nosec B603
        [
            os.path.join(NODE_BIN, "prisma"),
            "generate",
            "--schema",
            os.path.join(SCHEMAS_DIR, "prisma", "schema.prisma"),
            "--generator",
            "client",
        ],
        capture_output=True,
        text=True,
        cwd=SCHEMAS_DIR,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"prisma generate failed: {result.stderr}")


@asset(
    group_name="publish",
    deps=["publish_providers"],
    automation_condition=PIPELINE_CONDITION,
)
def validate_published(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Validate published providers against the Zod schema spec.

    Runs the Node.js validation script which checks every provider in
    published.providers against the generated Zod schemas and writes
    results into metadata.validation.
    """
    _ensure_node_deps(context)

    db_url = (
        f"postgresql://{bsil_postgres.user}:{bsil_postgres.password}"
        f"@{bsil_postgres.host}:{bsil_postgres.port}/{bsil_postgres.dbname}"
        f"?schema=published"
    )

    result = subprocess.run(  # nosec B603
        [
            os.path.join(NODE_BIN, "tsx"),
            os.path.join(SCHEMAS_DIR, "src", "validate-published.ts"),
        ],
        capture_output=True,
        text=True,
        cwd=SCHEMAS_DIR,
        env={**os.environ, "DATABASE_URL": db_url},
        timeout=600,
    )

    # Log stderr (progress lines)
    if result.stderr:
        for line in result.stderr.strip().splitlines():
            context.log.info(line)

    if result.returncode != 0:
        context.log.error(f"Validation script stderr: {result.stderr}")
        raise RuntimeError(f"Validation script exited with code {result.returncode}")

    report = json.loads(result.stdout)
    context.log.info(
        f"Validation: {report['valid']}/{report['total']} pass, "
        f"{report['invalid']} fail"
    )

    report_path = "/opt/dagster/app/output/validation_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    context.log.info(f"Report written to {report_path}")

    return MetadataValue.json(report)
