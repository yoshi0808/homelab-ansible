# review — Proxmox Policyの改名とscope拡張(Step 3)

日付: 2026-08-01(初回) / 2026-08-01(再レビュー、差し戻し後)
役割: Reviewer(独立レビュー、実装非関与)
契約: `2026-08-01_005_requirement_policy_rename.md`
対象実装記録: `2026-08-01_006_implement_policy_rename.md`(§5・§10改訂後。判定・根拠は鵜呑みにせず現物で再確認した)
使用Skill: `skills/document-norm-review/SKILL.md`(観点)、`skills/code-review/SKILL.md`(出力形式)

## 再レビュー結論(先頭サマリ)

初回レビュー(下記「初回レビュー(2026-08-01)」節)で指摘したCritical Issue 1・2(`proxmox_operations_policy.md`と`proxmox_backup_restore_verify_policy.md`が同一playbookの許可・禁止・停止条件について揃って正本を自称していた問題)は、**現物確認の結果、解消していることを確認した。**

- `docs/ai/policies/proxmox_operations_policy.md`の冒頭リードとSB-020該当行(87-88行目付近)、`docs/ai/context/system/proxmox.md` 3行目、`docs/ai/policies/proxmox_backup_restore_verify_policy.md` BRV-011の4箇所を突き合わせ、`proxmox_backup_restore_verify.yml`の許可・禁止・停止条件について正本を自称する文書がBRV Policy一本になったこと、Operations Policy側は「本表は自動実行tierの索引のみ」と明示的に自己を非規範的索引だと宣言していることを確認した。3箇所とも矛盾なく同じ結論(BRV Policyが正本)を指しており、循環参照や優先順位の空白もない。
- `python3 scripts/check-doc-consistency.py`を`/tmp`複製+`git init && git add -A`で独立に再実行し、`[check1] OK (96 compared)` `[check2] OK (8 compared)` `[check3] OK (90 compared)`、exit 0を確認した(Coordinatorの観測事実と一致)。新設した2本のMarkdownリンク(冒頭リード、SB-020該当行)が正しく解決されており、check3の比較件数増分(88→90)はリンク切れではなくリンク新設によるものであることを裏付けている。
- SB-001から「backup restore検証」を削除したことで生じ得る「SB-020の入口列挙とPolicyの目的宣言の齟齬」を確認したが、**新しい矛盾は生じていない**(理由は下記「再レビューで確認したこと」)。ただしSuggestionを1件追加した(非blocking)。
- 却下されたsuggestion(tester-gate根拠への差し替え)への再指摘は行わない。却下理由(SB-020とtester-gateは軸が異なり対応表が存在しない)を独立に確認済みで、誤りとは考えない。
- 権限境界: `git status`/`git diff --cached`で作業ツリー・indexとも変更なし(何も`add`していない)であることを確認済み。実ホスト接続、`git commit`/`push`の痕跡なし。

**Verdict(再レビュー): Approve**(非blockingのSuggestion 1件を残すのみ)。以下は初回レビューの原文(履歴として保持)と、再レビューの詳細。

---

## 初回レビュー(2026-08-01)

### Summary

改名(ファイル移動・13ファイルのlive参照retarget)自体は機械的に正確で、AC1・AC2・AC3・AC5・AC6は現物で満たされていることを確認した。しかし**AC7「抵触なし」の判定は妥当でない**。SB-020安全度表への`proxmox_backup_restore_verify.yml`追加とscope宣言の拡張が組み合わさった結果、同playbookの許可・禁止・停止条件について**`proxmox_operations_policy.md`と既存の`proxmox_backup_restore_verify_policy.md`が互いを参照せずに二重に「正本」を自称する状態**が生じている。これはrequirement §3「既存の規範文の意味を変えない」が防ごうとした事態そのものであり、実装者のAC7分析(Policy内部の禁止条項との照合)はこの種類の抵触を検査範囲に含めていなかった。

### Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| 1 | `docs/ai/policies/proxmox_operations_policy.md` | 3(冒頭リード)、87-88(SB-020) | scope拡張後の冒頭リードは「本書はProxmox VE hostの運用操作(…backup restore検証を含む…)に関する許可、禁止、停止条件の正本である」と明言し、SB-020表にも`proxmox_backup_restore_verify.yml`を`controlled apply`として追加した。ところが同playbookは既存の`docs/ai/policies/proxmox_backup_restore_verify_policy.md`が「本書はProxmox上のcore VM backupを実restoreして検証する際の許可、禁止、停止条件、判断軸の正本である」(同ファイル3行目)と明記し、BRV-011で「本Policyに対応するplaybookは`proxmox_backup_restore_verify.yml`の1本とする」としている対象そのものである。改名後も無変更で残っている`docs/ai/context/system/proxmox.md`3行目は今も「backup restore verificationの許可、禁止、停止条件は`proxmox_backup_restore_verify_policy.md`を正本とし」と、この責務をBRV Policy側だけに割り当てている。**2つのPolicyが同一playbookの許可範囲について、互いを参照せず「正本」を自称する状態になった。** 両文書間に優先順位や参照関係の記述はなく、将来どちらかの記述だけが更新されればもう一方が黙って古いまま残る(SB-020表側の要約文言と、BRV-071等の詳細規範が乖離しても検出する仕組みが無い)。`scripts/check-doc-consistency.py`はリンク解決のみを検査し、この種の意味的重複は検出しない。 | Critical |
| 2 | `docs/ai/reviews/norm_drift_mechanical_check/2026-08-01_006_implement_policy_rename.md` | §5(AC7の分析) | AC7の「抵触なし」という結論は、`proxmox_operations_policy.md`**内部**の禁止条項(SB-090、§7.1、§2.3、§7.3)とだけ照合しており、**他の既存Policy文書との重複・矛盾**という抵触経路を検査していない。requirement AC7は「既存の許可・禁止・停止条件の適用範囲が意図せず広がっていないこと」を一般に問うており、「これまで対象外だったplaybookが既存の禁止条項に抵触する状態になっていないか」はその特に指摘された一例に過ぎない。実装者は`proxmox_backup_restore_verify_policy.md`の存在自体を実装記録内で一度も言及しておらず、既存Policy群の横断確認が抜けている。requirement §5(6)では「該当があれば実装せず報告する」ことが求められており、Finding 1が是正されるまでSB-020表への当該行追加は実装として不完全である。 | Critical |

### Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `docs/ai/policies/proxmox_operations_policy.md` | 88 | `proxmox_backup_restore_verify.yml`を`controlled apply`行として追加する判断根拠(実装記録§3)は「playbookヘッダが`controlled apply`と自称する」ことだが、これは`playbooks/proxmox_backup_restore_verify.yml:2`の英語タイトル行のコメントであり、同playbookの正式なtester-gate宣言(`tester-gate: risk-accepted`、同ファイル25行目)とは異なる語彙。SB-020の「安全度」は`ansible_test_safety_policy.md`のtester-gate分類(safe-readonly/role-guarded/risk-accepted/check-mode-native/dry-run-aware)とは別軸の独自語彙であること自体は問題ないが、その根拠として非規範的なコメント文字列の一致を挙げるのは弱い。Finding 1を解消する過程で、根拠をBRV Policy側の正式な分類(BRV-011のtester-gate: risk-accepted)から引き直すことを勧める | consistency |
| 2 | `docs/ai/policies/proxmox_operations_policy.md` | 87-88 | 同じ`controlled apply`ラベルの行が2行に分かれ、それぞれ許可範囲の記述が異なる(evacuate/restoreは「guest配置変更」、backup_restore_verifyは「使い捨てVMID(999)へのbackup restore」)。安全度ラベル自体を他の規範箇所が汎用的に参照する箇所は現状ない(grep確認済み)ため、この2行自体が単独で誤動作を生む経路は無いが、Finding 1の是正時にこの行を残す場合は「詳細は`proxmox_backup_restore_verify_policy.md`を正本とする。この行は索引であり実行許可の実体ではない」という趣旨の注記を添え、BRV Policy §3のインデックス免責文言(「列挙自体は実行許可を意味せず…」)と対称にすることを勧める | clarity |

### What Looks Good

