# Public-network Build and Operate workshop

This independent Terraform root deploys the same Microsoft Foundry Standard
Agent workshop services as [privatelink](../privatelink/README.md), without
Private Link, private DNS, a VNet, subnet injection, NSGs or an Azure Monitor
Private Link Scope. Azure PaaS services expose their normal public HTTPS
hostnames; this template does not allocate dedicated public IP resources.

## Network and authentication policy

| Service | Public source access | Authentication |
| --- | --- | --- |
| Foundry account/project and models | All network sources; outbound access unrestricted | Microsoft Entra ID/RBAC; local keys disabled |
| Storage | All network sources | Entra/RBAC; shared keys and anonymous Blob access disabled |
| Cosmos DB | All network sources; no special all-Azure bypass | Entra/RBAC; local authentication disabled |
| AI Search | All network sources | Entra/RBAC; local authentication disabled |
| Key Vault | Only `allowed_public_ipv4_cidrs`; default Deny, no trusted-service bypass | Existing vault RBAC/managed identity |
| Container Registry | Only `allowed_public_ipv4_cidrs`; default Deny, no trusted-service bypass | Existing registry RBAC; admin and anonymous pull disabled |
| Application Insights/Log Analytics | Public ingestion and query enabled | Existing monitoring RBAC and Application Insights connection configuration |

**This is deliberately not an IP-restricted Foundry/data-service deployment.**
An operator-only allowlist does not admit managed-agent traffic: the public
runtime has no documented stable egress IP allowlist. Azure Monitor also has no
native public source-IP ACL. The public workshop therefore prioritizes working
managed-runtime connectivity while retaining the existing service authentication
controls. Public network access does not grant data permissions.

Key Vault and ACR are retained for parity with the private environment; they are
not connections used by this Standard Agent capability host. Their IP firewall
can block a managed runtime even when its identity has RBAC. Do not assume that
granting a role or enabling a trusted-service bypass would make optional hosted
agent use of these resources work.
ACR retains Premium because IP firewall rules require it; its export policy is
enabled because Azure only permits disabling exports when public access is off.

Microsoft documents the
[public bring-your-own-storage Standard Agent configuration](https://learn.microsoft.com/azure/foundry/agents/concepts/networking-options),
[Search trusted access](https://learn.microsoft.com/azure/search/service-configure-firewall#grant-access-to-trusted-azure-services),
[Storage resource-instance rules](https://learn.microsoft.com/azure/storage/common/storage-network-security-resource-instances),
the broad scope of
[Cosmos DB all-Azure access](https://learn.microsoft.com/azure/cosmos-db/how-to-configure-firewall#allow-requests-from-global-azure-datacenters-or-other-sources-within-azure),
and [Azure Monitor network controls](https://learn.microsoft.com/azure/azure-monitor/logs/network-access).
This root does not invent a Foundry-specific Cosmos bypass or quietly add
`0.0.0.0` to a caller-supplied allowlist.

## Configure and deploy

Install Terraform 1.12+ and Azure CLI. Select a subscription and region with
Foundry Agent Service, supported model versions, semantic ranker and sufficient
quota. The deploying identity needs resource-creation and role-assignment
permissions, such as Owner or Contributor plus User Access Administrator.

From this directory:

```bash
az login --use-device-code --tenant '<tenant-id>'
az account set --subscription '<subscription-id>'
cp terraform.tfvars.example terraform.tfvars
```

Replace the example placeholders, including subscription/tenant GUIDs, operator
object ID and actual public operator/CI egress CIDRs. For an interactive user:

```bash
az ad signed-in-user show --query id --output tsv
```

Set `operator_principal_type = "ServicePrincipal"` when using a service principal's
object ID. The required `allowed_public_ipv4_cidrs` is only the Key Vault/ACR
allowlist. It must be nonempty and contain canonical, globally routable IPv4
CIDRs; `/32` represents one address. Empty lists, `/0`, IPv6, noncanonical,
private, loopback, documentation and reserved ranges are rejected. The example
placeholder is intentionally invalid until replaced.

Use a different `resource_suffix` and backend state key from every private
deployment. Do not reuse its state; see the
[parent migration guide](../README.md#existing-private-deployments).

Confirm the example model versions, deployment SKUs and quota in your region:

```bash
az cognitiveservices model list --location '<region>' --output table
az cognitiveservices usage list --location '<region>' --output table
terraform init
terraform fmt -check
terraform validate
terraform plan -out main.tfplan
terraform apply main.tfplan
```

Provider registration requirements remain the same as the private root except
that this root does not register `Microsoft.Network`. Terraform uses Azure CLI
authentication and Entra authorization for Storage. Use a protected remote
backend for shared/CI use: local state and saved plans contain sensitive values.

## Configure and check the workshop

```bash
terraform output
terraform output -raw workshop_env > workshop.env
```

Merge the ignored `workshop.env` values into the repository-root `.env`. It has the
same workshop environment keys as the private root, including Foundry/model,
Search, Blob history and telemetry settings. The Application Insights connection
string and Terraform state must not be committed or shared.

From the repository root, then from this directory:

```bash
python build-and-operate-foundry-agents/tools/preflight.py
# Return to this public-network directory for the smoke test.
bash post-deploy-validation.sh
```

The smoke test reuses Azure CLI credentials, selects the tfvars subscription,
checks the resource group/Foundry project/model and invokes the mini model over
its public endpoint. It does not validate every data service or exercise the
Standard Agent/hosted-agent lifecycle. No VPN or private DNS is required.

Hosted agents have a platform-assigned identity separate from the project
identity. After first deployment, grant that identity the specific Search/Blob
roles needed by optional external resources, as described in the workshop setup.
Wait for RBAC propagation and run the relevant lab before treating the runtime
as verified.

## Offline validation and design critique

```bash
terraform init -backend=false -input=false -lockfile=readonly
terraform fmt -check -recursive
terraform validate
terraform test
```

`terraform test` uses mocked providers and module outputs only, never live Azure
resources. It checks public data-service policy, disabled local authentication,
public Monitor settings and allowlist rejection cases. The workshop validator
also checks both roots' graph boundaries, RBAC/connection/output parity and
network policy.
The mocked module outputs do not exercise Key Vault/ACR firewall wiring; the
workshop's source-contract tests cover those inputs separately. Run both suites.

The public path removes private-endpoint costs and DNS/VPN setup, but gives up
network isolation for Foundry, its data services and telemetry. Authentication
is the remaining access boundary; use synthetic workshop data only. Single-region
resources, LRS Storage, one Search replica and example capacity/quota are
workshop defaults, not a production resilience or performance design.

Neither validation nor mocked tests proves Azure Policy compliance, deployment
quota, regional API/model availability, role propagation or managed-runtime
connectivity. A live deployment, the model smoke test and the lab's hosted-agent
flow remain necessary before claiming Azure readiness. The
[private variant](../privatelink/README.md) is the supported alternative when
network isolation is required.

## Remove the deployment

Review a saved destroy plan before applying it:

```bash
terraform plan -destroy -out destroy.tfplan
terraform apply destroy.tfplan
```

Like the private root, this root purges the soft-deleted Foundry account after
destroy so its account name can be reused. Only the private root needs the
delegated-subnet cleanup cooldown; this root has no subnet association to drain.
If account deletion/purge fails, resolve that service lifecycle before reusing
the name. Key Vault retains purge protection and can still prevent immediate
vault-name reuse independently of networking.
