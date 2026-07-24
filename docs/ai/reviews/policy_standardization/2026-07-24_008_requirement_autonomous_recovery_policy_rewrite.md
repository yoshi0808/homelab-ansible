# 要求仕様: autonomous_recovery_policy.md の標準構造への書換(個別書換②)

## 1. 問題定義

`docs/ai/policy-migration-map.md`の10文書×8セクション対応表で、`autonomous_recovery_policy.md`(27KB、288行、Policy 9本中2番目に大きい)には次の欠落がある。

- 「対応するPlaybook」: 未整備。標準見出しがなく、入口は「5. 検知経路」L163-205と「8. 人間による手動レイヤー実行」L251-263に散在。
- 「変更履歴」: 未整備。見出しなし。

個別書換の優先順位案(同ファイル126-136行)でも本文書が第2位で、所見は「実装・アカウント・鍵・wrapper詳細が大きく、標準Playbook見出しと変更履歴がない。権限・禁止・ラダーだけをPolicy核にする」。ただし`proxmox_patch_policy.md`のときのような行単位の「Policy範囲超過候補」表はまだ作成されていない。

## 2. ゴール

`autonomous_recovery_policy.md`を標準8セクション構成(目的／対象と実行範囲／対応するPlaybook／判断軸／ライフサイクル・処理フロー／通知方針／制約・禁止事項／変更履歴)へ再編する。`proxmox_patch_policy.md`のときと同じ2段階で進める。

1. まず本文書の「Policy範囲超過候補」(実装詳細、アカウント・鍵・wrapperの具体値、Repository/Operations Context相当の内容)を行単位で洗い出し、移動先を決定する(`proxmox_patch_policy.md`のときの範囲超過表と同じ形式)。
2. 洗い出しに基づき、Policy核(許可・禁止・停止条件、復旧ラダーの判断軸)だけを残して書き換える。

## 3. 非ゴール

- Playbook / roleのコード変更。振る舞いは一切変えない、ドキュメントの再構成のみ。
- `autonomous_recovery_policy.md`以外のPolicy文書の書換(優先順位③以降は別依頼)。
- recovery系playbook群(`recovery_probe_setup.yml`、`recovery_exec_setup.yml`、`recovery_io_setup.yml`、`recovery_push_setup.yml`、`recovery_push_drill_setup.yml`、`recovery_ha_failover.yml`、`recovery_service_restart.yml`、`recovery_vm_reboot.yml`、`recovery_probe_notify.yml`)の実装是非そのものの見直し。

## 4. 要件(MoSCoW)

**P0(Must)**:
- 本文書のPolicy範囲超過候補を行単位で洗い出し、移動先(System Context/Repository Context/Skill/Operations Context/Issue)を決定した表を作成する(`proxmox_patch_policy.md`のときと同じ形式)。特にアカウント・鍵・wrapperの実装詳細を精査する。
- 標準8セクションへ再編する。「対応するPlaybook」を標準見出しとして新設し、上記recovery系playbook群を列挙する。
- 権限・禁止・復旧ラダーの判断軸(probe失敗回数、flapping判定、mute/global pauseのskip・再開gate等)を意味を変えず残す。
- 変更履歴セクションを新設する。

**P1(Should)**:
- 移動先ファイルが既存の他Policy・Contextと重複・矛盾しないか確認する。

## 5. 制約

- 実装コード(`playbooks/`、`roles/`)は一切変更しない。
- 安全境界(許可/禁止/停止条件、復旧ラダーの判断条件)の意味変更は行わない。
- IPアドレス・VLAN ID・VM ID・認証情報の実値は書かない。既に本文書にそのような実値が残っている場合は、この機会に是正する(Repository/System Contextへ移す際も実値を書かない)。
- 秘密情報を書かない。

## 6. 受入条件(Given/When/Then)

- Given 書換前の`autonomous_recovery_policy.md`が存在する状態で、When 書換を実施したとき、Then 新しい`autonomous_recovery_policy.md`が標準8セクション構成になっている。
- Given Policy範囲超過候補の洗い出し表が作成された状態で、When 書換を実施したとき、Then 各項目が移動先ファイルへ反映済み、またはPolicy核として新Policy本文に残っている。
- Given 新旧の`autonomous_recovery_policy.md`が存在する状態で、When Reviewerが許可・禁止・停止条件・復旧ラダーの判断軸を原文と新文書で1行ずつ突き合わせたとき、Then 意味が変わっていないことが確認され、差異があれば全て記録されている。
- Given 書換作業が完了した状態で、When `git diff`を確認したとき、Then `playbooks/`・`roles/`・他Policyファイルに意図しない変更がない。

## 7. 成果物

- 書換後の`docs/ai/policies/autonomous_recovery_policy.md`
- 新規作成または追記した移動先ファイル
- `docs/ai/reviews/policy_standardization/`配下の作業記録(investigation/implement/review)

## 8. プロセス上の要望

`proxmox_patch_policy.md`のときと同様、Reviewerは新旧Policyの許可・禁止・停止条件・判断軸を1行ずつ突き合わせる検証を必須で行うこと。Tier判定・implementer2/reviewer2への割り振りは通常どおり担当Tech Leadに委ねる。
