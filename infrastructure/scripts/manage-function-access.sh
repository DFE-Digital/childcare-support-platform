#!/usr/bin/env bash
set -euo pipefail

FUNCTION_APP_NAME="$1"
RESOURCE_GROUP_NAME="$2"
SUBSCRIPTION_ID="$3"
WORKER_ID="$4"
ENABLE_ACCESS="$5"

if [ "$ENABLE_ACCESS" = "true" ]; then
  echo "Enabling access for $FUNCTION_APP_NAME..."

  az role assignment create \
    --role "Website Contributor" \
    --assignee-object-id $WORKER_ID \
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.Web/sites/$FUNCTION_APP_NAME"
elif [ "$ENABLE_ACCESS" = "false" ]; then
  echo "Disabling access for $FUNCTION_APP_NAME..."

  az role assignment delete \
    --role "Website Contributor" \
    --assignee-object-id $WORKER_ID \
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.Web/sites/$FUNCTION_APP_NAME"
else
  echo "Invalid value for enable_access: $ENABLE_ACCESS"
  exit 1
fi

sleep 30