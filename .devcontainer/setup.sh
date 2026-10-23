#!/bin/bash
# Interactive first-run setup: collects AWS credentials and writes devcontainer.env.
# Runs on the Mac host (before the container exists).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/devcontainer.env"

echo ""
echo "=== Claude Code CLI — first-run setup ==="
echo ""
echo "This will configure your AWS Bedrock credentials."
echo ""

read -rp "AWS region [us-east-1]: " AWS_REGION
AWS_REGION="${AWS_REGION:-us-east-1}"

read -rp "AWS Access Key ID: " AWS_ACCESS_KEY_ID
while [ -z "$AWS_ACCESS_KEY_ID" ]; do
    echo "  AWS Access Key ID is required."
    read -rp "AWS Access Key ID: " AWS_ACCESS_KEY_ID
done

read -rsp "AWS Secret Access Key: " AWS_SECRET_ACCESS_KEY
echo ""
while [ -z "$AWS_SECRET_ACCESS_KEY" ]; do
    echo "  AWS Secret Access Key is required."
    read -rsp "AWS Secret Access Key: " AWS_SECRET_ACCESS_KEY
    echo ""
done

cat > "$ENV_FILE" <<EOF
AWS_REGION=${AWS_REGION}
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
CLAUDE_CODE_USE_BEDROCK=1
ANTHROPIC_DEFAULT_SONNET_MODEL=us.anthropic.claude-sonnet-4-6
ANTHROPIC_DEFAULT_SONNET_MODEL_NAME=Sonnet
ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION=Sonnet 4.6 · Best for everyday tasks
ANTHROPIC_CUSTOM_MODEL_OPTION=sonnet[1m]
ANTHROPIC_CUSTOM_MODEL_OPTION_NAME=Sonnet (1M context)
ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION=Sonnet 4.6 for long sessions
EOF

echo ""
echo "Credentials saved to .devcontainer/devcontainer.env"
echo ""
