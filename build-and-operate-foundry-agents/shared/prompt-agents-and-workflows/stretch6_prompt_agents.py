# %% [markdown]
# # Lab 11: One terminal Prompt Agent comparison
#
# **Technology focus.** This lab uses Microsoft Foundry (`PromptAgentDefinition`; versioned prompt agents).
# No Microsoft Agent Framework graph or knowledge resource is needed; Lab 4 provides the hosted comparison.
#
# This cell defines import-safe helpers without publishing or invoking Azure resources.
# %% Step S6.1 - Minimal comparison helpers
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
LABS_DIR = ROOT / "3-day-labs"
for folder in (ROOT, LABS_DIR):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import foundry_env, guardrails, resource_names

LAB = "stretch6"
ENV = foundry_env.load_env()
INSTRUCTIONS = (
    "Explain in two sentences why choosing a healthcare plan requires a licensed benefit advisor. "
    "Do not give participant-specific facts or recommend a plan. End with one next step.\n"
    + guardrails.COMPLIANCE_INSTRUCTIONS
)


async def publish_and_invoke(env: dict[str, str], question: str) -> dict:
    """Publish one independent version and perform exactly one pinned Responses turn."""
    from azure.ai.projects.aio import AIProjectClient
    from azure.ai.projects.models import AgentEndpointConfig, FixedRatioVersionSelectionRule, PromptAgentDefinition, VersionSelector
    from azure.identity.aio import DefaultAzureCredential

    name = resource_names.name("healthcare-prompt-comparison", env, required=True)
    async with DefaultAzureCredential() as credential, AIProjectClient(
        endpoint=env["FOUNDRY_PROJECT_ENDPOINT"], credential=credential, allow_preview=True,
    ) as project:
        agent = await project.agents.create_version(
            agent_name=name,
            definition=PromptAgentDefinition(
                model=env["AZURE_AI_MODEL_DEPLOYMENT_NAME"], instructions=INSTRUCTIONS,
            ),
        )
        await project.agents.update_details(
            agent_name=name,
            agent_endpoint=AgentEndpointConfig(version_selector=VersionSelector(
                version_selection_rules=[FixedRatioVersionSelectionRule(
                    agent_version=agent.version, traffic_percentage=100,
                )],
            )),
        )
        async with project.get_openai_client(agent_name=name, max_retries=0, timeout=60) as client:
            response = await client.responses.create(
                input=question, store=False,
            )
    if response.status != "completed" or not response.output_text.strip():
        raise RuntimeError("Prompt comparison did not complete; inspect the error before deliberately rerunning.")
    return {"agent_name": name, "agent_version": agent.version, "agent_id": agent.id,
            "text": response.output_text, "response_id": response.id, "terminal": True}
