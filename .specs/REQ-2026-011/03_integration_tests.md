# L2 テスト計画(結合): 運用規則の一本化

対になる設計書: [03_architecture.md](03_architecture.md)(L2 ↔ 結合)。要件: [01_req_spec.md](01_req_spec.md)。
根拠の種類: **[原典]** / **[データ]** / **[推論]**

方針: 一時ディレクトリの実 git リポジトリと、標準入力の JSON で、モジュールの組み合わせを確かめる。内部関数ではなく、`global_hook` の公開の入口を呼ぶ。テストは `tests/integration/` に置く。

| ID | 確認内容 | 期待 | 要件 |
|---|---|---|---|
| L2-I07 | `global-guard`(標準入力の JSON): main のリポジトリへの `git commit` の Bash | 終了コード 2。標準エラーにブランチ名とリポジトリ | F04 |
| L2-I08 | `global-guard`: `git -C <相対パス> commit`、`cd <相対> && git commit`、`cd A; cd ../B && git commit` | cwd からの相対が解決され、対象リポジトリのブランチで判定される(main なら deny、作業ブランチなら allow) | F04 |
| L2-I09 | `global-guard`: Edit/Write のパスが相対、存在しないディレクトリ、ignore されたファイル | 相対は cwd で絶対化、存在しない場合は最も近い親で判定、ignore されたファイルは通す | F04 |
| L2-I10 | `global-guard`: `git add -A`/`--all`/`.`/`src/a.py`、`git -C B add -A` | 前の3つと最後は deny、`src/a.py` は allow | F04 |
| L2-I11 | `global-guard`: `git push`、`git -C B push`、`merge-to-main.sh …` | 標準出力の JSON が `permissionDecision: "ask"` で、理由を含み、終了コード 0 | F05 |
| L2-I12 | `global-guard`: Write のパスが `.specs/REQ-X/approval.json`、Bash の `echo x > …approval.json`、`tee`、`sed -i`、`cp`、`mv`、`python -c`、および `cat`、`grep`、`jq .`、`sha256sum`、`git diff` | 書き込み系は ask、読み取り系は allow | F05 |
| L2-I13 | `global-guard`: main で `git merge feat/a`、`git merge --abort`、作業ブランチで `git merge main` | 1 つ目は deny(`merge-to-main.sh` を案内)、残りは allow | F05 |
| L2-I14 | `global-guard`: 複数の git 呼び出しのうち 1 つが deny、他が ask / allow | 全体は deny(最強)。ask と allow の組は ask | F05 |
| L2-I15 | フックの共通: 標準入力が JSON でない、`cwd` が存在しない、`git` がない環境 | 何も出さず終了コード 0 | F04、F05 |
| L2-I16 | `gov hook` の引数の選択肢 | 既存の 3 つと `global-guard` を受け付け、未知のイベントは拒否する | F04、F05 |
