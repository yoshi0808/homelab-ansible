# Ubuntu VM Patch Policy 標準構造書換 Phase 2 実装記録

## 1. 実装範囲と正本

- requirement: `2026-07-24_012_requirement_ubuntu_vm_patch_policy_rewrite.md`
- investigation: `2026-07-24_013_investigation_ubuntu_vm_patch_policy_rewrite.md`
- 旧Policy正本: Git HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `bf8cee43f3789dbae1b0a524f84fdb694a5445c7`、289行
- 移行契約: 範囲超過候補16行、UV-001〜UV-083、013 §4.4の逐行照合規則
- 未実施: playbook / role /他Policy / map / requirement / 013の編集、実機・Ansible実行、§3.4の既知実装不一致の解消

IP、VLAN ID、VM ID、認証情報、秘密情報の実値は5成果物へ転載していない。node名、時刻、service portは旧Policyの規範または実装契約を追跡する非秘密値として区別した。

## 2. 変更ファイル

| path | 操作 | 結果 |
|---|---|---|
| `docs/ai/policies/ubuntu_vm_patch_policy.md` | 全面再編 | 標準8節、UV marker 83件、対応playbook 5本 |
| `docs/ai/context/system/ubuntu-vm-patch.md` | 新規 | node、Ubuntu Pro、reboot管理、service依存の非規範事実 |
| `docs/ai/context/ansible/ubuntu-vm-patch.md` | 新規 | 5入口、role連携、apt / non-apt、report、通知の横断契約 |
| `docs/ai/context/operations/ubuntu-vm-patch.md` | 新規 | monthly判定、manual apply、nightly、healthcheck、schedule runbook |
| `docs/ai/reviews/policy_standardization/2026-07-24_014_implement_ubuntu_vm_patch_policy_rewrite.md` | 新規 | 移動実績、UV index、検査実績 |

3 Contextは冒頭で非規範であること、Policyが正本で競合時に優先することを明記した。単一task実装と秘密・接続値を複製せず、code / inventory / varsを事実の正本とした。

## 3. 標準8節の実績

| 順序 | 見出し | 新Policy行 | 主な収容内容 |
|---:|---|---:|---|
| 1 | 目的 | L5-22 | Ubuntu Proを基本とする目的、Ansible責務の限定 |
| 2 | 対象と実行範囲 | L24-56 | 方針1 / 2、apt / non-apt対象 |
| 3 | 対応するPlaybook | L58-82 | 5入口、列挙と実行許可の分離、既知不一致 |
| 4 | 判断軸 | L84-130 | monthly / non-apt Status、reboot OR条件、healthcheck |
| 5 | ライフサイクル・処理フロー | L132-210 | 定常更新、manual apply、reboot、post-check、schedule |
| 6 | 通知方針 | L212-273 | report、状況別channel / status、best-effort |
| 7 | 制約・禁止事項 | L275-310 | 定常自動適用禁止、manual gate、§3.4凍結、方針2除外 |
| 8 | 変更履歴 | L312-321 | 旧版、標準化、Context分離、Semaphore roadmap |

## 4. 範囲超過候補16行の移動実績

| # | 旧範囲 | 実移動先 | Policy核の最終到達行 |
|---:|---|---|---|
| 1 | L1-6 | 本014 §1、Policy P8 L312-318 | L3-22、L312-318 |
| 2 | §2.2 L34-43 | System Context L7-25、Operations Context L41-49 | L24-50、L143-167、L200-210 |
| 3 | §3.1 L49-57 | System Context L18-25、Repository Context L32-40 | L49-50、L279-280 |
| 4 | §3.2 L59-69 | 013 §3 #4、Repository Context L19-30 | L136-137、L282-283 |
| 5 | §3.3 L71-77 | Repository Context L19-30/L58-66 | L88-101、L214-215、L279-286 |
| 6 | §3.4 L79-83 | Repository Context L42-48/L58-66 | L52-56、L103-104、L217-227 |
| 7 | §3.4 L85-89 | Repository Context L42-48/L58-66 | L106-113、L217-227 |
| 8 | §3.4 L91 | Repository Context L42-48、Operations Context L17-26 | L288-305 |
| 9 | §4.1-§4.2 L97-122 | System Context L7-25、Repository Context L50-56 | L117-121、L136-167、L307-310 |
| 10 | §4.3 L124-129 | Repository Context L50-56、Operations Context L28-39 | L123-127 |
| 11 | §5 L133-173 | Repository Context L7-30/L50-56、Operations Context L17-39 | L58-82、L117-130、L169-196、L275-286 |
| 12 | §6.3 L197-219 | Repository Context L58-66 | L253-254、L269-273 |
| 13 | §6.3 L221-235 | Repository Context L58-66 | L238-273 |
| 14 | §7 L239-249 | Operations Context L41-49、本013 | L200-210、L320-321 |
| 15 | §8 L253-260 | Operations Context L41-49、本013 | L117-127、L200-210 |
| 16 | §9 L264-289 | System Context L18-25、本013 | L143-167、L312-318 |

全16行は具体的な移動先とPolicy核の双方へ到達した。旧§8の他systemを含む参考scheduleと旧§9の時点snapshotは生きたPolicyへ規範として昇格せず、013へ履歴として残した。

## 5. UV-001〜UV-083の新Policy marker index

行番号は最終版Policyのmarker行である。marker直後の規範を旧HEADの指定行と照合する。

