# L3 クラス設計(関数とデータ構造)

状態: **草案(スパイラル 3)。** 対になるテスト仕様: [04_unit_tests.md](04_unit_tests.md)(L3 ↔ 単体)。入力: [03_architecture.md](03_architecture.md)(契約とアルゴリズム)、[02_system_design.md](02_system_design.md)(規則)、[01_req_spec.md](01_req_spec.md)(F01〜F09)。決定は [decisions.md](decisions.md)、進行は [spirals.md](spirals.md)。ここには複製しない。
根拠の種類: **[原典]** / **[データ]**(実測。2026-10-27 の spike) / **[推論]** / **[決定]**(DEC-ID)

L3 が決めるのは、モジュールごとの公開 API(シグネチャ)、データ構造、非自明なアルゴリズムの手順、例外。L2 の表と同じ内容は繰り返さず、節番号で参照する。

---

## 1. 方針

- Python 3.11 以上。型注釈は完全(mypy strict)。 [原典: `pyproject.toml`]
- データは、`frozen` なデータクラスを基本にする。**Pydantic を使うのは、外部の JSON を読む `Approval` だけ**(JSON スキーマの生成が要るため。DEC-003、DEC-028)。他の型は標準のデータクラス(YAGNI)。
- 検査と導出は**関数**(クラスにしない)。クラスは、状態を持つ `GitRepo` と、テスト用の `FakeRepo` だけ。
- 純粋層(`domain`、`derive`、`checks`)は、`os`、`pathlib`、`subprocess`、`datetime`、`sys` などを import しない。入出力は `Repo` を通す。 [03 §2、I2]
- 設定値(閾値)は、コードに書かない。`pyproject.toml` が正本で、読むのは `gate.sh` だけ(03 §5)。
- 速度の最適化はしない。 [決定: DEC-014]

## 2. `domain`

### 2.1 `domain/errors.py`
```python
class RepoError(Exception):
    """git の読み取りに失敗した(base がない、git が失敗した)。"""
```
`ParseFailure` は例外ではなく値(2.2)。

### 2.2 `domain/models.py`
```python
Ref = Literal["base", "head"]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

@dataclass(frozen=True)
class Change:
    old_path: str | None
    new_path: str | None
    status: Literal["added", "modified", "deleted", "renamed"]
    def __post_init__(self) -> None: ...   # 03 §1 の不変条件を検査し、破れていれば ValueError
    def paths(self) -> tuple[str, ...]: ...  # None でないものを(旧, 新)の順に返す

class ApprovalState(StrEnum): OPEN = "open"; CLOSED = "closed"; WITHDRAWN = "withdrawn"

class Approval(BaseModel):                  # frozen、extra="forbid"、strict
    requirement: RequirementId
    state: ApprovalState
    files: dict[str, Sha256]                # キーは r"^0[1-5]_[^/]+$"(直下のファイル名のみ)。dict のキーは型注釈では検証されないので、`@field_validator("files")` で全キーを検査する

@dataclass(frozen=True)
class ParseFailure: reason: str

@dataclass(frozen=True)
class Finding:
    rule: str; path: str | None; message: str; hint: str | None = None

@dataclass(frozen=True)
class CheckResult:
    findings: tuple[Finding, ...]
    human_merge: tuple[str, ...]
    @property
    def ok(self) -> bool: return not self.findings
```

### 2.2b `domain/repo.py`
`Repo` Protocol(03 §2 の契約)をここに 1 回だけ定義する。`derive`・`checks`・`adapters` はここから import する。`adapters` に定義しない(逆依存を避ける)。 [レビュー R2-01]

### 2.3 `domain/ids.py`
```python
REQUIREMENT_ID = re.compile(r"^REQ-\d{4}-\d{3,}$")
FEATURE_TAG = re.compile(r"^REQ-\d{4}-\d{3,}-F\d{2,}$")
RequirementId = Annotated[str, StringConstraints(pattern=REQUIREMENT_ID.pattern)]
def requirement_of(tag: str) -> str: ...   # FEATURE_TAG に一致しなければ ValueError。"-F" の手前を返す
```

