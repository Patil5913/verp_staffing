#!/usr/bin/env bash
# Run this from apps/verp_staffing inside the frappe-bench dev container.
set -e

echo "== 1. Gitea CLI (tea) =="
if ! command -v tea &> /dev/null; then
  echo "Installing tea CLI..."
  TEA_VERSION="0.9.2"
  ARCH="$(dpkg --print-architecture)"
  wget -q "https://gitea.com/gitea/tea/releases/download/v${TEA_VERSION}/tea-${TEA_VERSION}-linux-${ARCH}" -O /usr/local/bin/tea
  chmod +x /usr/local/bin/tea
fi
tea login list | grep -q "git.vrugle.com" || tea login add \
  --name vrugle \
  --url https://git.vrugle.com

echo "  -> verify with: tea login list"

echo "== 2. Playwright MCP (browser agent) =="
# .mcp.json in the repo root already declares this server; this just
# pre-warms the npx cache so first Claude Code session doesn't stall.
npx -y @playwright/mcp@latest --version || true
npx -y playwright install --with-deps chromium

echo "== 3. Caveman skill (token-terse output) =="
# Installed as a Claude Code plugin (user scope) via its own marketplace/plugin
# commands -- not vendored into the repo. Idempotent; safe to re-run.
if command -v claude &> /dev/null; then
  claude plugin marketplace add JuliusBrussee/caveman || true
  claude plugin install caveman@caveman || true
else
  echo "  claude CLI not found on PATH, skipping caveman plugin install"
fi

echo "== 4. Claude Code =="
if ! command -v claude &> /dev/null; then
  npm install -g @anthropic-ai/claude-code
fi

echo "Done. Next steps:"
echo "  1. Copy CLAUDE.md and .mcp.json into apps/verp_staffing/ (repo root) if not already there."
echo "  2. Copy .claude/commands/pr.md into apps/verp_staffing/.claude/commands/"
echo "  3. cd into apps/verp_staffing and run: claude"
echo "  4. Verify MCP is loaded: inside claude, run /mcp"
echo "  5. Try: claude> /pr   (after making a change on a feature branch)"