| ID | 新Policy marker行 |
|---|---:|
| UV-001 | L7 |
| UV-002 | L10 |
| UV-003 | L15 |
| UV-004 | L17 |
| UV-005 | L19 |
| UV-006 | L21 |
| UV-007 | L28 |
| UV-008 | L31 |
| UV-009 | L34 |
| UV-010 | L37 |
| UV-011 | L40 |
| UV-012 | L43 |
| UV-013 | L46 |
| UV-014 | L49 |
| UV-015 | L279 |
| UV-016 | L136 |
| UV-017 | L282 |
| UV-018 | L88 |
| UV-019 | L285 |
| UV-020 | L214 |
| UV-021 | L91 |
| UV-022 | L94 |
| UV-023 | L97 |
| UV-024 | L100 |
| UV-025 | L52 |
| UV-026 | L55 |
| UV-027 | L103 |
| UV-028 | L217 |
| UV-029 | L220 |
| UV-030 | L223 |
| UV-031 | L226 |
| UV-032 | L106 |
| UV-033 | L109 |
| UV-034 | L112 |
| UV-035 | L292 |
| UV-036 | L295 |
| UV-037 | L298 |
| UV-038 | L301 |
| UV-039 | L304 |
| UV-040 | L143 |
| UV-041 | L146 |
| UV-042 | L117 |
| UV-043 | L149 |
| UV-044 | L152 |
| UV-045 | L155 |
| UV-046 | L160 |
| UV-047 | L120 |
| UV-048 | L309 |
| UV-049 | L163 |
| UV-050 | L166 |
| UV-051 | L123 |
| UV-052 | L126 |
| UV-053 | L72 |
| UV-054 | L75 |
| UV-055 | L171 |
| UV-056 | L129 |
| UV-057 | L174 |
| UV-058 | L78 |
| UV-059 | L81 |
| UV-060 | L177 |
| UV-061 | L180 |
| UV-062 | L183 |
| UV-063 | L186 |
| UV-064 | L189 |
| UV-065 | L192 |
| UV-066 | L195 |
| UV-067 | L229 |
| UV-068 | L232 |
| UV-069 | L235 |
| UV-070 | L238 |
| UV-071 | L241 |
| UV-072 | L244 |
| UV-073 | L247 |
| UV-074 | L250 |
| UV-075 | L253 |
| UV-076 | L256 |
| UV-077 | L269 |
| UV-078 | L272 |
| UV-079 | L200 |
| UV-080 | L203 |
| UV-081 | L206 |
| UV-082 | L209 |
| UV-083 | L320 |

## 6. 安全境界の自己逐行diffレビュー

| 重点 | 確認結果 |
|---|---|
| Ansible責務 | patch適用自体でなくreboot timing、post-check、日次healthcheck、通知へ限定する旧L16-21を保持 |
| node分類 | 方針1 / 2、4 nodeの差、新規node追加時の明示分類を保持 |
| apt | Ubuntu Pro定常更新、Ansible定常自動適用禁止、monthly read-only、確認付きsingle-node applyを保持 |
| hold / repository metadata | holdの表示条件と非判断用途、同一version候補を除外しない条件を保持 |
| non-apt判断 | dry-run時だけの取得、両取得成功+数値比較、Status昇格、上位Status非降格、fail-quietを保持 |
| §3.4 L91 | UV-035自動download禁止、UV-036自動更新禁止、UV-037service restart禁止を各「一切行わない」で独立保持。UV-038 human manual、UV-039 apply時check禁止も独立保持 |
| reboot | 方針1 / 2、reboot-required fileとneedrestartのOR、必要な場合だけ、1回、起動待機、post-check順序を保持 |
| healthcheck | read-only、manual standalone、OK無通知、WARNING / CRITICAL通知を保持 |
| 通知 | node単位、channel / status 7条件、best-effort、mail非使用を保持 |
| schedule | `quory`実行、3 timer時刻、Semaphore移行計画を保持 |
| 実装不一致 | P3とRepository Contextで見える化しただけで、Policyを実装へ合わせず、codeをPolicyへ合わせていない |

初稿自己diffではUV-053の対象文言、UV-044 / UV-045のport条件、UV-076のchannel / status全条件、UV-038の人間向け手順名に欠落または抽象化を検出した。旧HEADの意味へ復元してからindexを確定した。Context側の全量配置レビューではUbuntu Pro archive 3系統、non-apt通知 / report契約、timer名、node種別・依存影響の記載不足を検出し、非規範情報として補完した。その他の許可範囲拡大、禁止・停止の緩和、追加の厳格化、OR / only / manual / fail-quiet /通知なしの変更はない。

## 7. 検査実績

| 検査 | 結果 |
|---|---|
| 標準見出し | 8件、各1回、順序不整合0 |
| 範囲超過追跡 | 16行、欠落0 |
| UV marker | 83件、欠落0、重複0 |
| UV index | 83行、欠落0、重複0、line mismatch 0 |
| 対応Playbook | Policy 5本、013計画との差分0、実path欠落0 |
| §3.4凍結 | 3禁止の独立marker 3、各「一切行わない」一致3、human manual 1、`dry_run=false`禁止1 |
| Context | 3本、Policy link 3、非規範明記3 |
| Context重複 | 単一taskの逐語複製0。Policy規範とContext現状 /横断契約 / runbookを区分 |
| Markdown | 空table cell 0、相対link欠落0 |
| 禁止実値 | IPv4 0、VLAN ID実値0、VM ID実値0、認証・秘密実値0 |
| scope | Phase 2指定5 path以外の本件変更0 |
| whitespace | `git diff --check` PASS、未追跡3 Context / 014の`git diff --no-index --check` PASS |
| runtime | 実機・Ansible実行なし |

## 8. 結論

候補16行を3 Contextと本014へ分離し、Policy核を標準8節へ再編した。UV-001〜UV-083は全件markerと最終行indexを持ち、5 playbookを実行許可と分離して列挙した。§3.4の既知実装不一致は意図どおり未解決のままであり、自己diffレビュー上のその他の未解消差異はない。Reviewer工程完了まで指定5 pathを凍結する。