- **AC1(改名+参照retarget)**: 独立にgrepで確認した。`docs/ai/reviews/`を除くlive層で`proxmox_patch_policy`/`proxmox-patch\.md`にマッチするのは`proxmox_operations_policy.md`自身の変更履歴(2026-08-01行、改名の事実を記述)1箇所のみ。旧ファイルは実在しない。13ファイルのretarget内容(ADR 002/006/008、context-classification.md、context/system/proxmox.md、incident記録、policy-migration-map.md、roles 2件、recovery_exec template、codex-classify.sh)を個別にdiffで確認し、いずれも単純なファイル名置換で、周辺文言の意味を変えていないことを確認した。
- **AC2(`docs/ai/reviews/`配下無変更)**: `git status --porcelain -- docs/ai/reviews/`で対象フォルダ全体が新規(`??`)であり、追跡済みファイルへの変更が無いことを確認した。
- **AC3(scope限定表現の除去)**: タイトル・冒頭リード・SB-001を現物で確認し、いずれも「patchに関する」のような排他表現は残っていない。SB-001配下の箇条書き(pve2先行検証等)がpatch flow前提のまま残っている点は、requirement §3「既存の規範文の意味を変えない」の範囲内の判断として妥当。
- **AC5(`check-doc-consistency.py` exit 0)**: 現在のgit index(rename前の状態)に対して独立に実行し、`[check1] OK (96 compared)` `[check2] OK (8 compared)` `[check3] OK (88 compared)`、exit 0を確認した。実装記録が報告した`git add`→検証→`git reset`の手順もrename後の状態で同種の結果を示す内容であり、手順自体(pathspec指定add、mixed reset、reset後の`git status`一致確認)は`git add`/`git commit`状態を残さない設計として問題ない。
- **AC6(変更履歴)**: 既存の降順規約に沿った新規行が追加されており、既存行(2026-07-30以前)への書き換えは無い。
- **権限境界**: `git diff --cached`が空であることを確認し、実装記録が主張する「add後にreset済み」という状態と整合する。実ホストへの接続、`git commit`/`push`の痕跡は無い。作業はansyのworking treeと本reviewファイルの範囲に収まっている。
- **ADR-008への1文追加**: 「`proxmox_snapshot_check`はpatch domain外でPolicyの置き場が無い」という当時の前提が本改訂で解消されたことを注記した判断は妥当。無注記のまま残せば`skills/document-norm-review/SKILL.md`欠陥クラス3(撤回した根拠の残存)に該当していた。決定当時の記録は保持しつつ現状との齟齬を明示しており、範囲を超えた書き換えにはなっていない。
- **`docs/ai/status.md`のWatch行削除**: 差分はCoordinatorによるものであり(本レビュー対象外との申し送りどおり)、実装者の差分には含まれていないことをdiffで確認した。

### 未確認・保留事項

- Finding 1の是正方法(SB-020表からbackup_restore_verify行を外す/BRV Policyへの参照注記を足す/両Policyの優先順位を明記する、のいずれか)はCoordinator・Yoshinobuの判断範囲であり、本レビューでは方式を指定しない。
- 実装記録§6が列挙した副次的発見(context-classification.mdの「未作成」表記の誤り、role defaultsの節番号「(5.6)」の陳腐化、ADR-002の行番号/SB番号の陳腐化)はいずれも本requirementのscope外という実装者の判断を確認し、独立に妥当と判断した(いずれも改名前から存在した既存の陳腐化であり、本diffがscopeを広げて生じたものではない)。
- `scripts/check-doc-consistency.py`、`scripts/git-pre-commit-check.sh`、`.gitignore`、`scripts/tests/`、および`docs/ai/reviews/norm_drift_mechanical_check/`の001〜004は、依頼のとおりレビュー対象から除外した。

### Verdict(初回時点)

**Request Changes** — Critical Issue 1・2により、AC7が実質的に未充足。SB-020表への`proxmox_backup_restore_verify.yml`追加、または冒頭リードのscope宣言のいずれかを、既存の`proxmox_backup_restore_verify_policy.md`との関係が明示されるまで見直す必要がある。それ以外の改名・retarget・AC1〜AC6は現物確認済みで問題ない。

---

## 再レビュー(差し戻し対応後、2026-08-01)

対象差分: `docs/ai/policies/proxmox_operations_policy.md`(冒頭リード、SB-001、SB-020表の`proxmox_backup_restore_verify.yml`行、2026-08-01変更履歴行)、`docs/ai/context/system/proxmox.md` L3、`2026-08-01_006_implement_policy_rename.md` §5・§10(新設)。

### Critical Issue 1・2 の解消確認

