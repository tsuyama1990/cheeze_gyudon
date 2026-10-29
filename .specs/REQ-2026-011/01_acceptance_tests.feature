# REQ-2026-011 の受け入れテスト。各シナリオの前の行が、対応する機能タグ。
# 詳細な入力と期待値は 02_system_tests.md が正本。ここでは要件ごとに、代表のシナリオを 1〜2 件だけ書く。

Feature: 運用規則は AGENT.md に置かれ、強制は届く場所にある

  # [REQ-2026-011-F01]
  Scenario: 雛形の規則はエージェント非依存の文面で、全規則が ID を持つ
    Given gov の共通規則の雛形
    When 雛形の本文を読む
    Then R01 から R18 のすべての ID がある
    And ツール名(Claude など)は含まれない

  # [REQ-2026-011-F02]
  Scenario: AGENT.md も CLAUDE.md もないリポジトリで init を実行する
    Given AGENT.md と CLAUDE.md がないリポジトリ
    When gov init を実行する
    Then AGENT.md は共通ブロックを含んで作られ、CLAUDE.md は AGENT.md を指す 1 行で作られる

  # [REQ-2026-011-F02]
  Scenario: 共通ブロックが雛形と違うとき、上書きせず差分を出す
    Given 共通ブロックを書き換えた AGENT.md
    When gov init を実行する
    Then AGENT.md は変わらず、差分が出力され、終了コードは 1

  # [REQ-2026-011-F03]
  Scenario: doctor が共通ブロックの食い違いを警告する
    Given 共通ブロックが雛形と違う AGENT.md
    When gov doctor を実行する
    Then AGENT.md の食い違いが警告に出る

  # [REQ-2026-011-F04]
  Scenario: cwd が main でも、git -C で作業ブランチにコミットできる
    Given cwd は main のリポジトリで、別のリポジトリは作業ブランチにある
    When git -C で作業ブランチのリポジトリにコミットする Bash を実行する
    Then フックは通す

  # [REQ-2026-011-F04]
  Scenario: cwd が作業ブランチでも、git -C で main のリポジトリへのコミットは拒否される
    Given cwd は作業ブランチのリポジトリで、別のリポジトリは main にある
    When git -C で main のリポジトリにコミットする Bash を実行する
    Then フックは拒否する

  # [REQ-2026-011-F05]
  Scenario: approval.json の作成は人間の確認を挟む
    Given 任意のリポジトリ
    When approval.json を Write で書こうとする
    Then フックは ASK を返す

  # [REQ-2026-011-F05]
  Scenario: main 上の git merge は拒否され、作業ブランチへの main の取り込みは通る
    Given main にいるリポジトリと、作業ブランチにいるリポジトリ
    When それぞれで git merge を実行しようとする
    Then main では拒否され、作業ブランチでは通る

  # [REQ-2026-011-F06]
  Scenario: そのターンで触った別のリポジトリの未コミットのゲート失敗を Stop が検出する
    Given cwd 以外のリポジトリを編集し、未コミットで、ゲートが失敗する
    When Stop が発火する
    Then Stop は差し戻す

  # [REQ-2026-011-F06]
  Scenario: 前のターンの WIP には巻き込まれない
    Given 前のターンで触った、ゲートが失敗する未コミットのリポジトリがある
    When 新しいターンが始まり、そのリポジトリには触れずに Stop が発火する
    Then Stop は通す

  # [REQ-2026-011-F07]
  Scenario: bonsai の節がないマージメッセージで、マージが中止される
    Given bonsai の節のないメッセージファイル
    When merge-to-main.sh を実行する
    Then main は変わらず、足りない項目が示される

  # [REQ-2026-011-F08]
  Scenario: 全体の CLAUDE.md から共通規則が消え、AGENT.md を指す
    Given 移行後の ~/.claude/CLAUDE.md
    When 内容を読む
    Then 共通規則の見出しはなく、AGENT.md を指す行と個人情報だけがある
