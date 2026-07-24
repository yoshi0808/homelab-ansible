# 要求仕様: proxmox_backup_restore_verify_policy.md の標準構造への書換(個別書換④)

## 1. 問題定義

`docs/ai/policy-migration-map.md`の10文書×8セクション対応表で、`proxmox_backup_restore_verify_policy.md`(10KB、217行)の欠落は「変更履歴」のみ。他の標準7セクション(目的／対象と実行範囲／対応するPlaybook／判断軸／ライフサイクル・処理フロー／通知方針／制約・禁止事項)は全て「対応」済みで、「対応するPlaybook」は既に標準名見出しを持つ。

個別書換の優先順位案(同ファイル131行)の所見: 「lifecycleと安全装置は明確だが変更履歴がなく、実装詳細をRepository Contextへ寄せる余地がある」。前3件(proxmox_patch/autonomous_recovery/ubuntu_vm_patch)より軽量な案件と見込む。

## 2. ゴール

`proxmox_backup_restore_verify_policy.md`を標準8セクション構成へ再編する。前3件と同じ2段階(範囲超過候補の洗い出し→書換)で進めるが、既に大半のセクションが標準に近いため、作業の中心は(a)変更履歴の新設、(b)実装詳細でRepository Context相当のものがあれば分離、の2点になる見込み。

## 3. 非ゴール

- Playbook / roleのコード変更。振る舞いは一切変えない、ドキュメントの再構成のみ。
- `proxmox_backup_restore_verify_policy.md`以外のPolicy文書の書換(優先順位⑤以降は別依頼)。

## 4. 要件(MoSCoW)

**P0(Must)**:
- 本文書のPolicy範囲超過候補(該当があれば)を行単位で洗い出し、移動先を決定した表を作成する。特に「9. 制約」L182-189と「10. スコープ」L193-204が2見出しに分かれている点を確認し、標準「制約・禁止事項」への統合が適切か判断する。
- 標準8セクションへ再編する。
- 変更履歴セクションを新設する。
- 許可・禁止・停止条件、正常性判定・ロック方針・cleanup判定の判断軸は意味を変えず残す。

**P1(Should)**:
- 移動先ファイルが既存の他Policy・Contextと重複・矛盾しないか確認する。

## 5. 制約

- 実装コード(`playbooks/`、`roles/`)は一切変更しない。
- 安全境界(許可/禁止/停止条件、判断軸)の意味変更は行わない。
- IPアドレス・VLAN ID・VM ID・認証情報の実値は書かない。実値が残っていれば是正する。
- 秘密情報を書かない。

## 6. 受入条件(Given/When/Then)

- Given 書換前の`proxmox_backup_restore_verify_policy.md`が存在する状態で、When 書換を実施したとき、Then 新しい`proxmox_backup_restore_verify_policy.md`が標準8セクション構成になっている。
- Given 新旧の`proxmox_backup_restore_verify_policy.md`が存在する状態で、When Reviewerが許可・禁止・停止条件・判断軸を原文と新文書で1行ずつ突き合わせたとき、Then 意味が変わっていないことが確認されている。
- Given 書換作業が完了した状態で、When `git diff`を確認したとき、Then `playbooks/`・`roles/`・他Policyファイルに意図しない変更がない。

## 7. 成果物

- 書換後の`docs/ai/policies/proxmox_backup_restore_verify_policy.md`
- 新規作成または追記した移動先ファイル(該当があれば)
- `docs/ai/reviews/policy_standardization/`配下の作業記録(investigation/implement/review)

## 8. プロセス上の要望

前3件と同様、Reviewerは新旧Policyの許可・禁止・停止条件・判断軸を1行ずつ突き合わせる検証を必須で行うこと。ただし本文書は既に標準構造に近いため、Tier判定は前3件より軽くなる可能性がある。Tier判定・implementer2/reviewer2への割り振りは通常どおり担当Tech Leadに委ねる。
