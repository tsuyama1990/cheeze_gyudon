# L3 テスト仕様(単体)

状態: **草案(スパイラル 3)。** 対になる設計書: [04_detail_design.md](04_detail_design.md)(L3 ↔ 単体)。決定は [decisions.md](decisions.md)、経緯は [reviews/](reviews/)。
根拠の種類: **[原典]** / **[データ]** / **[推論]**

## 1. 方針
- 単体テストは、`domain`、`derive`、`checks` を `FakeRepo`(`tests/support/fake_repo.py`)で、`adapters` のうち純粋な部分(`classify_git`、`handle`、`report`、`render_*`)を関数として、確かめる。実 git を使うものは結合テスト(03_integration_tests.md)。
- ID は `L3-Uxx`。各テストは `requirement` marker(`REQ-2026-010-Fnn`)を持つ。表の「要件」の列がそのタグ。
- 表駆動で書く。1 行 = 1 ケース。期待値は、設計書の該当節が正本で、ここには要点だけを書く。
- 「現行」の列は、現行コードで実現できるか [データ: 2026-10-27]。現行は 03 とは別の構成のため、ほぼ「できない」。

## 2. `domain`

| ID | 対象 | ケース | 期待 | 要件 | 現行 |
|---|---|---|---|---|---|
| L3-U01 | `requirement_of` | `REQ-2026-010-F01`、`REQ-2026-010-F99`、`REQ-2026-010`(タグでない)、`req-2026-010-f01`、`REQ-INIT-001` | 最初の 2 つは `REQ-2026-010`、残りは `ValueError` | F03 | できない |
| L3-U02 | `Change` の不変条件 | `added` で `old_path` あり、`deleted` で `new_path` あり、`renamed` で片方が None、正常な 4 種 | 不正は `ValueError`、正常は通る | F01 | できない |
| L3-U03 | `Change.paths()` | 4 種 | 旧、新の順で None を除く | F01 | できない |
| L3-U04 | `Approval` の厳格な検証 | 正常、状態が不正、`files` のキーが `0[1-5]_*` でない(サブディレクトリ、`06_x.md`)、ハッシュが大文字、63 桁、余分なキー、`requirement` が不正な形式 | 正常以外は `ValidationError` | F02 | できない |
| L3-U05 | `CheckResult.ok` | findings が空 / 空でない | 真 / 偽 | F01 | できない |
| L3-U06 | `DELIVERABLES`・`APPROVED_FILE_PATTERN`・`GUARDED_PREFIX` | ゲート 1〜4 の各ファイル名、`05_decision.md`、`06_x.md`、`notes.md`、`01_notes/extra.md` | パターンへの一致が 03 §1.1・§4.1 のとおり | F02 | できない |
| L3-U07 | `machinery_reason` | 02 §4.4 の全パターンの代表パス、`.gitattributes`、`src/jtc_gov/adapters/cli.py`、`src/other/x.py`、`docs/x.md`、`.github/workflows/x.yml`、`scripts/gate.sh`、ルート直下の `conftest.py` と `tests/sub/conftest.py`、`.specs/REQ-2026-010/approval.json`(これは `human_merge` 側) | 当たるものは表示名、それ以外は None。ルート直下以外の `conftest.py` も当たり、`xconftest.py` は当たらない | F07 | できない |

## 3. `derive`

