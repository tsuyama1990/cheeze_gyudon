# L2 詳細設計(契約とアルゴリズム)

状態: **草案(スパイラル 2)。** 対になるテスト仕様: [03_integration_tests.md](03_integration_tests.md)(L2 ↔ 結合)。入力: [01_req_spec.md](01_req_spec.md)(F01〜F09)、[02_system_design.md](02_system_design.md)(規則 K・D・T・Q、フック、フロー)。決定は [decisions.md](decisions.md)(DEC-ID)、進行は [spirals.md](spirals.md)。ここには複製しない。
根拠の種類: **[原典]** / **[データ]**(実測。値の正本は [background/as_is_inventory.md](background/as_is_inventory.md) と [reviews/](reviews/)) / **[推論]** / **[決定]**(DEC-ID)

L2 が決めるのは、型、`Repo` の契約、各規則のアルゴリズム、コマンドと終了コード、フックのプロトコル、エラーの扱い、ハッシュ、モジュール配置、テスト構造。関数の内部とログの細部は L3 で決める。

---

## 0. L1 への修正(L2 の起草で判明したもの)

L1 の記述と、L2 で分かったことが食い違った箇所。二重管理を避けるため、L1(`02_system_design.md`)を同じ変更で直した。

| # | L1 の記述 | L2 の結論 | 理由 |
|---|---|---|---|
| 1 | `Repo` の ref は `base`、`head`、`worktree` の 3 つ(§3.1) | `base` と `head` の 2 つ。`head` が何を指すかは、入口が決める(CI は PR のマージ結果、push のフックは HEAD、commit と書き込みのフックは作業ツリー) | `worktree` は `head` の一種で、独立した概念にする必要がない |
| 2 | プロジェクトの `Stop` フックが全検査を実行する(§6) | プロジェクトの `Stop` フックは置かない | オーナーの全体設定の `Stop` フック(`~/.claude/hooks/stop_gate.sh`)が、すでに `scripts/gate.sh` を呼び、失敗回数の管理(3 回)までしている。重複する(DEC-025) |
| 3 | `adapters/github_action` が PR の差分から `Repo` を作る(§3) | 廃止。CI は `scripts/gate.sh` を呼ぶだけ | `pull_request` の CI は、PR のマージ結果をチェックアウトする。入口は `gov check --head HEAD` で足りる。GitHub のイベントを解析する部品が要らない(YAGNI) |
| 4 | ゲート 4 の対の例: `04_test_spec.md`(§4.1 D) | `04_unit_tests.md` | 02_system_tests、03_integration_tests と並ぶ名前にそろえる |
| 5 | 検証機構の一覧に `adapters/{github_action,claude_hook}/**`(§4.4) | `adapters/claude_hook/**` と `adapters/repo_git/**` | #3 による |

---

## 1. 型(`domain`)

すべて Pydantic v2(`frozen`、`extra="forbid"`)。JSON スキーマは型から生成する。 [決定: DEC-003、DEC-028]

| 型 | フィールドと制約 |
|---|---|
| `RequirementId` | 文字列。`^REQ-\d{4}-\d{3,}$` |
| `FeatureTag` | 文字列。`^REQ-\d{4}-\d{3,}-F\d{2,}$`。`.requirement` で `RequirementId` を返す |
| `Ref` | `"base"` または `"head"` |
| `Change` | `old_path: str \| None`、`new_path: str \| None`、`status: added \| modified \| deleted \| renamed`。不変条件: `renamed` は両方を持つ。`added` は `old_path` が None。`deleted` は `new_path` が None。`paths()` は None でないパスを返す |
| `ApprovalState` | `open` / `closed` / `withdrawn` |
| `Approval` | `requirement: RequirementId`、`state: ApprovalState`、`files: dict[str, Sha256]`。`files` のキーは `.specs/<REQ>/` 直下の `0[1-5]_*` に当たるファイル名。`Sha256` は小文字 16 進 64 文字 |
| `Finding` | `rule: str`(例: `K.a`、`D.b`、`T.a`、`E.repo`)、`path: str \| None`、`message: str`、`hint: str \| None`。重大度の区別はない(すべて失敗) |
| `CheckResult` | `findings: tuple[Finding, ...]`、`human_merge: tuple[str, ...]`(人間のマージが必要な理由)。`ok` は findings が空 |

