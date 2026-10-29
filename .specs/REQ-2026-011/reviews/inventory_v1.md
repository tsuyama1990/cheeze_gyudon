# 関所の棚卸し(v1)

対象: `~/.claude/CLAUDE.md`(全体)、`cheeze_gyudon/AGENT.md`、`matome/AGENT.md`(gov init が生成する雛形)。
根拠の種類: [原典]=規則の文面 / [データ]=本セッションで観測 / [推論]=未検証の判断。
実現手段: H=Claude Code フック(PreToolUse/Stop 等、`~/.claude`)、G=ゲート(`scripts/gate.sh`/`gov check`)、P=git の pre-commit(人間にもエージェントにも効く)、ASK=フックが permissionDecision "ask" を返し人間の承認を挟む。

## 共通の構造の穴(規則ではなく仕組み)
| ID | 穴 | 根拠 | 対策 |
|---|---|---|---|
| X1 | フックが「セッションの cwd のリポジトリ」しか見ない。`git -C <dir>` や他レポのパスでの編集は判定対象外 | [データ] branch_guard が cwd(main)を見て matome へのコミットを誤ブロック。stop_gate も cwd のレポだけ | H: 対象レポをコマンド/パスから解決する共通関数 `resolve_repo` を全フックで使う |
| X2 | 対象レポ側のフック(matome の gov フック)はセッションの cwd がそこでないと読まれない | [データ] 会話冒頭の jtc-gov 表示は cheeze_gyudon のもの | 対象レポの規則は X1 の全体フックから `gov check` を呼んで効かせる(matome に新しいフックは足さない) |
| X3 | Stop の検査は「未コミットの変更」だけ。こまめにコミットすると素通り | [原典] stop_gate.sh の条件 [データ] 今回は素通り | H(Stop): main より進んだブランチも検査対象にする |

## A. AGENT.md
| ID | 規則 | 機械判定 | 現状 | 提案 |
|---|---|---|---|---|
| A1 | 設計が承認されるまで src 変更を main に入れない(cheeze_gyudon 1) / 承認済み設計が要る(matome 1) | 可 | gov K(対象レポの gov フックが cwd のとき)。cheeze_gyudon の AGENT.md は「ツールはまだ止めない」と書くが REQ-2026-010 の導入後は陳腐化の疑い [推論] | H(X1/X2): src を編集する前に対象レポで `gov check` 相当を実行。AGENT.md の古い記述は直す |
| A2 | 設計とテスト仕様をセットで `.specs/<REQ>/` に | 可 | gov K | A1 に含む |
| A3 | 書く前に PyPI/OSS を検索 | 不可(判断) | なし | 機械化しない。src に新規ファイルを作る時にリマインダー文を返す H(情報のみ)か、規則から外す |
| A4 | テストを弱めない | 部分的 | gov T(印)のみ | H: tests/ の Edit で assert/期待値の行が減る・変わる場合は ASK。G: 差分で削除された assert 数を報告 |
| A5 | 品質の限界値は pyproject。`scripts/gate.sh` を実行 | 可 | stop_gate(未コミットのみ) | X3 を実装。P: コミット前にゲートの軽量版 |
| A6 | 依存の向きを守る | 可 | なし(設計書 §3 にあるだけ) | G: import-linter か構造テストをゲートに追加 |
| A7 | 同じ情報を2か所に書かない | 不可 | なし | 機械化しない(数値の二重書きだけ G の grep で拾う案) |
| A8 | 承認ファイルは人間が作る(matome 1) | 可 | なし。[データ] 本セッションで私が `approval.json` を作成できた | H: `.specs/*/approval.json` への Write/Edit/Bash を ASK(人間の承認を挟む) |
| A9 | 全テストに requirement マーカー、タグが req_spec にある(matome 2) | 可 | gov T | 維持 |
| A10 | 完了前に gate.sh(matome 3) | 可 | A5 と同じ | A5 に含む |

