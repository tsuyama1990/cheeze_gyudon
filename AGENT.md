# Rules for AI agents

Rules specific to this repository. The owner's global policy (`~/.claude/CLAUDE.md`) also applies and is not repeated here. Where each kind of information lives: `.specs/REQ-2026-010/02_system_design.md` §2.1.

1. **Design first.** Do not put new behavior (a change to `src/` together with tests or specs) on `main` before a human has approved the design. The definitions of approval and gates are in `.specs/REQ-2026-010/`. The tooling does not stop you yet (`.specs/REQ-2026-010/background/as_is_inventory.md`); follow this rule yourself.
2. **Write the design and its test specification together** in `.specs/<REQ>/`.
3. **Search before writing.** Check PyPI and existing OSS before writing a custom utility.
4. **Do not weaken tests.** Do not change test expectations to make failing code pass.
5. **Quality limits come from `pyproject.toml`.** Run `scripts/gate.sh`. Do not write the limits' numbers anywhere else.
6. **Dependency direction** is defined in `.specs/REQ-2026-010/02_system_design.md` §3.
7. **Do not write the same information in two places.** Find the source of truth in the table above and link to it.
