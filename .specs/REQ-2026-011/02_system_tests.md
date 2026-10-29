# L1 テスト計画(E2E): 運用規則の一本化

対になる設計書: [02_system_design.md](02_system_design.md)(L1 ↔ E2E)。要件: [01_req_spec.md](01_req_spec.md)。
根拠の種類: **[原典]** / **[データ]** / **[推論]**

## 1. 方針
- **E2E(`L1-Exx`)**: 一時ディレクトリに作った実 git リポジトリを入力に、`gov hook global-guard` の標準入力の JSON を与え、出力と終了コードを確かめる。内部関数は呼ばない。テストは `tests/e2e/` に置く。
- **手動確認(`L1-Mxx`)**: 利用者の環境(`~/.claude`)と、Claude Code の実機に依存するもの。自動のテストにしない。
- **E2E にしないもの**: `merge-to-main.sh` のメッセージ検査は、リポジトリの外のスクリプトなので版管理されない。`L1-M02` で、実行した記録を残す(既知の穴 [backlog.md](backlog.md) B-06)。

## 2. E2E

| ID | シナリオ | 期待 | 要件 |
|---|---|---|---|
| L1-E08 | `global-guard`: cwd は main のリポジトリ A、リポジトリ B は作業ブランチ。`git -C B commit` の Bash | 通す(終了コード 0、ASK なし) | F04 |
| L1-E09 | `global-guard`: cwd は作業ブランチのリポジトリ B、リポジトリ A は main。`git -C A commit`、`cd A && git commit` の Bash | 拒否(終了コード 2)。メッセージにブランチ名とリポジトリ | F04 |
| L1-E10 | `global-guard`: main のリポジトリのファイルを Write/Edit。ignore されたファイルを Write | 前者は拒否、後者は通す | F04 |
| L1-E11 | `global-guard`: `git add -A`、`git add .`、`git add --all`、`git add src/a.py` | 前の 3 つは拒否、最後は通す | F04 |
| L1-E12 | `global-guard`: `.specs/REQ-X/approval.json` への Write、`echo … > .specs/REQ-X/approval.json`、`cat .specs/REQ-X/approval.json` | 前の 2 つは ASK、`cat` は通す | F05 |
| L1-E13 | `global-guard`: `git push`、`git -C B push origin x`、`~/.claude/bin/merge-to-main.sh feat/a msg.md` | すべて ASK | F05 |
| L1-E14 | `global-guard`: main にいるリポジトリで `git merge feat/a`、作業ブランチにいるリポジトリで `git merge main` | 前者は拒否(メッセージが merge-to-main.sh を案内)、後者は通す | F05 |

## 3. 手動確認

| ID | 内容 | 期待 | 要件 |
|---|---|---|---|
| L1-M01 | Claude Code の実機で、グローバル設定の切り替え後、main のリポジトリで Edit、`git push`、`approval.json` の Write を試す | 順に、拒否、ASK、ASK が実際に出る | F04、F05 |
| L1-M02 | `merge-to-main.sh` を、bonsai の節がないメッセージファイルで実行 | main が変わらず、足りない項目が示される。節をそろえると、マージされる | F07 |
| L1-M03 | `~/.claude/CLAUDE.md` を読む | 共通規則の見出しがなく、AGENT.md を指す行と個人情報だけがある | F08 |
| L1-M04 | `gov` を PATH から外して Claude Code を起動し、Edit と Bash を試す | ツール呼び出しは止まらない。フックのエラー(127)が表示される。保護は効かない(DEC-039) | A2 |
| L1-M05 | cheeze_gyudon と matome の AGENT.md を読む | 共通規則表に R01〜R18 が 1 回ずつあり、ツール名を含まない。matome に CLAUDE.md がある | F01 |
