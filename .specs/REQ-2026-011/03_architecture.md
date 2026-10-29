# L2 アーキテクチャ(契約とアルゴリズム): 運用規則の一本化

対になるテスト仕様: [03_integration_tests.md](03_integration_tests.md)(L2 ↔ 結合)。入力: [01_req_spec.md](01_req_spec.md)(F01〜F08)、[02_system_design.md](02_system_design.md)。
根拠の種類: **[原典]**(コード・規則・決定の文面) / **[データ]** / **[推論]** / **[決定]**(DEC-ID)

L2 が決めるのは、モジュール配置、型と契約、各フックのアルゴリズム、状態ファイル、設定の切り替え、エラーの扱い。関数の内部は L3(`04_detail_design.md`)で決める。

## 0. REQ-2026-010 の設計との関係
| REQ-2026-010 の記述 | この REQ での扱い |
|---|---|
| `03_architecture.md` §7: プロジェクトの `Stop` は置かない。全体設定の `Stop` が `scripts/gate.sh` を呼ぶ | 変えない。全体設定が Stop を呼ぶ点は同じ。呼ぶ先を、`stop_gate.sh` から `gov hook global-stop` に替える(F06) |
| §7: gov 自身のエラーでは拒否しない(DEC-002)。実行ファイルがなければ 127 で、拒否にならない(DEC-039) | そのまま踏襲する(01 §5) |
| §11: モジュール配置 | 下の §1 で追加するモジュールを足す。既存は変えない |
| `domain/machinery.py`: `AGENT.md`、`CLAUDE.md`、`src/jtc_gov/**` は検証機構 | 変更しない。この REQ の変更は、すべて「人間のマージが必要」になる。意図どおり(規則の変更は人間が承認する) |

## 1. モジュール配置(追加分)
```
src/jtc_gov/
  derive/    git_commands.py   (純粋。Bash のコマンド文字列 → git 呼び出しの列)
  adapters/  agent_docs.py     (AGENT.md / CLAUDE.md の雛形、抽出、比較)
             global_hook.py    (global-guard / global-stop / global-turn-start)
  templates/ agent_rules.md    (共通ブロックの本文。パッケージのデータ)
```
- `cli.py`: `init` が `agent_docs` を使う(F02)。`doctor` の `CHECKS` に 1 項目を足す(F03)。`hook` の引数の選択肢に、3 つのイベントを足す。
- 依存の向き(既存と同じ): `adapters` → `derive` → `domain`。`global_hook` は `checks` を呼ばない。`derive/git_commands.py` は標準ライブラリだけ。

## 2. 共通ブロック(`adapters/agent_docs`)
- 印: 開始 `<!-- gov:rules v1 -->`、終了 `<!-- /gov:rules -->`。`v1` は雛形の版。雛形を改訂したら上げる。
- `render_rules_block() -> str`: `templates/agent_rules.md` の本文を印で囲んだ文字列。
- `render_agent_md() -> str`: `# Rules for AI agents` + 共通ブロック + `## This repository` の空の節。
- `render_claude_md() -> str`: cheeze_gyudon の現行の CLAUDE.md と同じ 1 行の文面。(cheeze_gyudon で `init` が差分を出さない)
- `extract_block(text) -> str | None`: 印を含む範囲。印がなければ `None`。印が2組以上、または終了が開始より前なら `None` 扱いで不一致。
- 雛形の本文: R01〜R18 を、ID、規則(エージェント非依存の文面)、強制の置き場の順に並べた表。ツール名を含まない。本文の正本はこの REQ の `02_system_design.md` §5 で、`templates/agent_rules.md` はそこから**生成**ではなく、実装時に手で写す(L3 でテストが両者の ID の一致を確かめる)。

## 3. `gov init` と `gov doctor`(F02、F03)
- `init`: 既存の流儀を踏襲する。対象を `AGENT.md`、`CLAUDE.md` の 2 つ足す。
  - ファイルがない → 作る(`作成: <path>` を出力)。
  - `AGENT.md` がある → `extract_block` を雛形のブロックと比べる。違う、または `None` → 統一差分(印の中だけ)を出力、終了コード 1、ファイルは変えない。同じ → 何もしない。
  - `CLAUDE.md` がある → 全体を雛形と比べる。違えば差分、終了コード 1。
  - 既存の `.claude/settings.json`、`.gitattributes` の扱いは変えない。終了コードは、どれか 1 つでも衝突すれば 1。
