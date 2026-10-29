# [REQ-2026-012] Antigravity (agy) でも global-guard の判定を効かせる

この文書が、要件・範囲・保証・非保証・前提の正本。設計は [02_system_design.md](02_system_design.md)、決定は [decisions.md](decisions.md)、積み残しは [backlog.md](backlog.md)。
REQ-2026-011(`gov hook global-guard`、F04・F05)の判定を、2 つ目のエージェントである agy に広げる。

根拠の種類: **[原典]**(資料・コードの文面) / **[データ]**(観測) / **[推論]**(未検証) / **[決定]**(DEC-ID)

## 1. 目的
Claude Code 以外の、よく使うエージェント(利用者の言う「cc と ac」)のうち agy でも、main への直接のコミット・編集、`git add -A`、main 上の `git merge` を拒否し、push・マージスクリプト・`approval.json` への書き込みで人間の確認を挟む。 [決定: DEC-054]

動機: REQ-2026-011 の阻止はすべて Claude Code のフックにあり、agy には届かない(011 の N1)。 [データ: 2026-10-29]

## 2. 範囲
**含む(MVP)**: `gov hook` の新イベント `agy-pre-tool-use`、判定部分の共有化(Claude 用と agy 用の入出力の変換だけを分ける)、agy が規則を読むための `AGENTS.md` ポインタ、`machinery` の一覧への `AGENTS.md` の追加、グローバルのフック設定(`~/.gemini/config/hooks.json`。リポジトリの外)。
**含まない**: agy の Stop・SessionStart・PreInvocation フック(B-01)、Roo(B-02)、agy のプラグイン化(B-03)、`overwrite` による引数の書き換え、`gov doctor` での agy 設定の検査。

## 3. 保証・非保証・前提

| ID | 保証(G) |
|---|---|
| G1 | agy の `run_command` と、ファイル書き込み系のツールに対し、REQ-2026-011 の G2・G3 と同じ判定(拒否・確認)が行われる。ただし、フックが読み込まれている間だけ |
| G2 | 判定を共有するので、Claude 用と agy 用で同じ入力は同じ判定になる |
| G3 | agy は、リポジトリ直下の `AGENTS.md` から、AGENT.md の規則表にたどり着ける |

| ID | 非保証(N) |
|---|---|
| N1 | フックは助言(DEC-002)。`gov` が PATH にない、フックの設定がない、フックが失敗した場合、agy が止めるかどうかは agy の仕様次第で、未確認 |
| N2 | agy の `allow` を返すと、agy 自身の確認を飛ばす可能性がある(ドキュメント: 「Automatically allow」)。このため、`allow` の場合は何も出力しない設計とする。**何も出力しないときの agy の挙動は未確認**(L1-M02) |
| N3 | Bash 文字列の解析の限界は 011 の N2 と同じ |
| N4 | agy の Stop 時のゲート検査はしない(B-01) |
| N5 | agy が `--dangerously-skip-permissions` などで動くとき、フックが走るかは未確認(L1-M03) |
| N6 | 協調的でないエージェントは止められない(011 の N4) |

| ID | 前提(A) |
|---|---|
| A1 | `gov` が PATH にある(011 の A2) |
| A2 | グローバルの `~/.gemini/config/hooks.json` が agy に読まれる。ドキュメントはワークスペースの `.agents/hooks.json` を明記し、グローバルの場所は「`~/.gemini/config/`」としか書かない。未確認(L1-M01) |

## 4. 機能要件

- **[REQ-2026-012-F01] agy の PreToolUse 判定**: `gov hook agy-pre-tool-use` は、agy の PreToolUse の JSON を標準入力で受け、`run_command`(コマンド `CommandLine`、作業ディレクトリ `Cwd`)とファイル書き込み系のツール(`write_to_file`、`replace_file_content`、`multi_replace_file_content`、`write_file`、`edit_file`。パスは `TargetFile` または `Path`)を、REQ-2026-011 の判定と同じ規則で判定する。拒否は `{"decision": "deny", "reason": …}`、確認は `{"decision": "ask", "reason": …}` を標準出力に出す。許可の場合は何も出力せず終了コード 0。その他のツール、壊れた入力、例外は、何も出力せず終了コード 0。
- **[REQ-2026-012-F02] 判定の共有**: Claude 用と agy 用で判定を 1 か所にまとめる。両者の違いは、入力の読み取りと出力の形だけ。既存の `global-guard` の振る舞いは変えない。
- **[REQ-2026-012-F03] AGENTS.md ポインタ**: cheeze_gyudon と matome のリポジトリ直下に、「規則は AGENT.md にある」の 1 行の `AGENTS.md` を置く(`CLAUDE.md` と同じ形)。`domain/machinery.py` の一覧に `AGENTS.md` を加え、その変更が人間のマージを要するようにする。
- **[REQ-2026-012-F04] グローバルのフック設定**: `~/.gemini/config/hooks.json` に、`PreToolUse`(マッチャー `*`)から `gov hook agy-pre-tool-use` を呼ぶ設定を置く(リポジトリの外。手動確認 `L1-M01`〜`L1-M03` で記録する)。

## 5. 非機能
- **失敗の向き**: 011 の §5 と同じ。判定できなければ通す(DEC-002、DEC-039)。
- **時間**: フックの判定は 1 秒以内。agy の既定タイムアウトは 30 秒。

## 6. 完了の定義
F01・F02 に対応する `02_system_tests.md` の E2E が通ること。F03 は両リポジトリでファイルの存在を確認(`L1-M04`)。F04 と agy の実機の挙動は手動確認(`L1-M01`〜`L1-M03`)で記録する。`scripts/gate.sh` が通ること。実機の確認(M01〜M03)が未了のうちは、「agy で止まる」とは書かず、「agy 用のフックを実装済み、実機は未確認」と書く。