## B. 全体 CLAUDE.md
| ID | 規則 | 機械判定 | 現状 | 提案 |
|---|---|---|---|---|
| B1 | main 上の編集・コミット禁止 | 可 | branch_guard(cwd 基準) | X1 で対象レポ基準に。`git -C`/`cd x && git commit` を解釈 |
| B2 | 着手前に `<type>/<topic>` ブランチ+完了基準を書く | 部分的 | ブランチ名は branch_guard が間接的に | H: ブランチ名の形式を検査。完了基準は gov のレポでは設計書がそれ。他のレポ用の置き場を決めてから(要設計) |
| B3 | 小さくコミット、各コミットでゲート通過 | 可 | なし | P: pre-commit に軽量ゲート。重いものは push/merge の関所へ |
| B4 | `git add -A`/`.` 禁止 | 可 | block_git_add_all | 維持(X1 で `git -C` も) |
| B5 | バックグラウンド処理の書き込み中はコミットしない | 不可に近い | なし | 機械化しない |
| B6 | 衝突は main でなくブランチ側で解消 | 可 | merge-to-main.sh | 維持 |
| B7 | マージは merge-to-main.sh を使う | 可 | なし(直接 `git merge` は止まらない) | H: main への `git merge`/`git push origin main` を直接実行したら deny し、スクリプトを案内 |
| B8 | 結果が変わる変更はマージ前にユーザー承認 | 判定は不可、承認取得は可 | なし | ASK: merge-to-main.sh の実行は常に人間の承認を挟む(挙動不変かの判断は人間がする) |
| B9 | push はユーザー指示があるときだけ | 可 | なし | ASK: `git push` は常に人間の承認を挟む |
| B10 | 委譲エージェントは別 worktree・別ブランチ | 部分的 | なし | H: Agent ツールの書き込み系呼び出しに isolation が無ければ ASK。`agy-cli --dangerously-skip-permissions` の `--add-dir` が main のチェックアウトなら ASK |
| B11 | 委譲中の指示書のファイルは main 側で編集しない | 部分的 | なし | 要設計(ロックファイル)。初期は対象外 |
| B12 | 同じ関門で3回失敗したら止める | 可 | stop_gate | 維持 |
| B13 | 報告は「受け入れ待ち/マージ済み」+純増減行数+削除したもの | 部分的 | なし | H(Stop): main より進んだブランチがあり、最後の応答に「純増減」「削除」「受け入れ待ち/マージ済み」がなければ差し戻す |
| B14 | 大きな変更後・ブランチごとに bonsai | 可(印で) | なし | H: `git push`/merge-to-main.sh の前に、HEAD に対する bonsai の完了印(純増減・削除内容つき)を要求 |
| B15 | YAGNI/抽象化は2例目から/旧コードを消す/コメントは非自明のみ | 一部のみ | ruff/mypy | G: 未使用コード検出(vulture)、docstring の ruff 規則。残りは機械化しない |
| B16 | 調整値・パスは config、マジックナンバー禁止 | 可 | なし(ruff 未設定の疑い [推論]) | G: ruff の PLR2004 等 |
| B17 | 数値はコミット直前に再計算、根拠ラベル、訂正履歴(設計・判断資料) | 部分的 | なし | G: `.specs/**/0*.md` に根拠ラベルのない数値主張が多いと警告、承認後に変更した設計書に訂正履歴がなければ失敗 |
| B18 | 設計書の主張と実装の一致 | 部分的 | gov は承認後の書き換えだけ検出 | G: 設計書のバッククォート内の識別子が src に存在するか(名前の一致まで) |
| B19 | V字: 設計→テスト→コードの順 | 可 | なし | G: ブランチの履歴で、src を変えた最初のコミットより前に、tests または .specs を変えたコミットがあること |
| B20 | テストは tests/e2e|integration|unit、`--strict-markers`、設計追跡表の抜け・設計のないモジュールを落とす | 可 | gov(レポごと) | 維持 |
| B21 | 完了基準に「想定する純増減」を書く | 可 | なし | B2 と同じ置き場に欄を設け、無ければ B13/B14 で警告 |

## 機械化しない(人間とモデルの判断として残す)
A3, A7, B5, B11(当面), B15 の大半。理由: 判定に意味の理解が要り、機械判定は誤検知が多い [推論]。
