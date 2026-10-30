# REQ-2026-012 の受け入れテスト。各シナリオの前の行が、対応する機能タグ。
# 詳細な入力と期待値は 02_system_tests.md が正本。

Feature: agy でも global-guard と同じ判定が効く

  # [REQ-2026-012-F01]
  Scenario: agy の run_command による main へのコミットは拒否される
    Given main にいるリポジトリ
    When agy の PreToolUse が git commit の run_command を送る
    Then フックは decision deny を返す

  # [REQ-2026-012-F01]
  Scenario: agy の run_command による push は確認を求める
    Given 作業ブランチにいるリポジトリ
    When agy の PreToolUse が git push の run_command を送る
    Then フックは decision ask を返す

  # [REQ-2026-012-F01]
  Scenario: agy のファイル書き込みでも approval.json は確認を求める
    Given 任意のリポジトリ
    When agy の PreToolUse が approval.json への write_to_file を送る
    Then フックは decision ask を返す

  # [REQ-2026-012-F01]
  Scenario: 許可される操作では何も出力しない
    Given 作業ブランチにいるリポジトリ
    When agy の PreToolUse が git status の run_command を送る
    Then 標準出力は空で、終了コードは 0

  # [REQ-2026-012-F02]
  Scenario: Claude 用と agy 用で同じ入力は同じ判定になる
    Given main にいるリポジトリ
    When Claude 用と agy 用の両方に、同じ git add -A を送る
    Then どちらも拒否される

  # [REQ-2026-012-F03]
  Scenario: AGENTS.md は AGENT.md を指す
    Given cheeze_gyudon と matome のリポジトリ直下
    When AGENTS.md を読む
    Then AGENT.md を指す 1 行がある

  # [REQ-2026-012-F04]
  Scenario: グローバルのフック設定が agy のツール呼び出しを止める
    Given 設定済みの ~/.gemini/config/hooks.json
    When agy が main のリポジトリで git commit を試みる
    Then agy は実行を止める
