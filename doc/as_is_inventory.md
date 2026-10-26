# jtc-gov 現状棚卸し (As-Is)

目的: 設計をやり直す前に「いま何があり、何が強制され、何が強制されていないか」を事実だけで固定する。
実装・修正の提案は含めない(未決事項は `open_design_decisions.md`)。

- 計測対象: `main` @ `7ca78ef`(PR #3, #5 マージ後)
- 計測日: 2026-10-26
- 根拠の種類: **[原典]** 資料・コードに記載 / **[データ]** 本日実測(コマンドと結果) / **[推論]** 未検証の判断

---

## 1. 規模

| 項目 | 値 | 根拠 |
|---|---|---|
| `src/` の Python 行数(`__init__` 含む) | 1,360 | [データ] `cat $(git ls-files 'src/*.py') \| wc -l` |
| `tests/` の Python 行数 | 2,000 | [データ] 同上(`tests/*.py`) |
| テスト数 | 96 | [データ] `pytest --collect-only -q -o addopts=""` |
| CLI コマンド数 | 14 | [データ] `gov --help` |
| 分岐カバレッジ | 95.6% | [データ] `bash scripts/verify_all.sh`(2026-10-26) |

テスト数の内訳 [データ]: `test_cli.py` 22 / `test_github_integration.py` 17 / `test_version.py` 14 / `test_domain_and_state.py` 9 / `test_cli_phase2.py` 8 / `test_coverage_gap.py` 6 / `test_services.py` 6 / `test_redteam.py` 4 / `test_decision.py` 3 / `distortions/` 6 / `e2e/` 1。

---

## 2. モジュール構成と依存

| モジュール | 行数 | 責務 | 内部依存 |
|---|---|---|---|
| `cli.py` | 247 | click のコマンド定義、services への委譲 | domain, services, integrations |
| `domain/models.py` | 49 | `GateId` `RequirementStatus` `RequirementItem` `StateModel` `GateReviewDeliverable` | なし |
| `domain/review_models.py` | 33 | `GateReview`(レビュー結果、フラット) | なし |
| `domain/exceptions.py` | 26 | 例外階層 | なし |
| `services/state_engine.py` | 88 | state.json の読み書き、パス判定(`is_path_unlocked`)、要件更新 | domain |
| `services/gate_keeper.py` | 142 | ゲート検証と状態前進、ゲートごとの unlock パターン | domain, state_engine |
| `services/escalator.py` | 72 | ゲートの巻き戻しと ESC 記録 | domain, gate_keeper, state_engine |
| `services/verifier.py` | 50 | PreToolUse 判定 | domain, state_engine |
| `services/tracer.py` | 101 | 仕様タグとテスト marker の双方向照合 | domain, state_engine |
| `services/redteam_engine.py` | 74 | ペルソナ別レビューの生成(**モック**) | review_models, templates |
| `services/decision_engine.py` | 64 | `05_decision.md` の生成 | review_models |
| `scaffold/initializer.py` | 105 | `gov init` の雛形出力 | domain, gate_keeper, state_engine |
| `diagnostics/doctor.py` | 87 | 環境診断 | なし |
| `integrations/github/*` | 208 | PR コメント/要約の整形、Actions エントリ | なし |
| `templates/presets.py` + `*.md` | 9 + 3 md | ペルソナのプリセット | なし |
| `adapters/` | 0 | **空** | — |

根拠: [データ] `wc -l`、`grep '^from jtc_gov'`。

観測:
- 依存方向は `cli → services → domain` で、循環はない [データ]。`AGENT.md` が宣言する `adapters → services → domain` は、`adapters/` が空のため成立していない [データ]。
- レビューを表すモデルが 2 つある: `GateReview`(redteam/decision が使用)と `GateReviewDeliverable`(gate_keeper が使用)。フィールドは同じだが、型が違う [データ] → §6 欠陥 B。
- `integrations/` を使うのは `cli.py` の 2 コマンド(`format-pr-comment` `format-pr-summary`)だけ。CI ワークフローはどちらも呼ばない(§5) [データ]。

### 宣言された依存のうち未使用のもの [データ]
`pyproject.toml` の `dependencies` に `pydantic-settings` `jsonschema` `pyyaml` があるが、`src/` で import しているファイルは 0 件(`click` 3 件、`pydantic` 3 件)。`.specs/gate_review.schema.json` も `src/` `scripts/` `tests/` `.github/` から参照されていない。

---

## 3. 状態とデータの所在

### 3.1 `.specs/state.json`(型付きスキーマ)[原典: `domain/models.py`]
```
StateModel { active_requirement_id: str, requirements: { <REQ-id>: RequirementItem } }
RequirementItem { title, current_gate: GateId, status: RequirementStatus,
                  unlocked_paths: [glob], completed_gates: [GateId] }
GateId: GATE1_SPEC → GATE2_SYSTEM → GATE3_INTEGRATION → GATE4_DETAIL → GATE5_IMPL
RequirementStatus: INIT | IN_PROGRESS | ROLLBACK | COMPLETED
```
`active_requirement_id` は 1 つだけ。同時に複数の要件を進める構造にはなっていない [原典]。

### 3.2 ファイルを書くのは誰か [データ: `grep write_state|write_text|mkdir`]
| 書き込み先 | 書くコマンド |
|---|---|
| `.specs/state.json` | `init`(新規)、`gate-check`(前進)、`escalate`(巻き戻し) |
| `.specs/<REQ>/escalations/ESC-NNN.json` | `escalate` |
| `.specs/<REQ>/reviews/<gate>_<persona>.json` | `redteam` |
| `.specs/<REQ>/05_decision.md` | `draft-decision` |
| `.agent/settings.json`, `.pre-commit-config.yaml`, `.github/workflows/gate_pipeline.yml`, `AGENT.md`, `CLAUDE.md` | `init` |

### 3.3 `status` の遷移は完結していない [データ: `grep IN_PROGRESS src`]
- `init` が `INIT` を設定、`gate-check`(GATE5)が `COMPLETED` を設定、`escalate` が `ROLLBACK` を設定する。
- `IN_PROGRESS` を設定するコードは存在しない(enum 定義のみ)。`INIT` から出る遷移も、`ROLLBACK` から戻る遷移も存在しない。

---

## 4. コマンド一覧

| コマンド | 状態を変更 | 失敗時 | 備考 |
|---|---|---|---|
| `init` | 書く | — | 要件 ID `REQ-0000-001` を出力 |
| `doctor` | 読む | exit 1 | git hooks 未導入だと失敗(§6) |
| `status` | 読む | exit 1 | |
| `gate-check --gate N` | **書く(前進)** | exit 1 | 現在ゲート == N のときだけ検証・前進 |
| `trace-check` | 読む | exit 1 | アクティブ要件の `REQ-xxx-Fnn` タグだけ照合 |
| `ci-verify` | 読む | exit 1 | `trace-check` を呼ぶだけ |
| `escalate --gate N --reason` | **書く(後退)** | exit 1 | N < 現在ゲートのときだけ |
| `verify-tool` | 読む | exit 1 | 状態ファイルが無いと許可(exit 0) |
| `redteam --gate G [--preset]` | 書く | exit 1 | **モック**(固定文言) |
| `draft-decision --req R` | 書く | exit 1 | 署名行を含むファイルを生成 |
| `review-status --gate G` | 読む | — | 状態から要件を取得できないとき `REQ-000` を参照 |
| `audit-push` | 読む | exit 1 | `pytest` と `trace-check` を実行 |
| `format-pr-comment` / `format-pr-summary` | 読む | — | CI から未使用 |

根拠: [原典] `cli.py`、[データ] `gov --help`。

### 4.1 ゲートごとの検証(`gate-check`)[原典: `gate_keeper.py`]
| ゲート | 必須成果物(`.specs/<REQ>/` 配下) | 追加検証 |
|---|---|---|
| GATE1_SPEC | `01_req_spec.md`, `01_acceptance_tests.feature` | `reviews/*.json` のうち当該ゲートのものがすべて APPROVED |
| GATE2_SYSTEM | `02_system_design.md`, `02_system_tests.md` | 同上 |
| GATE3_INTEGRATION | `03_architecture.md`, `03_integration_tests.md` | 同上 |
| GATE4_DETAIL | `04_detail_design.md`, `tests/test_*.py` | 同上 + `05_decision.md` に文字列 `HUMAN_SIGN_OFF: APPROVED` |
| GATE5_IMPL | なし | 同上 → status を `COMPLETED` |

### 4.2 ゲートごとの編集許可(`unlocked_paths`)[原典: `GATE_UNLOCK_PATTERNS`]
常時: `.agent/*` `doc/*` `README.md` `pyproject.toml` `.pre-commit-config.yaml` `scripts/*`。
加えて GATE1: `.specs/<REQ>/01_*` / GATE2: `02_*` / GATE3: `03_*` / GATE4: `04_*` `05_*` `tests/*` / GATE5: `.specs/<REQ>/*` `tests/*` `src/*`。
GATE5 を通過して `COMPLETED` になっても `src/*` は開いたまま [データ: `gate-check --gate 5` の実装]。

---

## 5. 強制の層(何が、どこで、実際に効いているか)

| 層 | 仕組み | 状態 | 根拠 |
|---|---|---|---|
| エージェントのツール実行前 | `.agent/settings.json` の PreToolUse | **無効(実測: エージェントを止めない)** | §5.1 |
| ローカル git | `.pre-commit-config.yaml` | **この clone では未導入** | [データ] `ls .git/hooks` に有効なフックなし。`gov doctor` が `[FAIL] Git hooks: missing pre-commit or pre-push` |
| CI | `.github/workflows/gate_pipeline.yml` | 稼働中。実行内容は `uv sync` → `gov ci-verify` → `scripts/verify_all.sh` | [原典] |
| リモートの保護 | `.github/templates/ruleset_main.json` | **未適用(テンプレートのみ)** | [データ] `gh api .../branches/main/protection` → 404 "Branch not protected"、`gh api .../rulesets` → `[]` |
| 人間レビュー | `.github/CODEOWNERS` | 宛先 `@architecture-reviewers` `@core-maintainers` はテンプレート値。保護が無いので強制されない | [原典]+[データ] |

CI のサインオフ確認ステップは `echo` のみ、PR コメント投稿ステップは「Placeholder」と明記された `echo` のみ [原典: workflow]。

### 5.1 フックの接続について [データ]
2026-10-26、Claude Code 2.1.310 のヘッドレス実行(`claude -p`)で、各設定のもとで Write を 1 回実行して測った(詳細: `proposal_l1_flow.md` §6 U5)。

| 設定 | フック呼び出し | 書き込み |
|---|---|---|
| このリポジトリと同じ flat 形式(`.claude/settings.json` に置いた場合) | 0 回(検証エラー `hooks.PreToolUse.0.hooks: Expected array`) | 成功 |
| 入れ子形式 + `exit 1`(`verify-tool` の拒否時の終了コード) | 1 回 | **成功**(拒否にならない) |
| 入れ子形式 + `exit 2` | 1 回 | 拒否 |

- Claude Code のフックは `.claude/settings.json` または `~/.claude/settings.json` に置き、`{"matcher", "hooks": [{"type": "command", "command"}]}` の入れ子構造で、入力を stdin の JSON(`tool_name` `tool_input.file_path` `cwd`)で受け取る。ブロックは exit code 2。
- このリポジトリの `.agent/settings.json` は、場所・構造・入力の受け取り方(環境変数)・終了コード(1)のすべてが、これと異なる。リポジトリに `.claude/` は存在しない。
- 結論: 現在の PreToolUse フックは、仮に設定を `.claude/settings.json` に置いても、構造が不正で読み込まれず、構造を直しても exit 1 では拒否にならない。**エージェントを止める経路は、いまのところ存在しない。**

### 5.2 `verify-tool` の判定仕様 [原典: `verifier.py`, `state_engine.py`, `cli.py`]
- 対象ツール名: `Edit` `Write` `MultiEdit` `NotebookEdit`。それ以外のツール名は、パスを見ずに許可。
- パスの取得キー: `path` `file_path` `filepath` `notebook_path`。
- 判定: プロジェクトルート(= `cwd`)基準の相対パスに正規化し、`unlocked_paths` に `fnmatch`。ルート外は拒否。`fnmatch` の `*` は `/` を越える。
- `state.json` が存在しない: 許可(exit 0)。壊れている・形式不正: 拒否(exit 1)。
- `--file X` 指定時は `Write` として判定。引数が何もなければ許可。
- シンボリックリンクは `resolve()` で実体に解決してから判定する。
- Bash などシェル経由の書き込みは、判定の対象外。

### 5.3 hook の所要時間 [データ]
`uv run python -m jtc_gov.cli verify-tool ...` を 5 回計測: 0.09〜0.11 秒(壁時計)。要件 `REQ-2026-001-F04` は「< 50ms」。`gov doctor` が報告する値(0.06ms)は、`extract_target_file` 相当の自明な関数呼び出しだけの時間であり、フック全体の所要時間ではない(`doctor.py` `_check_latency` は `is_path_unlocked("", [])` を計測)。

---

## 6. 既知の欠陥(本日実測で確認したもの)

| ID | 内容 | 再現 | 根拠 |
|---|---|---|---|
| A | **サインオフを自己発行できる。** `draft-decision` が `HUMAN_SIGN_OFF: APPROVED by @username` を含むファイルを生成し、`gate-check --gate 4` が通る | `init` → GATE1〜3 を通過 → `draft-decision --req REQ-0000-001` → `gate-check --gate 4` が exit 0 で GATE5_IMPL へ | [データ] 2026-10-26 |
| B | **redteam の出力が gate-check で読めない。** `gate_id` が `gate_1`、`requirement_id` が `REQ-000`(既定)で、`GateReviewDeliverable` の enum / 正規表現に合わない | `redteam --gate gate_1` → レビューを要件ディレクトリへ置く → `gate-check --gate 1` が `Failed to parse review` で exit 1 | [データ] 2026-10-26 |
| C | `redteam` は要件 ID を受け取らず常に `REQ-000` の配下へ書く(CLI が `requirement_id` を渡していない)。`review-status` も状態から取れないとき `REQ-000`。`REQ-000` は `REQ-YYYY-NNN` 形式(トレーサ・レビューモデル)に合わない | コード参照 | [原典] |
| D | `COMPLETED` になっても `src/*` が開いたまま | §4.2 | [原典] |
| E | 仕様 `01_acceptance_tests.feature` の escalate が `--to-gate` を使うが、実装のオプションは `--gate` | feature 内の記述 | [原典] |
| F | README のロードマップが Phase 1〜4 すべて未完了(`[ ]`)のまま、マージ済みだった | `README.md` §7 | [原典] 2026-10-26 に README を書き直して解消 |
| G | `doc/phase2.md` は 0 バイト | `wc -c` | [データ] |
| H | `gov doctor` は、この clone で git hooks 未導入のため失敗する | `gov doctor` | [データ] |
| I | **PreToolUse フックがエージェントを止めない**(場所・構造・終了コードの 3 点。§5.1) | `claude -p` で実測 | [データ] 2026-10-26 |

## 7. 仕様・テストの対応状況 [データ]

- 仕様ディレクトリは `.specs/REQ-2026-001/` のみ(F01〜F05)。
- **訂正(2026-10-27)**: 次の件数は、デコレータ行の grep による数で、文字列リテラル内の記述を含む。AST で数えた実際の marker 付きテスト関数は、REQ-2026-001 が 37、REQ-2026-002 系が 15+1、REQ-0000-001 が 0。テスト関数 96 本のうち、要件 marker なし 6、形式不正 29、形式は正しいが仕様なし 24。
- テストが付けている `@pytest.mark.requirement` のタグ(件数): `REQ-2026-001-F01..F05`(計 41)、`REQ-2026-002-F0x`/`REQ-2026-002`/`REQ-2026-002-F01`(17)、`REQ-2026-003-F01..F03`(17)、`REQ-2026-004-F01..F06`(7)、`REQ-INIT-001`(14)、`REQ-0000-001-F01`(1)。仕様が存在するのは `REQ-2026-001` だけなので、他の要件のタグは仕様に紐づかない。`trace-check` はアクティブ要件のタグだけを照合するため、これらは検査されない。
- テストのディレクトリは `tests/` 直下の平置き + `e2e/`(1 件)+ `distortions/`(6 件)。`unit/` `integration/` の区別はない。設計階層(L1〜L3)との対応づけはない。

## 8. 宣言と実態の差(`AGENT.md` / README / `doc/jtc_governance_framework.md`)

| 宣言 | 実態 |
|---|---|
| `AGENT.md`: 設定は型付き Pydantic settings に外出し | `pydantic-settings` は未使用 [データ] |
| `AGENT.md`: 重複コードは `jscpd` でゼロ | 自作 `scripts/check_duplicates.py`(5 行一致、import を除外)を使用 [原典] |
| `AGENT.md`: `adapters → services → domain` | `adapters/` は空 [データ] |
| `AGENT.md`: Gate 2/3 は `02_system_design.md + 02_system_tests.md` 等を同時に作成 | `gate-check` が存在確認はするが、内容は見ない(空ファイルでも通る) [データ: 本日の probe は `echo x` のみで通過] |
| README: 敵対的レビューは `gate_review.json` を厳密検証 | レビュー生成はモック固定文言。検証は `GateReviewDeliverable`(形式不一致、欠陥 B) |
| README: Layer 5 は「air-gapped、credential 漏洩ゼロ」の Actions | 実際は通常の GitHub-hosted runner で `uv sync` / テストを実行。保護ルールは未適用 |
| README / framework: `gov audit-push` は「air-gapped push validation」 | `pytest` と `trace-check` を実行するだけ |


## 9. ロードマップの食い違い [データ]

- `doc/jtc_governance_framework.md` のロードマップは Phase 1〜4。Phase 2 の定義は「フック・コマンドテンプレート(`.agent/`)」。実装された Phase 2 は red team と decision engine で、定義が違う。
- Phase 5(企業規模の運用展開・テレメトリ・署名による証明)は、リポジトリに記載がない。Jules 向けのプロンプトとしてだけ存在し、ブランチ・PR はない。評価は `open_design_decisions.md` の D13。

---

## 訂正履歴

| 日付 | 訂正対象 | 内容 |
|---|---|---|
| 2026-10-26 | README.md 「Human sign-off」注記(PR #5 で追加) | 「サインオフを代行するコマンドは存在しない」と記載したが誤り。`draft-decision` が署名行を生成する(欠陥 A)。README の記述を訂正した。 |
| 2026-10-26 | 会話中の報告 | 「pre-commit のゲートがコミット時に通る」前提で作業を報告したが、この clone には git hooks が未導入で、コミット時のゲートは動いていなかった(欠陥 H)。ゲートは `scripts/verify_all.sh` を手動実行して確認していた。 |
