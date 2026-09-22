#!/usr/bin/env bash
set -euo pipefail

KEYVAULT_NAME="$1"
RESOURCE_GROUP_NAME="$2"
ENABLE_ACCESS="$3"
WORKER_ID="$4"
SUBSCRIPTION_ID="$5"

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

  az role assignment create \
    --role "Key Vault Secrets Officer" \
    --assignee-object-id $WORKER_ID \
    --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.KeyVault/vaults/$KEYVAULT_NAME

elif [ "$ENABLE_ACCESS" = "false" ]; then
  echo "Disabling access for $KEYVAULT_NAME..."

  az keyvault network-rule remove \
    --name "$KEYVAULT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --ip-address "$WORKER_IP" > /dev/null || true

  az keyvault update \
    --name "$KEYVAULT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --public-network-access Disabled > /dev/null || true

  az role assignment delete \
    --role "Key Vault Secrets Officer" \
    --assignee-object-id $WORKER_ID \
    --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.KeyVault/vaults/$KEYVAULT_NAME

else
  echo "Invalid value for enable_access: $ENABLE_ACCESS"
  exit 1
fi

sleep 30