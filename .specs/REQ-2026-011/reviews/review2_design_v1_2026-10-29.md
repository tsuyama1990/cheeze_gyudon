独立レビュアーとして設計ドラフト（[design_rules_v1.md](file:///tmp/claude-1000/-home-tomo-project-cheeze-gyudon/fe52b292-861d-43e7-b105-b8a8584da814/scratchpad/design_rules_v1.md)）を精査しました。読み取り専用で調査を実施し、ファイル等の変更は行っていません。

詳細なレポートは成果物 [review_design_rules_v1.md](file:///home/tomo/.gemini/antigravity-cli/brain/ec7485b4-1051-4735-80a9-9a77d91f4c9a/review_design_rules_v1.md) に記録しました。以下に指定された6観点に基づく指摘を報告します。

---

## 1. 事実の誤り

### 指摘 1-1: `matome/CLAUDE.md` の存在に関する事実誤認
- **重大度**: 中
- **根拠**:
  - 設計書 L31: `- **CLAUDE.md**(リポジトリ内)は「規則は AGENT.md にある」の1行だけ(matome は既にこの形 [データ])。`
  - 実際のファイルシステム: `/home/tomo/project/matome/CLAUDE.md` は存在しない。一方、[/home/tomo/project/cheeze_gyudon/CLAUDE.md](file:///home/tomo/project/cheeze_gyudon/CLAUDE.md#L1-L3) に「The rules for this repository are in [AGENT.md](AGENT.md). This file holds nothing else.」と記載されている。
- **修正案**: リポジトリの取り違えを訂正し、「cheeze_gyudon は既にこの形」と改める。matome にはまだリポジトリ固有の `CLAUDE.md` が存在しない事実を明記すること。

### 指摘 1-2: vulture の現状に関する重大な事実誤認（既に稼働中）
- **重大度**: 高
- **根拠**:
  - 設計書 L84 (§7 やらないこと): `- **vulture の導入**。pytest のフィクスチャなどで誤検知が多い [推論]。必要になったら助言のみで導入。`
  - [cheeze_gyudon/scripts/gate.sh](file:///home/tomo/project/cheeze_gyudon/scripts/gate.sh#L14-L15): `echo "[3/7] Vulture..."; uv run vulture` が実装済み。
  - [02_system_design.md](file:///home/tomo/project/cheeze_gyudon/.specs/REQ-2026-010/02_system_design.md#L97): 品質検査 Q の項目として vulture が明記済み。
- **修正案**: vulture は cheeze_gyudon では既に必須ゲートとして実稼働している。設計意図が「cheeze_gyudon の gate.sh から vulture を削除する」のか、「matome への新規導入を見送る（cheeze_gyudon は現状維持）」のかを明確に区別して記述すること。

### 指摘 1-3: `claude_hook.py` が拒否（exit 2）する操作の認識漏れ
- **重大度**: 中
- **根拠**:
  - 設計書 L13: `- gov の hook(claude_hook.py): Edit/Write では**通知だけ**(exit 0)。拒否は、コミット時の K・D 規則のみ。T は警告。[原典: claude_hook.py の REJECTING_RULES]`
  - [claude_hook.py](file:///home/tomo/project/cheeze_gyudon/src/jtc_gov/adapters/claude_hook.py#L18-L20) および L40-44, L67-73: `classify_git` は `commit` だけでなく `push` も検知し、push 時にも `_gate` が呼ばれて K・D 違反時に exit 2 を返す。
- **修正案**: 「拒否は、コミット時およびプッシュ時の K・D 規則」と正確な記述に改めること。

### 指摘 1-4: `branch_guard.sh` の cwd 依存における誤許可（すり抜け）側の記述漏れ
- **重大度**: 低
- **根拠**:
  - 設計書 L11: `Bash の git commit だけ、セッションの cwd を見る。そのため git -C <dir> commit は、cwd の main に誤ブロックされる。`
  - [branch_guard.sh](file:///home/tomo/.claude/hooks/branch_guard.sh#L7): `dir=$(printf '%s' "$input" | jq -r '.tool_input.cwd // empty')`
- **修正案**: 「cwd が main のときに `git -C <別dir> commit` すると誤ブロックされる」だけでなく、「cwd が別ブランチのときに `git -C <mainレポ> commit` すると main への直接コミットが素通りする」という双方向の不整合がある旨を課題として明記すること。

---

## 2. gitフックの実現可能性

### 指摘 2-1: worktree 環境における `.git/` パス解決の破綻（R11 印の保存）
- **重大度**: 高
- **根拠**:
  - 設計書 L61 (R11): `gov stamp bonsai ... が印を .git/ に書く(ツリーのハッシュに紐づく)`
  - Git の worktree 仕様: worktree 内の `.git` はディレクトリではなくテキストファイル（`gitdir: ...`）である。
- **修正案**: worktree 配下で `.git/` 直下にファイルを作ろうとすると `Not a directory` エラーで即座に失敗する。また、マージ後に worktree は削除されるため（[merge-to-main.sh](file:///home/tomo/.claude/bin/merge-to-main.sh#L27)）、worktree 内に印を書くと参照不能になる。印を記録する場合は `git rev-parse --git-common-dir` などを経由して親の共通ディレクトリに解決する仕様が必要。

### 指摘 2-2: `merge-to-main.sh` の rebase によるツリーハッシュ無効化（R11 の検証破綻）
- **重大度**: 高
- **根拠**:
  - 設計書 L61, L77 (R11): `ツリーのハッシュに紐づく。pre-push と merge-to-main が印を要求。`
  - [merge-to-main.sh](file:///home/tomo/.claude/bin/merge-to-main.sh#L18): `git -C "$dir" rebase -q main` をマージ直前に実行。
- **修正案**: main に他のコミットがある状態で rebase が行われると、差分に競合がなくても **ツリーハッシュ（`git rev-parse HEAD^{tree}`）は必ず変化する**。エージェントが作業ブランチで押した印は `merge-to-main.sh` 内の rebase で即座に失効し、マージがブロックされる。ツリーハッシュに自己申告印を紐づける設計を撤回し、マージメッセージ（R08）の文面検査に一本化すること。

### 指摘 2-3: pre-commit フレームワークにおけるフックタイプのインストール・設定漏れ
- **重大度**: 高
- **根拠**:
  - 設計書 L40: `L2 git フック: pre-commit、pre-push、pre-merge-commit、commit-msg。pre-commit フレームワークで配る`
  - 設計書 L109: `各クローンで pre-commit install が要る。`
  - pre-commit の公式仕様: `pre-commit install` だけでは `pre-commit` フックしか入らない。
- **修正案**: `pre-push`、`pre-merge-commit`、`commit-msg` を有効化するには、それぞれ `--hook-type` 引数を付けてインストールする必要があり、`.pre-commit-config.yaml` 側でも `stages: [pre-push]` などの明示が必須。単に `pre-commit install` を促すだけでは L2 フックの大半が動かないため、`gov doctor` での検証項目および導入手順に `--hook-type` 4種の配線を明記すること。

### 指摘 2-4: マージコミットにおける `pre-commit` フックの不発火と設計記述の食い違い
- **重大度**: 中
- **根拠**:
  - 設計書 L53 (R03): `L2: pre-commit で現在のブランチが main なら拒否(マージコミットは pre-merge-commit で別扱い)。`
  - Git 公式仕様: `git merge` によるマージコミット作成時には `pre-commit` フックは発火せず、`pre-merge-commit` のみが発火する。
- **修正案**: マージコミット作成時に `pre-commit` が動かないのは Git のネイティブな仕様であるため、pre-commit 側でマージコミットを特別扱いする処理は不要。通常コミットのブランチ検査は `pre-commit`、マージの成否検査は `pre-merge-commit` と役割を Git のライフサイクルに即して整理すること。

### 指摘 2-5: `pre-merge-commit` での環境変数判定と pre-commit フレームワークの相性
- **重大度**: 中
- **根拠**:
  - 設計書 L56 (R06): `L2: pre-merge-commit が、環境変数(スクリプトが設定)なしで main へのマージを拒否`
- **修正案**: pre-commit フレームワーク経由で動かすとサブシェルや隔離環境により環境変数の伝播に注意を要する。数行の環境変数チェックのためだけに pre-commit フレームワークへ依存させるより、Git ネイティブのフック直接配置か、`merge-to-main.sh` 側での事前検証に留める方がシンプルである（推測）。

---

## 3. 設計内の矛盾と抜け

### 指摘 3-1: 移行順序（§9）における依存関係の逆転（開発デッドロックの発生）
- **重大度**: 高
- **根拠**:
  - 設計書 L96-101 (§9): 段3で pre-push（R07, R11）を導入し、段5で初めて AGENT.md の共通ブロックに規則を移す。
- **修正案**:
  - 段3 で pre-push に R11（bonsai 印要求）を導入すると、以降の段（段4の L1 実装など）で push やマージができなくなる。エージェントに対する bonsai 印押下の手順やルールの通知（AGENT.md の改訂）は段5 であり、エージェントは手順を知らないままブロックされる。
  - 段1 で `gov doctor` に共通ブロック検査を実装すると、段5 で各リポジトリの AGENT.md を置き換えるまで、段1〜4 のすべてのブランチで `gov doctor` が警告・失敗を出し続ける。
  - 移行順序を「1. 共通ブロックの設計と AGENT.md への反映（人間・エージェントへのルール周知） → 2. L1・L3 の拡充 → 3. L2 フックの配線と `gov doctor` による整合性検査の有効化」に再編すること。

### 指摘 3-2: 原典に存在する規則のカタログ（§5）からの抜け漏れ
- **重大度**: 中
- **根拠**:
  - [CLAUDE.md L43](file:///home/tomo/.claude/CLAUDE.md#L43): `置き換えたら同じコミットで旧コードを消す（関数・分岐・設定キー・テスト・ドキュメントまで）。互換レイヤーや未使用のフォールバックを残さない。`
  - [CLAUDE.md L59](file:///home/tomo/.claude/CLAUDE.md#L59): `同じ関門で3回失敗したら止めて「何が通らないか・何を試したか」を報告。掃除は差分と触ったモジュールに限定し、細かい指摘は直さず記録する。`
  - [matome/AGENT.md L6](file:///home/tomo/project/matome/AGENT.md#L6): `Every test function carries @pytest.mark.requirement("REQ-YYYY-NNN-Fnn") whose tag exists in that requirement's 01_req_spec.md.`
- **修正案**:
  - 「旧コードの即時削除（互換レイヤーを残さない）」は原典の基本思想（足し算防止）であるが、カタログ（R01〜R20）および§7の機械化しない枠のいずれからも脱落しているため追記すること。
  - 「3回失敗時の打ち切り報告ルール」は R12 で Stop フックの仕組みとして言及されているが、エージェント自身の行動規則としての記載が抜けているため追記すること。
  - 「全テスト関数への requirement marker 付与とタグ一致（gov T 規則）」が、R16 の陰に隠れてカタログの要件文面から漏れているため明記すること。

### 指摘 3-3: `pre-merge-commit` での `gate.sh` 実行に関する記述の矛盾
- **重大度**: 低
- **根拠**:
  - 設計書 L21 (§2 表): `pre-push と pre-merge-commit の段に、gate.sh と承認・印の検査を呼ぶ。`
  - 設計書 L57 (R07 実装欄): `L2: pre-push でも gate.sh`
- **修正案**: §2 では `pre-merge-commit` でも `gate.sh` を呼ぶと記載されているが、R07 では `pre-push` のみとなっており食い違っている。`merge-to-main.sh` 自身が L22 で `gate.sh` を呼ぶため二重実行の無駄が生じる。pre-merge-commit で gate.sh を呼ぶのかどうかの方針を統一すること。

---

## 4. 過去の決定の扱い

### 指摘 4-1: DEC-032（`no-commit-to-branch` の意図的除外決定）との衝突の看過
- **重大度**: 高
- **根拠**:
  - [decisions.md L237 (DEC-032)](file:///home/tomo/project/cheeze_gyudon/.specs/REQ-2026-010/decisions.md#L237): `DEC-032: main への直接コミット禁止が全体設定のフック、pre-commit、ruleset の 3 か所にある。答え: pre-commit の no-commit-to-branch を外す。`
  - 設計書 L53 (R03): `L2: pre-commit で現在のブランチが main なら拒否`
- **修正案**: 設計書 §2 では F09 の一部変更としてのみ記述されているが、実際には **DEC-032 で「多重管理を避けるために pre-commit から意図的に外した」決定を覆す提案**である。DEC-032 に一切触れずに pre-commit に main 拒否を再導入するのは決定管理の透明性を欠く。エージェント非依存化のために DEC-032 を見直す旨を §2 に明記し、正式な見直し提案として扱うこと。

### 指摘 4-2: DEC-029（`gov` コマンド体系の最小化・整理）との衝突
- **重大度**: 中
- **根拠**:
  - [decisions.md L234 (DEC-029)](file:///home/tomo/project/cheeze_gyudon/.specs/REQ-2026-010/decisions.md#L234): `DEC-029: 残すのは init、doctor、status、check(K・D・T・Q)、hook の 5 つ。廃止するのは gate-check、escalate、...`
  - 設計書 L61 (R11): `新規。gov stamp bonsai --net N --removed "…" が印を .git/ に書く`
- **修正案**: DEC-029 で肥大化したサブコマンドを廃止し 5 つに絞り込んだ経緯がある。新コマンド `gov stamp` の追加はコマンド体系の肥大化抑制方針と衝突するため、DEC-029 の見直し提案として記述するか、印付けサブコマンドの新設を見送ること。

### 指摘 4-3: DEC-025（正本管理）の改訂提案における表現の精緻化
- **重大度**: 低
- **根拠**:
  - 設計書 L20 (§2 表): `DEC-025 | 逆にする提案。共通の規則は各リポジトリの AGENT.md に置く(正本は gov の雛形)。~/.claude/CLAUDE.md は個人の情報だけにする`
  - [02_system_design.md L26-L50](file:///home/tomo/project/cheeze_gyudon/.specs/REQ-2026-010/02_system_design.md#L26-L50) (DEC-025): `情報の正本(二重管理の禁止)`
- **修正案**: 単に「逆にする」と表現すると二重管理を認めるように読める。実態は「正本を個人の `~/.claude/CLAUDE.md` からリポジトリ管理される `gov の雛形` に変更し、各リポジトリの `AGENT.md` は共通ブロックとして同期・生成される配布先とする」という構造変更である。DEC-025 の精神（二重管理の禁止）を維持した改訂であることを明記すること。

---

## 5. 実運用の摩擦

### 指摘 5-1: `pre-push` での `scripts/gate.sh` フル実行による著しい待ち時間と摩擦
- **重大度**: 高
- **根拠**:
  - 設計書 L57 (R07): `L2: pre-push でも gate.sh`
  - [scripts/gate.sh](file:///home/tomo/project/cheeze_gyudon/scripts/gate.sh): Ruff, Mypy, Vulture, Pytest & coverage, diff-cover, gov check, pre-commit (全ファイル走査)。
- **修正案**: `scripts/gate.sh` は全テストや全ファイル走査を含み、実行に数十秒〜1分程度を要する。作業ブランチのバックアップ push や頻繁な push のたびにこれを強制すると、開発リズムが著しく悪化し、`--no-verify` の乱用を誘発する。pre-push では軽量な検査（コミット対象の高速チェックや `gov check` のみ）に留め、重い gate.sh フル実行は `merge-to-main.sh` および CI に委ねること。

### 指摘 5-2: R14（設計書のバッククォート内識別子の実装存在検査）の大量誤検知
- **重大度**: 高
- **根拠**:
  - 設計書 L64 (R14): `承認済みの設計書のバッククォート内の識別子は、実装に存在する | L1 | gov check に追加(名前の一致のみ。意味の一致は検査しない)`
- **修正案**: 設計書内のバッククォートには、外部モジュール名、CLI 引数（`--strict-markers`）、ファイルパス（`01_req_spec.md`）、JSON キー（`"approval.json"`）、環境変数、Git コマンド、一般的な英単語などが大量に含まれる。「名前の一致のみ」を機械検査すると、これら非 Python シンボルが「実装に存在しない識別子」として大量に誤検知（False Positive）され、`gov check` が通過不能になる。R14 は機械ゲート化を見送り、「機械化しない（レビューでの確認）」枠に移すか、対象を限定する厳密な定義が必要である。

### 指摘 5-3: R13（コミット履歴における V字順序検査）の開発硬直化と誤検知
- **重大度**: 中
- **根拠**:
  - 設計書 L63 (R13): `gov check に追加: ブランチの履歴で、src/ を変えた最初のコミットより前に、tests または .specs/ を変えたコミットがある`
- **修正案**: 設計・テスト・コードをまとめて1コミットにコミットした場合（最初のコミットで `src/` と `tests/` を同時に触った場合）や、rebase による履歴整理時に誤検知でブロックされる。形式的な「中途半端なテストだけの先行コミット」を強要され、コミットログが汚染されるため、コミット履歴順序の強制ではなく、PR・マージ時点でのテスト・仕様の存在確認（gov K/D/T）で担保すること。

### 指摘 5-4: R02 の Bash コマンド監視による読み取りコマンドの誤ブロック
- **重大度**: 低
- **根拠**:
  - 設計書 L52 (R02): `L3: Write/Edit と、Bash のコマンド文字列に approval.json を含む場合を ASK。`
- **修正案**: コマンド文字列に `approval.json` を含むだけで一律 ASK にすると、`cat .specs/.../approval.json` や `grep` などの参照コマンドでも ASK が発生しアラート疲弊を招く。Write/Edit ツールの監視に絞るか、書き込み系コマンドに限定すること。

---

## 6. 最小性 (YAGNI)

### 指摘 6-1: R11 のための独自印付け機構（`gov stamp` + ツリーハッシュ照合）の過剰開発
- **重大度**: 高
- **根拠**:
  - 設計書 L61, L77 (R11): `gov stamp bonsai ... 印は自己申告で、質は検査しない`
  - [CLAUDE.md L41-42](file:///home/tomo/.claude/CLAUDE.md#L41-L42): `要件に紐づかないコードを書かない（YAGNI）。抽象化は2つ目の実例が出てから。`
- **修正案**: 設計書自身が「印は自己申告であり、質は検査しない」と認めている。質を検証しない自己申告のデータのために、新コマンド `gov stamp` を作り、ツリーハッシュと紐づけて Git 内部に独自ファイルを保存・検証する仕組みは過剰開発（YAGNI 違反）である。`merge-to-main.sh` のマージメッセージ（R08）内に「純増減」および「削除内容」のセクションが存在するかを正規表現でチェックするだけで同一の目的を達成できるため、独自の印付けサブシステムは全廃すること。

### 指摘 6-2: AGENT.md の「共通ブロック部分置換・同期機構」の過剰な抽象化
- **重大度**: 中
- **根拠**:
  - 設計書 L28-30: `印(<!-- gov:rules vN --> … <!-- /gov:rules -->)で囲む。gov doctor が、共通ブロックが雛形と一致するか検査する。更新は gov init の再実行で、共通ブロックだけを置き換える(固有部分は触らない)。`
- **修正案**: 現在の対象リポジトリは 2 つのみである。Markdown ファイル内の独自タグをパースし、差分比較して固有部分を壊さずに共通ブロックのみをインプレース置換するマージエンジンを `gov init` に実装するのは、2リポジトリの規模に対して機構が過大。共通規則を独立ファイル（`.rules/common.md` 等）として配布するか、シンプルなテンプレート差分警告にとどめること。

### 指摘 6-3: R18（訂正履歴文字列の機械チェック）の過剰な機械化
- **重大度**: 低
- **根拠**:
  - 設計書 L68 (R18): `承認済みの設計書のハッシュが変わり、再承認されていない場合に、文書末尾の「訂正履歴」の追記がなければ警告`
  - 設計書 L85 (§7 やらないこと): `機械化しないもの: ...文章の意味。判断が要る [推論]`
- **修正案**: 文書末尾に「訂正履歴」という見出しが存在するかどうかの機械チェックは、無意味な空見出しの追加を招くだけで実質的な妥当性を保証しない。§7 L85 の「機械化しない（判断が要る）」に分類し、人間レビューに委ねること。

---

以上の指摘事項の全体像と優先度については、成果物 [review_design_rules_v1.md](file:///home/tomo/.gemini/antigravity-cli/brain/ec7485b4-1051-4735-80a9-9a77d91f4c9a/review_design_rules_v1.md) をご確認ください。
exit 0
