# verp_staffing — Claude Code Project Guide

## What this is
`verp_staffing` is a custom Frappe app (NOT ERPNext-dependent core logic, though it
installs alongside ERPNext) implementing a staffing ERP. Canonical repo lives on
Gitea at git.vrugle.com. Dev happens inside a bench container
(`/workspace/development/frappe-bench`), app at `apps/verp_staffing`.

## Environment
- Bench root: /workspace/development/frappe-bench
- App path: apps/verp_staffing
- Start stack: `bench start` (runs web/socketio/watch/schedule/worker)
- Web: http://127.0.0.1:8000 (dev), site `172.18.0.5:8000` also bound
- Known module name collisions with erpnext: `setup`, `accounts`, `crm` —
  these UserWarnings on boot are expected, not bugs. Don't try to "fix" them
  unless the task is specifically about module resolution.

## Commands Claude may run without asking
- `bench build`
- `bench migrate`
- `bench run-tests --app verp_staffing`
- `bench console` (read-only exploration only, never mutate data this way)
- `git status`, `git diff`, `git log`, `git add`, `git commit`
- `tea pr create`, `tea pr list`, `tea issue list` (against git.vrugle.com)

## Commands that need explicit confirmation first
- Anything touching production/client sites (Frappe Cloud, client VPS)
- `bench --site <client-site> migrate`
- Any destructive DB command (`bench --site X reinstall`, truncate, drop)
- Force-pushing to any shared branch

## Conventions
- Custom JS overrides live under `verp_staffing/public/js/` and are bundled
  into files like `user_custom.js`, `about_override.js`,
  `quick_entry_override.js` — follow existing override patterns rather than
  monkey-patching core Frappe JS directly.
- Doctypes: [fill in naming convention, e.g. prefix/casing rules]
- Hooks: check `verp_staffing/hooks.py` before adding new hook entries;
  don't duplicate hook types already registered.

## Active migration context
- Migrating v15 → v16. Known risk areas: removed modules, query builder
  changes, frontend API changes. Before editing any file under active
  migration, check whether it's already been touched for v16 compat
  (search git log / CHANGELOG first).

## PR workflow
- Never commit directly to `stagging` or `main`. Always branch:
  `feature/<short-desc>` or `fix/<short-desc>`.
- Use the `/pr` slash command (see .claude/commands/pr.md) to open PRs —
  it fills in a standard template and links testing steps.
- Every PR touching a doctype must note migration impact (v15→v16) if any.

## Testing expectation
- Any UI-affecting change should be verified live via the Playwright MCP
  browser (see .mcp.json) before Claude reports the task done — navigate to
  the affected page, confirm no console errors, confirm expected DOM state.