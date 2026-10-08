"""Dependency-free source-contract checks; never run Terraform or contact Azure."""
from __future__ import annotations

import ipaddress
from pathlib import Path
import re
import unittest

INFRA = Path(__file__).resolve().parents[1] / "infra"
VARIANTS = ("privatelink", "public-network")
TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|/\*[\s\S]*?\*/|#[^\n]*|//[^\n]*|[{}]')
HEADERS = re.compile(
    r'\b(resource|data|module|variable|output)\s+"([^"]+)"(?:\s+"([^"]+)")?\s*\{'
)
PRIVATE_RESOURCE_FRAGMENTS = (
    "private_endpoint", "private_dns", "private_link", "virtual_network",
    "subnet", "network_security_group",
)
PRIVATE_AZURE_TYPES = re.compile(
    r"Microsoft\.(?:Network/(?:privateEndpoints|privateDnsZones|virtualNetworks"
    r"|networkSecurityGroups)|Insights/privateLinkScopes)(?:/|@)"
)
NETWORK_REFERENCES = re.compile(
    r"\b(?:subnet_id|subnet_ids|subnet_name|subnet_resource_id|subnetResourceId"
    r"|subnetArmId|subnets|networkInjection|networkInjections|network_injection|network_injections"
    r"|privateEndpoints|private_endpoints|private_dns_zones|virtual_network_address_space"
    r"|agent_subnet_address_prefix|private_endpoint_subnet_address_prefix|vnetConfiguration"
    r"|infrastructureSubnetId"
    r"|vnet_id|virtual_network_id|virtual_network_name|azurerm_virtual_network|azurerm_subnet"
    r"|virtual_network_subnet_ids|virtual_network_rules|virtualNetworkRules|delegations)\b"
)
MODULE_SERVICES = ("foundry_account", "storage", "key_vault", "container_registry", "application_insights")
RESOURCE_SERVICES = {
    "cosmos_db": "azurerm_cosmosdb_account",
    "search": "azurerm_search_service",
    "log_analytics": "azurerm_log_analytics_workspace",
}
WORKSHOP_ENVIRONMENT = {
    "FOUNDRY_PROJECT_ENDPOINT", "AZURE_AI_MODEL_DEPLOYMENT_NAME", "FOUNDRY_MODEL",
    "EMBEDDING_MODEL_DEPLOYMENT_NAME", "AZURE_AI_SEARCH_ENDPOINT",
    "AZURE_OPENAI_ENDPOINT", "PROJECT_RESOURCE_ID", "TENANT_ID",
    "APPLICATIONINSIGHTS_CONNECTION_STRING", "MARKETPLACE_BLOB_STORAGE_URL",
    "MARKETPLACE_BLOB_STORAGE_CONTAINER",
}


def without_comments(source: str) -> str:
    return TOKENS.sub(
        lambda match: "" if match[0].startswith(("#", "//", "/*")) else match[0],
        source,
    )


def blocks(source: str) -> dict[tuple[str, ...], str]:
    """Read declaration bodies without mistaking quoted/interpolated braces for blocks."""
    result = {}
    source = without_comments(source)
    for header in HEADERS.finditer(source):
        depth = 1
        for token in TOKENS.finditer(source, header.end()):
            if token[0] == "{":
                depth += 1
            elif token[0] == "}":
                depth -= 1
                if not depth:
                    key = tuple(value for value in header.groups() if value is not None)
                    if key in result:
                        raise ValueError(f"Duplicate Terraform declaration: {key}")
                    result[key] = source[header.end():token.start()]
                    break
        else:
            raise ValueError(f"Unclosed Terraform declaration: {header[0]}")
    return result


def normalized(body: str) -> str:
    body = re.sub(r"\bdepends_on\s*=\s*\[[^\]]*\]", "", body)
    return re.sub(r"\s+", "", body)


def object_body(source: str, name: str) -> str | None:
    header = re.search(rf"\b{re.escape(name)}\s*(?:=\s*)?\{{", source)
    if header is None:
        return None
    depth = 1
    for token in TOKENS.finditer(source, header.end()):
        if token[0] == "{":
            depth += 1
        elif token[0] == "}":
            depth -= 1
            if not depth:
                return source[header.end():token.start()]
    raise ValueError(f"Unclosed Terraform object: {name}")


