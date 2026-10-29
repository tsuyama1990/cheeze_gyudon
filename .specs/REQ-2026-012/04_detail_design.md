# L3 詳細設計: agy でも global-guard の判定を効かせる

対になるテスト仕様: [04_unit_tests.md](04_unit_tests.md)(L3 ↔ 単体)。入力: [03_architecture.md](03_architecture.md)。
定数は各モジュールの先頭に `Final` で置く(既存の流儀)。ロジックの中に文字列を直接書かない。

### 1. `adapters/agy_hook.py`
```python
EVENTS: Final = ("agy-pre-tool-use",)
COMMAND_TOOL: Final = "run_command"
PATH_KEYS: Final = {
    "write_to_file": "TargetFile",
    "replace_file_content": "TargetFile",
    "multi_replace_file_content": "TargetFile",
    "write_file": "Path",
    "edit_file": "Path",
}

def to_call(payload: dict[str, object]) -> ToolCall | None
def to_outcome(decision: Decision) -> HookOutcome
def main(event: str) -> NoReturn
```
- `to_call`:
  1. `toolCall` が辞書でなければ `None`。`name` が文字列でなければ `None`。`args` が辞書でなければ `None`。
  2. `workspacePaths` が、空でない文字列の配列でなければ `None`。`base = workspacePaths[0]`。
  3. `name == COMMAND_TOOL`: `args["CommandLine"]` が文字列でなければ `None`。`cwd = join(base, args["Cwd"])`(`Cwd` が文字列のときだけ。`posixpath.join` は絶対パスならそのまま採る)。`ToolCall(cwd, command=CommandLine, path=None)`。
  4. `name in PATH_KEYS`: `args[PATH_KEYS[name]]` が文字列でなければ `None`。`ToolCall(base, command=None, path=その値)`。
  5. それ以外は `None`。
- `to_outcome`: `deny` → `HookOutcome(0, stdout=json.dumps({"decision": "deny", "reason": …}, ensure_ascii=False))`。`ask` も同様。`allow` → `HookOutcome(0)`。
- `main(event)`: 標準入力を JSON として読み、辞書でなければ終了コード 0(何も出さない)。`to_call` が `None` なら何も出さず 0。それ以外は `global_hook.decide_call` の結果を `to_outcome` で出力する。例外は握りつぶして何も出さず 0(DEC-002)。標準出力・標準エラーへの書き出しと `SystemExit` は `global_hook.main` と同じ形(共通の出力関数 `emit(outcome)` を `global_hook` から使う)。

### 2. `adapters/global_hook.py` の変更
```python
@dataclass(frozen=True)
class ToolCall:
    cwd: str
    command: str | None
    path: str | None

def decide_call(call: ToolCall) -> Decision
def claude_call(payload: dict[str, object]) -> ToolCall | None
def emit(outcome: HookOutcome) -> NoReturn
```
- `decide_call`: `call.path` があれば `_guard_write(Path(call.cwd), call.path)`、`call.command` があれば `_guard_bash(Path(call.cwd), call.command)`、どちらもなければ `ALLOW`。
- `claude_call`: 011 の `guard` の入力部分。`cwd` と `tool_input` が条件を満たさなければ `None`。`WRITE_TOOLS` なら `path`、`Bash` なら `command`。
- `guard(payload)`: `claude_call` → `decide_call` → 011 の出力の形。結果は変えない。
- `emit`: 011 の `main` の末尾(標準出力・標準エラーへの書き出しと `SystemExit`)。

### 3. `adapters/cli.py` の変更
- `hook`: `click.Choice` を `claude_hook.EVENTS + global_hook.EVENTS + agy_hook.EVENTS` にする。ディスパッチは `event in agy_hook.EVENTS` → `agy_hook.main`、`event in global_hook.EVENTS` → `global_hook.main`、それ以外 → `claude_hook.main`。

### 4. `domain/machinery.py` の変更
- 一覧の `"AGENT.md"` の隣に `"AGENTS.md"` を足す。

### 5. リポジトリの外
- `~/.gemini/config/hooks.json`: 03 §5 の内容。
- `AGENTS.md`(cheeze_gyudon と matome のリポジトリ直下): `# AGENTS.md - adapter\n\nThe rules for this repository are in [AGENT.md](AGENT.md). This file holds nothing else.\n`。
