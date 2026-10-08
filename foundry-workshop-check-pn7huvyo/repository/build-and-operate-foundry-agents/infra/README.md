# Deploy the Build and Operate workshop infrastructure

This Terraform configuration deploys a self-contained, private Microsoft Foundry
Standard Agent environment for the Build and Operate Foundry Agents workshop.
It uses Microsoft Entra ID and a user-assigned managed identity; local keys and
public data-plane access are disabled.

## Resources

- Azure resource group
- Microsoft Foundry resource, project, capability host, and model deployments
- Azure Virtual Network with delegated agent and private endpoint subnets
- Azure Private Link private endpoints and Azure Private DNS zones
- Azure Managed Identities user-assigned managed identity
- Azure Storage account and Blob containers
- Azure Cosmos DB for NoSQL account
- Azure AI Search service
- Azure Key Vault
- Azure Container Registry
- Azure Monitor Log Analytics workspace
- Azure Monitor Application Insights
- Azure Monitor Private Link Scope
- Azure role assignments and Microsoft Foundry project connections

## Prerequisites

1. Install Terraform `1.12` or later and Azure CLI.
2. Sign in with Azure CLI and select the deployment subscription:

   ```bash
   az login --use-device-code --tenant '<tenant-id>'
   az account set --subscription '<subscription-id>'
   az account show --query '{subscription:id,tenant:tenantId,user:user.name}' --output table
   ```

3. Use an identity that can create the listed resources and role assignments.
   `Owner`, or `Contributor` plus `User Access Administrator`, at the target
   subscription or resource-group scope is sufficient.
4. Choose a region that supports Microsoft Foundry Agent Service, the requested
   model versions, Azure AI Search semantic ranker, and your required quota.
5. Plan secure client access to the virtual network. Terraform can run from any
   authenticated machine because it uses the management plane, but the workshop
   data-plane endpoints are private. Use a peered network with VPN or ExpressRoute,
   or a VM accessed through Azure Bastion. This template intentionally does not
   create a public endpoint, VPN gateway, Bastion host, or virtual machine.