### 1.1 ゲートごとの成果物
実装後は、コード(`domain/gates.py`)が正本になり、この表は参照に置き換える。 [02_system_design.md §2.1]

| ゲート | 設計 | 対のテスト仕様(文書) |
|---|---|---|
| 1 | `01_req_spec.md` | `01_acceptance_tests.feature` |
| 2 | `02_system_design.md` | `02_system_tests.md` |
| 3 | `03_architecture.md` | `03_integration_tests.md` |
| 4 | `04_detail_design.md` | `04_unit_tests.md` |
| (任意) | `05_*`(決定の根拠) | |

「そろっている」= ファイルが存在し、空でない。

### 1.2 検証機構のパターン
`.github/**`、`scripts/**`、`pyproject.toml`、`uv.lock`、`.pre-commit-config.yaml`、`.claude/settings.json`、`.claude/hooks/**`、任意の `conftest.py`、`AGENT.md`、`CLAUDE.md`、`src/jtc_gov/{domain,derive,checks}/**`、`src/jtc_gov/adapters/{claude_hook,repo_git}/**`。`domain/machinery.py` に 1 か所だけ置く(正本は 02 §4.4。実装後はコード)。

---

## 2. `Repo` の契約

```
class Repo(Protocol):
    def read(self, path: str, ref: Ref) -> bytes | None
    def list(self, ref: Ref) -> Sequence[str]
    def changes(self) -> Sequence[Change]
```

| 項目 | 契約 |
|---|---|
| パス | リポジトリのルートからの相対パス。区切りは `/`。`..` を含まない。大文字小文字は区別する |
| `read` | `ref` の時点の追跡ファイルの内容(バイト列)。存在しなければ None。シンボリックリンクは追わず、リンク先のパス文字列を内容とする(git の扱い) |
| `list` | `ref` の時点のファイルのパス一覧。昇順。`head` が作業ツリーのときは、追跡済みのファイルと、無視されていない未追跡のファイル(エージェントが作って `git add` していない新規ファイル)。作業ツリーで削除されたファイルは含まない |
| `changes` | `base` から `head` への変更。改名は git の検出(`-M`)による。改名は旧パスと新パスの両方を持つ。ファイルモードだけの変更は `modified` |
| エラー | `base` が見つからない、git の失敗は `RepoError(message)` を送出する。`derive` と `checks` は捕まえない。入口が `Finding(rule="E.repo")` に変えて、失敗として扱う(§9) |

実装は `adapters/repo_git`(1 つの実装で、`head` の指し方を切り替える)と、テスト用の `FakeRepo`(`tests/` に置く)。

| `head` の指し方 | 使う入口 |
|---|---|
| PR のマージ結果(CI で、チェックアウトされている `HEAD`) | CI(`gate.sh`) |
| `HEAD` | push のフック |
| 作業ツリー | commit のフック、書き込みのフック、`gov check` の既定、`gov status` |

`base` は、CI では `origin/${GITHUB_BASE_REF}`、それ以外は `origin/main` を既定とする。フックは必要なら `git fetch` する。

---

## 3. 導出(`derive`)

すべて `Repo` 経由で読む純粋関数。

