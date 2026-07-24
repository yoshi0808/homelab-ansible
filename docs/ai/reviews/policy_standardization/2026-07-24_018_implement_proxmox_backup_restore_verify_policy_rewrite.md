# Proxmox Backup Restore Verify Policy 標準構造書換 Phase 2 実装記録

## 1. 実装範囲と正本

- requirement: `2026-07-24_016_requirement_proxmox_backup_restore_verify_policy_rewrite.md`
- investigation: `2026-07-24_017_investigation_proxmox_backup_restore_verify_policy_rewrite.md`
- 旧Policy正本: Git HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `9204b94e61d0f3eb652e03406373cbacc5d0af5d`、217行
- 移行契約: 範囲超過候補20行、BRV-001〜BRV-082、017 §4.3の逐行照合規則
- 未実施: playbook / role / map / requirement / 017 /他Policyの編集、実機・Ansible実行

IP、VLAN ID、数値VM ID、認証情報、秘密情報の実値は4成果物へ転載していない。専用restore VMIDは`verify_restore_vmid`または値非依存の名称で表し、vars / codeを値の正本とした。

## 2. 変更ファイル

| path | 操作 | 結果 |
|---|---|---|
| `docs/ai/policies/proxmox_backup_restore_verify_policy.md` | 全面再編 | 標準8節、BRV marker 82件、対応playbook 1本 |
| `docs/ai/context/system/proxmox.md` | 必要最小追記 | 既存patch差分を保持し、Policy優先宣言とbackup / restore固有の環境事実を追加 |
| `docs/ai/context/ansible/proxmox-backup-restore-verify.md` | 新規 | 2-play、選定、role lifecycle、lock / ownership / cleanup、report /通知の横断契約 |
| `docs/ai/reviews/policy_standardization/2026-07-24_018_implement_proxmox_backup_restore_verify_policy_rewrite.md` | 新規 | 移動実績、BRV index、自己逐行diff、検査実績 |

両Contextは非規範であり、backup restore verificationの許可、禁止、停止条件はPolicyを正本として競合時に優先することを明記した。System Contextの既存patch差分を削除、上書き、再配置していない。

## 3. 標準8節の実績

| 順序 | 見出し | 新Policy行 | 主な収容内容 |
|---:|---|---:|---|
| 1 | 目的 | L5-12 | monthly実restore検証、本番非変更 |
| 2 | 対象と実行範囲 | L13-44 | tag対象、専用restore先、制御点、controlled apply、現行scope |
| 3 | 対応するPlaybook | L45-57 | 1入口、列挙と実行許可の分離、risk-accepted |
| 4 | 判断軸 | L58-173 | 対象 / backup、正常性、lock、residue、ownership、cleanup、終了code、review判断 |
| 5 | ライフサイクル・処理フロー | L174-205 | dynamic group、restore順序、rescue / always、unlock |
| 6 | 通知方針 | L206-231 | best-effort、priority、channel / status、report |
| 7 | 制約・禁止事項 | L232-284 | 本番危害防止、同時実行禁止、残余risk、現行除外 |
| 8 | 変更履歴 | L285-293 | history非永続化判断、旧版、標準化 |

## 4. 範囲超過候補20行の移動実績

