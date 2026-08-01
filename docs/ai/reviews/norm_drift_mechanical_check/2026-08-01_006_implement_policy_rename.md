# 実装記録 — Proxmox Policyの改名とscope拡張(Step 3)

日付: 2026-08-01
役割: Implementer
契約: `2026-08-01_005_requirement_policy_rename.md`
差し戻し: 独立レビューが「`proxmox_backup_restore_verify.yml`の許可・禁止・停止条件について、`proxmox_operations_policy.md`と`proxmox_backup_restore_verify_policy.md`の2つが揃って正本を自称している」というblocking findingを提示し、Coordinatorが差し戻した。対応内容は§5・§10。

## 1. 変更したパス

改名:

- `docs/ai/policies/proxmox_patch_policy.md` → `docs/ai/policies/proxmox_operations_policy.md`
- `docs/ai/context/operations/proxmox-patch.md` → `docs/ai/context/operations/proxmox-operations.md`

`git mv`ではなく`mv`(working treeのみの移動)を使った。理由は§5「権限境界」参照。

live層の参照retarget(13ファイル + 2ファイル自身、requirement §2.4の集計「13ファイル・18行」「3ファイル・6行」と一致することを実装前にgrepで確認済み):

- `docs/ai/adr/002-proxmox-patch-dryrun-single-node.md`(`proxmox_patch_policy`×2、`proxmox-patch.md`×1)
- `docs/ai/adr/006-proxmox-exec-node-selection.md`
- `docs/ai/adr/008-proxmox-readonly-check-unreachable-node.md`
- `docs/ai/context-classification.md`
- `docs/ai/context/system/proxmox.md`
- `docs/ai/memory/incidents/2026-07-26_proxmox-patch-dryrun-single-node-defects.md`
- `docs/ai/policy-migration-map.md`(4箇所、`replace_all`)
- `docs/ai/status.md`(`proxmox-patch.md`×1、`proxmox_patch_policy`×1)
- `roles/proxmox_evacuate_node/defaults/main.yml`
- `roles/proxmox_restore_vm_placement/defaults/main.yml`
- `roles/recovery_exec/templates/AGENTS.md.j2`
- `scripts/codex-classify.sh`(`POLICY_FILE`変数 — 実行時に読むパスであり、機能的に重要)

新規成果物: 本ファイル。

## 2. AC別の充足状況

**AC1(改名 + live層参照0件)**: 満たす。改名後、`grep -rln "proxmox_patch_policy\|proxmox-patch\.md"`を`docs/ai/reviews/`を除いて実行し0件を確認済み(新Policy自身の変更履歴に載る歴史的言及1件を除く — §3参照)。

**AC2(`docs/ai/reviews/`配下無変更)**: 満たす。`git status --short -- docs/ai/reviews/`で追跡ファイルの変更0件を確認。案件フォルダの新規ファイル(本ファイル)のみ追加。

**AC3(scope限定表現の除去)**: 満たす。タイトル「Proxmox Operations Policy」、冒頭リード、SB-001冒頭節のいずれも、patchを対象の一つとして列挙する形へ書き換え、「patchに関する」のような排他的表現は残していない。

**AC4(SB-020表への3本追加)**: 満たす。`proxmox_hw_check.yml`・`proxmox_snapshot_check.yml`をsafe行(`proxmox_healthcheck.yml`と同居)へ、`proxmox_backup_restore_verify.yml`をcontrolled apply行として新規追加した。既存の`proxmox_evacuate_node.yml`/`proxmox_restore_vm_placement.yml`の行とは別行にした理由は§3。

**AC5(`check-doc-consistency.py` exit 0)**: 満たす。手順は§4。

**AC6(変更履歴)**: 満たす。§8変更履歴に2026-08-01の行を最上段(既存の降順規約)へ追加。改名理由、scope拡張の対象、追加した3 playbookとその根拠、「既存の許可・禁止・停止条件そのものの内容、SB番号は変更していない」を明記。

