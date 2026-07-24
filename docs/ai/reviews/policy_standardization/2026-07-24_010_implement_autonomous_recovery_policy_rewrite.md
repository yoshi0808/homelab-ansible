# Autonomous Recovery Policy 標準構造書換 Phase 2 実装記録

## 1. 実装範囲と正本

- requirement: `2026-07-24_008_requirement_autonomous_recovery_policy_rewrite.md`
- investigation: `2026-07-24_009_investigation_autonomous_recovery_policy_rewrite.md`
- 旧Policy正本: Git HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `e141d3eae0be403cc30fd6f905e08d6c2ddc51d7`、288行
- 移行契約: 範囲超過候補22行、AR-001〜AR-094、009 §4.3の逐行照合規則
- 未実施: playbook / role /他Policy /既存Context / map / requirement / 009の編集、実機・Ansible実行

旧表の数値VM IDは5成果物へ転載せず、inventory / vars / codeを正本とした。内部IP、VLAN ID、認証・秘密の実値も記載していない。

## 2. 変更ファイル

| path | 操作 | 結果 |
|---|---|---|
| `docs/ai/policies/autonomous_recovery_policy.md` | 全面再編 | 標準8節、AR marker 94件、対応playbook 9本 |
| `docs/ai/context/system/autonomous-recovery.md` | 新規 | target、account、daemon、依存の非規範事実 |
| `docs/ai/context/ansible/autonomous-recovery.md` | 新規 | 9入口、key、forced command、wrapper、ACL、execpolicy、I/Oの横断契約 |
| `docs/ai/context/operations/autonomous-recovery.md` | 新規 | mute、manual、investigate追加、復旧・resume runbook |
| `docs/ai/reviews/policy_standardization/2026-07-24_010_implement_autonomous_recovery_policy_rewrite.md` | 新規 | 移動実績、AR index、検査実績 |

3 Contextは冒頭で非規範であること、Policyが正本で競合時に優先することを明記した。2026-07-05の経緯とtester教訓は009を参照し、生きたContextへ複製していない。

## 3. 標準8節の実績

| 順序 | 見出し | 新Policy行 | 主な収容内容 |
|---:|---|---:|---|
| 1 | 目的 | L5-11 | 限定自律復旧、Slack非承認gate |
| 2 | 対象と実行範囲 | L13-41 | target別許可、調査専用対象、manual入口 |
| 3 | 対応するPlaybook | L43-69 | setup 5、action 3、notification 1 |
| 4 | 判断軸 | L71-122 | probe、flapping、pvesh 4分岐、mute / pause |
| 5 | ライフサイクル・処理フロー | L124-164 | pull / push / manualの経路分離と終了 |
| 6 | 通知方針 | L166-172 | best-effort、通知時点、JST |
| 7 | 制約・禁止事項 | L174-332 | account / key、allowlist、二段検証、execpolicy、禁止8件 |
| 8 | 変更履歴 | L334-338 | 旧snapshot、標準化、Context分離、数値VM ID除去 |

## 4. 範囲超過候補22行の移動実績