- `doctor`: `CHECKS` に `_agent_docs(root) -> DoctorItem` を足す。`AGENT.md` が存在し共通ブロックが雛形と一致、かつ `CLAUDE.md` が存在して `AGENT.md` を指す(文字列 `AGENT.md` を含む)なら OK。違えば NG と、どちらが違うかを `detail` に出す。

## 4. `global-guard`(PreToolUse。F04、F05、F06 の記録)
入力は標準入力の JSON(`tool_name`、`tool_input`、`cwd`、`session_id`)。JSON でない、`cwd` がない、例外が出る、の場合は、何も出さず終了コード 0(DEC-002)。

**Edit/Write/NotebookEdit/MultiEdit**:
1. `tool_input.file_path`(または `notebook_path`)。相対なら `cwd` に対して絶対にする。
2. 最も近い存在するディレクトリから `git rev-parse --show-toplevel`。git のリポジトリでなければ終了コード 0。
3. 状態ファイルにそのリポジトリを追記する(§6)。
4. パスが `.specs/<dir>/approval.json` に当たれば **ASK**。
5. git に無視されるファイルなら終了。そうでなければ、そのリポジトリの現在のブランチが `main`/`master` なら **deny**。

**Bash**:
1. `derive.git_commands.parse_git_invocations(command)` で、git の呼び出しの列を得る(§5)。
2. 各呼び出しについて、作業ディレクトリ(`cd` と `-C` を反映)から `git rev-parse --show-toplevel` を求め、リポジトリを状態ファイルに追記する。
3. 判定(強い順 deny > ask > allow。全呼び出しの最強を採る):

| 呼び出し | 条件 | 判定 | 規則 |
|---|---|---|---|
| `commit` | 対象リポジトリの現在のブランチが main/master | deny | R03 |
| `add` | 引数に `-A`、`--all`、`.` のいずれか | deny | R05 |
| `merge` | `--abort`/`--continue`/`--quit` でなく、対象リポジトリの現在のブランチが main/master | deny(`merge-to-main.sh` を案内) | R06 |
| `push` | 常に | ask | R09 |

4. git の呼び出しとは別に、コマンド文字列全体に対して:
   - `merge-to-main.sh` を含む → **ask**(R10)。
   - `approval.json` を含み、かつ書き込み系の語(`>`、`>>`、`tee`、`sed -i`、`cp`、`mv`、`python`、`dd`、`install`)のいずれかを含む → **ask**(R02)。
5. 出力: deny は標準エラーに理由を書き終了コード 2。ask は標準出力に `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": "<理由>"}}`、終了コード 0。allow は何も出さず 0。

## 5. コマンド文字列の解析(`derive/git_commands`)
- `GitInvocation(subcommand: str, args: tuple[str, ...], directory: str | None)`。`directory` は、`cd` と `-C` を、`cwd` からの相対のまま連結したもの(絶対化は `global_hook` が行う)。
- 区切り: `;`、`&&`、`||`、`|`、改行で分割。各区間を `shlex.split(posix)` で字句に分ける。字句に失敗した区間は読み飛ばす。
- 区間の先頭の `env`、`command`、`sudo`、`VAR=val`、バックスラッシュ付きの `\git` は読み飛ばす。
- `cd <dir>`: 以降の区間の基準ディレクトリを更新する(相対なら連結)。`cd` を含む区間が `git` を含むなら、`cd` の後のものとして扱う(`cd A && git commit` で A)。
- `git` の後のオプション: `-C <dir>`(複数なら連結)、`-c <k=v>`、`--git-dir=…`、`--work-tree=…`、`--no-pager`、`-P` などを読み飛ばし、最初のオプションでない字句をサブコマンドとする。
- **限界**: 変数展開(`$G`)、`bash -c '…'` の中、サブシェルの中、スクリプトファイルの中は解析しない(N2)。

