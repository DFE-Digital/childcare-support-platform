#!/usr/bin/env bash
set -euo pipefail

KEYVAULT_NAME="$1"
RESOURCE_GROUP_NAME="$2"
ENABLE_ACCESS="$3"

WORKER_IP=$(curl -s https://api.ipify.org || curl -s https://ifconfig.me/ip || true)
if [ -z "$WORKER_IP" ]; then
  echo "Error: Could not retrieve worker IP address"
  exit 1
fi

echo "Worker IP: $WORKER_IP"

if [ "$ENABLE_ACCESS" = "true" ]; then
  echo "Enabling access for $KEYVAULT_NAME..."

  az keyvault update \
    --name "$KEYVAULT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --public-network-access Enabled > /dev/null

  az keyvault network-rule add \
    --name "$KEYVAULT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --ip-address "$WORKER_IP" > /dev/null

elif [ "$ENABLE_ACCESS" = "false" ]; then
  echo "Disabling access for $STORAGE_ACCOUNT_NAME..."

  az keyvault network-rule remove \
    --name "$KEYVAULT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --ip-address "$WORKER_IP" > /dev/null || true

  az keyvault update \
    --name "$KEYVAULT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --public-network-access Disabled > /dev/null

else
  echo "Invalid value for enable_access: $ENABLE_ACCESS"
  exit 1
fi

sleep 30