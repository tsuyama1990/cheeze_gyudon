# L1 全体設計: agy でも global-guard の判定を効かせる

要件: [01_req_spec.md](01_req_spec.md)。対になるテスト計画: [02_system_tests.md](02_system_tests.md)(L1 ↔ E2E)。決定は [decisions.md](decisions.md)、積み残しは [backlog.md](backlog.md)。
状態: ドラフト(承認前)。
根拠の種類: **[原典]**(資料・コードの文面) / **[データ]**(観測) / **[推論]**(未検証) / **[決定]**(DEC-ID)

## 1. 問題
1. REQ-2026-011 の阻止(R02・R03・R05・R06・R09・R10)は、Claude Code のフックにしかない。agy には、規則の文章すら届かない可能性がある。[データ]
2. 利用者が主に使うのは Claude Code と agy(「cc と ac」。2026-10-29)。Roo は対象外(B-02)。Aider はフックを持たないため対象外。[決定: DEC-054]

## 2. 確認できたこと(agy)
`~/.gemini/antigravity-cli/builtin/skills/agy-customizations/` の同梱ドキュメント [原典]:
| 項目 | 内容 |
|---|---|
| フック | `hooks.json` に `PreToolUse` / `PostToolUse` / `SessionStart` / `PreInvocation` / `PostInvocation` / `Stop`。コマンドを実行し、標準入力に JSON(camelCase)を渡す |
| PreToolUse の出力 | 標準出力に `{"decision": "allow" \| "deny" \| "ask" \| "force_ask", "reason": …}`。`allow` は「Automatically allow the tool execution」 |
| PreToolUse の入力 | `toolCall.name`、`toolCall.args`、共通の `workspacePaths` など。**`cwd` はない** |
| 設定の場所 | ワークスペースの `.agents/hooks.json`。グローバルは `~/.gemini/config/`(`hooks.json` の名前はドキュメントに明記なし) |
| 規則ファイル | `GEMINI.md`、`AGENTS.md`(複数形)、`.agents/rules/*.md`。**`AGENT.md`(単数)は読まれない** |
| 既知の制限 | `type: "command"` のみ。フックは同期で、エージェントのループを止める |

過去の会話ログから観測したツールと引数 [データ: `brain/*/transcript.jsonl`]: `run_command`(`CommandLine`、`Cwd`)、`write_to_file`・`replace_file_content`・`multi_replace_file_content`(`TargetFile`)、`write_file`・`edit_file`(`Path`)。

**未確認(実機での確認が要る)**: ① グローバルの `~/.gemini/config/hooks.json` が読まれるか(L1-M01)。② `allow` の代わりに何も出力しなかったとき、agy は通常の確認の流れに戻るか(L1-M02)。③ `--dangerously-skip-permissions` でもフックが走るか(L1-M03)。2026-10-29 に実機の確認を試みたが、権限の分類器に止められ未実施。[データ]

## 3. 設計
- **判定は 1 か所**: REQ-2026-011 の `decide_*` と、リポジトリの解決を、エージェントに依存しない形で共有する。`ToolCall(cwd, command | path)` に正規化し、`decide_call(ToolCall) -> Decision` が判定する。[決定: DEC-055]
- **エージェントごとの違いは、入力の読み取りと出力の形だけ**:
  | | Claude Code | agy |
  |---|---|---|
  | 入力 | `tool_name`、`tool_input`、`cwd` | `toolCall.name`、`toolCall.args`、`workspacePaths` |
  | 拒否 | 標準エラーに理由、終了コード 2 | 標準出力に `{"decision": "deny", "reason": …}`、終了コード 0 |
  | 確認 | `hookSpecificOutput.permissionDecision: ask` | `{"decision": "ask", "reason": …}` |
  | 許可 | 何も出さない | **何も出さない**(`allow` は agy の確認を飛ばす恐れがあるため。N2) |
- **規則の文章**: `AGENTS.md` を、`CLAUDE.md` と同じ 1 行のポインタにする。正本は AGENT.md のまま。AGENT.md の改名はしない(参照と `machinery.py` が多数あり、得るものが小さい)。[決定: DEC-056]
- **グローバルの設定**: `~/.gemini/config/hooks.json`(リポジトリの外)に PreToolUse を 1 つ置く。

## 4. 回避の穴と、できないこと
- 011 の §6 と同じ(Bash の文字列解析、ruleset の管理者バイパス、協調的でないエージェント)。
- agy 固有: フックの設定が読まれない、`gov` がない、フックが失敗する、のとき agy が止めるかは未確認(N1)。
- `allow` を返さない設計は、agy の既存の確認の流れに依存する。その流れで確認が出ないなら、フックは「拒否と確認を足す」だけで、害はない。

## 5. やらないこと
- agy の Stop フック(ゲート検査): B-01。011 で Claude 用のターン単位の Stop も見送った(011 B-10)。
- Roo: B-02(フック相当の機能が見つかっていない)。
- プラグインとして配布: B-03。単一のユーザー環境なので、`hooks.json` を直接置く。
- `AGENT.md` → `AGENTS.md` の改名: DEC-056。

## 6. 検証(V字)
- **E2E**: 一時リポジトリで、agy の JSON を `gov hook agy-pre-tool-use` に与え、拒否・確認・許可の出力を確かめる。Claude 用と同じ入力の同一判定。
- **結合**: CLI の引数の選択肢、壊れた入力、`git` がない環境。
- **単体**: agy の入力から `ToolCall` への変換、出力の形。
- **手動**: 実機の 3 点(M01〜M03)と、ポインタ(M04)。

## 7. 移行の順序
1. REQ-2026-011 のマージ(`global_hook.py` が main に入る)の後に、この REQ の実装ブランチを切る。
2. 判定の共有化(F02)→ agy の入出力(F01)→ ポインタと `machinery`(F03)。
3. リポジトリの外: `~/.gemini/config/hooks.json`(F04)。実機の確認を行い、結果を `decisions.md` に追記する。

## 8. 目的の達成度
| 欲しい保証 | agy での達成 |
|---|---|
| main への直接のコミット・編集の拒否 | 実装は可能。実機で止まるかは未確認 |
| push・マージスクリプト・approval.json の確認 | 同上 |
| 規則の文章が届く | `AGENTS.md` のポインタで届く見込み(実機で確認 M04) |

## 9. 要件との対応
| 要件 | この文書の節 |
|---|---|
| F01 | §2、§3 |
| F02 | §3 |
| F03 | §3 |
| F04 | §3、§7 |
