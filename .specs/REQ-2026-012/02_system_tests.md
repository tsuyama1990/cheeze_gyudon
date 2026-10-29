# L1 テスト計画(E2E): agy でも global-guard の判定を効かせる

対になる設計書: [02_system_design.md](02_system_design.md)(L1 ↔ E2E)。要件: [01_req_spec.md](01_req_spec.md)。

## 1. 方針
- **E2E(`L1-Exx`)**: 一時ディレクトリの実 git リポジトリを入力に、`gov hook agy-pre-tool-use` の標準入力の JSON を与え、出力と終了コードを確かめる。テストは `tests/e2e/` に置く。
- **手動確認(`L1-Mxx`)**: agy の実機に依存するもの。結果を `decisions.md` に追記する。

## 2. E2E

| ID | シナリオ | 期待 | 要件 |
|---|---|---|---|
| L1-E01 | main のリポジトリで、`run_command` の `git commit -m x` | 標準出力の JSON が `decision: deny`、理由にブランチ名。終了コード 0 | F01 |
| L1-E02 | 作業ブランチのリポジトリで、`run_command` の `git push` | `decision: ask`、理由あり | F01 |
| L1-E03 | `write_to_file` の `TargetFile` が `.specs/REQ-X/approval.json` | `decision: ask` | F01 |
| L1-E04 | 作業ブランチで `run_command` の `git status`、およびファイル書き込み | 標準出力は空、終了コード 0 | F01 |
| L1-E05 | main のリポジトリで `git add -A` を Claude 用(`global-guard`)と agy 用に送る | どちらも拒否(Claude は終了コード 2、agy は `deny`) | F02 |

## 3. 手動確認

| ID | 内容 | 期待 | 要件 |
|---|---|---|---|
| L1-M01 | `~/.gemini/config/hooks.json` を置き、agy が main のリポジトリで `git commit` を試みる | 止まる。止まらなければ、読まれていない(A2 が不成立) | F04 |
| L1-M02 | 許可の操作(`git status`)で、フックが何も出力する/しないときの agy の挙動 | 通常どおり実行され、フックの失敗として扱われない | F01、N2 |
| L1-M03 | `--dangerously-skip-permissions` 付きで L1-M01 と同じ操作 | フックが走るか(止まるか)を記録する | N5 |
| L1-M04 | cheeze_gyudon と matome の `AGENTS.md` を読み、agy が規則を認識しているか質問する | 規則表の R03 を答えられる | F03 |
