# L3 詳細設計: 運用規則の一本化

対になるテスト仕様: [04_unit_tests.md](04_unit_tests.md)(L3 ↔ 単体)。入力: [03_architecture.md](03_architecture.md)。
定数は各モジュールの先頭に `Final` で置く(既存の `claude_hook.py` と同じ流儀)。ロジックの中に数値や文字列を直接書かない。

## 1. `derive/git_commands.py`(純粋)
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
  1. 区間の先頭から、`WRAPPER_WORDS`、`NAME=value` の形、先頭が `\` の語(`\git` → `git`)を読み飛ばす。
  2. 先頭が `cd` なら、`current = normpath(join(current, 引数1))`(引数がなければ `~` 相当で変更しない)。次の区間へ。`current` は `None` から始める。`normpath` は `posixpath` を使い、`current` が `None` の相対パスは、そのまま保つ。
  3. 先頭が `git` なら、以降の字句を左から読む。`-C <dir>` は `directory = join(directory or current, dir)`。他の `OPTIONS_WITH_VALUE` は値ごと、`-` で始まるものは単独で読み飛ばす。最初の `-` で始まらない字句がサブコマンド。残りが `args`。
  4. 先頭が `git` 以外(`echo git commit` を含む)なら何も作らない。
- 戻り値は出現順。

## 2. `adapters/agent_docs.py`
```python
RULES_BEGIN: Final = "<!-- gov:rules v1 -->"
RULES_END: Final = "<!-- /gov:rules -->"
TEMPLATE_RESOURCE: Final = "agent_rules.md"          # jtc_gov/templates/
AGENT_MD: Final = Path("AGENT.md")
CLAUDE_MD: Final = Path("CLAUDE.md")

