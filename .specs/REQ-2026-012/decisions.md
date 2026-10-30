# 決定記録: REQ-2026-012

番号は REQ-2026-011 の `decisions.md`(DEC-053 まで)からの通し番号。日付は決定日。決定者は利用者(tsuyama1990)。

| ID | 日付 | 問い | 状態 | 答え |
|---|---|---|---|---|
| DEC-054 | 2026-10-29 | フックの一般化の対象 | 有効 | 事実: 利用者が使うのは Claude Code、Antigravity(agy)、Roo(「roo, antigravity or claude かな」)。Aider は実行前に止めるフックを持たない(`aider --help` v0.86.2)。Roo はフック相当の機能が見つからなかった(検索)。答え: 「とりあえず cc と ac」で進める(利用者、2026-10-29)。対象は Claude Code と agy。Roo は B-02 |
| DEC-055 | 2026-10-29 | 判定の共有のしかた | 有効 | 事実: 2 つ目の実例(agy)が出た(「抽象化は 2 つ目の実例が出てから」)。答え: `ToolCall(cwd, command \| path)` に正規化し、`decide_call` を共有する。エージェントごとの違いは、入力の読み取りと出力の形だけを持つ小さなモジュール(`agy_hook`)に置く。Protocol や基底クラスは作らない |
| DEC-056 | 2026-10-29 | agy が規則を読むための方法 | 有効 | 事実: agy が自動で読むのは `GEMINI.md`、`AGENTS.md`(複数形)、`.agents/rules/*.md` で、`AGENT.md`(単数)は読まれない [原典: 同梱ドキュメント]。答え: `AGENTS.md` を 1 行のポインタとして足す(`CLAUDE.md` と同じ形)。`AGENT.md` の改名はしない。決定: 利用者、2026-10-29(「はい」) |
| DEC-057 | 2026-10-29 | 許可のときの出力 | 有効 | 事実: agy の `decision: allow` は「Automatically allow the tool execution」で、agy 自身の確認を飛ばす恐れがある。答え: 許可のときは何も出力しない。何も出力しないときの agy の挙動は未確認(L1-M02)で、設計書に未確認と明記する |
| (作業記録) | 2026-10-29 | 実機の確認 | — | `agy-cli --dangerously-skip-permissions` でフックの実機確認(一時ディレクトリのみ)を 2 回試みたが、権限の分類器に止められ未実施。迂回していない。利用者が Bash の許可ルールを設定すれば実施できる |
| DEC-065 | 2026-10-30 | グローバル `hooks.json` の設置 | AI | 事実: `~/.gemini/config/hooks.json` に `gov hook agy-pre-tool-use` を設置した(旧設定は `~/.gemini/config.backup-2026-10-30` に退避)。ダミー入力では拒否・確認・無出力を確認済み。agy 実機での読み込みと挙動(L1-M01〜M04)は未観測。戻す: `hooks.json` を削除する。見直し: agy を使った際の観測で M01〜M04 を記録する |
