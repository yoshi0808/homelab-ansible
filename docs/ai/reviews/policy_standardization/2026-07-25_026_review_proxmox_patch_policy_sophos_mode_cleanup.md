# Code Review: proxmox_patch_policy.md 陳腐化記述・宙ぶらりん参照・冗長規範の整理

対象:
- `docs/ai/reviews/policy_standardization/2026-07-25_024_requirement_proxmox_patch_policy_sophos_mode_cleanup.md`(要件書、レビュー観点7項目)
- `docs/ai/reviews/policy_standardization/2026-07-25_025_implement_proxmox_patch_policy_sophos_mode_cleanup.md`(実装報告)
- `docs/ai/policies/proxmox_patch_policy.md`、`docs/ai/context/operations/proxmox-patch.md` の現在のgit差分
- `roles/proxmox_evacuate_node/tasks/main.yml`、`roles/proxmox_patch_dryrun/tasks/main.yml`、`playbooks/proxmox_patch_weekly_full.yml`(安全境界確認のための直接確認)
- `docs/ai/policies/autonomous_recovery_policy.md`(相互参照先の直接確認)

軽量レーン(Tier2)。要件書がreviewer必須と明示した7項目を全て独立に確認した。

## Summary

Policy文書のみの変更で実装コード差分はゼロ。要件書の変更1〜10は`git diff`全hunkの逐語突き合わせで完全一致を確認した。SBマーカー台帳(89件)は期待集合と完全一致(重複なし、退番4件消滅、新規3件各1回)。`Mode A`/`Mode B`・「移行前」表現の残存なし。最重要観点である安全境界の非緩和は、`roles/proxmox_evacuate_node/tasks/main.yml`のPhase 6実装とSB-091の文言を直接突き合わせ、`roles/proxmox_patch_dryrun`のcluster集約判定と`proxmox_patch_weekly_full.yml`の`_weekly_full_skip_statuses`(`NO_UPDATES`含む)を直接読んで確認し、いずれも独立の機構で担保されていることを確認した。blocking指摘なし。

## Critical Issues

なし。

## 要件書レビュー観点7項目の確認結果

### 1. 逐語一致

変更1〜10それぞれについて、要件書のbefore/after文字列と`git diff`の実際のhunkをテキスト単位で突き合わせた。全10箇所とも指定どおりで、言い換え・要約・追加解釈は見つからなかった。

### 2. SBマーカー台帳

`grep -oE '<!-- SB-[0-9]{3} -->'`で全マーカーを独立抽出し、「SB-001〜SB-090から退番4件(049/083/084/086)を除いた86件 + 新規3件(091/092/093)」の期待集合と`diff`で突き合わせた。

```
$ diff <期待集合(89件、sort済み)> <実マーカー(89件、sort済み)>
(差分なし)
```

- 重複: `uniq -d`で0件。
- 退番SB-049/083/084/086: `grep`で本文から消滅を確認。
- 新規SB-091/092/093: 各1回だけ存在。
- それ以外の欠落: 期待集合との完全一致により欠落なしを確認。

### 3. 宙ぶらりん参照の消滅

```
$ grep -n "Mode A\|Mode B" docs/ai/policies/proxmox_patch_policy.md docs/ai/context/operations/proxmox-patch.md
405:| 2026-07-25 | ...定義が存在しない`Mode A` / `Mode B`参照を条件記述へ置換。... |
```

本文中の実参照(旧SB-080)は変更6で条件記述に置換済みで消滅。唯一残るのは変更9で追加した変更履歴行内の記述で、これは要件書の指定文言そのものであり、定義なき本文参照(宙ぶらりん参照)には該当しない。

### 4. 陳腐化の掃引

```
$ grep -n "移行前\|移行する前" docs/ai/policies/proxmox_patch_policy.md docs/ai/context/operations/proxmox-patch.md
(出力なし)
```

Sophos移行完了前を前提とした表現は残っていない。

### 5. 安全境界の非緩和(最重要)

