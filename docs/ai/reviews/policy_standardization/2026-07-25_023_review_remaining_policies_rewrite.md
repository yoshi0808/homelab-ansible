# Code Review: 残り6文書の標準構造書換

## Summary

旧正本は `git show HEAD:<path>`（HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`）から独立取得した。020/021/022の自己検査を合格根拠にせず、coreの旧92行、log Policyの全旧規範文・表行・箇条書き、軽量4 Policyの安全境界を新版へ逆照合した。

coreの旧92行はbyte-levelで不変であり、CORE-001〜053を保持する。logのLOG-001〜061、migration 15、2入口、現行notification実装なし、軽量4 PolicyのCCK20 / CERT20 / TIME18 / UNIFI25にも意味の欠落、緩和、厳格化、条件・例外・順序変更は検出しなかった。初回レビューで検出したP6 exact表記とMarkdownのfence / table構造4件は指定範囲内で修正され、独立再検査に合格した。

## Must-fix

なし。

## 再レビューで確認した修正

| # | 初回差異 | 修正後の独立確認 | 判定 |
|---:|---|---|---|
| 1 | log P6 exact句点欠落 | Policy L157と022 L31/L96がexact `該当なし（未実装）。`。future / channel / status追加0 | 解消 |
| 2 | TIME-009がtext fence内 | markerはfence外L124。新版L126-L133と旧HEAD L103-L110の`cmp -s=0`、Phase 1〜5の表示・順序不変 | 解消 |
| 3 | TIME v1.1がtableから分離 | L211-L214でheader、v1.0、v1.1が連続 | 解消 |
| 4 | UNIFI v1.1がtableから分離 | L236-L239でheader、v1.0、v1.1が連続。UNIFI-017/018/025本文不変 | 解消 |

## Suggestions

なし。既存規範の言い換え、Contextの追加分割、通知契約の新設は今回の非ゴールへ広げない。

## core: CORE-001〜053独立確認

旧HEAD blobは `b856a4efc9fbb237c878a3dd2bcab9f8413207e4`、92行である。`git show HEAD:docs/ai/core.md` と新版 `head -n 92` のSHA-256はともに `acaca41e15e9e8bc64ce98699dcb57728d87dbb1ae5d7fae4d43b5a7c347839b`、`cmp -s` は0だった。したがって旧規範の文字、行、順序は全件同一であり、個別Policy用8節templateも適用されていない。

| CORE | 旧行=新版行 | 判定 | CORE | 旧行=新版行 | 判定 |
|---|---:|---|---|---:|---|
| 001 | L3 | 保持 | 028 | L52 | 保持 |
| 002 | L7 | 保持 | 029 | L53 | 保持 |
| 003 | L9 | 保持 | 030 | L54 | 保持 |
| 004 | L10 | 保持 | 031 | L55 | 保持 |
| 005 | L11 | 保持 | 032 | L56 | 保持 |
| 006 | L12 | 保持 | 033 | L57 | 保持 |
| 007 | L13 | 保持 | 034 | L58 | 保持 |
| 008 | L14 | 保持 | 035 | L60 | 保持 |
| 009 | L18 | 保持 | 036 | L64 | 保持 |
| 010 | L20 | 保持 | 037 | L65 | 保持 |
| 011 | L21 | 保持 | 038 | L66 | 保持 |
| 012 | L22 | 保持 | 039 | L67 | 保持 |
| 013 | L23 | 保持 | 040 | L68 | 保持 |
| 014 | L24 | 保持 | 041 | L69 | 保持 |
| 015 | L29 | 保持 | 042 | L71 | 保持 |
| 016 | L30 | 保持 | 043 | L75 | 保持 |
| 017 | L31 | 保持 | 044 | L76 | 保持 |
| 018 | L34 | 保持 | 045 | L77 | 保持 |
| 019 | L35 | 保持 | 046 | L78 | 保持 |
| 020 | L36 | 保持 | 047 | L82 | 保持 |
| 021 | L37 | 保持 | 048 | L83 | 保持 |
| 022 | L41 | 保持 | 049 | L84 | 保持 |
| 023 | L43 | 保持 | 050 | L85 | 保持 |
| 024 | L44 | 保持 | 051 | L86 | 保持 |
| 025 | L45 | 保持 | 052 | L90 | 保持 |
| 026 | L46 | 保持 | 053 | L92 | 保持 |
| 027 | L50 | 保持 | - | - | - |

新版L94-L99だけが変更履歴の追加であり、旧92行を移動・統合・言い換えしていない。

## log_observability: 全旧規範の逐行突合

旧HEAD blobは `c1a67206d89749cf3987e5395a085067ffb84bbf`、117行である。判定は `保持 / 欠落 / 緩和 / 厳格化 / 条件・例外・順序変更` から選んだ。旧行欄の範囲は、その範囲にある各表行・箇条書き・独立条件を個別に確認したことを表す。

| ID | 旧HEAD行 → 新版marker/到達行 | 判定 | 独立所見 |
|---|---|---|---|
| LOG-001 | L15 → L7-L8 | 保持 | loggingとrecoveryの目的分離。 |
| LOG-002 | L15 → L10-L11 | 保持 | current収集とfuture alertを分離。 |
| LOG-003 | L19 → L15-L16 | 保持 | collection path一本、目的別pipeline禁止。 |
| LOG-004 | L20 → L218-L219 | 保持 | Phase 3構想だけで現行化しない。 |
| LOG-005 | L22 → L18-L19 | 保持 | Alloy統一、Promtailを現行agentにしない。 |
| LOG-006 | L26 → L21-L22 | 保持 | applianceはmonnie集約点へ。 |
| LOG-007 | L27 → L24-L25 | 保持 | monnie local Alloyからlocal Loki。 |
| LOG-008 | L28 → L27-L28 | 保持 | remote Linuxのrsyslog funnel。 |
| LOG-009 | L30 → L30-L31 | 保持 | Loki writerをmonnie localだけに限定。 |
| LOG-010 | L30 → L161-L162 | 保持 | credential/repositoryをremoteへ広げずport非公開。 |
| LOG-011 | L34 → L164-L165 | 保持 | rsyslog集約をAlloy direct receiveへ置換しない。 |
| LOG-012 | L53 → L33-L34 | 保持 | CloudKey senderはGUI、Ansible直接編集禁止。 |
| LOG-013 | L54 → L36-L37 | 保持 | Sophos GUI、repositoryはreceiver readinessまで。 |
| LOG-014 | L55 → L39-L40 | 保持 | Proxmox senderはmanual、Ansible対象外。 |
| LOG-015 | L56 → L42-L43 | 保持 | Ubuntu sender / monnie receiverのowner分離。 |
| LOG-016 | L57-L58 → L66-L67 | 保持 | CloudKey stream label contract。 |
| LOG-017 | L59 → L69-L70 | 保持 | network-device host動的抽出。 |
| LOG-018 | L60 → L72-L73 | 保持 | Proxmox normalized host抽出。 |
| LOG-019 | L61 → L75-L76 | 保持 | Sophos static host。 |
| LOG-020 | L62 → L78-L79 | 保持 | Ubuntu normalized dynamic host。 |
| LOG-021 | L63 → L81-L82 | 保持 | monnie journal / unit relabel。 |
| LOG-022 | L64 → L84-L85 | 保持 | levelを4値に限定。 |
| LOG-023 | L64 → L87-L88 | 保持 | journal priorityの4-level対応。 |
| LOG-024 | L64 → L90-L91 | 保持 | rsyslog確定後Alloy抽出。 |
| LOG-025 | L64 → L93-L94 | 保持 | UniFi best-effort、unknown誤分類禁止。 |
| LOG-026 | L65 → L96-L97 | 保持 | normalized bodyはmessage-only。 |
| LOG-027 | L66 → L99-L100 | 保持 | exact unit AND low severityだけdrop。 |
| LOG-028 | L66 → L102-L103 | 保持 | warning/error保持、remote fileへdrop非適用。 |
| LOG-029 | L67 → L45-L46 | 保持 | push先はmonnie localhost。 |
| LOG-030 | L68 → L105-L106 | 保持 | dashboard上限/default/明示選択。 |
| LOG-031 | L68 → L108-L109 | 保持 | host/search/line format。 |
| LOG-032 | L72 → L59-L60 | 保持 | 2入口ともcheck-mode-native、APPLYはhuman gate。 |
| LOG-033 | L76 → L130-L131 | 保持 | existing repo、role管理、present、setupでversion-upなし。 |
| LOG-034 | L77 → L113-L114 | 保持 | monthly apt、major疑いをhuman review。 |
| LOG-035 | L78 → L167-L168 | 保持 | Git/role正本、host直接編集禁止。 |
| LOG-036 | L79 → L133-L134 | 保持 | existing UniFi config不変、追加sourceは別config。 |
| LOG-037 | L79 → L116-L117 | 保持 | deploy時resolve、配置後自動再解決なし。 |
| LOG-038 | L79 → L136-L137 | 保持 | address変更後に入口再実行。 |
| LOG-039 | L80 → L119-L120/L139-L144 | 保持 | auto-start抑止、validate合格後だけstop→start。 |
| LOG-040 | L80 → L146-L147 | 保持 | failure時Promtail restore、rollback資材保持。 |
| LOG-041 | L81 → L122-L123 | 保持 | positions非移植、source別tail start、gap/overlap受容。 |
| LOG-042 | L82 → L125-L126 | 保持 | activeだけでなくreal streamを確認。 |
| LOG-043 | L83 → L149-L150 | 保持 | production変更前のmute。 |
| LOG-044 | L87 → L221-L222 | 保持 | Phase 1完了をhistoricalに限定。 |
| LOG-045 | L88 → L224-L225 | 保持 | Phase 2時点状態をcurrentへ固定しない。 |
| LOG-046 | L89 → L227-L228 | 保持 | Phase 2 extensionを履歴扱い。 |
| LOG-047 | L90 → L154-L157/L218-L219 | 保持 | 未実装/future-onlyの意味を保持し、P6は指定exact表記。 |
| LOG-048 | L94-L98 → L170-L171 | 保持 | plaintext risk、allowlist非認証。 |
| LOG-049 | L97-L98 → L173-L174 | 保持 | TLSは対応senderだけのfuture option。 |
| LOG-050 | L99 → L176-L177 | 保持 | Loki一本。 |
| LOG-051 | L100 → L179-L180 | 保持 | rsyslog aggregation維持。 |
| LOG-052 | L101 → L182-L183 | 保持 | Loki/UFW非変更、remote非公開。 |
| LOG-053 | L102 → L185-L186 | 保持 | host直接編集禁止。 |
| LOG-054 | L103 → L188-L189 | 保持 | production APPLY human gate、tester既定非APPLY。 |
| LOG-055 | L104 → L191-L192 | 保持 | secret/IP literal禁止、runtime validation分離。 |
| LOG-056 | L105 → L194-L195 | 保持 | volume/capacity観測、retention変更は別review。 |
| LOG-057 | L109 → L197-L198 | 保持 | Proxmox local Alloy案不採用と再検討条件。 |
| LOG-058 | L110 → L200-L201 | 保持 | journal-remote不採用。 |
| LOG-059 | L111 → L203-L204 | 保持 | Alloy direct receive不採用。 |
| LOG-060 | L112 → L206-L207 | 保持 | Ansible/manual/GUI owner境界。 |
| LOG-061 | L114-L117 → L230-L231 | 保持 | historical PASS/known issueをcurrent gateにしない。 |

旧HEADを `Slack|notify|notification|alert|ruler|Alertmanager` 等でも逆検索した。対象2 playbook、`roles/alloy`、`roles/rsyslog_forward_to_monnie`、playbook-mapに現行通知経路はなく、dashboardにもalert rule objectはない。新版P8のSlackはfuture-only、旧実機結果はhistorical-onlyであり、現行へ相互昇格していない。P6はexact `該当なし（未実装）。` だけで通知契約を作文していない。

## log migration・Context・Playbook

| 観点 | 独立結果 |
|---|---|
| migration 15 | 旧metadata/history、architecture、topology、ownership、label/config/dashboard、repository index、package/path/defaults、lifecycle、operations link、roadmap、risk/environment、rejected decisions、historical test、future alertの15行すべてにContext/021とPolicy核の到達先がある。 |
| P3 | `alloy_setup.yml` / `alloy` と `rsyslog_forward_to_monnie.yml` / `rsyslog_forward_to_monnie` の2入口。実path・role・playbook-map ownerは一致し、列挙はAPPLY許可へ昇格していない。 |
| System Context | L3で非規範・Policy優先。L38-L44はcurrent topology/ownershipに限定し、port/path/default/queryを第二正本化していない。HEAD既存本文の削除・改変なし。 |
| Repository Context | L3で非規範・Policy優先。2入口、dataflow、label、cutover/rollback、notification不在をcross-file粒度で記録し、single task/default値はcode正本としている。 |
| link | Policy/Context/021/map/role-map/Operations Contextの相対link target欠落0。 |

## 軽量4 Policyの完全意味突合

| Policy | 旧HEAD | marker | 標準8節 | 独立判定 |
|---|---|---|---|---|
| CloudKey certificate | blob `400c591fd1ae8f8e7ecd739e5d52213f33858490`、275行 | CCK-001〜020各1、欠番/重複0 | L5/34/115/124/170/225/239/264 | 20境界すべて保持。Must-fixなし。 |
| certificate renew | blob `f54bc62f80c36f476089bc01c90b4f93bb2cf327`、253行 | CERT-001〜020各1、欠番/重複0 | L5/14/105/125/159/250/265/280 | 20境界すべて保持。Must-fixなし。 |
| time sync | blob `6422d22e35fa26bf00d2f4a845d6b7390107beba`、176行 | TIME-001〜018各1、欠番/重複0 | L5/22/75/92/118/142/157/193 | 18境界の意味を保持。fence / change-history tableも修正済み。 |
| UniFi backup | blob `8445dd53ac1ae189815955975d04e48032fc8b91`、217行 | UNIFI-001〜025各1、欠番/重複0 | L5/38/68/86/124/144/160/221 | 25境界の意味を保持。旧孤立fence削除は正当で、change-history tableも修正済み。 |

重点条件を旧HEADと照合した結果は次のとおり。

- CCK: cert renewalからのfailure domain分離、controller allowlist、3-level chain、upload→activate→live verify→delete、delete全条件AND、active/new/non-uploaded非削除、fingerprint AND ordered chain、temporary key always cleanup、no_log、Slack best-effort/re-fail、monthly force、unofficial API riskを保持する。account/path実値の一般化は許可対象を変えていない。
- CERT: primary 2 / supporting 1 / diagnostic 1を区別する。CloudKey除外はP7 L269-L276で意味不変。CAはquory only、mode必須/owner非固定、tmpfs cleanup failureは最終fail、leaf+intermediate chain、expiry warning、renew threshold OR explicit force、production monthly force/manual fallback、notification routingを保持する。
- TIME: check read-only / reference changeを分離し、reference未収集・未同期なら他hostへ接続せず停止する。chrony→direct target→CloudKey→aggregate、専用threshold、command/expect収集とAnsible判断、best-effort通知、GUI管理除外、no auto-correctionを保持する。Phase 1〜5表示は旧HEADとbyte-levelで一致する。
- UNIFI: certificate deploymentから分離し、API auth→download→freshness→same-FS atomic finalize→rotation→rescue→alwaysの順序を保持する。CSRF header priorityと両header空時だけJWT fallback、filename allowlist/basename/traversal guard、finalize後だけgeneration超過をdelete、always cleanup/notify後failure時だけre-fail、Slack best-effort、weekly衝突回避、risk-accepted gateを保持する。旧L217の孤立fence以外の削除はない。

## 独立機械検査

| 検査 | 独立実測 |
|---|---|
| core | 旧92行、新版先頭92行 `cmp=0`、SHA-256一致。変更履歴L94-L99だけ追加 |
| 新文書行数 | log 231、CCK 269、CERT 294、TIME 214、UNIFI 260、System Context 46、Repository Context 64、022 110 |
| 標準見出し | log + 軽量4 Policyの各8節が1回、1→8順。coreは旧9見出しを維持しtemplate非適用 |
| marker | LOG61 / CCK20 / CERT20 / TIME18 / UNIFI25。各連番、欠番0、重複0。022 indexの行番号不一致0 |
| Playbook/map | log 2、CloudKey 1、cert primary 2 / supporting 1 / diagnostic 1、time 2、UniFi 1。実path/role/map不一致0 |
| notification | log対象2 playbook/2 roleにcurrent Slack/contact point/alert rule/ruler/Alertmanager実装0 |
| scope | 022記載の本Phase変更は許可9 path。playbooks/roles/map/他Policyへの本Phase差分なし。レビューは023だけを新規作成 |
| 実値/秘密 | 対象9 pathと本レビューにIPv4 literal、VLAN ID、数値VM ID、password/token/private keyの代入実値0 |
| fence | 全対象で開閉数は偶数。TIME-009はfence外、TIME lifecycle表示は旧HEADと一致。UNIFI旧孤立fenceの削除もPASS |
| table | empty cellなし。TIME/UNIFIのv1.0/v1.1は各変更履歴table内で連続 |
| whitespace | `git diff --check` PASS。新規023の`git diff --no-index --check`もPASS |
| runtime | 文書reviewのためAnsible・実機実行なし |

## What Looks Good

- coreをPolicy templateへ無理に合わせず、旧92行とCORE53をbyte-levelで保持している。
- logはcurrent / future / historicalを分離し、現行通知が存在しない事実をcode・role・mapから再確認できる。2入口の追加も実行許可へ変えていない。
- CCK/CERTはdelete・cleanup・key placement・force条件を平坦化せず、cert P3のprimary/supporting/diagnosticとCloudKey除外を明確に保つ。
- TIMEのreference fail-closed、UNIFIのCSRF fallback・atomic finalize・rotation・conditional re-failは旧条件と順序を保持する。
- marker連番、migration 15、Context非規範境界、Playbook/map所有権、scope、秘密・実値、通常whitespaceは要求を満たす。

## Verdict

**Approve**

初回must-fix 4件はすべて解消した。旧HEADからの全規範照合、CORE53、LOG61、CCK20 / CERT20 / TIME18 / UNIFI25、migration 15、P3所有権、P6 exact、Context境界、scope、秘密・実値、fence / table / link / whitespaceの再検査に未解決差異はない。
