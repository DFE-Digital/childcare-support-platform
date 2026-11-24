#!/usr/bin/env bash
# Phase 1 of environment retirement: destroy Front Door routes and rules first.
#
# Azure rejects deleting the last origin in an origin group while a route or
# rule still references that group. Resources that have been removed from
# config are destroyed using the dependencies recorded in state, and those
# don't include a rule -> origin edge, so the order has to be forced here.
#
# Usage: retire-edge-routing.sh [extra terraform destroy args]
# Pass the same -var-file / -var arguments as the plan step, plus -input=false.
#
# Safe to re-run: exits without doing anything once no routes or rules remain
# in state. Run after `terraform init` and before the normal plan/apply.
set -euo pipefail

mapfile -t addresses < <(
  terraform state list | grep -E '(^|\.)azurerm_cdn_frontdoor_(route|rule)\.' || true
)

if [ "${#addresses[@]}" -eq 0 ]; then
  echo "No Front Door routes or rules in state; skipping phase 1."
  exit 0
fi

targets=()
for address in "${addresses[@]}"; do
  targets+=("-target=${address}")
done

echo "Phase 1: destroying ${#addresses[@]} Front Door route/rule resources:"
printf '  %s\n' "${addresses[@]}"

terraform destroy -auto-approve "$@" "${targets[@]}"