## 6. 状態ファイル(F06)
- 場所: `STATE_DIR`(既定 `~/.claude/state/`)。ファイル名は `<session_id>.repos`(`session_id` は `[A-Za-z0-9_-]` 以外を `_` にする)。
- 形式: 1 行 1 リポジトリ(絶対パス)。追記は、1 回の短い書き込み(`O_APPEND`)で行う。読むときに重複を除く。
- `global-turn-start`(UserPromptSubmit): そのセッションのファイルを空にし、`STATE_MAX_AGE_DAYS`(7)より古い `*.repos` を消す。標準入力が壊れていても、期限切れの削除だけは行う。

## 7. `global-stop`(Stop。F06)
1. リポジトリの集合 = `cwd` のリポジトリ + 状態ファイルのうち存在するもの(重複なし)。
2. 各リポジトリで、`scripts/gate.sh` が実行可能で、`git status --porcelain` から `.md` で終わる行と ` docs/` を含む行を除いて何か残るなら対象。
3. 対象にゲートを走らせる。全体の時間は `STOP_BUDGET_SECONDS`(280)で打ち切り、残りの時間がなければ、その旨を出力して終了コード 0(上限 300 秒の中で終える)。
4. 成功 → そのリポジトリの失敗回数のファイルを消す。失敗 → `<git-dir>/claude-stop-blocks-<session_id>` に回数を書き、`MAX_BLOCKS`(3)未満なら「失敗した。根本原因を直す」と、ゲートの出力の末尾 40 行を標準エラーに出す。`MAX_BLOCKS` に達したら回数を消し、`{"systemMessage": "NOT DONE: …"}` を標準出力に出す。
5. 1 つでも差し戻しがあれば終了コード 2、なければ 0。出力には、どのリポジトリかを含める。
(既存の `stop_gate.sh` の振る舞いを、複数リポジトリに拡張したもの。1 つのリポジトリだけの場合は同じ結果になる。)

## 8. 設定の切り替え(`~/.claude/settings.json`。リポジトリの外)
切り替え後の呼び出し(JSON の形は L3 に置く): `PreToolUse`(Bash、Edit、Write、NotebookEdit、MultiEdit)→ `gov hook global-guard`、`Stop` → `gov hook global-stop`、`UserPromptSubmit` → `gov hook global-turn-start`。置き換えた `~/.claude/hooks/{branch_guard,block_git_add_all,stop_gate}.sh` は、同じ作業で削除する(R17 の「置き換えたら旧コードを消す」)。切り替えは、新イベントが gov のリリースに入ってから行う。

## 9. マージスクリプト(`~/.claude/bin/merge-to-main.sh`。リポジトリの外。F07)
- `main` に触れる前(引数の検査と、ブランチの存在確認の直後)に、メッセージファイルを検査する。
- 必須: 要件 ID(`REQ-[0-9]{4}-[0-9]{3}`)、見出し行に「証拠」または `Evidence`、見出し行に「bonsai」(大文字小文字を区別しない)、語「純増減」または `Net`、語「削除」または `Removed`。足りない項目をすべて列挙して、終了コード 1。
- このスクリプトは版管理されない(既知の穴。backlog B-06)。

## 10. エラーの扱い
| 状況 | 振る舞い |
|---|---|
| 標準入力が JSON でない、必要なキーがない | 何も出さず終了コード 0 |
| `git` の実行に失敗、リポジトリでない | その呼び出しは allow 扱い |
| 状態ファイルの書き込みに失敗 | 無視する(判定は続ける) |
| `gov` がない | 127(フックが動かない。DEC-039) |
| ゲートの実行時間が予算を超えた | 残りの検査を打ち切り、その旨を標準エラーに出して終了コード 0 |

## 11. テスト構造
`tests/{unit,integration,e2e}/` に置く。ディレクトリから印を付ける(既存の方針)。一時リポジトリを作る補助は既存の `tests/support/` を使う。`merge-to-main.sh` の検査は手動確認(`02_system_tests.md` の L1-M02)。