### 2.4 `domain/gates.py`
```python
@dataclass(frozen=True)
class Deliverable: gate: int; design: str; test_spec: str    # ファイル名(.specs/<REQ>/ 直下)
DELIVERABLES: Final[tuple[Deliverable, ...]]                 # 03 §1.1 の表(ゲート 1〜4)
APPROVAL_FILE: Final = "approval.json"
APPROVED_FILE_PATTERN: Final = re.compile(r"^0[1-5]_[^/]+$")  # 直下のファイル名
GUARDED_PREFIX: Final = re.compile(r"^0[1-5]_")               # K.b: ディレクトリ配下も塞ぐ(03 §4.1)
```
実装後は、この定数がゲートごとの成果物の正本(03 §1.1 は参照に置き換える)。

### 2.5 `domain/machinery.py`
```python
MACHINERY: Final[tuple[tuple[str, re.Pattern[str]], ...]]    # (表示名, パターン)。正本の内容は 02 §4.4
def machinery_reason(path: str) -> str | None: ...           # 当たった表示名、なければ None
```
パターンは、`fnmatch` ではなく正規表現に変換して保持する(`**` を `.*`、`*` を `[^/]*` に。正規表現のメタ文字はエスケープする。パターン `**/name` は、ルート直下も含めるため `(?:.*/)?name` にする)。 [レビュー R2-10] [推論: `fnmatch` の `*` は `/` を越えるため、意図と違う]

## 3. `derive`

### 3.1 `derive/hashing.py`
`def sha256_hex(data: bytes) -> str`(`hashlib.sha256`)。`hashlib` の import は純粋層で許す(I/O ではない)。