| # | 旧範囲 | 実移動先 | Policy核の最終到達行 |
|---:|---|---|---|
| 1 | L1-10 | 本010 §1、009 | L3-11、L334-338 |
| 2 | §2 L22-29 | System Context L7-28 | L13-35 |
| 3 | §3 L41-49 | System Context L30-40、Repository Context L23-33 | L178-209 |
| 4 | §4 L55-62 | Repository Context L23-33 | L196-209 |
| 5 | §4.1 L64-66 | Repository Context L35-61 | L213-214 |
| 6 | §4.1.1 L68-82 | Operations Context L49-60、Repository Context L37-46 | L59-60、L216-232 |
| 7 | §4.2 L84-86 | Repository Context L27-28 | L141-142、L199-200、L234-235 |
| 8 | §4.3 L88-95 | Repository Context L40/L53/L64-69 | L239-246 |
| 9 | §4.4 L97-103 | Repository Context L41/L54/L66-69 | L248-255 |
| 10 | §4.5 L105-115 | 009、System Context L48-50 | L259-266 |
| 11 | §4.6 L117-134 | System Context L17、Repository Context L30/L55-57 | L268-278 |
| 12 | §4.6 L135-158 | Repository Context L39/L55-60/L69 | L280-293 |
| 13 | §4.6 L159 | 009、System Context L48-50、Repository Context L68-71 | L265-266、L295-296 |
| 14 | §5.1 L165-175 | System Context L11/L20-28、Repository Context L77 | L75-82、L131-135 |
| 15 | §5.1 L177-187 | Operations Context L64-77 | L84-108、L137-142、L163-164 |
| 16 | §5.2 L189-200 | System Context L45、Repository Context L14/L29/L42-44 | L146-156 |
| 17 | §5.3 L202-204 | System Context L12/L46、Repository Context L80 | L37-38 |
| 18 | §6 L210-223 | Repository Context L35-71 | L259-313 |
| 19 | §7 L231-247 | Operations Context L7-37 | L112-122 |
| 20 | §8 L251-263 | Operations Context L39-49 | L40-41、L62-69、L160-164 |
| 21 | §9 L267-269 | System Context L47、Repository Context L19/L81 | L168-172 |
| 22 | §10-§11 L273-288 | Operations Context L64-77 | L163-164、L317-332 |

全22行は移動先とPolicy核の双方へ到達し、VM ID数値実値を移していない。

## 5. AR-001〜AR-094の新Policy marker index

行番号は最終版Policyのmarker行である。marker直後の規範文を旧HEADの指定行と照合する。

| ID | 新Policy marker行 |
|---|---:|
| AR-001 | L7 |
| AR-002 | L10 |
| AR-003 | L17 |
| AR-004 | L19 |
| AR-005 | L21 |
| AR-006 | L23 |
| AR-007 | L25 |
| AR-008 | L128 |
| AR-009 | L28 |
| AR-010 | L31 |
| AR-011 | L34 |
| AR-012 | L178 |
| AR-013 | L181 |
| AR-014 | L184 |
| AR-015 | L187 |
| AR-016 | L190 |
| AR-017 | L193 |
| AR-018 | L196 |
| AR-019 | L199 |
| AR-020 | L202 |
| AR-021 | L205 |
| AR-022 | L208 |
| AR-023 | L213 |
| AR-024 | L216 |
| AR-025 | L219 |
| AR-026 | L222 |
| AR-027 | L225 |
| AR-028 | L228 |
| AR-029 | L59 |
| AR-030 | L231 |
| AR-031 | L234 |
| AR-032 | L141 |
| AR-033 | L239 |
| AR-034 | L242 |
| AR-035 | L245 |
| AR-036 | L248 |
| AR-037 | L251 |
| AR-038 | L254 |
| AR-039 | L259 |
| AR-040 | L262 |
| AR-041 | L265 |
| AR-042 | L268 |
| AR-043 | L271 |
| AR-044 | L274 |
| AR-045 | L277 |
| AR-046 | L280 |
| AR-047 | L283 |
| AR-048 | L286 |
| AR-049 | L289 |
| AR-050 | L292 |
| AR-051 | L295 |
| AR-052 | L131 |
| AR-053 | L75 |
| AR-054 | L78 |
| AR-055 | L81 |
| AR-056 | L134 |
| AR-057 | L84 |
| AR-058 | L87 |
| AR-059 | L92 |
| AR-060 | L95 |
| AR-061 | L98 |
| AR-062 | L101 |
| AR-063 | L104 |
| AR-064 | L107 |
| AR-065 | L146 |
| AR-066 | L149 |
| AR-067 | L152 |
| AR-068 | L37 |
| AR-069 | L300 |
| AR-070 | L303 |
| AR-071 | L155 |
| AR-072 | L306 |
| AR-073 | L309 |
| AR-074 | L312 |
| AR-075 | L112 |
| AR-076 | L115 |
| AR-077 | L118 |
| AR-078 | L121 |
| AR-079 | L40 |
| AR-080 | L62 |
| AR-081 | L65 |
| AR-082 | L68 |
| AR-083 | L160 |
| AR-084 | L168 |
| AR-085 | L171 |
| AR-086 | L317 |
| AR-087 | L319 |
| AR-088 | L321 |
| AR-089 | L323 |
| AR-090 | L325 |
| AR-091 | L327 |
| AR-092 | L329 |
| AR-093 | L331 |
| AR-094 | L163 |

