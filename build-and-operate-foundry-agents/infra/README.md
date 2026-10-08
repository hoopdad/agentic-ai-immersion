# Workshop infrastructure network variants

Choose one independent Terraform root before configuring or deploying:

| Root | Network path | Intended use |
| --- | --- | --- |
| [privatelink](privatelink/README.md) | Private endpoints, private DNS, delegated agent subnet and Azure Monitor Private Link Scope | Isolated environments with a working private client network path |
| [public-network](public-network/README.md) | Public service endpoints; Key Vault/ACR have explicit IPv4 allowlists; no private network resources | Synthetic-data workshops without VPN/private DNS |

Both deploy the same workshop services, model configuration, project connections,
managed identity and environment-variable contract. The public root omits the
private root's VNet, subnet and Monitor Private Link outputs. Public endpoints
are Azure PaaS hostnames, not dedicated `azurerm_public_ip` resources.

The public root intentionally accepts all network sources for Foundry, Storage,
Cosmos DB, Search and telemetry; Key Vault/ACR alone are IP-restricted. It retains
service authentication, but is a synthetic-data workshop path, not network isolation.

Each root owns its own variables, provider lock file and Terraform state. Use
different `resource_suffix` values and separate backend keys when deploying both.
Do not run Terraform in this parent directory, use the same state for both roots,
or apply one root over the other root's resources. Switching variants is a new
deployment, not a network-toggle migration.

## Existing private deployments

The former files in this directory now live in `privatelink/`. Terraform resource
addresses and provider versions are unchanged; no `terraform state mv` is needed
just because the files moved.

Before running Terraform again:

1. Back up your existing state securely, including any backup file.
2. Move your ignored `terraform.tfvars`, local state and any backend/override
   configuration into `privatelink/`. Do not commit them.
3. For a remote backend, preserve the same backend configuration and state key.
   For local state, make sure `privatelink/terraform.tfstate` is the original state,
   not a new empty file.
4. Run `terraform init` from `privatelink/`, then review `terraform plan`.
   Stop if the path-only move proposes resource replacement or deletion.

Never copy the private deployment's state into `public-network/`. Leave the
existing private environment intact until its replacement has been independently
validated.

## Offline validation

From either variant directory:

```bash
terraform init -backend=false -input=false -lockfile=readonly
terraform fmt -check
terraform validate
```

From the repository root:

```bash
python build-and-operate-foundry-agents/tools/validate_workshop.py
```

These checks do not deploy Azure resources. A successful Terraform validation
does not prove regional model availability, quota, policy compliance, firewall
reachability, role propagation or hosted-agent runtime connectivity. Follow the
selected root's deployment and post-deployment checks before using it in Azure.