**AC7(scope拡張の副作用確認)**: 確認した。初回提出時はPolicy自身の内部条項(§7、§2.3、§7.1〜7.3)だけを照合し、他Policyファイルとの突き合わせを行っていなかった。差し戻しレビューが指摘した「`proxmox_backup_restore_verify.yml`の許可・禁止・停止条件について2つのPolicyが揃って正本を自称する」状態を修正し、現在は結論「新たに違反状態になるplaybookは無いが、正本の二重化が1件生じていたため解消した」。根拠は§5「AC7の分析(改訂版)」。

## 3. 起草の判断根拠(Policy本文の文言)

- **タイトル**: `Proxmox Patch Policy` → `Proxmox Operations Policy`。requirementが`management`でなく`operations`を明示指定しているため従った。
- **冒頭リード(最終版)**: 「patchに関する」を「運用操作(patchの判断・適用、healthcheck、VM/CT退避・復帰、read-only点検を含む。対象入口は§3.1 SB-020が定める)に関する」へ変更。SB-020を対象範囲の一次情報源として明示することで、将来この文書がまた広がったときに「タイトル直下の説明文だけを見て判断」する読み手がSB-020を見落とさない導線にした。**当初は`backup restore検証を含む`をこの列挙に入れていたが、差し戻しにより除外し、代わりに`proxmox_backup_restore_verify.yml`はSB-020の索引としてのみ載り、許可・禁止・停止条件の詳細は`proxmox_backup_restore_verify_policy.md`が正本である旨を明記する1文を追加した**(§5・§10)。
- **SB-001(最終版)**: 「patchを安全に判断、適用、停止するため」→「patch適用と、これに付随する運用操作(healthcheck、VM/CT退避・復帰、read-only点検)を安全に判断、実行、停止するため」。**backup restore検証は当初この列挙に含めていたが、差し戻し後に除外した** — 同playbookの「目的」は`proxmox_backup_restore_verify_policy.md`のBRV-001/BRV-002が既に単独で規定しており、operations_policy側で重ねて述べる必要がない。配下の箇条書き(pve2先行検証、VM/CT保護等)はpatch flowに限定された記述のままでも一般的な目的として無矛盾なため、書き換えなかった(requirement §3「既存の規範文の意味を変えない」の対象と判断)。
- **SB-020表(最終版)**: `proxmox_hw_check.yml`と`proxmox_snapshot_check.yml`は、既存のSB-095が「read-only点検」として名指し済み(`proxmox_hw_check.yml`は既に本文で言及、`proxmox_snapshot_check.yml`は2026-07-30changelogが「patch domain外」としていたが今回の対象)という理由でsafe行へ同居させた。`proxmox_backup_restore_verify.yml`は既存のcontrolled apply行(`guest配置変更。条件付き可`)へ同居させず、独立行にした。理由: 同playbookは「guest配置変更」を行わない(使い捨てVMID 999への月次backup restore・起動確認・破棄であり、本番VMはconfig読み取りのみ)。既存行の許可範囲文言をそのまま流用すると、backup_restore_verifyが実際にはしないguest配置変更を許可されているかのように読める――規範文書レビューの「適用範囲の広狭変化」欠陥クラスを自ら作ることになるため、別行として正確な許可範囲を書いた。**差し戻し後、この行の「許可範囲」セルも書き換えた** — 当初はBRV-009/BRV-071と同内容の許可範囲を独自に記述しており、これが「2つの文書が同じplaybookの許可範囲を独立に記述する」形の正本二重化になっていた。修正後は「detailは`proxmox_backup_restore_verify_policy.md`が正本(本表は自動実行tierの索引のみ)」という、内容を再記述せず先方へ委譲する文言にした。
- **変更履歴**: 既存の行(2026-07-30以前)は一切書き換えず、新規行を追加するだけにした。2026-07-30の行が「`proxmox_snapshot_check`はpatch domain外」と書いている点は、その時点の判断として真であり、本改訂が上書きするものではないため、既存文言は保持している。追加した2026-08-01の行自体は、差し戻し前後で内容を書き直した(バージョン管理された案件記録ではなくPolicy自身の変更履歴であるため、遷移の過程でなく最終的に確定した内容を1行で記述するのが適切と判断し、「一度書いた後に訂正した」という工程の経緯はPolicy側でなく本実装記録側に残す)。