| 関数 | 内容 |
|---|---|
| `load_approvals(repo, ref)` | `list(ref)` から `^\.specs/(REQ-\d{4}-\d{3,})/approval\.json$` に当たるファイルを集め、`parse_approval` で読む。結果は要件 ID → `Approval` または `ParseFailure(reason)` |
| `parse_approval(raw, dir_name)` | JSON を strict に読む。`requirement` がディレクトリ名と一致すること。`files` のキーとハッシュの形式。余分なキーは失敗 |
| `validity(repo, ref, approval)` | `(有効か, 理由の一覧)`。有効 = 状態が `open`、`files` のキー集合が `.specs/<REQ>/` 直下の `0[1-5]_*` の集合と一致、各ファイルの SHA-256 が一致。理由は個別に返す(状態、集合の不一致、ハッシュの不一致) |
| `valid_open(repo, ref)` | 有効な承認の一覧(`open` かつ有効) |
| `spec_tags(repo, ref, req)` | `.specs/<REQ>/01_req_spec.md` から、正規表現 `\[(REQ-\d{4}-\d{3,}-F\d{2,})\]` に当たるタグの集合 |
| `markers(source: bytes)` | テストのソースを `ast` で解析し、テスト関数ごとに、`requirement` marker のタグの一覧を返す(下) |
| `related_requirements(repo, changes)` | 変更に含まれる `.specs/<REQ>/` のパスと、変更されたテストファイル(`head`)の marker から、要件 ID の集合 |
| `display_gate(repo, ref, req)` | ペア(1.1)がそろっていない最小のゲート。すべてそろっていれば 5(表示用。CI の合否に使わない) |

### 3.1 marker の読み取り
- テスト関数 = `tests/**` の `test_*.py`、`*_test.py` のうち、モジュール直下の `test*` 関数と、`Test*` クラス内の `test*` メソッド(`pyproject.toml` の pytest 設定に合わせる)。 [データ: 現行の設定]
- marker = デコレータ `@pytest.mark.requirement("TAG")` または `@requirement("TAG")`。クラスのデコレータは、そのクラスのメソッドに適用される。モジュールの `pytestmark = pytest.mark.requirement("TAG")` は、そのファイルの全テストに適用される。引数が文字列リテラルでないものは、タグなしとして扱う。
- 1 つの関数に複数の marker があってよい。
- 解析できないソース(構文エラー)は `ParseFailure` として、T で失敗にする。

---

## 4. 検査(`checks`)

各検査は `Repo` を受け取り、`list[Finding]` を返す。`changes` は 1 回だけ取得して共有する。

### 4.1 K
```
src_changed = いずれかの Change の paths() に "src/" で始まるものがある
aux_changed = いずれかの Change の paths() が "tests/" または ".specs/" で始まる
if not (src_changed and aux_changed): return []

opens = valid_open(repo, "base")
if len(opens) != 1: Finding(K.a, "有効な承認が {n} 個") ; return
req, manifest = opens[0]

guarded = {".specs/<req>/approval.json"} ∪ {".specs/<req>/<name>" for name in manifest.files}
for p in すべての Change の paths(): if p in guarded: Finding(K.b, path=p)

extra = related_requirements(repo, changes) - {req}
for r in extra: Finding(K.c, "要件 {r} は承認された要件の外")
```
- `src/` の判定は旧パスと新パスの両方を見る(改名)。 [データ: 改名の実験]
- 「ちょうど 1 つ」は、`open` の承認が 2 つ以上ある場合も K.a で失敗する(D.d が防ぐ状態だが、`base` が壊れていても検出する)。

### 4.2 D
`.specs/<REQ>/approval.json` に当たる Change(追加、変更、削除、改名)ごとに:

| 条件 | Finding |
|---|---|
| 削除、または改名で元のパスが `approval.json` | `D.delete` |
| `head` で `parse_approval` が失敗 | `D.parse` |
| 状態 `open`: (a) ゲート 1〜4 のペア(1.1)のうち、そろっていないもの | `D.a`(欠けているファイルごと) |
| 状態 `open`: (b) `validity` の理由のうち、集合の不一致とハッシュの不一致 | `D.b`(理由ごと) |
| 状態 `open`: (d) `head` で `valid_open` ではなく、`open` の `approval.json` が 2 つ以上 | `D.d` |
| 状態 `closed`: (c) `spec_tags(head)` の各タグに、`head` のテスト関数の marker が 1 つもない | `D.c`(タグごと) |
| 状態 `withdrawn` | なし |

`D.d` の数え方: `head` の `list` から `approval.json` を全部読み、状態が `open` のものが 2 つ以上なら失敗(有効かどうかは問わない)。

### 4.3 T
`head` の全ファイルに対して(変更されたものだけでなく):