def render_rules_block() -> str
def render_agent_md() -> str
def render_claude_md() -> str
def extract_block(text: str) -> str | None
def block_diff(current: str, label: str) -> str      # 統一差分。同じなら空文字列
```
- `render_rules_block`: `importlib.resources` で本文を読み、`RULES_BEGIN + "\n" + 本文(末尾の改行を 1 つ) + RULES_END + "\n"`。
- `render_agent_md`: `"# Rules for AI agents\n\n" + render_rules_block() + "\n## This repository\n\n"`。
- `render_claude_md`: `"# CLAUDE.md - adapter\n\nThe rules for this repository are in [AGENT.md](AGENT.md). This file holds nothing else.\n"`。
- `extract_block`: `RULES_BEGIN` と `RULES_END` が各 1 回ずつ、開始が終了より前なら、その範囲(両方の印を含み、終了の行末の改行まで)。それ以外は `None`。
- `block_diff`: 雛形のブロックと `extract_block(current)`(`None` なら空文字列)の統一差分。ラベルは `f"{label} (現在)"` と `f"{label} (gov init)"`。
- 本文 `templates/agent_rules.md`: 規則表(`| ID | 規則 | 強制の置き場 |`)。R01〜R18 を昇順で 1 行ずつ。規則の文面は `02_system_design.md` §5 の「規則」の列から写す。ツール名を含まない。

## 3. `cli.py` の変更
- `init`: 既存のループの対象に、`(AGENT_MD, render_agent_md())` と `(CLAUDE_MD, render_claude_md())` を足す。ただし `AGENT.md` が既存のときの比較は、全体ではなく `extract_block` の範囲(`block_diff`)。差分が空でなければ衝突として出力し終了コード 1。印がなくて `extract_block` が `None` のときは、雛形のブロック全体を「追加すべきブロック」として出力し、終了コード 1。
- `doctor`: `CHECKS` に `_agent_docs` を足す。
  ```python
  def _agent_docs(root: Path) -> DoctorItem
  ```
  名前は `"AGENT.md の共通ブロックが雛形と一致し、CLAUDE.md が AGENT.md を指す"`。`ok` = AGENT.md が存在し `extract_block` が雛形のブロックと等しい、かつ CLAUDE.md が存在し `"AGENT.md"` を含む。`detail` = 違うものを `、` でつないだ文(`AGENT.md がない`、`AGENT.md の共通ブロックが違う`、`CLAUDE.md がない`、`CLAUDE.md が AGENT.md を指していない`)。
- `hook`: `click.Choice` の選択肢を `claude_hook.EVENTS + global_hook.EVENTS` にする。`global_hook.EVENTS` のイベントは `global_hook.main(event)`、それ以外は既存の `claude_hook.main(event)`。

## 4. `adapters/global_hook.py`
```python
EVENTS: Final = ("global-guard", "global-stop", "global-turn-start")
PROTECTED_BRANCHES: Final = ("main", "master")
STATE_DIR: Final = Path("~/.claude/state").expanduser()
STATE_SUFFIX: Final = ".repos"
STATE_MAX_AGE_DAYS: Final = 7
GIT_TIMEOUT_SECONDS: Final = 5
GATE_SCRIPT: Final = "scripts/gate.sh"
MAX_BLOCKS: Final = 3
STOP_BUDGET_SECONDS: Final = 280
GATE_TAIL_LINES: Final = 40
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
def sanitize_session(session_id: str) -> str                       # [A-Za-z0-9_-] 以外を _ に
def record_repo(session_id: str, repo: Path, state_dir: Path = STATE_DIR) -> None
def read_repos(session_id: str, state_dir: Path = STATE_DIR) -> list[Path]   # 重複なし、存在するもの、出現順
def reset_turn(session_id: str, state_dir: Path = STATE_DIR, now: float | None = None) -> None
def dirty_paths(porcelain: str) -> list[str]                       # .md で終わる行と " docs/" を含む行を除く
def next_block_count(current: int) -> tuple[int, bool]             # (新しい回数, 打ち切りか)
def main(event: str) -> None
```
- `decide_invocation`: `commit` かつ `branch in PROTECTED_BRANCHES` → deny。`add` かつ args に `-A`/`--all`/`.` → deny。`merge` かつ args に `--abort`/`--continue`/`--quit` がなく `branch in PROTECTED_BRANCHES` → deny(理由に `merge-to-main.sh`)。`push` → ask。それ以外は allow。`branch` が `None`(取得失敗、デタッチ)なら、branch に依存する判定は allow。
- `decide_command_text`: `MERGE_SCRIPT` を含む → ask。`APPROVAL_NAME` を含み、`REDIRECT_TO_STREAM` を除いた文字列に `WRITE_TOKENS` が一致 → ask。それ以外は allow。
- `decide_write_path`: 次の判定を集めて `strongest` を返す。`APPROVAL_PATH` に一致 → ask。`ignored` でなく `branch in PROTECTED_BRANCHES` → deny。どれも当たらなければ allow。(`approval.json` を main で書こうとすると deny、作業ブランチなら ask)
- `record_repo`: `state_dir` を作り(`mkdir(parents=True, exist_ok=True)`)、`<sanitized>.repos` を `os.open(O_WRONLY|O_APPEND|O_CREAT)` で開き、`f"{repo}\n"` を 1 回の `os.write` で書く。`OSError` は無視。
- `reset_turn`: セッションのファイルを空にする(なければ作らない)。`*.repos` のうち、`mtime` が `now - STATE_MAX_AGE_DAYS*86400` より**小さい**ものを消す(ちょうど 7 日は残す)。`OSError` は無視。
- `next_block_count(current)`: `n = current + 1`、`(n, n >= MAX_BLOCKS)`。
- `main(event)`:
  - 標準入力を読み、JSON として解析。失敗、またはオブジェクトでなければ終了コード 0。
  - `global-guard`: 03 §4 のとおり。Edit/Write 系は `file_path`(または `notebook_path`)、Bash は `command`。git の呼び出しの作業ディレクトリは `join(cwd, inv.directory or ".")` を絶対にしたもの。リポジトリは `git -C <dir> rev-parse --show-toplevel`、ブランチは `git -C <repo> branch --show-current`、無視は `git -C <repo> check-ignore -q <path>`(終了コード 0 なら無視)。
  - `global-stop`: 03 §7 のとおり。ゲートは `subprocess.run([gate], cwd=repo, capture_output, text, timeout=残り時間)`。`TimeoutExpired` は打ち切りとして扱う。回数のファイルは `git rev-parse --absolute-git-dir` の下の `claude-stop-blocks-<sanitized session>`。
  - `global-turn-start`: `reset_turn(session_id)`。
  - すべて、例外が出れば何も出さず終了コード 0。出力は `claude_hook.HookOutcome` を再利用する。
- 判定の出力: deny は標準エラーに `f"Blocked: {reason}"`、終了コード 2。ask は 03 §4 の JSON。

## 5. `~/.claude/bin/merge-to-main.sh`(リポジトリの外)
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

## 6. `~/.claude/settings.json` の切り替え後(リポジトリの外)
`hooks` の呼び出しコマンドを `gov hook global-guard`(PreToolUse。マッチャー `Bash|Edit|Write|NotebookEdit|MultiEdit`)、`gov hook global-stop`(Stop。`timeout` は 300 のまま)、`gov hook global-turn-start`(UserPromptSubmit)にする。既存の `if` 条件(`Bash(git *)` など)は外す(判定は gov が行う)。