## 4. AC5の実行手順(工程上の注意点)

`scripts/check-doc-consistency.py`はgit indexから読む(working treeではない)。本セッション開始時点で`git status`は次の理由で非cleanだった。

- `.gitignore`・`scripts/git-pre-commit-check.sh`(both modified)
- `scripts/check-doc-consistency.py`・`scripts/tests/`(both untracked)
- `docs/ai/reviews/norm_drift_mechanical_check/`(untracked — 001〜005を含む先行工程の成果物)

これらは本requirement §5で「別工程の成果物であり検証に使うだけ」と明記された対象であり、一切変更していない。

AC5を意味のある検証にするため(indexが変更前のままでは私の改名を検査したことにならない)、次の手順を取った。

1. 私が変更した14ファイル(改名2件 + retarget12件)だけを個別パス指定で`git add`(`-A`は使わない — 上記の別工程ファイルを巻き込まないため)。
2. `python3 scripts/check-doc-consistency.py`を実行 → `[check1] OK (96 compared)` `[check2] OK (8 compared)` `[check3] OK (88 compared)`、exit 0。
3. `git reset`(pathspecなし、mixed reset)で全ステージを解除し、indexをHEADへ戻した。working treeの変更(私の改名・編集)はそのまま残る。
4. `git status --short`で、reset後の状態が`git add`実行前と完全一致することを確認した。

この手順により、「`git add`が実行された状態で報告が返る」ことを避けつつ、AC5が要求する機械的証拠(私の変更を含んだ状態でexit 0)を得た。実行前(改名前)のbaselineでも同一コマンドがexit 0だったことを事前に確認しており、「何も検査していないのに0が出た」ではないことを担保している。

**差し戻し対応後の再実行**: §5・§10の修正(冒頭リード・SB-020該当行・`proxmox.md` L3への正本委譲の明記、Markdownリンク2本の追加)を終えた後、同じ14ファイルで同一手順(add → check → reset)を再実行した。結果は`[check1] OK (96 compared)` `[check2] OK (8 compared)` `[check3] OK (90 compared)`、exit 0。check3の比較件数が88→90に増えたのは、`proxmox_operations_policy.md`から`proxmox_backup_restore_verify_policy.md`への内部リンクを2箇所(冒頭リード、SB-020表の該当行)新設したためであり、想定どおりの増分である(リンク切れの兆候ではない)。reset後、`git status --short`が再度`git add`実行前と一致することを確認した。

## 5. AC7の分析(改訂版 — 他Policyファイルとの突き合わせを含む)

requirementが名指しした懸念(「これまで対象外だったplaybookが、既存の禁止条項に抵触する状態になっていないか」)について、`proxmox_hw_check.yml`・`proxmox_snapshot_check.yml`・`proxmox_backup_restore_verify.yml`それぞれを、Policy全文の禁止・停止条件(§7、§2.3、§7.1〜7.3)と照合した。