| 条件 | Finding |
|---|---|
| `test_*.py`、`*_test.py` が `tests/` の外にある | `T.c` |
| `tests/**` のテスト関数に、有効な形式の marker がない | `T.a`(関数ごと) |
| marker のタグの要件の `01_req_spec.md` が `head` にない、またはタグが仕様に含まれない | `T.b` |
| テストのソースが解析できない | `T.a`(ファイル) |

### 4.4 人間のマージの明示
`human_merge(changes)`: 全 Change の `paths()` が、1.2 のパターンまたは `.specs/*/approval.json` に当たるなら、その理由(パターン名)を `CheckResult.human_merge` に入れる。失敗にはしない(規約 C2、C3)。

### 4.5 実行
`run_all(repo) -> CheckResult` は K、D、T を順に実行して Finding を連結する。K と D と T は互いに独立で、一方の失敗が他方の実行を妨げない。

---

## 5. 品質検査 Q と `scripts/gate.sh`

`gov check` が行うのは K・D・T だけ。Q のツール(lint、型、デッドコード、テスト、カバレッジ、変更行のカバレッジ)は `scripts/gate.sh` が実行する。`gate.sh` が品質ゲートの**唯一の入口**で、`gov check` もその 1 ステップ。 [決定: F09、DEC-025]

| 順 | ステップ | 閾値の置き場 |
|---|---|---|
| 1 | `ruff check`、`ruff format --check` | `pyproject.toml` |
| 2 | `mypy` | `pyproject.toml` |
| 3 | `vulture` | `pyproject.toml` |
| 4 | `pytest`(分岐カバレッジ。閾値を満たさなければ失敗) | `pyproject.toml` の `fail_under` |
| 5 | `diff-cover`(`src/**` の変更行。`--fail-under` を必ず指定) | `pyproject.toml` の `[tool.jtc_gov]` の `diff_coverage_fail_under` |
| 6 | 新しい `# pragma: no cover` の検出(`git diff` の追加行) | — |
| 7 | `gov check --base $GATE_BASE --head worktree` | — |
| 8 | pre-commit の衛生フック(`pre-commit run --all-files`) | `.pre-commit-config.yaml` |

