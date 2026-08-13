# Azure Terraform Backend Bootstrap

This blueprint automates the "Day 0" infrastructure required to run Terraform at scale in Azure.

## 🏛️ Architecture: Why the Hybrid Mix?
Terraform has a "Chicken and Egg" problem: it needs a Storage Account to store its state, but shouldn't manually create it.

**The Solution:**
- **Bicep (Stateless):** We use these native declarative tools to build the "House" (Resource Group, VNet, Private Endpoint, Storage, and RBAC).
- **Terraform (Stateful):** Terraform then moves in and manages the application infrastructure, storing its state in the storage created here.

## 🛡️ Governance & Security Best Practices
- **Resilience:** Defaulted to **Standard_ZRS** for zone redundancy.
- **Zero-Trust:** Shared Access Keys are **Disabled**. All access must use Entra ID (Azure AD) tokens.
- **Network Isolation:** Public network access is completely **Disabled**. All backend connectivity is secured via a Private Endpoint deployed to a dedicated subnet with an explicit `DenyAllInbound` Network Security Group rule.
- **Auditability:** Log Analytics captures both control-plane metrics (transactions at the Storage Account level) and data-plane operations (reads, writes, and deletes at the Blob Service level).
- **Recovery:** Blob Versioning and 14-day Soft Delete are enabled for both blobs and containers.

## 🔑 Why GUIDs for Role Definitions?
We use the GUID `ba92f5b4-2d11-453d-a403-e96b0029c9fe` (Storage Blob Data Contributor) because:
1. **Immutability:** Display names (like "Contributor") can be renamed by Microsoft; GUIDs are permanent.
2. **Localization:** GUIDs are the only universal language the Azure API understands across all global regions.
3. **Precision:** Prevents name collisions with custom roles.

## ⚠️ Critical Implementation Notes
1. **Global Uniqueness:** Storage names must be unique across all of Azure. Use a specific prefix.
2. **Deployment Permissions:** The identity running this requires **Owner** or **User Access Administrator** at the Subscription scope to assign RBAC roles.
3. **ZRS Availability:** Ensure the `location` supports Zone-Redundant Storage.
4. **RBAC Delay:** Wait ~5 minutes after deployment before running `terraform init` to allow permissions to sync.

## ⚠️ Pipeline Networking Strategy (Crucial)
Because this blueprint disables public network access on the Storage Account and relies on a **Private Endpoint**, Microsoft-hosted or GitHub-hosted runners will be **blocked** from accessing the state file. When configuring your CI/CD pipelines to run Terraform, you must adopt one of the following strategies:

### 💡 Option A: Self-Hosted Agents / VNet Integration (Recommended)
Deploy self-hosted runner agents (e.g., GitHub Runner, Azure DevOps Self-hosted Agent) directly within the Virtual Network or a peered VNet.
*   **Pros:** Highly secure, traffic never leaves the private network, no dynamic firewall modifications required.
*   **Cons:** Requires managing the VM/container hosting the runner agent.

### 💡 Option B: Dynamic Firewall Whitelisting
If you must use public hosted runners, you can dynamically whitelist the runner's public IP during the pipeline execution and remove it immediately after the Terraform step completes.

Here is a sample bash script you can integrate into your pipeline steps:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Inputs
RESOURCE_GROUP="myapp-dev-rg-uks-terraform"
STORAGE_ACCOUNT="myappdevtfstatestorage"
ACTION="${1:-add}" # 'add' or 'remove'

# Get the runner's current public IP address
RUNNER_IP=$(curl -s https://api.ipify.org)

if [ "$ACTION" == "add" ]; then
  echo "Whitelisting pipeline runner IP: $RUNNER_IP"
  az storage account network-rule add \
    --resource-group "$RESOURCE_GROUP" \
    --account-name "$STORAGE_ACCOUNT" \
    --ip-address "$RUNNER_IP"
  
  # Allow propagation of the firewall rule (typically 10-30 seconds)
  echo "Waiting for firewall rule propagation..."
  sleep 20
elif [ "$ACTION" == "remove" ]; then
  echo "Removing pipeline runner IP from whitelist: $RUNNER_IP"
  az storage account network-rule remove \
    --resource-group "$RESOURCE_GROUP" \
    --account-name "$STORAGE_ACCOUNT" \
    --ip-address "$RUNNER_IP"
else
  echo "Unknown action. Use 'add' or 'remove'."
  exit 1
fi
```

*   **Pros:** Allows the use of free, Microsoft-managed hosted runners.
*   **Cons:** Temporarily opens a pinhole in the storage firewall; requires the pipeline identity to have permissions to modify storage firewall rules (`Microsoft.Storage/storageAccounts/write`).

## 🚀 Deployment via Bicep

To deploy the Day 0 infrastructure, execute a subscription-scoped deployment using the Azure CLI. Choose the appropriate environment parameter file (e.g., `development`, `production`, `test`):

```bash
# Example: Deploying to the Development environment
az deployment sub create \
  --location uksouth \
  --template-file bicep/main.bicep \
  --parameters bicep/environments/development.params.json \
  --parameters workflowPrincipalId=<YOUR_PIPELINE_SP_OBJECT_ID>
```

Replace `<YOUR_PIPELINE_SP_OBJECT_ID>` with the Object ID of the service principal or managed identity that runs your CI/CD pipelines (it will be granted Storage Blob Data Contributor access to the state storage).

## 🛠️ Usage in Terraform
```hcl
terraform {
  backend "azurerm" {
    resource_group_name  = "myapp-dev-rg-uks-terraform"
    storage_account_name = "myappdevtfstatestorage"
    container_name       = "tfstate"
    key                  = "dev.terraform.tfstate"
    use_azuread_auth     = true
  }
}
```