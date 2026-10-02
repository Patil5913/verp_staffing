---
description: Analyze current branch changes and open a PR via gh CLI
---

You are preparing a pull request for the `verp_staffing` repo.

1. Confirm we are on a feature/fix branch, not `main` or `stagging`. If we
   are on main/stagging, stop and tell the user to create a branch first.
2. Run `git diff main...HEAD` (or `stagging...HEAD` if that's the base) to
   see all changes since branching.
3. Run `git log main..HEAD --oneline` to see the commit history for this
   branch.
4. Write a PR description using this template:

   ## Summary
   <1-3 sentence summary of what changed and why>

   ## Changes
   - <bullet list of concrete changes, file by file or feature by feature>

   ## Migration impact
   <Note any v15->v16 migration risk this touches, or "None">

   ## Testing
   <How this was verified — mention if Playwright MCP was used to check
   the UI, and what was checked>

   ## Checklist
   - [ ] `bench migrate` runs clean
   - [ ] `bench run-tests --app verp_staffing` passes
   - [ ] No new console errors in affected UI (verified via browser)

5. Push the branch if not already pushed: `git push -u origin HEAD`.
6. Confirm `tea login list` shows a working login for git.vrugle.com. If not,
   stop and tell the user to run `tea login add` first.
7. Open the PR with the content from step 4, e.g.:
   `tea pr create --repo <owner>/<repo> --base stagging --head <branch> --title "..." --description "..."`
   (fill in the real owner/repo, branch name, and the actual title/body —
   don't leave placeholders in the executed command).
8. Report back the PR URL from `tea`'s output.