def output_value(body: str) -> str:
    match = re.search(
        r"(?ms)^\s*value\s*=\s*(.*?)(?=^\s*(?:sensitive|description)\s*=|\Z)", body
    )
    if match is None:
        raise ValueError("Terraform output has no value")
    return normalized(match[1])


class TerraformSourceReaderTests(unittest.TestCase):
    def test_comments_and_string_braces_do_not_change_declarations(self) -> None:
        source = '''
        # resource "wrong" "comment" {}
        resource "example" "real" {
          value = "https://${var.host}/a}b"
          nested = { enabled = true } /* } ignored */
        }
        '''
        parsed = blocks(source)
        self.assertEqual(set(parsed), {("resource", "example", "real")})
        self.assertIn("enabled = true", parsed[("resource", "example", "real")])

    def test_unclosed_declaration_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unclosed"):
            blocks('resource "example" "broken" { enabled = true')

    def test_module_objects_and_output_values_ignore_descriptions(self) -> None:
        parsed = blocks('module "storage" { network_rules = { default_action = "Allow" } }')
        body = parsed[("module", "storage")]
        self.assertIn('default_action = "Allow"', object_body(body, "network_rules"))
        private = 'description = "Private endpoint"\nvalue = local.endpoint\nsensitive = true'
        public = 'description = "Public endpoint"\nvalue = local.endpoint\nsensitive = true'
        self.assertEqual(output_value(private), output_value(public))


class TerraformNetworkVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = {}
        cls.declarations = {}
        for variant in VARIANTS:
            files = sorted((INFRA / variant).glob("*.tf"))
            if not files:
                raise AssertionError(f"Missing Terraform variant: {INFRA / variant}")
            source = "\n".join(path.read_text(encoding="utf-8") for path in files)
            cls.sources[variant] = without_comments(source)
            cls.declarations[variant] = blocks(source)

    def resource(self, variant: str, resource_type: str) -> str:
        matches = [
            body for key, body in self.declarations[variant].items()
            if key[:2] == ("resource", resource_type)
        ]
        self.assertEqual(len(matches), 1, f"{variant}: expected one {resource_type}")
        return matches[0]

    def azapi_resources(self, variant: str, azure_type: str) -> dict[tuple[str, ...], str]:
        return {
            key: body for key, body in self.declarations[variant].items()
            if key[:2] == ("resource", "azapi_resource")
            and re.search(r'\btype\s*=\s*"' + re.escape(azure_type) + r'@', body)
        }

    def service(self, variant: str, name: str) -> str:
        if name in MODULE_SERVICES:
            return self.declarations[variant][("module", name)]
        return self.resource(variant, RESOURCE_SERVICES[name])

    def assert_setting(self, body: str, name: str, value: str) -> None:
        self.assertRegex(body, rf"\b{re.escape(name)}\s*=\s*{re.escape(value)}(?=\s|[,}}])")

    def allowlist_variable(self) -> tuple[str, str]:
        matches = [
            (key[1], body) for key, body in self.declarations["public-network"].items()
            if key[0] == "variable" and "allow" in key[1] and "ip" in key[1]
        ]
        self.assertEqual(len(matches), 1, "Expected one mandatory public source-IP allowlist")
        return matches[0]

    def test_infra_root_is_only_a_selector(self) -> None:
        self.assertFalse(list(INFRA.glob("*.tf")), "Run Terraform inside a variant, not infra/")
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                self.assertTrue((INFRA / variant / "README.md").is_file())
                self.assertTrue((INFRA / variant / "terraform.tfvars.example").is_file())

    def test_private_variant_retains_private_graph_and_disabled_public_access(self) -> None:
        resource_types = {
            key[1] for key in self.declarations["privatelink"] if key[0] == "resource"
        }
        self.assertTrue({
            "azurerm_private_endpoint", "azurerm_private_dns_zone",
            "azurerm_private_dns_zone_virtual_network_link", "azurerm_monitor_private_link_scope",
        } <= resource_types)
        self.assertIn(("module", "spoke_vnet"), self.declarations["privatelink"])
        self.assertIn("Microsoft.App/environments", self.sources["privatelink"])
        self.assertIsNotNone(object_body(self.service("privatelink", "foundry_account"), "network_injections"))
        for name in ("foundry_account", "storage", "cosmos_db", "search", "container_registry", "key_vault"):
            with self.subTest(service=name):
                self.assert_setting(
                    self.service("privatelink", name), "public_network_access_enabled", "false"
                )

    def test_account_purge_is_preserved_without_public_subnet_cooldown(self) -> None:
        key = ("resource", "azapi_resource_action", "purge_foundry_account")
        self.assertEqual(
            normalized(self.declarations["privatelink"][key]),
            normalized(self.declarations["public-network"][key]),
        )
        for variant in VARIANTS:
            self.assertIn(
                "azapi_resource_action.purge_foundry_account",
                self.service(variant, "foundry_account"),
            )
        self.assertNotIn("foundry_purge_cooldown", self.sources["public-network"])

    def test_public_variant_has_no_private_graph_or_network_injection(self) -> None:
        for key in self.declarations["public-network"]:
            if key[0] in ("resource", "data"):
                with self.subTest(declaration=key):
                    self.assertFalse(any(part in key[1] for part in PRIVATE_RESOURCE_FRAGMENTS))
        self.assertNotRegex(self.sources["public-network"], PRIVATE_AZURE_TYPES)
        self.assertNotRegex(self.sources["public-network"], NETWORK_REFERENCES)
        self.assertNotIn("Azure/avm-res-network-", self.sources["public-network"])
        for name in ("foundry_account", "storage", "cosmos_db", "search", "container_registry", "key_vault"):
            with self.subTest(service=name):
                self.assert_setting(
                    self.service("public-network", name), "public_network_access_enabled", "true"
                )

    def test_key_vault_and_acr_allowlist_is_required_and_bounded(self) -> None:
        name, body = self.allowlist_variable()
        self.assertEqual(name, "allowed_public_ipv4_cidrs")
        self.assertNotRegex(body, r"\bdefault\s*=", "The operator must supply the allowlist")
        self.assertRegex(body, r"\btype\s*=\s*(?:list|set)\(\s*string\s*\)")
        self.assert_setting(body, "nullable", "false")
        self.assertRegex(
            body, rf"\blength\(\s*var\.{re.escape(name)}\s*\)\s*(?:>\s*0|>=\s*1)"
        )
        self.assertIn("alltrue(", body)
        self.assertIn("cidrnetmask(", body, "Validate IPv4 CIDRs, not arbitrary strings")
        self.assertRegex(
            body,
            r'!\s*contains\([\s\S]*?"0\.0\.0\.0/0"'
            r'|!=\s*"0\.0\.0\.0/0"'
            r'|cidrnetmask\(\s*\w+\s*\)\s*!=\s*"0\.0\.0\.0"'
            r'|!\s*endswith\([^)]*"/0"\s*\)'
            r'|split\(\s*"/"\s*,\s*\w+\s*\)\[1\]\s*\)?\s*(?:>\s*0|>=\s*1)',
            "Reject the allow-all /0 prefix",
        )
        self.assertIn("local.reserved_ipv4_ranges", body)
        self.assertIn("reserved.first", body)
        self.assertIn("reserved.last", body)
        for cidr in (
            "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16",
            "172.16.0.0/12", "192.0.0.0/24", "192.0.2.0/24", "192.168.0.0/16",
            "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4",
        ):
            with self.subTest(reserved_cidr=cidr):
                self.assertIn(f'"{cidr}"', self.sources["public-network"])
        example = (INFRA / "public-network" / "terraform.tfvars.example").read_text(encoding="utf-8")
        assignment = re.search(rf"\b{re.escape(name)}\s*=\s*\[([^\]]*)\]", example)
        self.assertIsNotNone(assignment, "Document the required source-IP input")
        cidrs = re.findall(r'"([^"]+)"', assignment[1])
        self.assertTrue(cidrs, "The example must show a bounded allowlist")
        for cidr in cidrs:
            with self.subTest(cidr=cidr):
                if cidr == "<your-public-egress-ip>/32":
                    continue
                network = ipaddress.ip_network(cidr)
                self.assertEqual(network.version, 4)
                self.assertGreater(network.prefixlen, 0)
                self.assertTrue(network.network_address.is_global and network.broadcast_address.is_global)

    def test_public_data_services_allow_all_sources_without_bypass(self) -> None:
        for name, rules in (("foundry_account", "network_acls"), ("storage", "network_rules")):
            with self.subTest(service=name):
                body = self.service("public-network", name)
                self.assertIsNotNone(object_body(body, rules))
                self.assert_setting(body, "default_action", '"Allow"')
                self.assertRegex(body, r'\bbypass\s*=\s*(?:"None"|\[\s*"None"\s*\])')
                self.assertNotRegex(body, r"\b(?:ip_rules|private_link_access)\b")
        cosmos = self.service("public-network", "cosmos_db")
        self.assert_setting(cosmos, "ip_range_filter", "[]")
        self.assert_setting(cosmos, "network_acl_bypass_for_azure_services", "false")
        self.assertNotRegex(cosmos, r'"0\.0\.0\.0"|\bnetwork_acl_bypass_ids\b')
        search = self.service("public-network", "search")
        self.assert_setting(search, "allowed_ips", "[]")
        self.assert_setting(search, "network_rule_bypass_option", '"None"')
        for name in ("foundry_account", "storage", "cosmos_db", "search"):
            with self.subTest(service=name):
                self.assertNotIn("var.allowed_public_ipv4_cidrs", self.service("public-network", name))

    def test_only_key_vault_and_acr_consume_the_allowlist_and_deny_other_sources(self) -> None:
        name, _ = self.allowlist_variable()
        for service, rule in (("container_registry", "ip_rule"), ("key_vault", "ip_rules")):
            with self.subTest(service=service):
                body = self.service("public-network", service)
                self.assertRegex(body, rf"\b{rule}\s*=")
                self.assert_setting(body, "default_action", '"Deny"')
                self.assertIn(f"var.{name}", body)
                self.assertNotRegex(body, r'"\*"|"0\.0\.0\.0/0"|"::/0"')
        self.assert_setting(self.service("public-network", "key_vault"), "bypass", '"None"')
        self.assert_setting(
            self.service("public-network", "container_registry"), "network_rule_bypass_option", '"None"'
        )

    def test_registry_export_settings_are_compatible_with_public_access(self) -> None:
        for variant, enabled in (("privatelink", "false"), ("public-network", "true")):
            with self.subTest(variant=variant):
                body = self.service(variant, "container_registry")
                self.assert_setting(body, "public_network_access_enabled", enabled)
                self.assert_setting(body, "export_policy_enabled", enabled)
        rules = object_body(self.service("public-network", "container_registry"), "network_rule_set")
        self.assertIsNotNone(rules)
        self.assert_setting(rules, "default_action", '"Deny"')
        self.assertIn("var.allowed_public_ipv4_cidrs", rules)
        self.assertRegex(rules, r"\bip_rule\s*=")

    def test_authentication_controls_are_not_relaxed(self) -> None:
        controls = (
            ("foundry_account", "local_auth_enabled", "false"),
            ("storage", "shared_access_key_enabled", "false"),
            ("storage", "default_to_oauth_authentication", "true"),
            ("storage", "allow_nested_items_to_be_public", "false"),
            ("cosmos_db", "local_authentication_enabled", "false"),
            ("search", "local_authentication_enabled", "false"),
            ("container_registry", "admin_enabled", "false"),
            ("container_registry", "anonymous_pull_enabled", "false"),
        )
        for variant in VARIANTS:
            for service, name, value in controls:
                with self.subTest(variant=variant, service=service, setting=name):
                    self.assert_setting(self.service(variant, service), name, value)
            with self.subTest(variant=variant, service="key_vault"):
                self.assertNotRegex(
                    self.service(variant, "key_vault"), r"\blegacy_access_policies_enabled\s*=\s*true"
                )
            self.assert_setting(self.sources[variant], "storage_use_azuread", "true")
        for name in MODULE_SERVICES:
            for setting in ("source", "version"):
                pattern = rf'\b{setting}\s*=\s*"([^"]+)"'
                private = re.search(pattern, self.service("privatelink", name))[1]
                public = re.search(pattern, self.service("public-network", name))[1]
                self.assertEqual(public, private, f"Preserve the {name} module's security defaults")

    def test_monitoring_endpoints_follow_the_selected_variant(self) -> None:
        for variant, ingestion in (("privatelink", "false"), ("public-network", "true")):
            for service in ("application_insights", "log_analytics"):
                with self.subTest(variant=variant, service=service):
                    self.assert_setting(self.service(variant, service), "internet_ingestion_enabled", ingestion)
                    self.assert_setting(self.service(variant, service), "internet_query_enabled", "true")

    def test_role_assignments_and_managed_identities_are_equivalent(self) -> None:
        def identity_contract(variant: str) -> dict[tuple[str, ...], str]:
            return {
                key: normalized(body) for key, body in self.declarations[variant].items()
                if key[0] == "resource" and (
                    "role_assignment" in key[1] or "user_assigned_identity" in key[1]
                    or re.search(r'\btype\s*=\s*"[^"]*/roleAssignments@', body)
                )
            }

        private = identity_contract("privatelink")
        self.assertTrue(private, "The private variant must define its RBAC contract")
        self.assertEqual(identity_contract("public-network"), private)
        for name in MODULE_SERVICES:
            with self.subTest(module=name):
                self.assertEqual(
                    object_body(self.service("public-network", name), "role_assignments"),
                    object_body(self.service("privatelink", name), "role_assignments"),
                )
        self.assertEqual(
            normalized(self.declarations["public-network"][("module", "foundry_identity")]),
            normalized(self.declarations["privatelink"][("module", "foundry_identity")]),
        )
        for service, block in (("foundry_account", "managed_identities"), ("search", "identity")):
            self.assertEqual(
                object_body(self.service("public-network", service), block),
                object_body(self.service("privatelink", service), block),
            )

    def test_foundry_project_and_connections_are_equivalent(self) -> None:
        self.assertEqual(
            normalized(self.resource("public-network", "azurerm_cognitive_account_project")),
            normalized(self.resource("privatelink", "azurerm_cognitive_account_project")),
        )
        for azure_type in (
            "Microsoft.CognitiveServices/accounts/projects/connections",
            "Microsoft.CognitiveServices/accounts/projects/capabilityHosts",
        ):
            with self.subTest(azure_type=azure_type):
                private = self.azapi_resources("privatelink", azure_type)
                public = self.azapi_resources("public-network", azure_type)
                self.assertTrue(private, f"Missing project contract: {azure_type}")
                self.assertEqual(
                    {key: normalized(body) for key, body in public.items()},
                    {key: normalized(body) for key, body in private.items()},
                )
        for variant in VARIANTS:
            connections = "\n".join(self.azapi_resources(
                variant, "Microsoft.CognitiveServices/accounts/projects/connections"
            ).values())
            self.assertIn("module.storage.", connections)
            self.assertIn("azurerm_cosmosdb_account.", connections)
            self.assertIn("azurerm_search_service.", connections)

    def test_workshop_output_contract_is_equivalent(self) -> None:
        def outputs(variant: str) -> dict[str, str]:
            return {
                key[1]: output_value(body) for key, body in self.declarations[variant].items()
                if key[0] == "output"
            }

        private = outputs("privatelink")
        public = outputs("public-network")
        private_network_outputs = {"vnet_id", "subnet_ids", "monitor_private_link_scope_id"}
        self.assertEqual(public, {name: value for name, value in private.items() if name not in private_network_outputs})
        private_environment = object_body(self.sources["privatelink"], "workshop_environment")
        public_environment = object_body(self.sources["public-network"], "workshop_environment")
        self.assertIsNotNone(private_environment)
        self.assertIsNotNone(public_environment)
        self.assertEqual(normalized(public_environment), normalized(private_environment))
        for variable in WORKSHOP_ENVIRONMENT:
            with self.subTest(variable=variable):
                for variant in VARIANTS:
                    self.assertRegex(self.sources[variant], rf"\b{variable}\b")


if __name__ == "__main__":
    unittest.main()
