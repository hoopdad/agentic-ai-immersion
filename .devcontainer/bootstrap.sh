#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
azd extension install azure.ai.agents
python build-and-operate-foundry-agents/tools/preflight.py

git config --global devcontainers-theme.hide-status 1
compact_prompt_setting='export PROMPT_DIRTRIM=1'
if ! grep -qxF "$compact_prompt_setting" "$HOME/.bashrc"; then
    printf '\n# Keep the dev-container prompt focused on the current folder.\n%s\n' \
        "$compact_prompt_setting" >> "$HOME/.bashrc"
fi

printf '\nSign in inside this container: az login --use-device-code --tenant <tenant-id>\n'