## 6. 安全境界の自己diffレビュー

| 重点 | 確認結果 |
|---|---|
| target allowlist | pull、push、manualを平坦化せず、service / reboot / failover /調査の対象差を保持 |
| probe | 60秒間隔、target別2 probe、5回連続失敗を保持 |
| flapping | 直近24時間で3回以上ならladderをskipしescalation通知だけとする条件を保持 |
| `pvesh`分岐 | node到達不能、stopped、not-found、running無応答の4分岐と順序を保持 |
| ladder | stoppedはstart、running無応答だけreboot、未復旧かつ許可targetだけfailover、各段1回を保持 |
| push | mute / lock、investigate→recover順序、Codexにreboot / failoverを渡さない到達限界を保持 |
| mute / pause | 独立機構、skip時counter reset、target muteのpush確認、TTL 6件、失敗時の人間明示resumeを保持 |
| manual | probe状態を発火条件にせず人間判断で実行可能だが、allowlist / tag /存在 / HA gateを迂回不可とした |
| privilege | account / token / key分離、forced command、二段検証、default deny、no privilege escalationを保持 |
| 禁止事項 | 旧L275-282の8件をAR-086〜AR-093として個別保持 |
| 数値VM ID | 旧表の実値を転載せず、inventory / vars / codeを正本と明記 |

### 6.1 011 review補正

| review | 補正実績 | marker / index |
|---|---|---|
| must-fix #1 | AR-033へ、定型3 command、optional target最大1 path segment、component grammar、filename末尾の固定`.json` suffixだけをdot例外として必須許可、その他のslash / dot拒否、list / show対象JSON限定を旧L92-93どおり復元。009 ledgerも同じ全条件へ補正 | Policy marker L239、010 index L239のまま一致 |

旧HEADの各対象行とAR marker直後を009 §4.3どおり比較し、許可範囲の拡大、禁止・停止の緩和、追加の厳格化、AND / OR、only / all、skip、明示resume、人間判断、経路順序の変更はない。

## 7. 検査実績

| 検査 | 結果 |
|---|---|
| 標準見出し | 8件、各1回、順序不整合0 |
| 範囲超過追跡 | 22行、欠落0 |
| AR marker | 94件、欠落0、重複0 |
| AR index | 94行、欠落0、重複0、line mismatch 0 |
| 対応Playbook | Policy 9本、requirementとの差分0、実path欠落0 |
| Context | 3本、Policy link 3、非規範明記3、旧path 0 |
| Context重複 | 同一taskの逐語複製0。Policy規範とContext現状契約を区分 |
| Markdown | 空table cell 0、相対link欠落0 |
| 禁止実値 | IPv4 0、VLAN ID実値0、数値VM ID実値0、認証・秘密実値0 |
| scope | Phase 2指定5 path以外の変更0。011補正は再許可されたPolicy / 009 / 010だけで、3 Context、playbooks / roles /他Policy /既存Context / 011の変更0 |
| whitespace | `git diff --check` PASS、未追跡の009・3 Context・010に対する`git diff --no-index --check` PASS |
| 011補正 | AR-033旧L92-93逐語照合PASS、marker/index L239一致、22 migration・9 playbook不変 |
| runtime | 実機・Ansible実行なし |

## 8. 結論

候補22行を3 Contextと本010へ分離し、Policy核を標準8節へ再編した。AR-001〜AR-094は全件markerと最終行indexを持ち、9 playbookをsetup / action / notificationの差を保って列挙した。自己diffレビュー上の未解決差異はない。Reviewer工程完了まで5 pathを凍結する。
