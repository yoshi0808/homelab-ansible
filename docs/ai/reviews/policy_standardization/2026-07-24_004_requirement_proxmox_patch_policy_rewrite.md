# 要求仕様: proxmox_patch_policy.md の標準構造への書換(索引作成の次工程)

## 1. 問題定義

`docs/ai/policy-migration-map.md`(2026-07-24作成)で、`proxmox_patch_policy.md`(68KB、2007行)が標準8セクション構成から大きく逸脱し、Policy(許可・禁止・停止条件の定義)の範囲を超える内容(System Context相当、Repository Context相当、Skill相当、Operations Context相当、Issue/project plan相当)を18箇所にわたり抱えていることが判明した(同ファイル100-125行目「`proxmox_patch_policy.md`のPolicy範囲超過候補」表)。個別書換の優先順位案でも本文書が第1位。

## 2. ゴール

`docs/ai/policy-migration-map.md`の範囲超過表と標準テンプレート(目的／対象と実行範囲／対応するPlaybook／判断軸／ライフサイクル・処理フロー／通知方針／制約・禁止事項／変更履歴)に従い、`proxmox_patch_policy.md`を実際に書き換える。Policy核(許可・禁止・停止条件)だけを残し、範囲外の内容を範囲超過表が示す移動先(System Context/Repository Context/Skill/Operations Context/Issue)へ分離する。

## 3. 非ゴール

- Playbook / roleのコード変更。振る舞いは一切変えない、ドキュメントの再構成のみ。
- 他のPolicy文書(`autonomous_recovery_policy.md`以下)の書換。優先順位②以降は別依頼とする。
- 移動先Context/Skill/Issueの内容そのものの新規設計。範囲超過表が既に移動先候補を示しているものはそれに従う。移動先候補が複数(例: 「Skill/Repository Context」)の場合、担当Tech Leadが実際の受け皿として最も適切な1つを選び、選定理由を記録する。

## 4. 要件(MoSCoW)

**P0(Must)**:
- `proxmox_patch_policy.md`を標準8セクション構成に再編する。
- 範囲超過表(18項目、L100-125)の各項目について、該当箇所を適切な移動先ファイルへ移す(新規作成または既存ファイルへの追記)。移動先ファイルが存在しない場合は新規作成する。
- 各項目の「Policyへ残す核」欄が示す許可・禁止・停止条件は、**意味を変えず**(緩めず、厳しくもせず)新しいPolicy本文へ残す。特に以下は一言一句慎重に扱う:
  - §11.6 停止する条件(L1304-1319)
  - §13 BLOCKED時のContingency Plan(L1356-1412)
  - §16.8.3 apply停止条件(L1785-1789)
  - §18.1 OS rollbackを原則行わず再インストールする(L1888-1893)
  - §19/§20 Sophos稼働時の安全前提・patch制約(L1933-1960、Policy核部分のみ)
- 変更履歴セクションを新設し、今回の再構成を最初のエントリとして記録する。
- 「対応するPlaybook」セクションを標準名で新設する(現行は「6. Playbook分離方針」という別名見出し)。

**P1(Should)**:
- 移動先ファイルが既存の他Policy・Contextと重複・矛盾しないか確認する。

## 5. 制約

- 実装コード(`playbooks/`、`roles/`)は一切変更しない。
- 安全境界(許可/禁止/停止条件)の意味変更は行わない。
- IPアドレス・VLAN ID・VM ID・認証情報の実値は書かない。
- 秘密情報を書かない。

## 6. 受入条件(Given/When/Then)

- Given 書換前の`proxmox_patch_policy.md`が存在する状態で、When 書換を実施したとき、Then 新しい`proxmox_patch_policy.md`が標準8セクション構成になっている。
- Given 範囲超過表の18項目が存在する状態で、When 書換を実施したとき、Then 各項目が移動先ファイルへ反映済み、またはPolicy核として新Policy本文に残っている(表の指示通り)。
- Given 新旧の`proxmox_patch_policy.md`が存在する状態で、When Reviewerが安全境界(許可/禁止/停止条件の実質的な意味)を原文と新文書で1行ずつ突き合わせたとき、Then 意味が変わっていないことが確認され、差異があれば全て記録されている。
- Given 書換作業が完了した状態で、When `git diff`を確認したとき、Then `playbooks/`・`roles/`・他Policyファイルに意図しない変更がない。

## 7. 成果物

- 書換後の`docs/ai/policies/proxmox_patch_policy.md`
- 新規作成または追記した移動先ファイル(System Context/Repository Context/Skill/Operations Context/Issue、範囲超過表に従う)
- `docs/ai/reviews/policy_standardization/`配下の作業記録(investigation/implement/review)
- 安全境界の新旧突き合わせ結果(Reviewerの検証記録として残す)

## 8. プロセス上の要望

安全境界の意味変更リスクが高いため、Reviewerは通常のレビューに加えて「新旧Policyの許可・禁止・停止条件を1行ずつ突き合わせ、意味が変わっていないことを明示的に確認する」工程を必ず行うこと。Tier判定・implementer2/reviewer2への割り振りは通常どおり担当Tech Leadに委ねる。