現物3箇所を突き合わせた。

1. `docs/ai/policies/proxmox_operations_policy.md`冒頭リード(3行目): 「本書はProxmox VE hostの運用操作(patchの判断・適用、healthcheck、VM/CT退避・復帰、read-only点検を含む…)に関する許可、禁止、停止条件の正本である。」から「backup restore検証」が削除され、続けて「`proxmox_backup_restore_verify.yml`はSB-020の安全度表に自動実行tierの索引としてのみ含み、その許可、禁止、停止条件の詳細は[proxmox_backup_restore_verify_policy.md]を正本とする(競合する二重の正本を作らないため)。」という委譲文が追加されている。
2. 同ファイルSB-020該当行(87-88行目付近): 許可範囲セルが独自記述(旧: 「使い捨てVMID(999)への月次backup restore、起動確認、破棄によるbackup検証。本番VMはconfig読み取りのみで変更しない」)から「backup restore検証。許可、禁止、停止条件の詳細は[proxmox_backup_restore_verify_policy.md]が正本(本表は自動実行tierの索引のみ)。」という委譲文へ差し替えられている。行自体は表から削除されておらず(Yoshinobuの指示どおり)、AC4の充足(3本追加)は維持されている。
3. `docs/ai/context/system/proxmox.md` 3行目: 「両Policyの対象は排他的であり、`proxmox_backup_restore_verify.yml`の許可・禁止・停止条件の正本は常に後者(`proxmox_backup_restore_verify_policy.md`)だけとする(前者のSB-020は同playbookを自動実行tierの索引として載せるのみで、詳細規範を重複させない)。」という一文が追加されている。
4. `docs/ai/policies/proxmox_backup_restore_verify_policy.md` BRV-011(無変更): 「本Policyに対応するplaybookは`proxmox_backup_restore_verify.yml`の1本とする」は元のまま残っており、上記1〜3の委譲文と矛盾しない。

3つの生きた文書(Operations Policy、System Context、BRV Policy)がいずれも「`proxmox_backup_restore_verify.yml`の許可・禁止・停止条件の正本はBRV Policyのみ」という同一の結論を指しており、循環参照や優先順位の空白は無い。**Critical Issue 1は解消したと判断する。**

Critical Issue 2(AC7分析が他Policyとの横断確認を欠いていた点)についても、実装記録§5(改訂版)が`docs/ai/policies/*.md`全体を対象に新規3playbook名で横断grepを行い、`autonomous_recovery_policy.md`のmute契約への言及(同playbook自身の許可・禁止・停止条件を規定するものではない)と、`proxmox_backup_restore_verify_policy.md`との重複(解消済み)を区別して記録している。手法・結論とも独立に妥当と判断する。**Critical Issue 2も解消したと判断する。**

### 新しい矛盾が持ち込まれていないかの確認

Coordinatorの懸念(「SB-001から「backup restore検証」を外したことで、SB-020の表に載る入口と本Policyの目的宣言との間に齟齬が生じていないか」)を検証した。

- SB-020の表題直下の文(SB-020マーカー直後): 「入口は次の4安全度に固定し、自動実行範囲を分類どおりに制限する。」は表全体に掛かる一般文であり、行ごとの例外を想定した書き方ではない。`proxmox_backup_restore_verify.yml`の行は「本表は自動実行tierの索引のみ」と行内で明示的に自己の位置づけを限定しているため、行内の特定文言が表全体の一般文に優先すると読める設計になっており、読解上の矛盾はない。ただしこの一般文自体は「この表がPolicyとして自動実行範囲を制限する」と読めるため、初見の読者が表の一般文だけを読んで`proxmox_backup_restore_verify.yml`もOperations Policyが実行範囲を決めていると誤解する余地はわずかに残る(下記Suggestion参照)。
- SB-001(目的)がbackup restore検証を含まなくなったことと、§3.1(対応するPlaybook)のSB-020がbackup restore検証を「索引としてのみ」含むことは、目的(何を安全に判断・実行・停止するか)と索引(何を一覧として指し示すか)という異なる機能の文であるため、両立可能である。`proxmox_backup_restore_verify_policy.md` §3の索引テーブルも同じ構造(「列挙自体は実行許可を意味せず…」という免責文つきの索引)を既に持っており、今回の設計はこの既存の書き方に倣ったものと言える。
- 変更履歴(2026-08-01行、最終版)を確認した。「`proxmox_backup_restore_verify.yml`(controlled apply)もSB-020の索引へ追加したが、同playbookは`proxmox_backup_restore_verify_policy.md`が既に許可・禁止・停止条件の正本として存在するため、本書はSB-020の自動実行tier索引としてのみ扱い、詳細規範の正本を二重化しない」と明記されており、実際のPolicy本文の状態と一致している。書き換えた事実を隠さず、遷移過程(初回提出→差し戻し→修正)は変更履歴でなく実装記録側(§3、§5、§10)に残すという判断も、requirement §5「Policy自身の変更履歴は最終状態を1行で書く」性質と整合している。

