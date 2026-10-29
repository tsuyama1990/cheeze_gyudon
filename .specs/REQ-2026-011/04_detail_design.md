# L3 詳細設計: 運用規則の一本化

対になるテスト仕様: [04_unit_tests.md](04_unit_tests.md)(L3 ↔ 単体)。入力: [03_architecture.md](03_architecture.md)。
定数は各モジュールの先頭に `Final` で置く(既存の `claude_hook.py` と同じ流儀)。ロジックの中に数値や文字列を直接書かない。

### 1. `derive/git_commands.py`(純粋)
```python
@dataclass(frozen=True)
class GitInvocation:
    subcommand: str
    args: tuple[str, ...]        # サブコマンドの後の字句
    directory: str | None        # cd と -C を連結したもの。cwd からの相対のまま。なければ None

def split_segments(command: str) -> list[str]
def parse_git_invocations(command: str) -> list[GitInvocation]
```
- 定数: `SEGMENT_SEPARATORS = (";", "&&", "||", "|", "\n")`、`WRAPPER_WORDS = ("env", "command", "sudo")`、`OPTIONS_WITH_VALUE = ("-C", "-c", "--git-dir", "--work-tree", "--namespace")`(`=` 付きの形も読み飛ばす)、`OPTIONS_WITHOUT_VALUE_PREFIX = "-"`。
- `split_segments`: 引用符(`'`、`"`)とバックスラッシュのエスケープの外にある区切りで分割する。引用が閉じていなければ、最後の区間を引用の中として扱い、そのまま返す。
- `parse_git_invocations`: 区間ごとに `shlex.split(posix=True)`。`ValueError` なら、その区間を読み飛ばす。
  1. 区間の先頭から、`WRAPPER_WORDS`、`NAME=value` の形を読み飛ばす(`\git` は `shlex` が `git` にする)。
  2. 先頭が `cd` なら、`current = normpath(join(current, 引数1))`(引数がなければ `~` 相当で変更しない)。次の区間へ。`current` は `None` から始める。`normpath` は `posixpath` を使い、`current` が `None` の相対パスは、そのまま保つ。
  3. 先頭が `git` なら、以降の字句を左から読む。`-C <dir>` は `directory = join(directory or current, dir)`。他の `OPTIONS_WITH_VALUE` は値ごと、`-` で始まるものは単独で読み飛ばす。最初の `-` で始まらない字句がサブコマンド。残りが `args`。
  4. 先頭が `git` 以外(`echo git commit` を含む)なら何も作らない。
- 戻り値は出現順。

## 2. `cli.py` の変更
- `hook`: `click.Choice` の選択肢を `claude_hook.EVENTS + global_hook.EVENTS` にする。`global_hook.EVENTS` のイベントは `global_hook.main(event)`、それ以外は既存の `claude_hook.main(event)`。
- `init`、`doctor` は変えない(DEC-053)。

### 3. `adapters/global_hook.py`
```python
EVENTS: Final = ("global-guard",)
PROTECTED_BRANCHES: Final = ("main", "master")
GIT_TIMEOUT_SECONDS: Final = 5
APPROVAL_PATH: Final = re.compile(r"(?:^|/)\.specs/[^/]+/approval\.json$")
APPROVAL_NAME: Final = "approval.json"
WRITE_TOKENS: Final = re.compile(r"(?:>|\btee\b|\bsed\s+-i\b|\bcp\b|\bmv\b|\bpython3?\b|\bdd\b|\binstall\b)")
REDIRECT_TO_STREAM: Final = re.compile(r"\d*>&\d+|\d*>\s*/dev/null")
MERGE_SCRIPT: Final = "merge-to-main.sh"
```

```python
@dataclass(frozen=True)
class Decision:
    kind: Literal["allow", "ask", "deny"]
    reason: str = ""

def strongest(decisions: Iterable[Decision]) -> Decision          # deny > ask > allow。空なら allow
def decide_invocation(inv: GitInvocation, branch: str | None) -> Decision
def decide_command_text(command: str) -> Decision                  # merge-to-main.sh と approval.json
def decide_write_path(relative_path: str, branch: str | None, ignored: bool) -> Decision
def main(event: str) -> None
```
- `decide_invocation`: `commit` かつ `branch in PROTECTED_BRANCHES` → deny。`add` かつ args に `-A`/`--all`/`.` → deny。`merge` かつ args に `--abort`/`--continue`/`--quit` がなく `branch in PROTECTED_BRANCHES` → deny(理由に `merge-to-main.sh`)。`push` → ask。それ以外は allow。`branch` が `None`(取得失敗、デタッチ)なら、branch に依存する判定は allow。
- `decide_command_text`: `MERGE_SCRIPT` を含む → ask。`APPROVAL_NAME` を含み、`REDIRECT_TO_STREAM` を除いた文字列に `WRITE_TOKENS` が一致 → ask。それ以外は allow。
- `decide_write_path`: 次の判定を集めて `strongest` を返す。`APPROVAL_PATH` に一致 → ask。`ignored` でなく `branch in PROTECTED_BRANCHES` → deny。どれも当たらなければ allow。(`approval.json` を main で書こうとすると deny、作業ブランチなら ask)
- `main(event)`:
  - 標準入力を読み、JSON として解析。失敗、またはオブジェクトでなければ終了コード 0。
  - `global-guard`: 03 §3 のとおり。Edit/Write 系は `file_path`(または `notebook_path`)、Bash は `command`。git の呼び出しの作業ディレクトリは `join(cwd, inv.directory or ".")` を絶対にしたもの。リポジトリは `git -C <dir> rev-parse --show-toplevel`、ブランチは `git -C <repo> branch --show-current`、無視は `git -C <repo> check-ignore -q <path>`(終了コード 0 なら無視)。
  - すべて、例外が出れば何も出さず終了コード 0。出力は `claude_hook.HookOutcome` を再利用する。
- 判定の出力: deny は標準エラーに `f"Blocked: {reason}"`、終了コード 2。ask は 03 §3 の JSON。

## 4. `~/.claude/bin/merge-to-main.sh`(リポジトリの外)
`check_message()` を足し、`[ -z "$(git status --porcelain)" ] …` と `git rev-parse --verify …` の直後(rebase の前)に呼ぶ。
```bash
check_message() {
  local f=$1 missing=()
  grep -Eq 'REQ-[0-9]{4}-[0-9]{3}' "$f"                       || missing+=("要件 ID (REQ-YYYY-NNN)")
  grep -Eiq '^#+[[:space:]]*(証拠|evidence)' "$f"             || missing+=("見出し: 証拠 / Evidence")
  grep -Eiq '^#+[[:space:]]*bonsai' "$f"                      || missing+=("見出し: bonsai")
  grep -Eiq '純増減|net' "$f"                                 || missing+=("語: 純増減 / Net")
  grep -Eiq '削除|removed' "$f"                               || missing+=("語: 削除 / Removed")
  [ ${#missing[@]} -eq 0 ] || die "merge message is missing: ${missing[*]}"
}
```
(`net` と `removed` は大文字小文字を区別しない。)

## 5. `~/.claude/settings.json` の切り替え後(リポジトリの外)
`hooks` の PreToolUse の呼び出しコマンドを `gov hook global-guard`(マッチャー `Bash|Edit|Write|NotebookEdit|MultiEdit`)にする。既存の `if` 条件(`Bash(git *)` など)は外す(判定は gov が行う)。Stop(`stop_gate.sh`)は変えない。
