# L3 テスト計画(単体): agy でも global-guard の判定を効かせる

対になる設計書: [04_detail_design.md](04_detail_design.md)(L3 ↔ 単体)。要件: [01_req_spec.md](01_req_spec.md)。テストは `tests/unit/` に置く。

| ID | 対象 | 入力 | 期待 | 要件 |
|---|---|---|---|---|
| L3-U01 | `to_call`(`run_command`) | `CommandLine`+`Cwd` 絶対 / `Cwd` 相対 / `Cwd` なし | `command` と `cwd`(絶対はそのまま、相対は `workspacePaths[0]` に連結、なしは `workspacePaths[0]`) | F01 |
| L3-U02 | `to_call`(書き込み系) | `write_to_file`・`replace_file_content`・`multi_replace_file_content`(`TargetFile`)、`write_file`・`edit_file`(`Path`) | 5 つとも `path` が入り、`cwd` は `workspacePaths[0]` | F01 |
| L3-U03 | `to_call`(対象外のツール) | `view_file` / `grep_search` / `list_dir` | `None` | F01 |
| L3-U04 | `to_call`(壊れた入力) | `toolCall` なし / `name` が数値 / `args` が配列 / `CommandLine` が数値 / `workspacePaths` が空・文字列でない | すべて `None`(例外を出さない) | F01 |
| L3-U05 | `to_outcome` | deny / ask / allow | deny と ask は `decision` と `reason` を持つ JSON を標準出力に(終了コード 0)。allow は標準出力が空 | F01 |
| L3-U06 | 日本語の理由 | `reason` が日本語を含む deny | JSON に日本語がそのまま(エスケープされない)入る | F01 |
| L3-U07 | `decide_call` | `ToolCall(cwd, command=None, path=None)` | `allow` | F02 |
| L3-U08 | `claude_call` | Bash / Write / 対象外のツール / `cwd` なし | `command` / `path` / `None` / `None`。011 の `guard` の結果が変わらない | F02 |
| L3-U09 | `AGENTS.md` のポインタ | cheeze_gyudon の `AGENTS.md` の内容 | `AGENT.md` へのリンクを含み、他の規則を含まない(1 行) | F03 |