| ID | 対象 | ケース | 期待 | 要件 | 現行 |
|---|---|---|---|---|---|
| L3-U08 | `sha256_hex` | 空、LF、CRLF | 既知のダイジェスト。LF と CRLF は違う | F01 | できない |
| L3-U09 | `parse_approval` | 正常、JSON でない、空、`requirement` がディレクトリ名と違う、Approval の不正(U04 の各ケース)、**JSON の重複キー**(`state` が 2 回)、**非 UTF-8 のバイト列** | 正常は `Approval`、他は `ParseFailure`(理由つき。重複キーは黙って後勝ちにしない) | F02 | できない |
| L3-U10 | `load_approvals` | `approval.json` が 0 個、1 個、2 個、壊れたもの 1 個、`approval.json` に似た名前(`approval.json.bak`、`x/approval.json`) | 正確なパスだけを読む。壊れたものは `ParseFailure` で返る | F02 | できない |
| L3-U11 | `validity` | 状態が `closed`、承認後に `05_*` を足した、承認済みのファイルが消えた、ハッシュが違う、複数の問題が同時、すべて一致 | 一致は空。それ以外は種別ごとの `Reason` が個別に返る | F01 | できない |
| L3-U12 | `valid_open` | open が 0 個、1 個、2 個、open だが無効なもの、`closed`、壊れた承認 | 有効な open だけ。壊れたものと無効なものは含まれない | F01 | できない |
| L3-U13 | `spec_tags` | 要件の行(`- **[TAG] 名前**`、`* **[TAG]**`)、本文中の `[TAG]`、フェンスの中の行、形式不正のタグ、重複、`01_req_spec.md` がない、UTF-8 でない | 要件の行の正しいタグだけ。他は拾わない。仕様なしは空集合、デコード失敗は `ParseFailure`(D.c が失敗にする) | F03 | できない |
| L3-U14 | `test_functions`: 抽出 | モジュール直下の `test_a`、`Test*` クラスのメソッド、`Test*` でないクラスの `test_x`、ネストした `test_inner`、`test` で始まらない関数、非同期、**モジュール直下の `if`・`try`・`for`・`while`・`match` の中の `def test_*`**、**同名関数の重複定義** | 直下(`if`・`try`・`with` の本体を含む)とクラス直下の `test*` だけ。ネストした関数は含まない。重複は別の項目(`#2`)になる | F03 | できない |
| L3-U15 | `test_functions`: marker | `@pytest.mark.requirement("T")`、`@requirement("T")`、複数の marker、引数が変数、引数なし、クラスのデコレータ、`pytestmark = pytest.mark.requirement("T")`、**`pytestmark = [pytest.mark.requirement("T"), …]`(リスト・タプル)**、他の marker だけ | リテラルは `tags` に入る。変数・引数なしは `has_marker` だけ真。クラスとモジュールの marker は各関数に加わる。他の marker は無視 | F03 | できない |
| L3-U16 | `test_functions`: 範囲とハッシュ | デコレータ付き(複数行の `parametrize`)、同じ内容のコメントだけの変更、関数内の 1 文字の変更 | ソースの範囲はデコレータの最初の行から `end_lineno`。関数内の変更で `source_sha` が変わる。関数の外のコメントでは変わらない [データ: R7] | F01 | できない |
| L3-U17 | `test_functions`: 失敗 | 構文エラー、非 UTF-8 のバイト列、空ファイル | 前 2 つは `ParseFailure`。空は空のリスト [データ: R7] | F03 | できない |
| L3-U18 | `related_requirements` | `.specs/<REQ>/` の変更、関数の追加、削除、marker の付け替え(A → B)、**クラスのデコレータの付け替え**、**モジュールの `pytestmark` の付け替え**、改名(ファイルを移動)、複数要件の marker を持つファイルで 1 関数だけ変更、構文エラーのテスト、不正な形式のタグを含む関数 | 変更された関数の marker の要件だけ(`base` と `head` の両方の実効のタグ)。クラス・モジュールの付け替えも検出する。変更していない関数の要件は含まない。構文エラーは無視。不正な形式のタグは要件に含めない(`ValueError` で落ちない) | F01 | できない |
| L3-U19 | `display_gate` | ペアの組み合わせ(なし、1 だけ、1 と 2、1〜4 すべて、設計だけ、空ファイル) | 03 §3 のとおり | F06 | できない |

## 4. `checks`

