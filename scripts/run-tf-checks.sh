#!/usr/bin/env bash
set -eo pipefail

TF_DIR="infrastructure/terraform"

# Have there been any changes to terraform?
git diff --quiet HEAD -- $TF_DIR || CODE=$?

if [[ $CODE -eq 0 ]]; then
  # No terraform changes have been made - no reason to continue
  exit 0
else
  echo "[PRE-COMMIT]: terraform changes have been made. Running format check and validation."
fi

# Run a format check in the terraform directory
# Pipe the stdout to dev/null as we don't want to print it out
terraform -chdir=$TF_DIR fmt -check >/dev/null || FMT_CODE=$?

if [[ $FMT_CODE -ne 0 ]]; then
  echo "[PRE-COMMIT]: terraform fmt -check failed. Please run terraform fmt and try again."
  exit 1
fi

# Run validation in the terraform directory
# Pipe the stderr to dev/null as we don't want to print it out
terraform -chdir=$TF_DIR validate 2>/dev/null || VAL_CODE=$?

if [[ $VAL_CODE -ne 0 ]]; then
  echo "[PRE-COMMIT]: terraform validate failed. Please fix any validation errors and try again."
  exit 1
fi