**SB-014分割(SB-091新設)**: `roles/proxmox_evacuate_node/tasks/main.yml` Phase 6(L216-262)を直接確認した。`Find remaining running VMs/CTs on target node`(L222-232)のselect条件は`type`/`node`/`status`のみで**tagによる絞り込みを一切含まない**。続く強制停止(L242-258)も同じ`_remaining_running`をtag無関係にloopする。これはSB-091の文言「tagの有無や分類に関わらず、残存するrunning guestは強制停止する」と一致する。旧SB-014の「tagなしguestは...最終確認で停止する」という書き方はむしろ対象をtagなしguestに限定して読める点で実装より曖昧であり、分割後のSB-091の方が実装に忠実である。保証は弱まっていない。

**SB-049削除**: `roles/proxmox_patch_dryrun/tasks/main.yml` L89-104の`_pre_status`判定を直接確認した。`NO_UPDATES`は`unified_dryrun.cluster_summary.total_unique_updates == 0 and total_unique_removes == 0`というcluster集約値のみで決まり、per-node値では決まらない。`playbooks/proxmox_patch_weekly_full.yml` L156-166を直接確認し、`_weekly_full_skip_statuses`に`NO_UPDATES`が含まれ、該当時は`_weekly_full_skip: true`を設定して以降の全apply系play(L224, 232, 266, 274, 282, 316など)を`when: not (...skip...)`でskipすることを確認した。SB-049が定めていた「pve2だけ手動適用済みでもcluster集約でNO_UPDATESならapplyされない」という帰結は、SB-049の文言を介さずこの独立した機構で既に担保されている。SB-049削除によって新たにapplyされる経路は生まれていない。

### 6. 相互参照の妥当性

`docs/ai/policies/autonomous_recovery_policy.md`を直接読み、SB-093が参照する内容を確認した。

- L76(probe閾値): `` `sophos-fw`はicmpとdnsの両probeについて5回連続失敗を発火閾値とする。`` — 要件書の引用と一致。
- L119(mute契約): `proxmox_evacuate_node.yml`は120分、`proxmox_patch_apply_node.yml`は60分、`proxmox_restore_vm_placement.yml`は90分、`proxmox_patch_weekly_full.yml`は360分(いずれも`authy`/`monnie`/`sophos-fw`の3 target) — 要件書の引用と一致。SB-093本文は具体的な分数を再掲せず`autonomous_recovery_policy.md`への参照のみに留めており、数値の二重管理・将来の値ズレを避ける書き方になっている。

あわせてSB-092が内部参照する`SB-012`(L44-45、apply前のVM/CT所在確認・退避復帰を含める)、`SB-018`(L50-51、migration許可)も実在し、SB-092の要約と整合することを確認した。

### 7. scope

```
$ git diff --stat -- playbooks/ roles/
(出力なし)
$ git diff --stat -- docs/ai/policies/ | grep -v proxmox_patch_policy.md
1 file changed, 13 insertions(+), 27 deletions(-)   ← proxmox_patch_policy.md自身の集計行のみで、他Policyファイル名は出現しない
```

playbooks/roles差分ゼロ、`proxmox_patch_policy.md`以外のPolicyファイル差分ゼロを確認した。`autonomous_recovery_policy.md`への言及はSB-093内のMarkdownリンク追加のみで、同ファイル自体は未編集。

## Suggestions

なし。

## What Looks Good

- SB-091を「tagなしguest向けの個別処理ではなく...終端不変条件」と明記したことで、旧SB-014の曖昧さ(tagなしguest限定に読める)を解消し、実装(全running guestを無条件force-stop)との一致度が上がった。
- SB-049削除にあたり、消える規範の実質を機構(cluster集約判定 + `_weekly_full_skip_statuses`)で代替できることをrequirement段階で先に検証してから削除している。Policy文書の整理が実装の安全境界を暗黙に変えていないかを裏付けで確認できる。
- SB-093がmute契約の具体的分数を再掲せず参照リンクに留めた設計は、`autonomous_recovery_policy.md`側の値が将来変わってもPolicy間の不整合が生まれない。
- 変更履歴(§8)に退番SB番号を明記し、Yoshinobu/AIが将来同じ番号を誤って再利用しないようにしている。

## Verdict

**Approve**

要件書が指定したレビュー観点7項目は全てPASS。blocking指摘なし。