**新しい矛盾は確認できなかった。** requirement §3「既存の許可・禁止・停止条件の意味を変えない」も、SB番号・既存条項本文とも無変更であることを確認し、引き続き守られている。

### 却下されたsuggestionについて

実装記録§10に記録された却下(「`controlled apply`分類の根拠をtester-gate: risk-acceptedに依るべき」という初回suggestionを、SB-020とtester-gateは軸が異なり対応表が存在しないという理由で却下)について、再指摘は行わない。`docs/ai/policies/*.md`・`playbooks/*.yml`を横断grepし、SB-020の4値(safe/semi-safe/controlled apply/unsafe)とtester-gateの5値(safe-readonly/role-guarded/risk-accepted/check-mode-native/dry-run-aware)を対応付ける表がどこにも存在しないこと、SB-020の値がplaybook側のコメントで直接自称されているケース(`proxmox_backup_restore_verify.yml:2`)が実在することを独立に確認しており、却下理由は妥当と判断する。判断そのものを誤りだとは考えない。

### AC再確認(影響範囲のみ)

- AC1: 今回の差分がold名を再度持ち込んでいないことをgrepで再確認(`docs/ai/reviews/`以外でのヒットはOperations Policy自身の変更履歴の歴史的言及のみ)。維持。
- AC3: 冒頭リード・SB-001に「backup restore検証」を含めない最終形でも、「patchに関する」のような排他表現は入っておらず、scope限定表現の除去は維持されている。
- AC4: SB-020表の3行追加(safe×2、controlled apply×1)は維持。controlled apply行を削除していないことを確認。
- AC5: `/tmp`複製+`git init && git add -A`で独立に再実行し、`[check1] OK (96 compared)` `[check2] OK (8 compared)` `[check3] OK (90 compared)`、exit 0を確認(Coordinator観測と一致)。作業ツリーのまま(未追跡)の場合はcheck3が88件になることも確認しており、90件との差はリンク新設2本の未追跡起因であることを裏付けた。
- AC6: 変更履歴の最終版がPolicy本文の現状と一致することを確認済み(上記)。
- AC7: 解消(上記Critical Issue解消確認のとおり)。

### Suggestions(再レビュー、非blocking)

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `docs/ai/policies/proxmox_operations_policy.md` | SB-020マーカー直後の一般文(87行目付近) | 「入口は次の4安全度に固定し、自動実行範囲を分類どおりに制限する。」という表全体への一般文が、行内で「索引のみ」と自己限定した`proxmox_backup_restore_verify.yml`行にもそのまま掛かって読める。一般文の末尾に「(`proxmox_backup_restore_verify.yml`の実行範囲は本表でなく[proxmox_backup_restore_verify_policy.md]が定める)」のような一言を足すと、表の先頭だけを読んだ読者がこの1行を誤読する余地がなくなる。blockingではない | clarity |

### 権限境界の確認

`git status --porcelain`で作業ツリーの変更集合が対象13ファイル+新規2ファイルのみであることを確認し、`git diff --cached`が空であることを確認した(何も`add`していない)。独立検証のための`/tmp`複製・`git init`・`git add -A`は`/tmp`配下のみで行い、検証後に複製ディレクトリごと削除した。実ホストへの接続、本体リポジトリでの`git add`/`git commit`/`git push`はいずれも実行していない。

### Verdict(再レビュー)

**Approve** — Critical Issue 1・2は解消を確認した。AC1〜AC7はすべて現物で充足を確認した。残るのはSuggestion 1件(非blocking、可読性向上のための任意の追記)のみ。