| # | 旧範囲 | 実移動先 | Policy核の最終到達行 |
|---:|---|---|---|
| 1 | L1-12 | 本018 §1 / §3、Policy P8 L285-293 | L3-12、L285-293 |
| 2 | §2 L26-34 | System Context L48-54、Repository Context L23-27 | L13-42、L232-282 |
| 3 | §2 L36-41 | Repository Context L5-11/L23-27 | L30、L45-56 |
| 4 | §3 L53-54 | Repository Context L13-27 | L68-69 |
| 5 | §3.1 L58-63 | Repository Context L23-24 | L15-16、L33-34、L71-78 |
| 6 | §3.2 L67-68 | Repository Context L23-25 | L80-84 |
| 7 | §3.3 L72-77 | Repository Context L25-27 | L62-93、L174-177 |
| 8 | §4 L83 | System Context L50-54、Repository Context L5-11 | L36-37 |
| 9 | §4 L85-96 | Repository Context L29-47 | L125-156、L174-198 |
| 10 | §4 L98-100 | Repository Context L42-47 | L200-201、L234-235 |
| 11 | §5 L106-116 | Repository Context L42-47、本017 | L99-106、L237-241 |
| 12 | §6.2 L132-138 | Repository Context L49-59 | L110-123、L203-204、L246-247 |
| 13 | §6.3 L143-147 | Repository Context L49-59 | L128-155、L249-253 |
| 14 | §6.4 L149-153 | 本017、Policy P7 | L255-259 |
| 15 | §7 L157-163 | Repository Context L49-59 | L142-155、L197-204 |
| 16 | §8 L167-178 | Repository Context L61-66 | L206-230 |
| 17 | §10.1 L195-198 | Repository Context L5-66 | L42-43、L174-230 |
| 18 | §10.2 L200-204 | 本017、Policy P2 / P7 / P8 | L33-34、L273-277、L285-288 |
| 19 | §11 L208-217 | 本017、Policy P4 / P7 | L159-172、L279-283 |
| 20 | 旧数値restore VMIDの全出現 | vars / codeを値の正本とし、新成果物へ転載しない | `verify_restore_vmid`と専用固定restore VMIDとしてL10-28、L125-153、L181-190、L252-282 |

20候補すべてが具体的な移動先とPolicy核へ到達した。旧§9 L184-189は全量をP7へ統合し、旧§10は実装契約、現行除外、history decisionへ分割した。旧§11のreview方針は017へ、現役6判断はP4 / P7へ保持した。

## 5. BRV-001〜BRV-082の新Policy marker index

行番号は最終版Policyのmarker行である。marker直後の規範を旧HEADの指定行と照合する。

| ID | 新Policy marker行 |
|---|---:|
| BRV-001 | L7 |
| BRV-002 | L10 |
| BRV-003 | L15 |
| BRV-004 | L18 |
| BRV-005 | L62 |
| BRV-006 | L21 |
| BRV-007 | L65 |
| BRV-008 | L24 |
| BRV-009 | L27 |
| BRV-010 | L30 |
| BRV-011 | L53 |
| BRV-012 | L68 |
| BRV-013 | L71 |
| BRV-014 | L74 |
| BRV-015 | L77 |
| BRV-016 | L33 |
| BRV-017 | L80 |
| BRV-018 | L83 |
| BRV-019 | L86 |
| BRV-020 | L89 |
| BRV-021 | L176 |
| BRV-022 | L36 |
| BRV-023 | L181 |
| BRV-024 | L125 |
| BRV-025 | L92 |
| BRV-026 | L183 |
| BRV-027 | L185 |
| BRV-028 | L187 |
| BRV-029 | L189 |
| BRV-030 | L191 |
| BRV-031 | L194 |
| BRV-032 | L197 |
| BRV-033 | L200 |
| BRV-034 | L234 |
| BRV-035 | L99 |
| BRV-036 | L102 |
| BRV-037 | L105 |
| BRV-038 | L237 |
| BRV-039 | L240 |
| BRV-040 | L243 |
| BRV-041 | L110 |
| BRV-042 | L39 |
| BRV-043 | L113 |
| BRV-044 | L116 |
| BRV-045 | L119 |
| BRV-046 | L122 |
| BRV-047 | L246 |
| BRV-048 | L203 |
| BRV-049 | L249 |
| BRV-050 | L252 |
| BRV-051 | L128 |
| BRV-052 | L133 |
| BRV-053 | L136 |
| BRV-054 | L139 |
| BRV-055 | L255 |
| BRV-056 | L258 |
| BRV-057 | L142 |
| BRV-058 | L145 |
| BRV-059 | L148 |
| BRV-060 | L151 |
| BRV-061 | L154 |
| BRV-062 | L208 |
| BRV-063 | L211 |
| BRV-064 | L220 |
| BRV-065 | L223 |
| BRV-066 | L226 |
| BRV-067 | L229 |
| BRV-068 | L261 |
| BRV-069 | L264 |
| BRV-070 | L267 |
| BRV-071 | L270 |
| BRV-072 | L42 |
| BRV-073 | L273 |
| BRV-074 | L276 |
| BRV-075 | L287 |
| BRV-076 | L159 |
| BRV-077 | L162 |
| BRV-078 | L165 |
| BRV-079 | L279 |
| BRV-080 | L168 |
| BRV-081 | L171 |
| BRV-082 | L282 |

