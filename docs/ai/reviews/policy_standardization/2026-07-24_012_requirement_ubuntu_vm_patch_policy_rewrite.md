# 要求仕様: ubuntu_vm_patch_policy.md の標準構造への書換(個別書換③)

## 1. 問題定義

`docs/ai/policy-migration-map.md`の10文書×8セクション対応表で、`ubuntu_vm_patch_policy.md`(13KB、289行)には次の欠落・不統一がある。

- 「対応するPlaybook」: 別名見出し「5. Playbook構成」L133-173で内容自体はあるが、標準名に未統一。
- 「制約・禁止事項」: 未整備。独立した見出しがなく、規範は「3. パッチ適用方針」L47-91と「4. reboot方針」L95-129に散在。
- 「変更履歴」: 未整備。見出しなし。

個別書換の優先順位案(同ファイル130行)の所見: 「apt/非apt/reboot/healthcheckが混在し、標準Playbook・制約・変更履歴を整える必要がある。目的別groupとの境界も同時に明示する」。

**既知の未解決事項(重要、今回は解消しない)**: `docs/ai/context/ansible/playbook-map.md`末尾「Policy整合の注意」に記録済みだが、`prometheus_update_check.yml`のPolicy候補である本書§3.4は、非apt Prometheusの自動download・自動更新・service restartを禁止している。一方、現行playbook/roleは確認入力に基づく更新・rollback機能を持ち、Policy記述と実装が一致していない。これはIssue化候補として既に記録されており、**本件(構造の標準化)では解消しない**。

## 2. ゴール

`ubuntu_vm_patch_policy.md`を標準8セクション構成へ再編する。`proxmox_patch_policy.md`・`autonomous_recovery_policy.md`と同じ2段階(範囲超過候補の洗い出し→書換)で進める。

## 3. 非ゴール

- Playbook / roleのコード変更。振る舞いは一切変えない、ドキュメントの再構成のみ。
- **§3.4のPolicy記述と`prometheus_update_check.yml`実装の不一致を解消すること**。今回は構造の標準化(セクション名・配置)のみを扱い、記述内容とコードの整合性チェックは別Issueとする。再編の過程でこの箇所の文言を動かす場合も、既存の規範文言の意味を変えない(緩めない・厳しくしない)。動かした結果、この不一致がより見えやすくなること自体は問題ない。
- `ubuntu_vm_patch_policy.md`以外のPolicy文書の書換(優先順位④以降は別依頼)。
- `docs/ai/policy-migration-map.md`の目的別group案(特にgroup2「アプリ・パッケージ更新」)の実際の統合作業。今回はPolicy本文の構造整理のみ。

## 4. 要件(MoSCoW)

**P0(Must)**:
- 本文書のPolicy範囲超過候補(該当があれば)を行単位で洗い出し、移動先を決定した表を作成する。
- 標準8セクションへ再編する。「対応するPlaybook」を標準見出し名にする(内容は既存の「5. Playbook構成」を踏襲)。
- 「制約・禁止事項」を独立見出しとして新設し、「3. パッチ適用方針」「4. reboot方針」に散在する禁止・停止条件を集約する(元の文言の意味は変えない)。
- 変更履歴セクションを新設する。
- §3.4(prometheus_update_check.yml関連)の記述は、位置が変わっても文言の意味を変えない。既知の不一致(実装との齟齬)については、新Policy内に「実装との不一致が既知の未解決事項としてplaybook-map.mdに記録されている」旨を一言添えてもよい(必須ではない)。

**P1(Should)**:
- `docs/ai/policy-migration-map.md`のgroup2案(アプリ・パッケージ更新)との境界(`ubuntu_nightly.yml`をreboot lifecycle従属として扱う等)を踏まえ、本Policyの「対象と実行範囲」がgroup2の対象playbook群と矛盾しないか確認する。矛盾があれば指摘のみ行い、解消は次工程とする。

## 5. 制約

- 実装コード(`playbooks/`、`roles/`)は一切変更しない。
- 安全境界(許可/禁止/停止条件、判断軸)の意味変更は行わない。既知の実装不一致(§3.4)を今回のタイミングで「実装に合わせてPolicyを書き換える」形で解消しない。
- IPアドレス・VLAN ID・VM ID・認証情報の実値は書かない。実値が残っていれば是正する。
- 秘密情報を書かない。

## 6. 受入条件(Given/When/Then)

- Given 書換前の`ubuntu_vm_patch_policy.md`が存在する状態で、When 書換を実施したとき、Then 新しい`ubuntu_vm_patch_policy.md`が標準8セクション構成になっている。
- Given 新旧の`ubuntu_vm_patch_policy.md`が存在する状態で、When Reviewerが許可・禁止・停止条件・判断軸を原文と新文書で1行ずつ突き合わせたとき、Then 意味が変わっていないことが確認され、§3.4の既知の不一致も文言レベルでは変化していないことが確認されている。
- Given 書換作業が完了した状態で、When `git diff`を確認したとき、Then `playbooks/`・`roles/`・他Policyファイルに意図しない変更がない。

## 7. 成果物

- 書換後の`docs/ai/policies/ubuntu_vm_patch_policy.md`
- 新規作成または追記した移動先ファイル(該当があれば)
- `docs/ai/reviews/policy_standardization/`配下の作業記録(investigation/implement/review)

## 8. プロセス上の要望

前2件と同様、Reviewerは新旧Policyの許可・禁止・停止条件・判断軸を1行ずつ突き合わせる検証を必須で行うこと。特に§3.4は「文言が変わっていないこと」を明示的に確認すること(既知の不一致を今回拡大も縮小もしないため)。Tier判定・implementer2/reviewer2への割り振りは通常どおり担当Tech Leadに委ねる。
