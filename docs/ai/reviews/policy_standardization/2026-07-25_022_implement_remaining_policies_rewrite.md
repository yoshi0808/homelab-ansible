# 残り6文書の標準構造書換 Phase 2 実装記録

## 1. 正本・scope・実施境界

- requirement: `2026-07-25_020_requirement_remaining_policies_rewrite.md`
- investigation: `2026-07-25_021_investigation_remaining_policies_rewrite.md`
- snapshot: `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`
- 実施: 許可された9 pathだけを編集。実機操作、Ansible実行、code / role / config / map編集なし
- 旧snapshotと現worktreeを逐行比較し、許可・禁止・停止・必須・例外・判断軸を緩和も厳格化もしていない

| path | 実績 |
|---|---|
| `docs/ai/core.md` | 旧92行をbyte-levelで保持し、末尾へ変更履歴だけを追加 |
| `docs/ai/policies/log_observability_policy.md` | 標準8節、LOG-001〜061、P3 2入口、P6未実装 |
| `docs/ai/context/system/monitoring.md` | 非規範宣言とcurrent topology / ownershipの最小追記 |
| `docs/ai/context/ansible/log-observability.md` | 非規範Repository Contextを新設 |
| `docs/ai/policies/cert_renew_cloudkey_policy.md` | 標準8節、CCK-001〜020 |
| `docs/ai/policies/cert_renew_policy.md` | 標準8節、CERT-001〜020 |
| `docs/ai/policies/time_sync_check_policy.md` | 標準8節、TIME-001〜018 |
| `docs/ai/policies/unifi_backup_fetch_policy.md` | 標準8節、UNIFI-001〜025。孤立fenceだけformat修正 |
| 本書 | migration / marker index /検査実績 |

## 2. core.md

`head -n 92`とsnapshot blobを`cmp -s`で比較し一致した。旧CORE-001〜053の位置と本文は変更していない。L94-L99へ変更履歴だけを追加し、個別Policy用8節templateやmarkerを旧本文へ追加していない。

## 3. log_observability実績

### 3.1 標準節・入口・通知

標準見出しはP1 L5、P2 L13、P3 L50、P4 L62、P5 L128、P6 L154、P7 L159、P8 L209に各1回、この順で配置した。P3は`alloy_setup.yml` / `alloy`と`rsyslog_forward_to_monnie.yml` / `rsyslog_forward_to_monnie`の2入口だけを列挙した。P6はexact `該当なし（未実装）。`であり、channel、status、failure通知を作文していない。Phase 3 Slack構想はP8のfuture-onlyとして現行契約から分離した。

### 3.2 migration 15件

| # | 旧範囲 | 移動 / 保持実績 |
|---:|---|---|
| 1 | L1-11 metadata / history | P8 L209-L231、021 |
| 2 | L24-30 system / repository fact | monitoring Context L40-L45、Repository Context L17-L30。Policy核P2/P7 |
| 3 | L32-34 design decision | Repository Context L17-L30、021。Policy核P2/P7 |
| 4 | L36-51 topology | monitoring Context L40-L45、Repository Context L17-L25。Policy核P2 |
| 5 | L53-56 ownership | monitoring Context L42-L45、Repository Context L9-L15。Policy核P2/P7 |
| 6 | L57-68 labels / config / dashboard | Repository Context L32-L40、code。Policy核P4/P7 |
| 7 | L70-72 repository index | Repository Context L7-L15、P3 L50-L60。sender入口を追加 |
| 8 | L76-79 package / path / defaults | Repository Context L17-L30、code。Policy核P4/P5/P7 |
| 9 | L80-82 lifecycle | Repository Context L42-L57。Policy核P4/P5/P7 |
| 10 | L83 operations link | Repository Context L58、既存Operations Context。Policy核P5/P7 |
| 11 | L85-90 roadmap | 021、P8。現行通知はP6で未実装 |
| 12 | L94-105 risk / environment | Context 2文書、P7 L159-L195 |
| 13 | L107-112 rejected decisions | 021、Context。現行管理境界だけP7 |
| 14 | L114-117 historical test | 021、P8。合格条件だけP4 |
| 15 | L20/L90 future alert | 021、P8。P6へ現行実装を作文しない |

### 3.3 LOG marker line index

LOG-001@L7, LOG-002@L10, LOG-003@L15, LOG-005@L18, LOG-006@L21, LOG-007@L24, LOG-008@L27, LOG-009@L30, LOG-012@L33, LOG-013@L36, LOG-014@L39, LOG-015@L42, LOG-029@L45, LOG-032@L59, LOG-016@L66, LOG-017@L69, LOG-018@L72, LOG-019@L75, LOG-020@L78, LOG-021@L81, LOG-022@L84, LOG-023@L87, LOG-024@L90, LOG-025@L93, LOG-026@L96, LOG-027@L99, LOG-028@L102, LOG-030@L105, LOG-031@L108, LOG-034@L113, LOG-037@L116, LOG-039@L119, LOG-041@L122, LOG-042@L125, LOG-033@L130, LOG-036@L133, LOG-038@L136, LOG-040@L146, LOG-043@L149, LOG-047@L156, LOG-010@L161, LOG-011@L164, LOG-035@L167, LOG-048@L170, LOG-049@L173, LOG-050@L176, LOG-051@L179, LOG-052@L182, LOG-053@L185, LOG-054@L188, LOG-055@L191, LOG-056@L194, LOG-057@L197, LOG-058@L200, LOG-059@L203, LOG-060@L206, LOG-004@L218, LOG-044@L221, LOG-045@L224, LOG-046@L227, LOG-061@L230.

