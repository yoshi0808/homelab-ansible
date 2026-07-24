# 要求仕様: 残り6文書の標準構造への書換(個別書換⑤〜⑦、まとめて依頼)

## 1. 問題定義

`docs/ai/policy-migration-map.md`の個別書換の優先順位案(126-134行)のうち、①〜④(proxmox_patch/autonomous_recovery/ubuntu_vm_patch/proxmox_backup_restore_verify)は完了した。残る6文書は軽量な作業と見込まれるため、まとめて1件の案件として依頼する。

## 2. ゴール

以下6文書を、それぞれの欠落度合いに応じて標準構造へ整える。

### 2.1 core.md(優先順位⑤)

migration mapの所見(132行): 「個別Policyテンプレートを機械適用せず、変更履歴だけを共通原則の保守方式として整える」。**8セクションの個別Policyテンプレートは適用しない**。変更履歴セクションのみ新設する。対応するPlaybook・ライフサイクル・通知方針は「該当なし」(migration map 28行の判定通り)であり、無理に見出しを作らない。

### 2.2 log_observability_policy.md(優先順位⑥)

migration mapの所見(133行): 「現行通知方針と将来アラート構想を分離し、現状構成・検証結果をContextへ寄せる」。索引本体(40行目)では「通知方針」が未整備("「5. Phaseロードマップ」L90に将来のSlack構想のみあり、現行通知方針なし")。**現状、現行の通知方針が本当に存在しないのか、単に未文書化なのかを担当Tech Leadが判断すること**。存在しないなら標準「通知方針」セクションは「該当なし(未実装)」として明示し、無理に作文しない。将来構想と現状構成の分離、実装詳細のContext移動は行う。

### 2.3 cert_renew_cloudkey_policy.md、cert_renew_policy.md、time_sync_check_policy.md、unifi_backup_fetch_policy.md(優先順位⑦)

migration mapでは8セクション全て「対応」済み(見出し名の表記だけが標準と異なる)。**内容の意味は変えず、見出し名を標準8セクション名(目的／対象と実行範囲／対応するPlaybook／判断軸／ライフサイクル・処理フロー／通知方針／制約・禁止事項／変更履歴)へ統一するだけ**でよい。範囲超過の洗い出しは軽く確認する程度でよく、大規模な内容移動は想定しない。

## 3. 非ゴール

- Playbook / roleのコード変更。振る舞いは一切変えない、ドキュメントの再構成のみ。
- core.mdへ個別Policyの8セクションテンプレートを機械適用すること(2.1参照)。
- log_observability_policy.mdの「現行通知方針」を、存在しないのに新規に作文すること(2.2参照)。

## 4. 要件(MoSCoW)

**P0(Must)**:
- core.md: 変更履歴セクションのみ新設。他は現状構成を維持。
- log_observability_policy.md: 標準8セクションへ再編(該当なしの扱いは2.2の判断に従う)。将来構想と現状の分離。
- cert_renew_cloudkey_policy.md、cert_renew_policy.md、time_sync_check_policy.md、unifi_backup_fetch_policy.md: 見出し名を標準名へ統一。内容の意味は変えない。

**P1(Should)**:
- 4文書(cert_renew系2本、time_sync_check、unifi_backup_fetch)について、見出し統一の過程で軽微な範囲超過(実装詳細等)が見つかれば指摘する。今回の書換で必ず解消する必要はない。

## 5. 制約

- 実装コード(`playbooks/`、`roles/`)は一切変更しない。
- 安全境界(許可/禁止/停止条件、判断軸)の意味変更は行わない。
- IPアドレス・VLAN ID・VM ID・認証情報の実値は書かない。実値が残っていれば是正する。
- 秘密情報を書かない。

## 6. 受入条件(Given/When/Then)

- Given 書換前の6文書が存在する状態で、When 書換を実施したとき、Then 各文書がそれぞれの2.1〜2.3の方針に従って再編されている。
- Given 新旧の6文書が存在する状態で、When Reviewerが許可・禁止・停止条件・判断軸を原文と新文書で突き合わせたとき、Then 意味が変わっていないことが確認されている(見出し統一のみの4文書は軽い突合でよい、core.md/log_observability_policy.mdは前4件と同水準の突合を行う)。
- Given 書換作業が完了した状態で、When `git diff`を確認したとき、Then `playbooks/`・`roles/`・他Policyファイルに意図しない変更がない。

## 7. 成果物

- 書換後のcore.md、log_observability_policy.md、cert_renew_cloudkey_policy.md、cert_renew_policy.md、time_sync_check_policy.md、unifi_backup_fetch_policy.md
- 新規作成または追記した移動先ファイル(該当があれば、主にlog_observability_policy.md関連)
- `docs/ai/reviews/policy_standardization/`配下の作業記録

## 8. プロセス上の要望

軽量レーンとして扱ってよい(`docs/ai/memory/lessons/`の工程重量の教訓を参照)。ただしcore.md・log_observability_policy.mdは前4件と同水準の1行突き合わせを行い、見出し統一のみの4文書は範囲超過の軽い確認に留めてよい。implementer2への複数ファイル一括割り当て、reviewer2による一括確認も可。Tier判定・割り振りは通常どおり担当Tech Leadに委ねる。全て完了したら、これで`docs/ai/policy-migration-map.md`の個別書換優先順位案①〜⑦が完走する。