### 3.2 `derive/approvals.py`
```python
@dataclass(frozen=True)
class Reason: kind: Literal["state","set","hash","parse"]; detail: str

def parse_approval(raw: bytes, dir_name: str) -> Approval | ParseFailure
def load_approvals(repo: Repo, ref: Ref) -> dict[str, Approval | ParseFailure]   # キーは要件 ID(ディレクトリ名)
def validity(repo: Repo, ref: Ref, approval: Approval) -> list[Reason]            # 空なら有効
def valid_open(repo: Repo, ref: Ref) -> list[Approval]
def spec_tags(repo: Repo, ref: Ref, req: str) -> set[str] | ParseFailure
```
- `parse_approval`: `json.loads(raw, object_pairs_hook=…)`(**同じキーが重複していれば `ParseFailure`**。`json.loads` は重複を黙って最後の値にするため)(`UnicodeDecodeError` を含む解析の例外は、すべて `ParseFailure`)→ `Approval.model_validate`(例外は `ParseFailure`)→ `approval.requirement == dir_name` を確認。
- `load_approvals`: `repo.list(ref)` を走査し、`^\.specs/(REQ-\d{4}-\d{3,})/approval\.json$` に当たるものだけを読む。
- `validity`: ①`state != OPEN` なら `Reason("state")` ②`files` のキー集合と、`list(ref)` のうち `.specs/<REQ>/` 直下で `APPROVED_FILE_PATTERN` に当たるファイル名の集合を比べ、差があれば `Reason("set")`(足りない、余分、をそれぞれ) ③各ファイルの `sha256_hex(read(...))` を比べ、違えば `Reason("hash")`(ファイルごと。ファイルが読めなければ同じ種別)。
- `spec_tags`: `01_req_spec.md` を `utf-8` でデコード(失敗は `ParseFailure`。空集合にして通さない。ファイルがなければ空集合)。行を走査し、行頭が `- **[`TAG`]` の形で、フェンス(```` ``` ````)の外にあるものから `FEATURE_TAG` に当たるタグを集める。正規表現: `^\s*[-*]\s+\*\*\[(REQ-\d{4}-\d{3,}-F\d{2,})\]`。

### 3.3 `derive/markers.py`
```python
@dataclass(frozen=True)
class TestFunction:
    qualname: str                  # "test_a" または "TestK.test_m"
    tags: tuple[str, ...]          # requirement marker の引数(リテラルのみ)。なければ空
    has_marker: bool               # requirement marker が(引数がリテラルでないものを含めて)1 つでもあるか
    source_sha: str                # デコレータの最初の行から end_lineno までのソースの SHA-256
    lineno: int

def test_functions(source: bytes) -> list[TestFunction] | ParseFailure
```
手順: [データ: R7]
1. `ast.parse(source)`。`SyntaxError` は `ParseFailure`。ソースは `splitlines` した行を保持する。
2. モジュール直下の文を走査する。`ast.walk` は使わない(ネストした関数を拾うため)。ただし、直下の `if`・`try`・`with`・`for`・`while`・`match` の**本体の中の文**には降りる(pytest は実行後の名前空間から集めるので、`if` の中の `def test_*` も収集される)。関数とクラスの中には降りない。`pytestmark = …` の代入があれば、値が `requirement` の呼び出し、またはそのリスト・タプルのとき、モジュール共通のタグとして集める。 [推論: pytest の収集との整合。レビュー指摘 I-01、L-03]
3. 直下の `FunctionDef`/`AsyncFunctionDef` で名前が `test` で始まるもの、と、名前が `Test` で始まる `ClassDef` の直下の同様のメソッドを `TestFunction` にする。クラスのデコレータの marker は、そのメソッドに加える。**同じ名前の関数が複数あれば、すべてを別の項目にする**(2 つ目以降の `qualname` に `#2`、`#3` を付ける)。pytest は最後の定義だけを実行するが、検査は全部に対して行う(厳しい側)。
4. デコレータからタグを取る: `ast.Call` で、`func` が `Attribute(attr="requirement")`(`pytest.mark.requirement`)または `Name("requirement")` のもの。第 1 引数が `ast.Constant` の `str` ならタグ、そうでなければ `has_marker` だけを真にする。
5. 範囲: `min(デコレータの lineno, def の lineno)` から `end_lineno` までの行を連結して SHA-256。`tags` は、関数自身、クラス、モジュールの marker を合わせた**実効のタグ**。

### 3.4 `derive/changes.py`
```python
def related_requirements(repo: Repo, changes: Sequence[Change]) -> set[str]
```
1. `changes` の各パスが `^\.specs/(REQ-\d{4}-\d{3,})/` に当たれば、その要件 ID を加える。
2. `tests/` 配下の `test_*.py` に当たる Change について、`old_path` を `base` で、`new_path` を `head` で読み、`test_functions` を取る(解析失敗は無視)。
3. 関数を `qualname` で突き合わせ、「片方にしかない」「`source_sha` が違う」「**実効の `tags` が違う**」のいずれかに当たる関数を変更とみなし、`base` と `head` の両方の `tags` を、`FEATURE_TAG` に一致するものだけ `requirement_of` で要件 ID にして加える。クラスのデコレータやモジュールの `pytestmark` の付け替えは、関数のソースを変えないが、実効の `tags` を変えるので検出される。改名は、旧パスと新パスの関数を `qualname` で突き合わせる。 [レビュー指摘 F-01]

### 3.5 `derive/gates.py`
`def display_gate(repo: Repo, ref: Ref, req: str) -> int`: `DELIVERABLES` を順に見て、設計とテスト仕様の**どちらかが**存在しない、または空のゲートの番号を返す。すべてそろっていれば 5。

---

## 4. `checks`

すべて `def check_x(repo: Repo, changes: Sequence[Change]) -> list[Finding]` の形(`changes` は 1 回だけ取得して共有)。

### 4.1 `checks/k.py`
03 §4.1 の擬似コードのとおり。補助関数:
```python
def _touches(changes, prefix: str) -> bool        # old/new どちらかのパスが prefix で始まる
def _guarded(path: str, req: str) -> bool          # approval.json か、.specs/<req>/ 以下で GUARDED_PREFIX に当たる先頭成分
```
`Finding` の `rule` は `K.a`/`K.b`/`K.c`。`K.c` の `message` に要件 ID、`hint` に「承認された要件は <req>」。

### 4.2 `checks/d.py`
`approval.json` に当たる Change を列挙し、03 §4.2 の表を実装する。
- 削除、または `old_path` が `approval.json` の改名 → `D.delete`。
- `head` で `parse_approval` が `ParseFailure` → `D.parse`。
- `open`: `DELIVERABLES` の各ゲートについて、`design` と `test_spec` が存在し空でないか → `D.a`(ファイルごと)。`validity(repo, "head", approval)` の `set` と `hash` の理由 → `D.b`(理由ごと)。
- `closed`: `01_req_spec.md` がなければ `D.c`(仕様なし)。`spec_tags(head)` の各タグが、`head` の `tests/**/test_*.py` の `test_functions` のどれかの `tags` に含まれなければ `D.c`(タグごと)。`spec_tags` が `ParseFailure` なら `D.c`(仕様が読めない)。`test_functions` が `ParseFailure` のファイルは、この照合から外す(`T.a` が失敗にする)。 [レビュー指摘 I-02]
- 最後に、1 つでも承認ファイルの Change があれば、`head` の全 `approval.json` の状態が `open` の数を数え、2 以上なら `D.d`。

### 4.3 `checks/t.py`
`head` の `list` から、`tests/` 配下でない `test_*.py` を `T.c`、`tests/` 配下の `test_*.py` を読み、`test_functions` を取る。`ParseFailure` は `T.a`(ファイル)。各関数について: ①`tags` のうち `FEATURE_TAG` に**一致しないもの**ごとに `T.a`(形式不正)②`FEATURE_TAG` に一致するものが 1 つもなければ `T.a`(理由は、marker なし / 引数がリテラルでない(`has_marker` だけ真)/ 形式不正のみ、のいずれか)③`FEATURE_TAG` に一致するタグだけについて、要件の仕様(`01_req_spec.md`)が `head` になければ、またはタグが `spec_tags` に含まれなければ `T.b`。`requirement_of` には、一致したタグだけを渡す(`ValueError` で落ちない)。 [レビュー指摘 I-03]

### 4.4 `checks/pragma.py`
03 §4.5 のとおり。正規化 = `line.strip()`。`# pragma: no cover` の判定は、行に部分文字列 `pragma: no cover` を含むか。ファイルは `src/` 配下の `.py` で、`utf-8` でデコードできなければ飛ばす。超過した分の位置は、`head` のファイルの該当行の番号(同じ行が複数あるときは、後ろから)を `path:lineno` として返す。

### 4.5 `checks/human_merge.py`
`def human_merge(changes) -> tuple[str, ...]`: 全パスについて `machinery_reason(path)` を集め、`approval.json` に当たれば「決定(approval.json)」を加える。重複を除き、昇順。

### 4.6 `checks/__init__.py`
```python
def run_all(repo: Repo) -> CheckResult:
    changes = repo.changes()
    findings = [*check_k(repo, changes), *check_d(...), *check_t(repo, changes), *check_pragma(repo, changes)]
    return CheckResult(tuple(findings), human_merge(changes))
```
`RepoError` は捕まえない(入口が扱う)。

---

## 5. `adapters`

### 5.1 `adapters/repo_git.py`
```python
class GitRepo:
    def __init__(self, root: Path, base: str, head: str | Literal["worktree"]) -> None
    def read(self, path: str, ref: Ref) -> bytes | None
    def list(self, ref: Ref) -> Sequence[str]
    def changes(self) -> Sequence[Change]
```
- `_git(*args: str) -> bytes`: `subprocess.run(["git", "-C", str(root), "-c", "core.quotepath=off", *args], capture_output=True, check=False)`。終了コードが 0 でなければ `RepoError(標準エラー)`。`FileNotFoundError`(`git` がない)と `OSError` も `RepoError` にする。シェルを使わない。 [レビュー指摘 I-05]
- 起動時に、`git rev-parse --verify <base>^{commit}` で `base` を確かめる(なければ `RepoError`)。`head` が `worktree` でなければ、同様に確かめる。
- `read(path, ref)`: `ref` が `base` または `head` がコミットのとき `git show <rev>:<path>`(存在しなければ None。`git cat-file -e` で確認)。`head=worktree` のときは、`list("head")` に含まれるパスだけを読む: シンボリックリンクなら `os.fsencode(os.readlink(path))`、通常のファイルなら内容(バイト列)。含まれなければ None。 [データ: R6、リンクは git の扱いと同じ]
- サブモジュール(gitlink)は対象外(MVP。`ls-tree` が返しても `read` は `RepoError`)。 [レビュー R2-14]
- `list(ref)`: コミットのとき `git ls-tree -r --name-only -z <rev>` を**昇順に並べる**(ls-tree の順はフルパス昇順を保証しない)。`worktree` のときは `git ls-files -z -c -o --exclude-standard` から、`git ls-files -z -d`(作業ツリーで削除されたもの)を引き、**昇順に並べる**。 [データ: R6、`ls-files -c -o` は削除済みの追跡ファイルを含み、昇順でもない]
- `changes()`: `git diff -M --name-status -z <base> <head>`(コミットのとき)または `git diff -M --name-status -z <base>`(`worktree` のとき)を解析する。形式は、状態、NUL、パス、NUL(`R`・`C` は旧パス、NUL、新パス、NUL)。`A` → added(`old_path=None`)、`M`・`T` → modified(`old_path` と `new_path` に**同じパス**)、`D` → deleted(`new_path=None`)、`R*` → renamed(旧、新)。それ以外の状態(`C*` を含む。`-M` ではコピーは検出されない)が出たら `RepoError("unsupported status")`。 [レビュー指摘 L-01]`worktree` のときは、これに加えて、`git ls-files -z -o --exclude-standard` の未追跡ファイルを `added` として足す。**ステージ前の改名は、`deleted`(旧)と `added`(未追跡の新)の組になる**(これは `Q.pragma` が改名に強い定義で吸収する)。 [データ: R6]
- 結果は、インスタンス内でキャッシュする(1 回の実行の間、作業ツリーは変わらないとみなす)。 [推論]

### 5.2 `adapters/report.py`
```python
def format_findings(result: CheckResult) -> str       # "<rule> <path>: <message>"(`path` が None なら "<rule>: <message>")を 1 行ずつ。最後に「人間のマージが必要: <理由>」
def findings_json(result: CheckResult) -> str          # {"ok", "findings": [{rule,path,message,hint}], "human_merge": [...]}
def format_status(repo: Repo, head_label: str) -> str  # 要件ごとの状態、承認の有効/失効の理由、表示用ゲート、いま `src/` を変えてよいか(open が 1 つか)
def short_status(repo: Repo) -> str                    # 3 行以内。フックの通知用
```
`report` は `derive` を呼ぶ(`checks` は呼ばない)。

### 5.3 `adapters/cli.py`
`click` のグループ `main`。コマンド `check`、`status`、`init`、`doctor`、`hook`(03 §6)。
- `_open_repo(base, head) -> GitRepo`: `Path.cwd()` から `git rev-parse --show-toplevel` でルートを求める。
- `check`: 純粋に近い関数 `run_check(open_repo: Callable[[], Repo], as_json: bool) -> tuple[int, str]` に委ねる(単体テストできるように)。`open_repo()` と `run_all` を実行し、`RepoError` は `Finding(rule="E.repo", message=…)` にして出力し終了コード 2、**`gov` 自身の想定外の例外も `Finding(rule="E.internal")` にして終了コード 2**(traceback は出さない。`--debug` なら出す)、`result.ok` でなければ 1、それ以外は 0。出力は `format_findings` または `findings_json`。`E.repo` と `E.internal` は評価できなかったことを表す。 [レビュー指摘 I-05。03 §9 の「`E.repo`、終了コード 2」の実装]
- `init`: `.claude/settings.json` と `.gitattributes` の内容を生成する関数 `render_settings() -> str`、`render_gitattributes() -> str`(純粋)を呼び、書き込む。既存ファイルと内容が違えば、書かずに差分を出して終了コード 1。同じなら何もしない。
- `doctor`: 検査を関数の一覧 `CHECKS: list[Callable[[Path], DoctorItem]]` として持つ。項目は 03 §6 と spirals.md §2。`gate.sh` が存在し実行可能、`.pre-commit-config.yaml` が衛生フックだけ(ruff、mypy、vulture、pytest、`gate.sh`、`gov check` を持たない)、`.claude/settings.json` が入れ子形式で `gov hook` を呼ぶ、`origin/main` が解決できる。

### 5.4 `adapters/claude_hook.py`
```python
@dataclass(frozen=True)
class HookOutcome: exit_code: int; stdout: str = ""; stderr: str = ""

GIT_COMMAND: Final[re.Pattern[str]]   # 正規表現は 03 §7 が正本。コードに 1 回だけ書く

def classify_git(command: str) -> Literal["commit", "push"] | None
def handle(event: str, payload: dict[str, object], root: Path, repo_factory: Callable[..., Repo]) -> HookOutcome
def main(event: str) -> NoReturn            # 標準入力を読み、handle を呼び、出力して終了
```
- `classify_git`: `GIT_COMMAND.finditer(command)` の全一致を集め、`commit` が 1 つでもあれば `commit`、なければ `push`(順序によらない)。両方が含まれるときは `commit` を優先する(`git commit && git push`。commit のフックが先に走り、push のときに再び呼ばれる)。
- `handle`: ペイロードの不備(`tool_input` や `file_path` がない、型が違う)は `HookOutcome(0)` に正規化し、例外を外に出さない。フックは `GitRepo` を開く前に、`origin/main` がなければ 1 回だけ `git fetch origin main` を試す(失敗は `RepoError`。fail-open)。
- `handle("pre-tool-use", ...)`: `tool_name` が書き込み系なら、`tool_input` の `file_path`(または `notebook_path`)を `root` からの相対パスにして、`src/` 配下で `valid_open` が 1 つでなければ `short_status` 付きの通知。`Bash` なら `classify_git`。commit は `head=worktree`、push は `head=HEAD` で `run_all`。Finding があれば `HookOutcome(2, stderr=format_findings(...))`。
- `.specs/` がなければ、通知系は `HookOutcome(0)`。拒否系は検査を実行する(03 §7)。
- 例外(`RepoError` を含む)は、拒否系では `HookOutcome(0, stderr="gov hook: 検査を実行できませんでした: …(権威は CI)")`、通知系では `HookOutcome(0)`。`except Exception` を使うので、その行に理由のコメントを書く(ruff の `BLE001`)。 [決定の適用: 03 §7]
- 標準入力が JSON でない、`cwd` が git の外 → `HookOutcome(0)`。

---

## 6. テスト用: `FakeRepo`(`tests/support/fake_repo.py`)
```python
class FakeRepo:
    def __init__(self, base: Mapping[str, bytes], head: Mapping[str, bytes], renames: Mapping[str, str] = {}) -> None
```
`read`・`list` は辞書から。`changes()` は、`base` と `head` の辞書の差から `added`/`modified`/`deleted` を作り、`renames`(旧パス → 新パス)に指定されたものは `renamed` にまとめる(内容の類似度は見ない)。`list` は昇順。ファイルモードだけの変更とシンボリックリンクは表現しない(適合テスト L2-I09 の対象外。実 git だけで確かめる)。 [推論: 実際の git の改名検出との差は、適合テストで確かめる]

## 7. 例外とエラーの一覧

| 例外/値 | 送出元 | 扱い |
|---|---|---|
| `RepoError` | `GitRepo` | `check` は終了コード 2。フックは警告(拒否しない) |
| `ParseFailure` | `parse_approval`、`test_functions` | 値として返す。`K.a` の理由、`D.parse`、`T.a` になる |
| `ValueError` | `Change.__post_init__`、`requirement_of` | プログラムの誤り。握りつぶさない |

## 8. 未決
| ID | 内容 |
|---|---|
| Q-L3-1 | `GitRepo` の `read` を `git cat-file --batch` にまとめる最適化は、速度の要件がないので入れない(DEC-014)。必要になったら次のスパイラル |
| Q-L3-2 | `Finding` の `hint` の文面は、実装時に決める(メッセージの詳細は L3 の範囲外) |

## 承認

| 日付 | 内容 | 承認者 |
|---|---|---|
| (未承認。スパイラル 3 の終わりに記録する) | | |

## 訂正履歴
(事実の訂正のみ。版の履歴は git。)

| 日付 | 内容 |
|---|---|
| (なし) | |