| ID | 対象 | ケース | 期待 | 要件 | 現行 |
|---|---|---|---|---|---|
| L3-U20 | K: 適用条件 | (`src/` 変更の有無)×(`tests/`・`.specs/` の変更の有無)の 4 通り | 両方ありのときだけ検査する。他は空 | F01 | できない |
| L3-U21 | K.a | 有効な承認が 0、1、2 | 1 以外は `K.a` | F01 | できない |
| L3-U22 | K.b | `approval.json`、`01〜05` の承認済み、足した `05_*`、`01_x/extra.md`、改名、`notes.md`、`06_x.md` | 最初の 5 つは `K.b`、最後の 2 つは通る | F01 | できない |
| L3-U23 | K.c | 別要件のテスト関数、別要件の `.specs/`、別要件のテストの削除、同じ要件のテスト | 前 3 つは `K.c`、最後は通る | F01 | できない |
| L3-U24 | K: 改名 | `src/a.py` → `lib/a.py` とテスト変更 | `src/` の変更として扱う(旧パス) | F01 | できない |
| L3-U25 | D: 削除・改名・構文 | `approval.json` の削除、改名、壊れた JSON | `D.delete`、`D.delete`、`D.parse` | F02 | できない |
| L3-U26 | D: `open` | ペアが欠ける(ゲートごと、設計だけ、テスト仕様だけ)、空ファイル、ハッシュ不一致、集合不一致、すべて正常 | 欠けているファイルごとに `D.a`、理由ごとに `D.b`、正常は空 | F02 | できない |
| L3-U27 | D: `closed` | 仕様なし、タグにテストなし(複数)、全タグにテストあり、タグが 0 個の仕様、**構文エラーのテストファイルがあるとき** | 仕様なしは `D.c`、タグごとに `D.c`、全部あれば空。タグ 0 個は空。構文エラーのファイルは照合から外れ、落ちずに他の検査が走る | F02 | できない |
| L3-U28 | D: `withdrawn` | どんな状態でも | 空 | F02 | できない |
| L3-U29 | D.d | 承認ファイルの変更あり + `head` の open が 0、1、2。承認ファイルの変更なし + open が 2 | 変更ありで 2 以上のときだけ `D.d` | F02 | できない |
| L3-U30 | T.a | marker なし、引数が変数(`dynamic` が真)、**リテラルのタグ(`pytestmark`)と変数の marker の併用(`dynamic` で `T.a`)**、形式不正のタグ、正しいタグ、構文エラー、**正しいタグ + 不正なタグが同じ関数にある** | 順に `T.a`(marker なし)、`T.a`(リテラルでない)、`T.a`(形式不正)、通る、`T.a`(ファイル)、`T.a`(形式不正。`ValueError` で落ちない)。理由が区別される | F03 | できない |
| L3-U31 | T.b | 仕様がない要件のタグ、タグが仕様にない、正常 | `T.b`、`T.b`、空 | F03 | できない |
| L3-U32 | T.c | `tests/` の外の `test_*.py`、`tests/` の外の `*_test.py`、`conftest.py` | 最初だけ `T.c` | F03 | できない |
| L3-U33 | `Q.pragma` | 新しい `pragma` 行、既存行の保持、`git add` 前の改名(`deleted` + `added`、同じ行)、追跡された改名、別ファイルへの移動、未追跡の新規ファイルに足す、同じ行を 2 回に増やす、`src/` 外の `.py`、非 UTF-8 | 回数が増えたときだけ `Q.pragma`(超過した分の位置つき)。保持・改名・移動は通る。`src/` 外と非 UTF-8 は無視 | F04 | できない |
| L3-U34 | `human_merge` | 検証機構の各パス、`approval.json`、無関係、重複するパス | 理由を重複なく昇順に | F07 | できない |
| L3-U35 | `run_all` | K と D と T と Q.pragma のすべてが違反 | 4 つの検査の Finding が連結され、`human_merge` が付く。一つの違反が他を止めない | F01 | できない |
| L3-U36 | `run_all`: `RepoError` | `FakeRepo` が `RepoError` を投げる | 捕まえずに伝わる | F01 | できない |

## 5. `adapters`(純粋な部分)