Microsoft documents the resource model in
[Microsoft Foundry architecture](https://learn.microsoft.com/azure/foundry/concepts/architecture),
the network requirements in
[Set up private networking for Foundry Agent Service](https://learn.microsoft.com/azure/foundry/agents/how-to/virtual-networks),
and the Terraform control-plane workflow in
[Use Terraform to create Microsoft Foundry](https://learn.microsoft.com/azure/foundry/how-to/create-resource-terraform).

## Configure

From this directory, copy the tracked example to Terraform's conventional local
variables file:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit every placeholder in `terraform.tfvars`. At minimum, set:

- `subscription_id` and `tenant_id`
- `location`
- `operator_principal_id` and `operator_principal_type`
- `name_prefix` and globally unique `resource_suffix`
- nonoverlapping RFC 1918 virtual network and subnet CIDRs
- model names, versions, SKUs, and capacities available in the selected region

For an interactive user, get the operator object ID with:

```bash
az ad signed-in-user show --query id --output tsv
```

For a service principal, use its Microsoft Entra object ID and set
`operator_principal_type = "ServicePrincipal"`.

Check model availability and quota before planning:

```bash
LOCATION='eastus2'
SUBSCRIPTION_ID="$(az account show --query id --output tsv)"

az cognitiveservices model list \
  --location "$LOCATION" \
  --subscription "$SUBSCRIPTION_ID" \
  --output table

az cognitiveservices usage list \
  --location "$LOCATION" \
  --subscription "$SUBSCRIPTION_ID" \
  --output table
```

The supplied model values mirror the source deployment. They are examples, not a
promise of regional availability or quota. Remove deployments the workshop does
not need, but keep the entries selected by `chat_model_deployment_key` and
`embedding_model_deployment_key`.

## Deploy

Format and validate the configuration, then review and apply a saved plan:

```bash
terraform init -upgrade
terraform fmt -check
terraform validate
terraform plan -out main.tfplan
terraform apply main.tfplan
```

The AzureRM provider registers the resource providers used by this template. If
your organization restricts provider registration, have an administrator register
`Microsoft.App`, `Microsoft.Authorization`, `Microsoft.CognitiveServices`,
`Microsoft.ContainerRegistry`, `Microsoft.ContainerService`,
`Microsoft.DocumentDB`, `Microsoft.Insights`, `Microsoft.KeyVault`,
`Microsoft.ManagedIdentity`, `Microsoft.Network`,
`Microsoft.OperationalInsights`, `Microsoft.Search`, and `Microsoft.Storage`
before deployment.

Terraform state contains sensitive values, including the Application Insights
connection string. The default local state is appropriate only for an individual
workshop deployment. Configure a protected remote backend before using this
configuration from a team or CI/CD system.

## Configure the workshop

After apply, inspect the nonsecret outputs:

```bash
terraform output
```

Write the workshop settings to an ignored local file:

```bash
terraform output -raw workshop_env > workshop.env
```

Merge those values into the repository-root `.env` without removing the other
workshop settings. `workshop.env` contains an Application Insights connection
string; do not commit or share it. The output includes:

- `FOUNDRY_PROJECT_ENDPOINT`
- `PROJECT_RESOURCE_ID`
- `AZURE_AI_MODEL_DEPLOYMENT_NAME` and `FOUNDRY_MODEL`
- `EMBEDDING_MODEL_DEPLOYMENT_NAME`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_AI_SEARCH_ENDPOINT`
- `APPLICATIONINSIGHTS_CONNECTION_STRING`
- `MARKETPLACE_BLOB_STORAGE_URL`
- `MARKETPLACE_BLOB_STORAGE_CONTAINER`
- Azure tenant, subscription, resource group, project, and workshop suffix values

Run the workshop preflight from the repository root after connecting to the
virtual network:

```bash
python build-and-operate-foundry-agents/tools/preflight.py
```

Run the post-deployment management-plane and model smoke tests from this
directory:

```bash
bash post-deploy-validation.sh
```

The script reads tenant, subscription, location, naming, project, and model
values from `terraform.tfvars`. It reuses an existing Azure CLI session when
possible, selects the configured subscription, and starts device-code login only
when usable cached credentials are unavailable. Because the Foundry data plane
is private, the final mini-model inference check requires the configured private
DNS and network path.

For a full private-endpoint investigation, run:

```bash
./troubleshoot-private-endpoint.sh
```

The troubleshooting script reads the target tenant, subscription, region, and
resource names from `terraform.tfvars`; it reuses cached Azure CLI credentials
and starts device-code login only when needed. It continues through read
permission failures and checks the deployed resource inventory, Foundry and
operator RBAC, VNet and subnet configuration, NSGs, private endpoint approval
and NIC addresses, private DNS zones and VNet links, service public-access
settings, local hostname resolution, managed-identity roles, and recent failed
Azure operations. Its final table reports every executed resource check as
`PASS` or `FAIL` and identifies the most likely fault domain.

Hosted agents receive a platform-assigned identity that is separate from the
project identity. After each first hosted-agent deployment, grant that identity
access to optional external resources it uses, such as `Search Index Data Reader`
on Azure AI Search or `Storage Blob Data Contributor` on the history container.

## Verify

Management-plane checks can run from any authenticated machine:

```bash
RESOURCE_GROUP="$(terraform output -raw resource_group_name)"

az resource list \
  --resource-group "$RESOURCE_GROUP" \
  --query "[].{name:name,type:type,state:properties.provisioningState}" \
  --output table

az network private-endpoint list \
  --resource-group "$RESOURCE_GROUP" \
  --query "[].{name:name,status:privateLinkServiceConnections[0].privateLinkServiceConnectionState.status}" \
  --output table
```

Every provisioning state should be `Succeeded`, and every private endpoint
connection should be `Approved`. From a machine connected to the virtual network,
verify that the Foundry, Azure AI Search, Blob Storage, Azure Cosmos DB, Key Vault,
and Azure Container Registry host names resolve to private IP addresses.

## Destroy

Review the destroy plan before removing the environment:

```bash
terraform plan -destroy -out destroy.tfplan
terraform apply destroy.tfplan
```

Destroy includes a 15-minute cooldown and purge action so Microsoft Foundry can
remove the `legionservicelink` association from the delegated agent subnet. If a
failed deployment leaves that association in place, wait for cleanup before
reusing the subnet; otherwise deploy with a new virtual network or subnet.