- **SB-090「Ansible実行端末はansyまたはquoryに限定する。管理対象host自身から実行せず」は、文言上は"patch"に限定されておらず、scope拡張後は3本にも及ぶ。** しかし実際に技術的preflight(実行端末を検査して拒否する仕組み)を持つのは`weekly_full`だけであり、既にSB-020表に載っている(scope拡張前から)`proxmox_healthcheck.yml`・`proxmox_patch_dryrun.yml`も同じくpreflightを持たない。`proxmox_hw_check.yml`・`proxmox_snapshot_check.yml`は`proxmox_healthcheck.yml`と全く同じrole構成(`proxmox_reachable_nodes`)であり、既存のSB-095が`proxmox_hw_check.yml`を名指しで「read-only点検」と分類済みだったことから、この2本は事実上scope拡張前から同待遇だったと判断できる。したがって、この「preflight未実装」というgapはscope拡張が新規に作ったものではなく、既存in-scope playbookと同一クラスの既存gapであり、**新たな抵触ではない**。
- **§7.1「共通禁止と停止条件」(SB-050〜055)は、いずれも「次nodeへ進まない」という複数node順次パッチのsequencing概念に特化している。** hw_check/snapshot_checkは全nodeを並行に読むだけ、backup_restore_verifyは月1回1nodeで完結し、いずれも「次node」という構造を持たないため、これらの条項は構造的に適用対象がない(違反しようがない)。
- **§2.3(control node別の範囲、SB-047/048/076-079)は文言が「patch対象node」「full flow」「weekly full」を名指ししており、3本のいずれにも該当しない。**
- **§7.3(SB-092/093、Sophos前提)はguest退避に関する規定であり、3本はguestを退避しない(backup_restore_verifyが唯一VMを起動するが、対象は使い捨てVMID 999でSophos VMではない)。** 該当なし。

**初回提出時の欠落: 上記はいずれも`proxmox_operations_policy.md`内部の条項だけを対象にしており、他のPolicyファイルとの突き合わせを行っていなかった。** 差し戻しを受けて`docs/ai/policies/*.md`全体を対象に、新規追加した3 playbookの名前で横断grepを行った。

```
grep -rl "proxmox_hw_check\|proxmox_snapshot_check" docs/ai/policies/*.md
  → proxmox_operations_policy.md のみ(他Policyに言及なし)
grep -n "proxmox_healthcheck.yml\|proxmox_evacuate_node.yml\|proxmox_restore_vm_placement.yml\|proxmox_patch_dryrun.yml\|proxmox_patch_apply_node.yml\|proxmox_patch_weekly_full.yml" docs/ai/policies/*.md
  → proxmox_operations_policy.md 以外では autonomous_recovery_policy.md に3件
```

`autonomous_recovery_policy.md`の3件は、これらplaybook実行中のSlack mute時間契約(`proxmox_evacuate_node.yml`等へ120分、`proxmox_patch_weekly_full.yml`だけ360分)を定めるものであり、**当該playbook自身の許可・禁止・停止条件を規定するものではない**(autonomous_recovery_policy.mdが自らの管轄領域であるmute契約を、他playbookの名前を借りて記述しているだけ)。両Policyが同じ対象について同じ種類の規範(許可・禁止・停止条件)を重ねて主張しているわけではないため、単一正本の原則に反しない。

**発見した抵触: `proxmox_backup_restore_verify.yml`は既に`proxmox_backup_restore_verify_policy.md`(BRV-001〜BRV-084)を持ち、BRV-011が「本Policyに対応するplaybookは`proxmox_backup_restore_verify.yml`の1本とする」と明記し、`docs/ai/context/system/proxmox.md` L3も同Policyを唯一の正本として指していた。** 初回提出の`proxmox_operations_policy.md`は、冒頭リードとSB-001で「backup restore検証」を自らの統括対象として明記し、SB-020表にもBRV-009/BRV-071と同内容の許可範囲を独自に記述していた。これは`proxmox_hw_check.yml`/`proxmox_snapshot_check.yml`のケース(他Policyに記載が無く、追加しても抵触が生じない)とは異なり、**既に単独の正本を持つplaybookへ2つ目の正本を作る**行為であり、requirement §3「既存の規範文の意味を変えない」に反する状態だった。

**修正内容(§3の該当箇所参照):**

1. `proxmox_operations_policy.md`冒頭リードから「backup restore検証を含む」を削除し、代わりに「`proxmox_backup_restore_verify.yml`はSB-020の安全度表に自動実行tierの索引としてのみ含み、その許可・禁止・停止条件の詳細は`proxmox_backup_restore_verify_policy.md`を正本とする」という委譲文を追加。
2. SB-001の目的列挙から「backup restore検証」を削除(同playbookの目的はBRV-001/BRV-002が単独で規定)。
3. SB-020表の該当行の「許可範囲」列を、独自記述から`proxmox_backup_restore_verify_policy.md`への委譲文へ差し替え。**Yoshinobuの指示どおり表からは削除していない**(controlled apply行として残存)。
4. `docs/ai/context/system/proxmox.md` L3に、両Policyの対象は排他的でありbackup_restore_verify.ymlの正本は常にBRV Policyである旨を明記する1文を追加。

