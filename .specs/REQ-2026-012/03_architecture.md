# L2 アーキテクチャ(契約とアルゴリズム): agy でも global-guard の判定を効かせる

対になるテスト仕様: [03_integration_tests.md](03_integration_tests.md)(L2 ↔ 結合)。入力: [01_req_spec.md](01_req_spec.md)(F01〜F04)、[02_system_design.md](02_system_design.md)。
根拠の種類: **[原典]** / **[データ]** / **[推論]** / **[決定]**(DEC-ID)

## 0. REQ-2026-011 との関係
| 011 の記述 | この REQ での扱い |
|---|---|
| `adapters/global_hook.py` に `guard(payload)` があり、Claude の入出力と判定が同居 | 判定(リポジトリの解決を含む)を `decide_call(ToolCall)` に出し、`guard` は変換だけを持つ。振る舞いは変えない(F02) |
| `cli.py` の `hook` の選択肢は `claude_hook.EVENTS + global_hook.EVENTS` | `agy_hook.EVENTS` を足す。ディスパッチは「どのモジュールの EVENTS に入っているか」で選ぶ |
| 依存の向き: `adapters` → `derive` → `domain` | 変えない。`agy_hook` は `global_hook` を使う(同じ層) |

## 1. モジュール配置(追加・変更分)
```
src/jtc_gov/
  adapters/  global_hook.py   (変更: ToolCall、decide_call を出す。Claude 用の変換と出力を残す)
             agy_hook.py      (新規: agy の入力の変換と出力。EVENTS = ("agy-pre-tool-use",))
  domain/    machinery.py     (変更: AGENTS.md を一覧に足す)
```

## 2. 共有する判定(`global_hook`)
- `ToolCall(cwd: str, command: str | None, path: str | None)`: `command` か `path` のどちらか 1 つだけが入る。
- `decide_call(call) -> Decision`: 011 の `_guard_write` / `_guard_bash` の中身そのもの。`path` があれば書き込みの判定、`command` があれば Bash の判定。
- Claude 用: `payload → ToolCall | None`(`tool_name` が書き込み系なら `path`、`Bash` なら `command`。それ以外は `None`)と、`Decision → HookOutcome`。

## 3. agy の入力の変換(`agy_hook`)
入力は標準入力の JSON(camelCase)。`toolCall.name`、`toolCall.args`、`workspacePaths`。
| `toolCall.name` | `command` / `path` | `cwd` |
|---|---|---|
| `run_command` | `args.CommandLine`(文字列) | `args.Cwd`。相対なら `workspacePaths[0]` に連結。なければ `workspacePaths[0]` |
| `write_to_file`、`replace_file_content`、`multi_replace_file_content` | `path = args.TargetFile` | `workspacePaths[0]` |
| `write_file`、`edit_file` | `path = args.Path` | `workspacePaths[0]` |
| それ以外 | `None` を返す(判定しない) | — |
- `workspacePaths` が空、`args` が辞書でない、必要なキーが文字列でない、の場合は `None`。
- `path` が相対なら、`cwd` に対して解決される(011 の `_guard_write`)。

## 4. agy の出力
| 判定 | 標準出力 | 終了コード |
|---|---|---|
| deny | `{"decision": "deny", "reason": "<理由>"}` | 0 |
| ask | `{"decision": "ask", "reason": "<理由>"}` | 0 |
| allow、判定しない、エラー | 何も出さない | 0 |
`allow` を出さない理由は 02 §3 と N2。

## 5. 設定(リポジトリの外。F04)
`~/.gemini/config/hooks.json`:
```json
{
  "gov-guard": {
    "PreToolUse": [
      {"matcher": "run_command|write_to_file|replace_file_content|multi_replace_file_content|write_file|edit_file",
       "hooks": [{"type": "command", "command": "gov hook agy-pre-tool-use", "timeout": 10}]}
    ]
  }
}
```
マッチャーは、ドキュメントの「`run_command\|view_file`」の例に従い、正規表現の `|` で並べる。 [原典]

## 6. エラーの扱い
| 状況 | 振る舞い |
|---|---|
| 標準入力が JSON でない、必要なキーがない | 何も出さず終了コード 0 |
| `git` の実行に失敗、リポジトリでない | 011 の §7 と同じ |
| `gov` がない | 127(フックの失敗。agy の挙動は未確認。N1) |
| フックの実行が 10 秒を超える | agy の側で打ち切り(挙動は未確認) |

## 7. テスト構造
`tests/{unit,integration,e2e}/`。一時リポジトリの補助は `tests/support/guard_repos.py`(011 で追加済み)を使う。実機の確認は `02_system_tests.md` の L1-M01〜M04。