## 4. 軽量4 Policy実績

### 4.1 標準見出し

| Policy | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CloudKey certificate | L5 | L34 | L115 | L124 | L170 | L225 | L239 | L264 |
| certificate renew | L5 | L14 | L105 | L125 | L159 | L250 | L265 | L280 |
| time sync | L5 | L22 | L75 | L92 | L118 | L142 | L157 | L193 |
| UniFi backup | L5 | L38 | L68 | L86 | L124 | L144 | L160 | L221 |

Certificate renew P3はprimary 2、supporting 1、diagnostic 1を区分し、supporting / diagnosticをrenewal実行対象へ昇格していない。UniFi旧L217の孤立fenceだけを削除し、規範を変更していない。

### 4.2 marker line index

CCK: CCK-001@L9, CCK-002@L25, CCK-003@L38, CCK-005@L68, CCK-006@L87, CCK-019@L105, CCK-004@L117, CCK-009@L128, CCK-010@L138, CCK-011@L146, CCK-012@L154, CCK-013@L165, CCK-007@L174, CCK-008@L190, CCK-017@L221, CCK-016@L227, CCK-014@L243, CCK-020@L246, CCK-015@L249, CCK-018@L254.

CERT: CERT-001@L8, CERT-002@L17, CERT-003@L31, CERT-005@L53, CERT-016@L54, CERT-017@L55, CERT-006@L72, CERT-007@L83, CERT-018@L84, CERT-004@L108, CERT-010@L128, CERT-012@L148, CERT-020@L149, CERT-008@L162, CERT-019@L163, CERT-009@L179, CERT-013@L197, CERT-014@L229, CERT-011@L253, CERT-015@L268.

TIME: TIME-001@L8, TIME-002@L25, TIME-006@L40, TIME-007@L45, TIME-016@L59, TIME-003@L78, TIME-017@L86, TIME-018@L89, TIME-004@L95, TIME-005@L110, TIME-008@L121, TIME-009@L124, TIME-010@L137, TIME-011@L145, TIME-012@L160, TIME-013@L161, TIME-014@L162, TIME-015@L181.

UNIFI: UNIFI-001@L8, UNIFI-002@L27, UNIFI-003@L41, UNIFI-014@L56, UNIFI-004@L71, UNIFI-019@L80, UNIFI-020@L83, UNIFI-008@L89, UNIFI-009@L101, UNIFI-022@L102, UNIFI-010@L106, UNIFI-011@L114, UNIFI-012@L115, UNIFI-005@L127, UNIFI-006@L128, UNIFI-023@L129, UNIFI-024@L130, UNIFI-013@L147, UNIFI-007@L163, UNIFI-021@L164, UNIFI-015@L184, UNIFI-016@L199, UNIFI-017@L242, UNIFI-018@L252, UNIFI-025@L259.

## 5. Context配置と重複確認

- System Contextはcurrent topology / ownershipだけを追記し、label、path、port、default、query等を複製していない。
- Repository Contextは2入口とcross-role contractをtaskより上の粒度で記録し、single task実装を複製していない。
- 両Contextは非規範でPolicy優先を明記し、相互link、Policy、map、021へのlinkを確認した。
- 現行notification不在をcode / role / config / mapと突合し、future Slack記述をcurrentへ昇格していない。

## 6. 自己diff・機械検査実績

| 検査 | 結果 |
|---|---|
| core旧92行byte比較 | `cmp=0`、差異0 |
| 標準見出し | 5 Policy × 8、各1回、order不一致0 |
| marker | LOG61 / CCK20 / CERT20 / TIME18 / UNIFI25、欠落0、重複0 |
| log migration | 15、欠落0 |
| Playbook | log 2、CloudKey 1、cert primary 2 / supporting 1 / diagnostic 1、time 2、UniFi 1 |
| log P6 | exact `該当なし（未実装）。`、channel / status追加0 |
| Context | 非規範 / Policy優先link 2、broken relative link 0、task-level過剰複製0 |
| 実値 / secret | IPv4 literal 0、VLAN ID 0、VM ID 0、password / token実値0 |
| scope | 許可9 path以外の本案件差分0 |
| whitespace | tracked `git diff --check` PASS、new files no-index check PASS |
| runtime | 実機 / Ansible実行0 |

自己diffでは、意味を失う統合、conditionのAND / OR反転、failureのsuccess化、future / historicalのcurrent化がないことを旧HEADと照合した。CloudKeyのCA / API / live verification、certificateのforce / cleanup / key placement、time syncのreference stop gate、UniFiのCSRF fallback / atomic finalize / rotation / re-failを独立条件のまま保持した。

## 7. 023 review補正実績

- log P6を句点込みのexact `該当なし（未実装）。`へ補正し、future / channel / statusは追加していない。
- TIME-009をtext fence外へ移し、fence表示のPhase 1〜5は旧HEAD L103-L110との逐行一致を確認した。
- time syncのv1.0 / v1.1、UniFi backupのv1.0 / v1.1をそれぞれ同じtable内の連続rowへ補正した。
- 補正後の全marker / index、fence、table、link、scope、実値、tracked / untracked whitespaceを再検査し、欠落・重複・不一致0を確認した。