## 6. 安全境界の自己逐行diffレビュー

| 重点 | 確認結果 |
|---|---|
| manual bypass | monthly rotationだけを迂回し、対象存在、restore node、agent期待、本番非変更、fixed restore / destroyを迂回しない |
| lifecycle | lock、residue、backup、restore、owner stamp、NIC isolation、boot、health、rescue、alwaysの順序を保持 |
| lock | 同時実行禁止の補助で完全なdistributed mutexではない。existing時no-wait停止 /通知 /非ゼロ、empty、stale回収、取得時だけ解放を保持 |
| lock非依存guard | fixed destroy hard assert、開始前residue非接触、owner tokenを独立保持 |
| ownership | ownはdestroy、emptyはno-overlap前提の途中失敗例外、otherは非接触の3分岐を保持 |
| cleanup | `restore_attempted AND not preexisting_residue`、live existence、ownershipの順とdestroy失敗時cleanup failureを保持 |
| best-effort | stop / notificationはbest-effort。other-owner、unlock、reportを新規失敗条件へ変更していない |
| 終了 | verification failure OR cleanup failureのどちらかで非ゼロを保持 |
| §9 / §10 / §11 | §9全量P7、§10分割、§11現役6判断P4 / P7の計画どおり |
| risk-accepted | `--check`でも本実行、`tester_mode=true`拒否、列挙と実行許可の分離を明示 |

初稿のmarker検査でBRV-024の配置漏れを検出して復元した。旧HEAD逐行diffでBRV-015のmonth index式、BRV-046のstale回収時間、BRV-056の残余risk表現が抽象化または意味のずれを持つことを検出し、旧条件へ復元した。その他の許可範囲拡大、禁止・停止の緩和、追加の厳格化、AND / OR、only、best-effort、例外、順序の変更はない。

## 7. 検査実績

| 検査 | 結果 |
|---|---|
| 標準見出し | 8件、各1回、順序不整合0 |
| 範囲超過追跡 | 20行、欠落0 |
| BRV marker | 82件、欠落0、重複0 |
| BRV index | 82行、欠落0、重複0、line mismatch 0 |
| 対応Playbook | Policy 1本、017計画との差分0、実path欠落0 |
| Context | 2本、Policy link 2、非規範 / Policy優先明記2 |
| Context重複 | 単一taskの逐語複製0。System事実とRepository横断契約を分離 |
| Markdown | 空table cell 0、相対link欠落0 |
| 禁止実値 | IPv4 0、VLAN ID実値0、数値VM ID実値0、認証・秘密実値0 |
| scope | Phase 2指定4 path以外の本件変更0、既存System Context patch差分保持 |
| whitespace | `git diff --check` PASS、未追跡Repository Context / 018の`git diff --no-index --check` PASS |
| runtime | 実機・Ansible実行なし |

## 8. 結論

候補20行をSystem / Repository Contextと本018へ分離し、Policy核を標準8節へ再編した。BRV-001〜BRV-082は全件markerと最終行indexを持ち、1 playbookを実行許可と分離して列挙した。lock非依存guard、ownership 3分岐、cleanup AND、終了OR、best-effort /非失敗条件に未解消差異はない。Reviewer工程完了まで指定4 pathを凍結する。
