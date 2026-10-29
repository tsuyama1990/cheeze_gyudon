# L2 テスト計画(結合): agy でも global-guard の判定を効かせる

対になる設計書: [03_architecture.md](03_architecture.md)(L2 ↔ 結合)。要件: [01_req_spec.md](01_req_spec.md)。
方針: 一時ディレクトリの実 git リポジトリと `CliRunner` で、`gov hook` の入口を呼ぶ。テストは `tests/integration/` に置く。

| ID | 確認内容 | 期待 | 要件 |
|---|---|---|---|
| L2-I01 | `agy-pre-tool-use`: main のリポジトリで `run_command` の `git -C <相対> commit`、`cd A && git commit` | cwd(`Cwd`)からの相対が解決され、対象リポジトリのブランチで判定(main なら `deny`、作業ブランチなら出力なし) | F01 |
| L2-I02 | `Cwd` がない、`Cwd` が相対、`workspacePaths` だけ | 相対は `workspacePaths[0]` に連結。`Cwd` がなければ `workspacePaths[0]` を使う | F01 |
| L2-I03 | `TargetFile`(絶対・相対・存在しないディレクトリ)と `Path` の書き込み系 5 種 | main では `deny`、無視されるファイルと作業ブランチでは出力なし | F01 |
| L2-I04 | `git push`、`merge-to-main.sh …`、`approval.json` への `write_file`、`echo x > …approval.json` | すべて `decision: ask`(理由あり)、終了コード 0 | F01 |
| L2-I05 | `view_file`、`grep_search`、`list_dir` など、判定の対象外のツール | 出力なし、終了コード 0 | F01 |
| L2-I06 | 標準入力が JSON でない、配列、`toolCall` がない、`workspacePaths` が空、`git` がない環境 | 出力なし、終了コード 0 | F01 |
| L2-I07 | `gov hook` の引数の選択肢 | 既存の 4 つ(`pre-tool-use`、`session-start`、`user-prompt-submit`、`global-guard`)と `agy-pre-tool-use` を受け付け、未知のイベントは拒否する | F01 |
| L2-I08 | 同じ判定の入力(main の `git add -A`、`git merge feat`、作業ブランチの `git push`)を `global-guard` と `agy-pre-tool-use` に与える | 判定の種類(deny / ask / allow)が一致する | F02 |
| L2-I09 | 011 の既存テスト(`global-guard`) | すべて、変更なしで通る | F02 |
| L2-I10 | `machinery` の一覧 | `AGENTS.md` を変更した差分が「人間のマージが必要」に出る | F03 |