- `GATE_BASE` の既定は `origin/main`。CI では `origin/${GITHUB_BASE_REF}`。
- `gate.sh` から `pre-commit` を呼ぶので、`.pre-commit-config.yaml` には**衛生フックだけ**を置く(ruff、mypy、vulture、pytest などの重複を持たない)。 [提案: Q-L2-4。監査 #15]
- `__init__.py` を `coverage` の `omit` から外す(移行)。 [データ: reviews/L1_review5 §3]
- 変更行のカバレッジの移動・改名・整形の扱いは、`diff-cover` の挙動に従う(未カバー行の移動はテストの追加が必要)。

---

## 6. コマンド(`adapters/cli`)

残すのは 5 つ。 [決定: DEC-029]

| コマンド | 内容 | 終了コード |
|---|---|---|
| `gov check [--base REF] [--head worktree\|HEAD\|REF] [--json]` | K・D・T を実行する。既定は `--base origin/main --head worktree`。出力は 1 行 1 Finding: `<rule> <path>: <message>`。最後に「人間のマージが必要: <理由>」を出す。`--json` は `{"ok", "findings", "human_merge"}` | 0: 通過 / 1: 規則違反あり / 2: 評価できない(`RepoError` など) |
| `gov status [--head ...]` | 要件ごとに、状態、承認の有効/失効(理由つき)、表示用の現在ゲート、「テストまたは仕様も変える `src/` の変更が可能か」を表示する。`state.json` を書かない | 0 / 2 |
| `gov init` | `.claude/settings.json`(入れ子形式のフック設定)と、`.gitattributes`(`.specs/** text eol=lf`)を作る。既存のファイルは上書きせず、差分を表示して終了コード 1 | 0 / 1 |
| `gov doctor` | 前提の検査(spirals.md §2 の preflight のうち機械で確かめられるもの)を実行する | 0 / 1 |
| `gov hook <event>` | フックの入口(§7)。`event` は `pre-tool-use`、`session-start`、`user-prompt-submit` | §7 |

廃止: `gate-check`、`escalate`、`draft-decision`、`redteam`、`review-status`、`audit-push`、`format-pr-comment`、`format-pr-summary`、`ci-verify`。

---

## 7. フックのプロトコル(`adapters/claude_hook`)

実測した機構: 拒否 = 終了コード 2 + 標準エラーの文面。通知 = 標準出力の文面(終了コード 0)。 [データ: 2026-10-27 の `claude -p`。JSON 形式でも動くが、機構を 1 つにするため使わない] [決定: DEC-015]

共通: 標準入力の JSON から `hook_event_name`、`tool_name`、`tool_input`、`cwd` を読む。`cwd` から `git rev-parse --show-toplevel` でルートを求める。git のリポジトリでない、または `.specs/` がない場合は何もしない(終了コード 0、出力なし)。標準入力が JSON でない場合も、何もしない。

| イベントとマッチャー | 内容 | 出力 |
|---|---|---|
| `PreToolUse`、`Edit\|Write\|MultiEdit\|NotebookEdit` | 対象パスをルートからの相対パスにする。`src/` の下で、`valid_open` が 1 つでなければ通知する。拒否しない | 標準出力(通知) |
| `PreToolUse`、`Bash` | コマンド文字列を `;`、`&&`、`\|\|`、`\|` で分け、各部を `shlex` で分解する。`git` の最初の非オプション引数が `commit` なら `head=作業ツリー`、`push` なら `head=HEAD` で `run_all` を実行する。Finding があれば拒否。複合コマンドや `-a` も、同じ判定になる(作業ツリー全体を見るため)。 `git stash`、`git commit` を含まない書き込みは対象外(N1) | 標準エラー(拒否)/ なし |
| `SessionStart` | `gov status` と同じ要約(3 行以内) | 標準出力(通知) |
| `UserPromptSubmit` | 同上。承認の状態が変わっていなければ短くする | 標準出力(通知) |

- **内部エラーの扱い**: 拒否系(`Bash` の commit と push)で、`gov` 自身が例外を出したとき(`RepoError` を含む)は、終了コード 2 と「gov hook internal error: …」を返す(fail-closed)。通知系で例外が出たときは、何も出さずに終了コード 0。 [提案: D4。§9]
- `Stop` はプロジェクトでは置かない(§0 #2)。全体設定の `Stop` フックが `scripts/gate.sh` を呼ぶ。
- 設定ファイル `.claude/settings.json` は入れ子形式で、`gov hook <event>` を呼ぶ。内容は `gov init` が出す。この文書には複製しない。

---

## 8. CI(GitHub Actions)

- ジョブ(`gate-verification`)は、`fetch-depth: 0` でチェックアウトし、`uv sync` して `scripts/gate.sh` を実行するだけ。`GATE_BASE=origin/${{ github.base_ref }}`。
- `pull_request` では、PR のマージ結果がチェックアウトされる。`gov check --head worktree` はそのチェックアウトに対して `base`(最新の `main`)との差分を評価する。`strict_required_status_checks_policy: true` で、PR が最新の `main` に追従していることを保証する。 [02_system_design.md §8]
- PR 側のチェッカーが実行される穴(A3)は残る。`main` 側のチェッカーで実行する方式(`pull_request_target`)の実測は、リスク R1(`spirals.md` §5)。

---

## 9. エラーの扱い(D4)

| 状況 | `gov check` | 拒否系のフック | 通知系のフック |
|---|---|---|---|
| `base` が見つからない(`origin/main` が取得できない) | `E.repo`、終了コード 2 | 終了コード 2 | 通知しない |
| `approval.json` が壊れている(`base`) | 承認は無効として扱う。K.a の理由に出る | 同左 | 同左 |
| `approval.json` が壊れている(`head`、変更した PR) | `D.parse` | 同左 | — |
| `.specs/` がない(未初期化) | 有効な承認が 0 個。K が適用される PR は K.a で失敗 | 同左 | 何もしない |
| テストのソースが解析できない | `T.a`(ファイル) | 同左 | — |
| `gov` 自身の例外 | 終了コード 2 | 終了コード 2 + 文面 | 終了コード 0、出力なし |
| 標準入力が JSON でない / `cwd` が git の外 | — | 何もしない(終了コード 0) | 何もしない |

方針: 検査を評価できないときは失敗にする(fail-closed)。ただし、拒否できない通知系は黙って終了する。ホスト(Claude Code)の入力の不備は、こちらの失敗にしない。 [提案: Q-L2-7]

---

## 10. ハッシュと承認ファイル

- SHA-256 は、ファイルのバイト列そのままで取る。改行の揺れは、`.gitattributes` の `.specs/** text eol=lf` で防ぐ。 [決定: DEC-027]
- `approval.json` の例:
  ```json
  {
    "requirement": "REQ-2026-010",
    "state": "open",
    "files": {
      "01_req_spec.md": "<64 桁の 16 進>",
      "02_system_design.md": "<...>"
    }
  }
  ```
- 人間が作る(規約 C1)。コマンドによる生成 `gov approve` は、MVP のコマンド(DEC-029)に含めない(Q-L2-6)。

---

## 11. モジュール配置

```
src/jtc_gov/
  domain/    ids.py  models.py  gates.py  machinery.py
  derive/    approvals.py  markers.py  gates.py
  checks/    k.py  d.py  t.py  __init__.py(run_all)
  adapters/  cli.py  claude_hook.py  repo_git.py
```
現行モジュールとの対応は 02 §10(L2 の結論で #3 を反映)。

## 12. テスト構造(D10)

| 層 | 場所 | 内容 |
|---|---|---|
| 単体 | `tests/unit/` | `domain`、`derive`、`checks` を `FakeRepo` で。K・D・T の全分岐を表駆動で。構造検査(依存の向き、純粋性、`state.json` を書かない) |
| 結合 | `tests/integration/` | `repo_git` を実 git の一時リポジトリで。`FakeRepo` と `repo_git` が同じ入力に同じ結果を返す適合テスト。`cli`、`claude_hook`(標準入力の JSON → 出力と終了コード) |
| E2E | `tests/e2e/` | `gov` を subprocess で、一時リポジトリに対して。02_system_tests.md のシナリオ |

すべてのテストは `requirement` marker(`REQ-2026-010-Fnn`)を持つ。テスト仕様との対応は、各仕様書の追跡表が正本。

## 13. 実装の順序(移行の入口)
02 §11 に従う。L2 から見た追加: (1) `domain` と `derive` と `checks` を、`FakeRepo` の単体テストと一緒に作る (2) `repo_git` と適合テスト (3) `gov check` と `gov status` (4) `gov hook` (5) `gate.sh` に `gov check` と変更行のカバレッジを追加 (6) 旧コマンドの削除。

## 14. 未決の小さな問い

| ID | 事実 | 問い | 暫定の答え(推論) |
|---|---|---|---|
| Q-L2-4 | `gate.sh` が pre-commit を呼び、pre-commit も ruff、mypy、vulture、pytest を持つ(重複。監査 #15) | pre-commit は衛生フックだけにするか | そうする |
| Q-L2-5 | `main` への直接コミット禁止は、全体設定のフック、pre-commit の `no-commit-to-branch`、ruleset の 3 つで実装される(監査 #16) | pre-commit の `no-commit-to-branch` を外すか | 外す。エージェントは全体のフック、人間の push は ruleset が止める |
| Q-L2-6 | 承認ファイルは人間が `sha256sum` で作る | `gov approve`(生成コマンド)を足すか | MVP では足さない(DEC-029 の 5 つに含めない)。手作業が負担なら次のスパイラル |
| Q-L2-7 | 拒否系のフックは、`gov` 自身の不具合でも拒否する(fail-closed) | 不具合のときの回避手段(環境変数など)を設けるか | 設けない。回避手段は、エージェントも使えるため。人間が設定を直す |
| Q-L2-8 | 変更行のカバレッジの閾値のキー名は `[tool.jtc_gov]` の `diff_coverage_fail_under`(仮) | 値は全体のカバレッジと同じにするか | 同じ値にする。実測して調整する |