| ID | 対象 | ケース | 期待 | 要件 | 現行 |
|---|---|---|---|---|---|
| L3-U37 | `classify_git` | `git commit -m x`、`git -C . commit`、`git add . && git commit`、`git commit -a`、`git push origin x`、`command git commit`、`env git push`、`(git commit)`、複数行、`git push && git commit`、`git push; git commit`、`echo "git commit"`、`bash -c "git commit"`、`git stash`、`git status`、`git log --oneline`、`github commit`、`legit commit` | commit・push は対応する値(`command`、`env`、サブシェル、複数行、引用符の中を含む)。`git stash`、`git status`、`git log`、`github commit`、`legit commit` は None。`git commit && git push` は `commit` | F05 | できない |
| L3-U38 | `handle`: 書き込み | `src/` 内で承認 0 / 1 / 2、`src/` 外、絶対パス、リポジトリ外、`notebook_path` | `src/` 内で承認が 1 つでなければ通知(拒否しない、終了コード 0)。他は出力なし | F05 | できない |
| L3-U39 | `handle`: commit | 違反あり / なし(`FakeRepo`) | 違反ありは終了コード 2 と標準エラー。なしは 0 | F05 | できない |
| L3-U40 | `handle`: push | 同上 | 同上 | F05 | できない |
| L3-U41 | `handle`: 例外 | `repo_factory` が `RepoError` を投げる、`Exception` を投げる | 拒否系は終了コード 0 と警告。通知系は終了コード 0 で出力なし | F05 | できない |
| L3-U42 | `handle`: 入力の不備 | `payload` に `tool_name` なし、未知のツール、`.specs/` なし(通知系 / 拒否系)、`tool_input` なし、`file_path` なし、型が違う | 未知のツールは何もしない。`.specs/` なしは通知系が何もせず、拒否系が検査を実行 | F05 | できない |
| L3-U43 | `report.format_findings` | 0 件、複数件、`path` が None、`human_merge` あり | 1 行 1 件の形式(`path` が None なら `<rule>: <message>`)。最後に「人間のマージが必要」の行(あるときだけ) | F07 | できない |
| L3-U44 | `report.findings_json` | 0 件、複数件 | JSON として読め、`ok`、`findings`、`human_merge` を持つ | F07 | できない |
| L3-U45 | `report.short_status` / `format_status` | 要件 0、1、2、無効な承認(理由つき)、`src/` を変えてよいか(open が 1 つ / 0 / 2) | 3 行以内(short)。理由が出る | F06 | できない |
| L3-U46 | `render_settings` / `render_gitattributes` | 出力 | `settings` は入れ子形式で `gov hook` を呼ぶ。`.gitattributes` は `.specs/** text eol=lf` を含む | F05 | できない |
| L3-U47 | `FakeRepo`、`GitRepo.changes` のフィールド(added は old=None、modified は同じパス、deleted は new=None) | `list` の昇順、`changes` の追加・変更・削除・指定した改名、`read` の None。モードだけの変更は表現しない | 契約(03 §2)のとおり。実 git との一致は適合テスト(L2-I09) | F01 | できない |
| L3-U48 | `run_check` | `open_repo` が `RepoError` を投げる / 想定外の例外を投げる / 違反あり / 通過、`--json` の有無 | 順に 終了コード 2 と `E.repo` の行、2 と `E.internal`(traceback なし)、1、0。JSON も同じ内容 | F01 | できない |
| L3-U49 | `changed_test_functions` | 新規ファイル、既存ファイルに関数を足す、既存関数の本体の書き換え、marker の付け替え、削除だけ、ファイルの改名だけ、関数の改名、解析失敗 | 順に 真、真、真、真、偽、偽、真、偽 | F01 | できない |
| L3-U50 | `check_d`(完了の遷移) | `base` に有効な `open` があり `closed` にする: 仕様のタグを消す、設計ファイルを書き換える、`05_evidence/` のような番号付きディレクトリの下のファイルを書き換える、変更なし。`base` の承認が失効している。`base` が `withdrawn`。`base` に承認がない / 既に `closed` | 前 4 つ(変更なしを除く 2 つと失効・取り下げ)は `D.c`、残りは仕様のタグにテストがあれば `Finding` なし | F02 | できない |
| L3-U51 | `check_k`(テストだけの PR) | 関数を足す、本体を書き換える、関数の改名: 承認 0 / 1 個、marker が承認の要件 / 外 | 0 個は `K.a`、要件外は `K.c`、それ以外は空 | F01 | できない |
| L3-U52 | `short_status` / `format_status` の「`src/` の変更が可能か」 | `base` は `closed`、`head` は `open` | 「不可」(K と一致) | F06 | できない |

## 6. 追跡表(設計 → テスト)

| 設計(04) | テスト |
|---|---|
| §2.1〜2.3 domain | U01〜U05 |
| §2.4 gates | U06 |
| §2.5 machinery | U07 |
| §3.1 hashing | U08 |
| §3.2 approvals | U09〜U13 |
| §3.3 markers | U14〜U17 |
| §3.4 changes | U18、U49 |
| §3.5 display_gate | U19 |
| §4.1 K | U20〜U24、U51 |
| §4.2 D | U25〜U29、U50 |
| §4.3 T | U30〜U32 |
| §4.4 Q.pragma | U33 |
| §4.5 human_merge | U34 |
| §4.6 run_all | U35、U36 |
| §5.2 report | U43〜U45 |
| §5.3 cli(`render_*`、`run_check`) | U46、U48 |
| §5.4 claude_hook | U37〜U42 |
| §6 FakeRepo | U47 |
| §5.1 GitRepo | 結合テスト L2-I01〜I09(実 git が必要) |
| §5.3 `check`・`status`・`doctor` のコマンド | 結合テスト L2-I25〜I30 |
| §7 例外 | U02、U36、U41 |

**テストがない項目(明示)**: `GitRepo` の `git` 呼び出し(結合テスト)。`doctor` の個々の検査(L2-I30、I43)。メッセージの文面(Q-L3-2)。性能(DEC-014)。

## 承認

| 日付 | 内容 | 承認者 |
|---|---|---|
| 2026-10-27 | 承認(DEC-036) | tsuyama1990 |

## 訂正履歴
(事実の訂正のみ。版の履歴は git。)

| 日付 | 内容 |
|---|---|
| (なし) | |
