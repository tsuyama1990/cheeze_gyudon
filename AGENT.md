# Rules for AI agents

Common rules. The same table is in every repository; change all copies together (the source is `.specs/REQ-2026-011/02_system_design.md` §5).

"Enforced by" names the mechanism that stops a violation. An agent hook only works where the harness has it installed (not every agent has one); `text only` means nothing stops you, so follow the rule yourself.

<!-- gov:rules v1 -->
| ID | Rule | Enforced by |
|---|---|---|
| R01 | Do not put new behavior on `main` before a human has approved its design (`.specs/<REQ>/approval.json`, state `open`). | gate (`gov check`, K) |
| R02 | Approval files are created by a human, never by an agent. | agent hook (asks) |
| R03 | Do not commit or edit directly on `main` / `master`. | agent hook; remote ruleset |
| R04 | Name branches `<type>/<topic>`. | text only |
| R05 | Do not run `git add -A` / `git add .`; stage by path. | agent hook |
| R06 | Merge into `main` only through `merge-to-main.sh`. | agent hook (denies `git merge` on `main`) |
| R07 | The gate passes before merge. | merge script; CI |
| R08 | The merge message states requirement → evidence. | merge script (message check) |
| R09 | Push only when the user asks. | agent hook (asks) |
| R10 | A change that alters results needs the user's approval before merge. | agent hook (asks before the merge script) |
| R11 | Run bonsai before merge; report the net line change and what was removed. | merge script (message check) |
| R12 | Uncommitted changes in the working repository pass the gate; after 3 failures at the same gate, stop and report. | agent hook (Stop) |
| R13 | Work in this order: design, tests, code. Do not write code before its test. | text only |
| R14 | Every test carries a requirement marker whose tag exists in the spec. | gate (`gov check`, T) |
| R15 | If the implementation must diverge from an approved design, fix the design and get re-approval first. | text only |
| R16 | Do not weaken tests to make code pass. | text only |
| R17 | When you replace code, delete the old code in the same commit. | gate (dead-code check, partial) |
| R18 | Delegate to a separate worktree and branch; the receiver re-runs the gate and does not trust self-reports. | text only (R07 re-runs the gate) |
<!-- /gov:rules -->

## This repository

Where each kind of information lives: `.specs/REQ-2026-010/02_system_design.md` §2.1.

1. **Design first.** The definitions of approval and gates are in `.specs/REQ-2026-010/`. At commit and push `gov` rejects a change to `src/` together with tests or specs that has no approved design; at edit time it only notifies.
2. **Write the design and its test specification together** in `.specs/<REQ>/`.
3. **Search before writing.** Check PyPI and existing OSS before writing a custom utility.
4. **Quality limits come from `pyproject.toml`.** Run `scripts/gate.sh`. Do not write the limits' numbers anywhere else.
5. **Dependency direction** is defined in `.specs/REQ-2026-010/02_system_design.md` §3.
6. **Do not write the same information in two places.** Find the source of truth in the table above and link to it.
