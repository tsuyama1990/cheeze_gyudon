# L2 テスト計画(結合): 運用規則の一本化

対になる設計書: [03_architecture.md](03_architecture.md)(L2 ↔ 結合)。要件: [01_req_spec.md](01_req_spec.md)。
根拠の種類: **[原典]** / **[データ]** / **[推論]**

方針: 一時ディレクトリの実 git リポジトリと、`CliRunner` または標準入力の JSON で、モジュールの組み合わせを確かめる。内部関数ではなく、`global_hook` と `agent_docs` の公開の入口を呼ぶ。`ゲート` は、終了コードだけを返す小さな偽の `scripts/gate.sh` にする。テストは `tests/integration/` に置く。

| ID | 確認内容 | 期待 | 要件 |
|---|---|---|---|
| L2-I01 | `render_agent_md()` と `render_rules_block()` | 共通ブロックは印で囲まれ、`extract_block(render_agent_md())` が `render_rules_block()` と一致する。2 回呼んでも同じ | F01、F02 |
| L2-I02 | 雛形の本文と `02_system_design.md` §5 の規則表 | 両方の ID の集合が一致する(R01〜R18) | F01 |
| L2-I03 | 一時リポジトリで `init`(CliRunner)。AGENT.md と CLAUDE.md がない | 2 つとも作られ、`作成:` が出力され、終了コード 0。2 回目は何も変わらず 0 | F02 |
| L2-I04 | `init`: 共通ブロックを書き換えた AGENT.md | 終了コード 1、差分が出力され、ファイルは変わらない。印の外だけを変えた場合は 0 | F02 |
| L2-I05 | `init`: 印がない AGENT.md、別の内容の CLAUDE.md | どちらも終了コード 1、ファイルは変わらない | F02 |
| L2-I06 | `doctor`: 一致、ブロックの食い違い、CLAUDE.md の不在 | それぞれ OK / NG(AGENT.md)/ NG(CLAUDE.md)。`detail` にどちらかが出る | F03 |
| L2-I07 | `global-guard`(標準入力の JSON): main のリポジトリへの `git commit` の Bash | 終了コード 2。標準エラーにブランチ名とリポジトリ | F04 |
| L2-I08 | `global-guard`: `git -C <相対パス> commit`、`cd <相対> && git commit`、`cd A; cd ../B && git commit` | cwd からの相対が解決され、対象リポジトリのブランチで判定される(main なら deny、作業ブランチなら allow) | F04 |
| L2-I09 | `global-guard`: Edit/Write のパスが相対、存在しないディレクトリ、ignore されたファイル | 相対は cwd で絶対化、存在しない場合は最も近い親で判定、ignore されたファイルは通す | F04 |
| L2-I10 | `global-guard`: `git add -A`/`--all`/`.`/`src/a.py`、`git -C B add -A` | 前の3つと最後は deny、`src/a.py` は allow | F04 |
| L2-I11 | `global-guard`: `git push`、`git -C B push`、`merge-to-main.sh …` | 標準出力の JSON が `permissionDecision: "ask"` で、理由を含み、終了コード 0 | F05 |
| L2-I12 | `global-guard`: Write のパスが `.specs/REQ-X/approval.json`、Bash の `echo x > …approval.json`、`tee`、`sed -i`、`cp`、`mv`、`python -c`、および `cat`、`grep`、`jq .`、`sha256sum`、`git diff` | 書き込み系は ask、読み取り系は allow | F05 |
| L2-I13 | `global-guard`: main で `git merge feat/a`、`git merge --abort`、作業ブランチで `git merge main` | 1 つ目は deny(`merge-to-main.sh` を案内)、残りは allow | F05 |
| L2-I14 | `global-guard`: 複数の git 呼び出しのうち 1 つが deny、他が ask / allow | 全体は deny(最強)。ask と allow の組は ask | F05 |
| L2-I15 | `global-guard`: Edit(リポジトリ B)と `git -C C status` の後の状態ファイル | B と C が 1 行ずつ。同じものを 2 回触っても、読むと 1 つ | F06 |
| L2-I16 | `global-turn-start`: 状態ファイルの初期化と期限切れの削除 | そのセッションのファイルは空。8 日前の `*.repos` は消え、1 日前のものは残る。標準入力が壊れていても期限切れの削除は行う | F06 |
| L2-I17 | `global-stop`: cwd のリポジトリで未コミットあり、ゲートが失敗 | 終了コード 2、ゲートの出力の末尾とリポジトリ名が標準エラーに出る。同じ条件で成功なら 0 | F06 |
| L2-I18 | `global-stop`: 2 つのリポジトリ(B は成功、C は失敗)が状態ファイルにある | 終了コード 2。C だけが出力に出る | F06 |
| L2-I19 | `global-stop`: 失敗を 3 回続ける | 1、2 回目は 2。3 回目は 0 で、標準出力の JSON に `NOT DONE`。その後の回数は 0 から | F06 |
| L2-I20 | `global-stop`: `gate.sh` がない、変更が `.md` と `docs/` のみ、変更なし | 終了コード 0、ゲートは走らない | F06 |
| L2-I21 | `global-stop`: ゲートが予算を超える(`sleep` する偽のゲート。予算を短く設定) | 打ち切られ、終了コード 0 で、標準エラーに打ち切りが出る | F06 |
| L2-I22 | フックの共通: 標準入力が JSON でない、`cwd` が存在しない、`git` がない環境 | 3 つのイベントすべてで、何も出さず終了コード 0 | F04〜F06 |
| L2-I23 | `gov hook` の引数の選択肢 | 既存の 3 つと新しい 3 つを受け付け、未知のイベントは拒否する | F04〜F06 |