修正後、`proxmox_backup_restore_verify.yml`について許可・禁止・停止条件の正本を自称する文書は`proxmox_backup_restore_verify_policy.md`のみになった。`proxmox_operations_policy.md`のSB-020表とproxmox.md L3は、いずれも「同playbookはBRV Policyが正本」と明記したうえでの索引・相互参照であり、規範の二重主張ではない。

**結論: scope拡張によって新たに違反状態になるplaybookは無い。ただし初回提出は正本の二重化を1件見落としており、上記のとおり修正した。** SB-090の一般的文言が名目上及ぶようになった点は、既存のhealthcheck/dry-runと同一水準の構造的gapであり、本requirementが求める「新規の抵触」には該当しないと引き続き判断する。

## 6. 副次的に発見した、対応していない事項(未解決事項)

いずれも今回のscope拡張が原因で生じたものではなく、既存の状態を確認する過程で見つけた。requirement §3「やらないこと」の範囲外と判断し、手を入れていない。

- **`docs/ai/context-classification.md`の「例(将来作成予定)」に`proxmox_operations_policy.md`(旧名)が挙げられている一文自体が既に事実と異なる**(Policyは2026-05-09に作成済みで「未作成」ではない)。ファイル名だけ改名時に合わせて更新したが、「未作成」という記述そのものの誤りは本作業のscope外のため残した。
- **`roles/proxmox_evacuate_node/defaults/main.yml`と`roles/proxmox_restore_vm_placement/defaults/main.yml`のコメントが指す「(5.6)」という節番号は、現行Policyの節構成(5.1〜5.3)に存在しない。** 2026-07-24の標準8節再編で節番号が変わった後に取り残された既存の陳腐化であり、今回のファイル名変更とは無関係。ファイル名だけ更新し、節番号は触れていない。
- **`docs/ai/adr/002-proxmox-patch-dryrun-single-node.md`が引用する行番号(`:99`、`:30`)は、SB-023が既に2026-07-26にSB-094へ置換されているため、当時から既に現物と一致しない。** ADRは意思決定時点の記録として扱い、ファイル名のみ更新し行番号・SB番号への言及は書き換えていない。
- **`docs/ai/adr/008-proxmox-readonly-check-unreachable-node.md`には、本requirementが解消した前提(「`proxmox_snapshot_check`はpatch domain外でPolicyの置き場が無い」)を注記した。** 単純なファイル名置換に留めず一文追加した点は他のADR編集より踏み込んでいるが、この一文はまさに本requirementが変える対象そのものを指しており、無注記のまま残すと規範文書レビューの「撤回した根拠の残存」欠陥クラスに直接該当すると判断したため。
- **`docs/ai/status.md`の該当Watch行**(`proxmox_hw_check.yml`がSB-020表に無い、という項目)は、本実装そのものによって解消される内容だったため、本ファイルへの参照を添えて解消済みである旨を注記した。status.mdの維持はCoordinator/coordinator.mdの領域だが、この行は他ならぬ本diffが直接falsifyする内容であり、無修正のまま残すと「表に無い」という虚偽の現在地情報になるため、既存の同文書内の他行(例: L77「2026-08-01の修正が持ち込んだものではなく既存」)と同じ注記パターンに倣って更新した。Coordinatorの確認を要する。

## 7. Context文書の文言判断

