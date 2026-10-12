#!/usr/bin/env bash
set -euo pipefail

FUNCTION_APP_NAME="$1"
RESOURCE_GROUP_NAME="$2"
SUBSCRIPTION_ID="$3"
ENABLE_ACCESS="$4"

RULE_NAME="github-deploy-runner"

WORKER_IP=$(curl -s https://api.ipify.org || curl -s https://ifconfig.me/ip || true)
if [ -z "$WORKER_IP" ]; then
  echo "Error: Could not retrieve worker IP address"
  exit 1
fi

echo "Worker IP: $WORKER_IP"

if [ "$ENABLE_ACCESS" = "true" ]; then
  echo "Allowing $WORKER_IP to reach the SCM site of $FUNCTION_APP_NAME..."

  # Clear any rule left behind by a previous failed run
  az functionapp config access-restriction remove \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --subscription "$SUBSCRIPTION_ID" \
    --rule-name "$RULE_NAME" \
    --scm-site true || true

  az functionapp config access-restriction add \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --subscription "$SUBSCRIPTION_ID" \
    --rule-name "$RULE_NAME" \
    --action Allow \
    --ip-address "$WORKER_IP" \
    --priority 100 \
    --scm-site true

  # Access restriction changes take a little while to apply
elif [ "$ENABLE_ACCESS" = "false" ]; then
  echo "Removing runner access rule from $FUNCTION_APP_NAME..."

  az functionapp config access-restriction remove \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --subscription "$SUBSCRIPTION_ID" \
    --rule-name "$RULE_NAME" \
    --scm-site true || echo "No '$RULE_NAME' rule found; nothing to remove."
else
  echo "Invalid value for ENABLE_ACCESS: $ENABLE_ACCESS"
  exit 1
fi

sleep 30