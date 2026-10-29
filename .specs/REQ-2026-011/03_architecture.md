# L2 アーキテクチャ(契約とアルゴリズム): 運用規則の一本化

対になるテスト仕様: [03_integration_tests.md](03_integration_tests.md)(L2 ↔ 結合)。入力: [01_req_spec.md](01_req_spec.md)(F01、F04、F05、F07、F08。F02・F03・F06 は取り下げ、DEC-053)、[02_system_design.md](02_system_design.md)。
根拠の種類: **[原典]**(コード・規則・決定の文面) / **[データ]** / **[推論]** / **[決定]**(DEC-ID)

L2 が決めるのは、モジュール配置、型と契約、フックのアルゴリズム、設定の切り替え、エラーの扱い。関数の内部は L3(`04_detail_design.md`)で決める。

## 0. REQ-2026-010 の設計との関係
| REQ-2026-010 の記述 | この REQ での扱い |
|---|---|
| `03_architecture.md` §7: プロジェクトの `Stop` は置かない。全体設定の `Stop` が `scripts/gate.sh` を呼ぶ | 変えない。`stop_gate.sh` もそのまま(DEC-053。ターン単位の検査は B-10) |
| §7: gov 自身のエラーでは拒否しない(DEC-002)。実行ファイルがなければ 127 で、拒否にならない(DEC-039) | そのまま踏襲する(01 §5) |
| §11: モジュール配置 | 下の §1 で追加するモジュールを足す。既存は変えない |
| `domain/machinery.py`: `AGENT.md`、`CLAUDE.md`、`src/jtc_gov/**` は検証機構 | 変更しない。この REQ の変更は、すべて「人間のマージが必要」になる。意図どおり(規則の変更は人間が承認する) |

## 1. モジュール配置(追加分)
```
src/jtc_gov/
  derive/    git_commands.py   (純粋。Bash のコマンド文字列 → git 呼び出しの列)
  adapters/  global_hook.py    (global-guard)
```
- `cli.py`: `hook` の引数の選択肢に、`global-guard` を足す。`init`・`doctor` は変えない。
- 依存の向き(既存と同じ): `adapters` → `derive` → `domain`。`global_hook` は `checks` を呼ばない。`derive/git_commands.py` は標準ライブラリだけ。

## 2. 共通規則表(F01。コードなし)
- 各リポジトリの AGENT.md に、印 `<!-- gov:rules v1 -->` … `<!-- /gov:rules -->` で囲んだ表(`| ID | 規則 | 強制の置き場 |`)を手で置く。R01〜R18 を昇順で 1 行ずつ。規則の文面は `02_system_design.md` §5 の「規則」の列から写す。ツール名を含まない。印は将来の検査(B-09)のためで、今は何も読まない。
- matome には CLAUDE.md を置く(cheeze_gyudon と同じ 1 行)。

## 3. `global-guard`(PreToolUse。F04、F05)
入力は標準入力の JSON(`tool_name`、`tool_input`、`cwd`)。JSON でない、`cwd` がない、例外が出る、の場合は、何も出さず終了コード 0(DEC-002)。

**Edit/Write/NotebookEdit/MultiEdit**:
1. `tool_input.file_path`(または `notebook_path`)。相対なら `cwd` に対して絶対にする。
2. 最も近い存在するディレクトリから `git rev-parse --show-toplevel`。git のリポジトリでなければ終了コード 0。
3. パスが `.specs/<dir>/approval.json` に当たれば **ASK**。
4. git に無視されるファイルなら終了。そうでなければ、そのリポジトリの現在のブランチが `main`/`master` なら **deny**。

**Bash**:
1. `derive.git_commands.parse_git_invocations(command)` で、git の呼び出しの列を得る(§4)。
2. 各呼び出しについて、作業ディレクトリ(`cd` と `-C` を反映)から `git rev-parse --show-toplevel` を求める。
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

## 4. コマンド文字列の解析(`derive/git_commands`)
- `GitInvocation(subcommand: str, args: tuple[str, ...], directory: str | None)`。`directory` は、`cd` と `-C` を、`cwd` からの相対のまま連結したもの(絶対化は `global_hook` が行う)。
- 区切り: `;`、`&&`、`||`、`|`、改行で分割。各区間を `shlex.split(posix)` で字句に分ける。字句に失敗した区間は読み飛ばす。
- 区間の先頭の `env`、`command`、`sudo`、`VAR=val`、バックスラッシュ付きの `\git` は読み飛ばす。
- `cd <dir>`: 以降の区間の基準ディレクトリを更新する(相対なら連結)。`cd` を含む区間が `git` を含むなら、`cd` の後のものとして扱う(`cd A && git commit` で A)。
- `git` の後のオプション: `-C <dir>`(複数なら連結)、`-c <k=v>`、`--git-dir=…`、`--work-tree=…`、`--no-pager`、`-P` などを読み飛ばし、最初のオプションでない字句をサブコマンドとする。
- **限界**: 変数展開(`$G`)、`bash -c '…'` の中、サブシェルの中、スクリプトファイルの中は解析しない(N2)。

## 5. 設定の切り替え(`~/.claude/settings.json`。リポジトリの外)
切り替え後の呼び出し(JSON の形は L3 に置く): `PreToolUse`(Bash、Edit、Write、NotebookEdit、MultiEdit)→ `gov hook global-guard`。`Stop` は `stop_gate.sh` のまま。置き換えた `~/.claude/hooks/{branch_guard,block_git_add_all}.sh` は、同じ作業で削除する(R17 の「置き換えたら旧コードを消す」)。切り替えは、新イベントが gov のリリースに入ってから行う。

## 6. マージスクリプト(`~/.claude/bin/merge-to-main.sh`。リポジトリの外。F07)
- `main` に触れる前(引数の検査と、ブランチの存在確認の直後)に、メッセージファイルを検査する。
- 必須: 要件 ID(`REQ-[0-9]{4}-[0-9]{3}`)、見出し行に「証拠」または `Evidence`、見出し行に「bonsai」(大文字小文字を区別しない)、語「純増減」または `Net`、語「削除」または `Removed`。足りない項目をすべて列挙して、終了コード 1。
- このスクリプトは版管理されない(既知の穴。backlog B-06)。

## 7. エラーの扱い
| 状況 | 振る舞い |
|---|---|
| 標準入力が JSON でない、必要なキーがない | 何も出さず終了コード 0 |
| `git` の実行に失敗、リポジトリでない | ブランチに依存する判定(`commit`、`merge`)だけ allow 扱い。`add -A` と `push` はリポジトリがなくても判定する |
| `gov` がない | 127(フックが動かない。DEC-039) |

## 8. テスト構造
`tests/{unit,integration,e2e}/` に置く。ディレクトリから印を付ける(既存の方針)。一時リポジトリを作る補助は既存の `tests/support/` を使う。`merge-to-main.sh` の検査は手動確認(`02_system_tests.md` の L1-M02)。AGENT.md の規則表は手動確認(L1-M05)。