`docs/ai/context/operations/proxmox-operations.md`は、タイトルのみ`Proxmox operations`へ改めたが、本文(「複数roleにまたがるpatch運用の順序と復旧情報を示す」)は書き換えていない。理由: requirement §2.2が明示的にscope拡張を要求したのはPolicy側の3箇所(タイトル・冒頭リード・SB-001)のみであり、この非規範Context自身は実際にpatch flow(control node条件別手順、evacuate/apply/restore、host OS復旧)しか記述していない。healthcheck/hw_check/snapshot_check/backup_restore_verifyの運用手順はこの文書のどこにも書かれていない(各playbookのheader commentと関連ADRが持つ)。タイトルだけを改名済みのファイル名に合わせ、本文の自己申告範囲は実際に書いてある内容に正直なままにした。

## 8. 自己検証で確認したこと

- AC1〜AC7(§2)。
- 変更したファイル集合が requirement §5 の範囲に収まっていること: `git status --short`で、`scripts/check-doc-consistency.py`・`scripts/git-pre-commit-check.sh`・`.gitignore`・`scripts/tests/`・`docs/ai/reviews/`配下(本ファイルを除く)に変更が無いことを確認した(いずれも私の変更前から存在した別工程の差分のまま)。
- `git add`/`git commit`/`git push`が実行された状態で終わっていないこと: §4の手順どおり`git reset`で復元し、`git status --short`が`git add`実行前と一致することを確認した。
- 本ファイルが参照するパス(新Policy・新Context)が実在すること: `ls`で確認済み。
- 実ホストへは一切接続していない(Ansible実行なし、`ansible-playbook`/`ansible`コマンドは未実行)。
- **差し戻し対応後**: `proxmox_backup_restore_verify.yml`について正本を自称する文書が`proxmox_backup_restore_verify_policy.md`だけになったこと(`proxmox_operations_policy.md`冒頭リード・SB-001・SB-020該当行、`docs/ai/context/system/proxmox.md` L3の4箇所を目視で再確認)。SB-020表から同playbookを削除していないこと(表の行として現存することを確認)。2つのPolicyファイルを統合していないこと(両ファイルとも独立して存在し、`docs/ai/policies/`配下のファイル数は`git ls-tree -r HEAD --name-only -- docs/ai/policies/ | wc -l`で確認したHEAD時点の11本と、改名後の`ls docs/ai/policies/ | wc -l`が一致し、増減が無い)。AC1〜AC6が差し戻し後も引き続き満たされること(§2、§4)。

## 9. 未解決事項(Coordinatorの判断を要するもの)

- §6に列挙した5件の副次的発見。いずれも本作業のscope外だが、特に`docs/ai/status.md`の注記(L76)はCoordinatorの確認・整形を要する。
- Policy本文(タイトル・冒頭リード・SB-001・SB-020表・変更履歴)の文言は、Implementerとして起草したが、requirement冒頭に明記されている通りYoshinobuの最終承認が必要である。

## 10. 差し戻しで却下されたレビュー指摘(対応していない)

差し戻しメッセージにより、次の指摘は明示的に却下され、対応しないよう指示された。黙って無視した形にしないため、指摘内容と却下理由をここに記録する。

**指摘**: SB-020表で`proxmox_backup_restore_verify.yml`を`controlled apply`に分類した根拠が、playbook冒頭コメントの文字列(`Monthly VM backup restore-verify (controlled apply).`)との一致に依っており、実際の`# tester-gate: risk-accepted`ヘッダに依るべきである。

**却下理由(Coordinatorが提示)**: `docs/ai/reviews/norm_drift_mechanical_check/2026-08-01_001_survey.md` §3.2が確認済みのとおり、SB-020の4値(safe / semi-safe / controlled apply / unsafe)とtester-gateの5値(safe-readonly / role-guarded / risk-accepted / check-mode-native / dry-run-aware)は語彙も軸も異なる。SB-020は「自動実行を許すか」という自動化安全度の軸、tester-gateは「検証時にどう実行するか」という検証手法の軸であり、両者の対応表はどこにも定義されていない。tester-gateの値からSB-020の値を機械的に導出することは、この独立した2軸を混同する。playbook自身がSB-020と同じ語彙(`controlled apply`)で自己分類していることのほうが、SB-020表への追加根拠として適切である。

この却下判断はCoordinatorから明示された契約要素であり、Implementerとして再度提起しない。
