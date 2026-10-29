# L3 テスト計画(単体): 運用規則の一本化

対になる設計書: [04_detail_design.md](04_detail_design.md)(L3 ↔ 単体)。要件: [01_req_spec.md](01_req_spec.md)。テストは `tests/unit/` に置く。

| ID | 対象 | 入力 | 期待 | 要件 |
|---|---|---|---|---|
| L3-U01 | `split_segments` | `echo "a && b"; git commit` / `a \| b` / `a && b \|\| c` / 改行区切り / `echo 'x;y'` | 引用の中の区切りでは分割しない。引用の外の区切りの数 + 1 の区間(1 つ目は 2 区間、`echo 'x;y'` は 1 区間) | F04 |
| L3-U02 | `split_segments` 閉じない引用 | `git commit -m "abc` | 例外を出さず、区間を 1 つ返す | F04 |
| L3-U03 | `parse_git_invocations` | `git commit -m x` | `commit`、`directory` は `None` | F04 |
| L3-U04 | `-C` | `git -C /a commit` / `git -C /a -C b commit` / `git -C rel push` | `directory` は `/a` / `/a/b` / `rel` | F04 |
| L3-U05 | `cd` | `cd A && git commit` / `cd A; cd ../B && git push` / `cd /abs && cd rel && git add -A` | `directory` は `A` / `B` / `/abs/rel` | F04 |
| L3-U06 | 先頭の語 | `env X=1 git push` / `command git push` / `\git push` / `sudo git push` / `X=1 git push` | すべて `push` として 1 件 | F04、F05 |
| L3-U07 | オプションの読み飛ばし | `git -c user.name=x --no-pager log` / `git --git-dir=/g status` / `git -P diff` | `log` / `status` / `diff` | F04 |
| L3-U08 | git でないもの | `echo git commit` / `gitk` / `cat .git/config` / 空文字列 / `git` だけ | 件数 0。`git` だけは件数 0(サブコマンドなし) | F04 |
| L3-U09 | 複数の呼び出し | `git add a && git commit -m x && git push` | `add`、`commit`、`push` の 3 件、出現順 | F04、F05 |
| L3-U10 | `decide_invocation`(表) | `commit` × (main / master / feat/x / `None`)、`add -A`/`--all`/`.`/`a.py`、`merge feat` × main、`merge --abort` × main、`merge main` × feat/x、`push` | `commit` は main・master で deny、feat/x と `None` で allow。`add` は `-A`/`--all`/`.` で deny、`a.py` で allow。`merge feat`×main は deny、`--abort` は allow、`merge main`×feat/x は allow。`push` は ask | F04、F05 |
| L3-U11 | `strongest` | [] / [allow, ask] / [ask, deny, allow] / [allow, allow] | allow / ask / deny / allow | F05 |
| L3-U12 | `APPROVAL_PATH` | `.specs/REQ-1/approval.json` / `a/b/.specs/R/approval.json` / `approval.json` / `.specs/R/approval.json.bak` / `.specs/R/x/approval.json` | 前の 2 つが一致、後ろの 3 つは一致しない | F05 |
| L3-U13 | `decide_command_text` 書き込み系 | `echo {} > .specs/R/approval.json` / `… >> …` / `tee` / `sed -i s/a/b/ …` / `cp x …` / `mv x …` / `python3 -c "…approval.json…"` | すべて ask | F05 |
| L3-U14 | `decide_command_text` 読み取り系 | `cat .specs/R/approval.json` / `grep state …` / `jq . …` / `sha256sum …` / `git diff -- …approval.json` / `cat approval.json 2>&1` / `cat approval.json 2>/dev/null` | すべて allow(ストリームのリダイレクトは除いてから判定) | F05 |
| L3-U15 | `decide_command_text` 実行 | `~/.claude/bin/merge-to-main.sh feat/a m.md` / `bash merge-to-main.sh …` / `echo merge-to-main.sh` | 前の 2 つは ask。3 つ目も ask(語を含むため。誤検知として許容し、テストで固定) | F05 |
| L3-U16 | `decide_write_path` | `.specs/R/approval.json`×main / `.specs/R/approval.json`×feat / `src/a.py`×main / `src/a.py`×feat / `build/x`×main×無視 / `src/a.py`×`None` | deny / ask / deny / allow / allow / allow | F04、F05 |
