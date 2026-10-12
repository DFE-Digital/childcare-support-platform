#!/usr/bin/env bash
set -euo pipefail

STORAGE_ACCOUNT_NAME="$1"
RESOURCE_GROUP_NAME="$2"
SUBSCRIPTION_ID="$3"
CONTAINER_NAME="$4"
WORKER_ID="$5"
ENABLE_ACCESS="$6"

WORKER_IP=$(curl -s https://api.ipify.org || curl -s https://ifconfig.me/ip || true)
if [ -z "$WORKER_IP" ]; then
  echo "Error: Could not retrieve worker IP address"
  exit 1
fi

echo "Worker IP: $WORKER_IP"

if [ "$ENABLE_ACCESS" = "true" ]; then
  echo "Enabling access for $STORAGE_ACCOUNT_NAME..."

  az storage account update \
    --name "$STORAGE_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --public-network-access Enabled > /dev/null

  az storage account network-rule add \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --ip-address "$WORKER_IP" > /dev/null

  az role assignment create \
    --role "Storage Blob Data Contributor" \
    --assignee-object-id $WORKER_ID \
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_NAME/blobServices/default/containers/$CONTAINER_NAME"
elif [ "$ENABLE_ACCESS" = "false" ]; then
  echo "Disabling access for $STORAGE_ACCOUNT_NAME..."

  az storage account network-rule remove \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --ip-address "$WORKER_IP" > /dev/null || true

  az storage account update \
    --name "$STORAGE_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --public-network-access Disabled > /dev/null

  az role assignment delete \
    --role "Storage Blob Data Contributor" \
    --assignee-object-id $WORKER_ID \
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_NAME/blobServices/default/containers/$CONTAINER_NAME"
else
  echo "Invalid value for enable_access: $ENABLE_ACCESS"
  exit 1
fi

sleep 30