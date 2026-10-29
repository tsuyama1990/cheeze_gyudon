# L1 テスト計画(E2E): 運用規則の一本化

対になる設計書: [02_system_design.md](02_system_design.md)(L1 ↔ E2E)。要件: [01_req_spec.md](01_req_spec.md)。
根拠の種類: **[原典]** / **[データ]** / **[推論]**

## 1. 方針
- **E2E(`L1-Exx`)**: 一時ディレクトリに作った実 git リポジトリを入力に、`gov` の入口(CLI の `init`・`doctor`、`hook` の標準入力の JSON)の出力と終了コードを確かめる。内部関数は呼ばない。テストは `tests/e2e/` に置く。
- **手動確認(`L1-Mxx`)**: 利用者の環境(`~/.claude`)と、Claude Code の実機に依存するもの。自動のテストにしない。
- **E2E にしないもの**: `merge-to-main.sh` のメッセージ検査は、リポジトリの外のスクリプトなので版管理されない。`L1-M02` で、実行した記録を残す(既知の穴 [backlog.md](backlog.md) B-06)。

## 2. E2E

| ID | シナリオ | 期待 | 要件 |
|---|---|---|---|
| L1-E01 | 雛形の共通ブロックを読む | R01〜R18 のすべての ID がある。「Claude」「claude」「Anthropic」を含まない。印がある | F01 |
| L1-E02 | AGENT.md も CLAUDE.md もない一時リポジトリで `gov init` | AGENT.md は共通ブロックを含み、CLAUDE.md は AGENT.md を指す 1 行。終了コード 0。もう一度実行しても 0 で何も変わらない | F02 |
| L1-E03 | 共通ブロックを書き換えた AGENT.md で `gov init` | AGENT.md は変わらない。差分が出力される。終了コード 1。固有部分(印の外)だけの違いでは終了コード 0 | F02 |
| L1-E04 | 共通ブロックがない AGENT.md(印がない)で `gov init` | AGENT.md は変わらない。追加すべきブロックが出力される。終了コード 1 | F02 |
| L1-E05 | CLAUDE.md が別の内容で `gov init` | 変わらない。差分が出力される。終了コード 1 | F02 |
| L1-E06 | 共通ブロックが違う AGENT.md、CLAUDE.md なし、で `gov doctor` | 共通ブロックの食い違いと CLAUDE.md の不在の両方が警告に出る | F03 |
| L1-E07 | 一致する AGENT.md と CLAUDE.md で `gov doctor` | 警告に AGENT.md・CLAUDE.md は出ない | F03 |
| L1-E08 | `global-guard`: cwd は main のリポジトリ A、リポジトリ B は作業ブランチ。`git -C B commit` の Bash | 通す(終了コード 0、ASK なし) | F04 |
| L1-E09 | `global-guard`: cwd は作業ブランチのリポジトリ B、リポジトリ A は main。`git -C A commit`、`cd A && git commit` の Bash | 拒否(終了コード 2)。メッセージにブランチ名とリポジトリ | F04 |
| L1-E10 | `global-guard`: main のリポジトリのファイルを Write/Edit。ignore されたファイルを Write | 前者は拒否、後者は通す | F04 |
| L1-E11 | `global-guard`: `git add -A`、`git add .`、`git add --all`、`git add src/a.py` | 前の 3 つは拒否、最後は通す | F04 |
| L1-E12 | `global-guard`: `.specs/REQ-X/approval.json` への Write、`echo … > .specs/REQ-X/approval.json`、`cat .specs/REQ-X/approval.json` | 前の 2 つは ASK、`cat` は通す | F05 |
| L1-E13 | `global-guard`: `git push`、`git -C B push origin x`、`~/.claude/bin/merge-to-main.sh feat/a msg.md` | すべて ASK | F05 |
| L1-E14 | `global-guard`: main にいるリポジトリで `git merge feat/a`、作業ブランチにいるリポジトリで `git merge main` | 前者は拒否(メッセージが merge-to-main.sh を案内)、後者は通す | F05 |
| L1-E15 | `global-turn-start` の後、`global-guard` でリポジトリ B(cwd 以外)を編集、B に未コミット、B の `scripts/gate.sh` は失敗。続けて `global-stop` | `global-stop` は終了コード 2。メッセージにゲートの出力の末尾 | F06 |
| L1-E16 | L1-E15 の状態から、`global-turn-start` を呼び、B には触れずに `global-stop` | 終了コード 0(B は前のターンの WIP なので検査しない) | F06 |
| L1-E17 | `global-stop` を、同じ失敗するリポジトリで 3 回続ける | 3 回目は終了コード 0 で、出力の JSON に「NOT DONE」を含む | F06 |
| L1-E18 | 触れたリポジトリに `scripts/gate.sh` がない、または変更がドキュメントのみ | `global-stop` は終了コード 0 | F06 |
| L1-E19 | 移行後に cheeze_gyudon と matome の AGENT.md に `gov doctor` | どちらも共通ブロックの警告なし | F01、F03 |

## 3. 手動確認

| ID | 内容 | 期待 | 要件 |
|---|---|---|---|
| L1-M01 | Claude Code の実機で、グローバル設定の切り替え後、main のリポジトリで Edit、`git push`、`approval.json` の Write を試す | 順に、拒否、ASK、ASK が実際に出る | F04、F05 |
| L1-M02 | `merge-to-main.sh` を、bonsai の節がないメッセージファイルで実行 | main が変わらず、足りない項目が示される。節をそろえると、マージされる | F07 |
| L1-M03 | `~/.claude/CLAUDE.md` を読む | 共通規則の見出しがなく、AGENT.md を指す行と個人情報だけがある | F08 |
| L1-M04 | `gov` を PATH から外して Claude Code を起動し、Edit と Bash を試す | ツール呼び出しは止まらない。フックのエラー(127)が表示される。保護は効かない(DEC-039) | A2 |
