# Code Review: Ubuntu VM Patch Policy 標準構造書換

## Summary

旧版正本は `git show HEAD:docs/ai/policies/ubuntu_vm_patch_policy.md`（HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `bf8cee43f3789dbae1b0a524f84fdb694a5445c7`、289行）から独立取得した。013/014の要約を合格根拠にせず、旧版の全規範文、表行、箇条書きを新版へ突合した。

全83 UVとledger外を逆検索し、許可・禁止・停止・判断軸に欠落、緩和、厳格化、条件・例外・順序変更は検出しなかった。旧§3.4 L91の自動download、自動更新、service restartの3禁止は各「一切行わない」を保ち、human manual指定手順と`dry_run=false`時のnon-apt check禁止も独立して保持されている。`prometheus_update_check.yml`のP3列挙は実行許可と明示的に分離され、既知のPolicy /実装不一致を拡大、縮小、解消していない。

## Must-fix

なし。

## Suggestions

なし。今回の非ゴールである実装不一致の解消やPolicy統合へレビュー範囲を広げない。

## 旧原文規範行の独立突合

判定は `保持 / 欠落 / 緩和 / 厳格化 / 条件・例外・順序変更` で記録した。旧行欄のセミコロン区切りは、原文の文、表行、箇条書きを個別に確認したことを表す。

| UV | 旧原文単位 → 新版到達行 | 判定 | 所見 |
|---|---|---|---|
| UV-001 | L12→L8 | 保持 | Ubuntu node patch方針の目的。 |
| UV-002 | L14→L11 | 保持 | Ubuntu Pro自動patchを基本とする。 |
| UV-003 | L16限定→L13/L16; L18 reboot timing→L16 | 保持 | Ansible責務をreboot timingへ限定。 |
| UV-004 | L16限定→L13/L18; L19 post-check→L18 | 保持 | sensitive VMのreboot後疎通。 |
| UV-005 | L16限定→L13/L20; L20 daily healthcheck→L20 | 保持 | sensitive VMの日次確認。 |
| UV-006 | L16限定→L13/L22; L21異常・reboot通知→L22 | 保持 | 通知責務。 |
| UV-007 | L29二方針→L26; L31停止影響大のVM→L29; L31深夜Ansible管理→L29 | 保持 | 方針1の選択条件。 |
| UV-008 | L29二方針→L26; L32開発/backup/検証/infra node→L32; L32自動reboot→L32 | 保持 | 方針2の選択条件。 |
| UV-009 | L38 `authy`方針1→L35; L38 required時だけreboot→L35/L118; L38 healthcheckあり→L35 | 保持 | 対象と条件。 |
| UV-010 | L39 `monnie`方針1→L38; L39 required時だけreboot→L38/L118; L39 healthcheckあり→L38 | 保持 | 対象と条件。 |
| UV-011 | L40 `ansy`方針2→L41; L40 unattended任せ→L41; L40 healthcheckなし→L41/L310 | 保持 | 方針2除外。 |
| UV-012 | L41 `quory`方針2→L44; L41固定時刻→L44/L167; L41 nightly管理不可→L44/L167 | 保持 | 実行基盤の自己管理禁止。 |
| UV-013 | L43対象表追記→L47; L43方針1/2明示→L47 | 保持 | 新node分類義務。 |
| UV-014 | L51 security系定常更新→L50; L55 security archive→Repository L36; L56 ESM infra→Repository L37; L57 ESM Apps→Repository L38 | 保持 | 3 archiveの具体値はContext、定常自動更新の核はPolicy。 |
| UV-015 | L51 Ansible定常自動適用なし→L280; L51対象外通常更新だけ→L280; L51 monthly判定+確認付きmanual apply→L280 | 保持 | apt適用境界。 |
| UV-016 | L61 post-install restart→L137; L63許容→L137; L65深夜→L137; L66低需要→L137; L67低実害→L137 | 保持 | 3理由を許容条件として保持。 |
| UV-017 | L69 Package-Blacklist manual管理不採用→L283 | 保持 | 対応忘れを生む方式の禁止。 |
| UV-018 | L73通常更新monthly判定→L89; L73 node単位→L89; L73 `#patches`通知→L89 | 保持 | monthly判断単位。 |
| UV-019 | L73 `dry_run=true` read-only→L286; L73実適用は確認文字列付き→L286; L73 single-node manualだけ→L286 | 保持 | `only`とmanual confirmation。 |
| UV-020 | L75 install/remove/phasing件数→L215; L75 package別version→L215 | 保持 | monthly通知内容。 |
| UV-021 | L75 hold read-only→L92; L75 1件以上の月だけ→L92; L75 phasing直後→L92; L75件数/name→L92 | 保持 | 表示条件と位置。 |
| UV-022 | L75 Status不使用→L95; L75重要package不使用→L95; L75件数閾値不使用→L95; L75 apply判断不使用→L95 | 保持 | holdの非判断用途。 |
| UV-023 | L77同一version候補→L98; L77 metadata既知事象→L98; L77表示に残す→L98 | 保持 | 候補を隠さない。 |
| UV-024 | L77同一文字列だけを根拠に除外しない→L101 | 保持 | epoch等を隠す専用除外禁止。 |
| UV-025 | L81 registry登録対象だけ→L53; L81 `dry_run=true` monthly時だけ→L53 | 保持 | non-apt確認範囲。 |
| UV-026 | L81 monnie manual Prometheusだけ→L56 | 保持 | 初期対象を限定。 |
| UV-027 | L81 current read-only GET→L104; L81 latest read-only GET→L104; L81両方成功・数値versionだけ比較→L104 | 保持 | 比較のAND条件。endpoint詳細はRepository L44。 |
| UV-028 | L83通知/report→L218; L85 current→latest→L218; L85 manual update必要→L218 | 保持 | updateあり出力。 |
| UV-029 | L83通知/report→L221; L86 current/latest状態→L221 | 保持 | latest出力。 |
| UV-030 | L83通知/report→L224; L87取得/比較失敗→L224; L87 current/latest rc→L224 | 保持 | failure出力。 |
| UV-031 | L83 `nonapt` name/current/latest/state→L227; L83 current/latest rc・HTTP status・note→L227 | 保持 | report fields。 |
| UV-032 | L89両取得成功→L107; L89数値比較→L107; L89 update確定時だけ→L107; L89最低REVIEW_REQUIRED+reason→L107 | 保持 | AND、only、最低Status。 |
| UV-033 | L89既存BLOCKED非降格→L110; L89既存MAJOR非降格→L110 | 保持 | 上位Status保護。 |
| UV-034 | L89取得失敗→L113; L89 JSON parse失敗→L113; L89比較失敗→L113; L89 best-effort/fail-quiet→L113; L89通知/reportだけ→L113; L89 Status不変・playbook非fail→L113 | 保持 | failure例外を拡大しない。 |
| UV-035 | L91確認専用→L290/L293; L91自動downloadを一切行わない→L293 | 保持 | 独立した第1禁止。「一切」を維持。 |
| UV-036 | L91確認専用→L290/L296; L91自動更新を一切行わない→L296 | 保持 | 独立した第2禁止。「一切」を維持。 |
| UV-037 | L91確認専用→L290/L299; L91 service restartを一切行わない→L299 | 保持 | 独立した第3禁止。「一切」を維持。 |
| UV-038 | L91人間が実施→L302; L91 Notion「Prometheus / Grafana / unifi-poller セットアップ手順」→L302; L91手作業→L302 | 保持 | 自己補正対象。指定human manual手順を逐語保持。 |
| UV-039 | L91 `dry_run=false` apt apply→L305; L91 non-apt check自体を実行しない→L305 | 保持 | apply時check禁止。 |
| UV-040 | L99方針1 Automatic-Reboot false→L144 | 保持 | unattended自動reboot禁止。 |
| UV-041 | L101 timingはAnsible制御→L147 | 保持 | 方針1 controller。 |
| UV-042 | L103 nightlyがflag確認→L118; L103必要時だけreboot→L118 | 保持 | reboot許可条件。 |
| UV-043 | L105 reboot後service状態→L150; L105疎通→L150 | 保持 | post-check必須。 |
| UV-044 | L108 FreeRADIUS状態→L153; L108 1812/udp→L153; L108 1813/udp→L153 | 保持 | 自己補正対象。2 portを個別保持。 |
| UV-045 | L109 Prometheus 9090/tcp→L156; L109 Grafana 3000/tcp→L156; L109 Loki 3100/tcp→L156 | 保持 | 自己補正対象。3 service/portを個別保持。 |
| UV-046 | L113方針2 Automatic-Reboot true→L161 | 保持 | 自動reboot設定。 |
| UV-047 | L115 unattendedがflag検出→L121; L115自動reboot→L121 | 保持 | 方針2の判断。 |
| UV-048 | L117 Ansible管理なし→L310; L117監視なし→L310; L117 healthcheckなし→L310 | 保持 | 方針2の3除外。 |
| UV-049 | L121 `ansy`再構築可能→L164; L121 code/VM backup→L164/System L13; L121自動reboot許容→L164 | 保持 | 方針2例外理由。 |
| UV-050 | L122 `quory`は実行基盤→L167; L122 nightly管理不可→L167; L122 reboot time固定→L167/System L25 | 保持 | 自己管理禁止と固定時刻。 |
| UV-051 | L126いずれか→L127; L128 reboot-required file存在→L124 | 保持 | ORの第1条件。 |
| UV-052 | L126いずれか→L127; L129 needrestart reboot要→L127 | 保持 | ORを明記した第2条件。 |
| UV-053 | L135方針1 VMだけ→L73; L135 authy/monnie→L35/L38/L73; L135方針2をAnsible管理対象にしない→L73/L310 | 保持 | 自己補正対象。P3列挙はL60で許可と分離され、対象禁止を変えない。 |
| UV-054 | L144 service別専用healthcheck→L76 | 保持 | 方針1 VM契約。 |
| UV-055 | L150 read-only→L172; L150収集→L172; L150判定→L172; L150 report→L172 | 保持 | healthcheckは変更なし。 |
| UV-056 | L152 WARNING通知→L130/L245; L152 CRITICAL通知→L130/L248 | 保持 | severity判断。 |
| UV-057 | L154朝に前夜reboot/service稼働確認→L175 | 保持 | post-nightly確認。 |
| UV-058 | L156 manual単体実行可→L79 | 保持 | standalone許可。 |
| UV-059 | L146方針1共通nightly→L82; L160 radius/monitoring group→L82/Repository L13 | 保持 | group対象を方針1に限定。 |
| UV-060 | L165最初にreboot_required確認→L178 | 保持 | nightly順序1。 |
| UV-061 | L166 falseならrebootなし→L181; L166通知なし→L181/L230 | 保持 | stopとno notification。 |
| UV-062 | L167 true分岐→L184; L168 reboot前開始通知→L184 | 保持 | gate後の順序。 |
| UV-063 | L169 reboot実行→L187 | 保持 | 単一flow内の1回実行。自動反復を追加していない。 |
| UV-064 | L170起動完了待機→L190 | 保持 | reboot後順序。 |
| UV-065 | L171対象VM service確認→L193 | 保持 | 起動後post-check。 |
| UV-066 | L172確認結果通知→L196; L172 OK/CRITICAL→L196 | 保持 | 終了通知。 |
| UV-067 | L183 false時通知なし→L230 | 保持 | 通知表の停止条件。 |
| UV-068 | L184 reboot実施+OK通知→L233 | 保持 | 正常通知。 |
| UV-069 | L185 NG時CRITICAL→L236 | 保持 | 異常通知。 |
| UV-070 | L186 monthly dry-run/manual apply→L239; L186 node単位→L239; L186通常patches→L239; L186 BLOCKEDだけalerts→L239 | 保持 | channel例外。 |
| UV-071 | L187 healthcheck OK通知なし→L242 | 保持 | no notification。 |
| UV-072 | L188 WARNING通知→L245 | 保持 | warning通知。 |
| UV-073 | L189 CRITICAL通知→L248 | 保持 | critical通知。 |
| UV-074 | L193深夜送信→L251; L195翌朝確認可→L251 | 保持 | 運用例外。 |
| UV-075 | L199 common Slack task→L254; L201 Webhook Vault管理→L254 | 保持 | 通知経路と秘密管理。 |
| UV-076 | L223-224表契約→L257-260; L225 nightly開始 info/info→L261; L226 nightly正常 info/ok→L262; L227 service異常 alerts/critical→L263; L228 timeout alerts/critical→L264; L229 full-upgrade patches・BLOCKED alerts・Status別→L265; L230 health WARNING alerts/warning→L266; L231 health CRITICAL alerts/critical→L267 | 保持 | 自己補正対象。7表行を個別保持。 |
| UV-077 | L233 best-effort→L270; L233 caller playを止めない→L270 | 保持 | 通知failure例外。 |
| UV-078 | L235 Slack移行taskはmail vars非参照→L273; L235 mail module不使用→L273 | 保持 | deprecated経路禁止。 |
| UV-079 | L241 timerはquory上→L201 | 保持 | scheduler配置。 |
| UV-080 | L245 nightly timer→L204; L245毎日03:30→L204 | 保持 | schedule 1。入口は方針1共通L82。 |
| UV-081 | L246 authy healthcheck timer→L207; L246毎日05:30→L207 | 保持 | schedule 2。 |
| UV-082 | L247 monitoring healthcheck timer→L210; L247毎日05:35→L210 | 保持 | schedule 3。 |
| UV-083 | L249 Semaphore導入後→L321; L249 timerからScheduleへ移行→L321/Operations L49 | 保持 | roadmapは許可変更なし。 |

## 旧§3.4 L91と既知実装不一致

| 条件 | 旧HEAD | 新Policy | 判定 |
|---|---|---|---|
| 自動download | L91「一切行わない」 | UV-035 L292-293「一切行わない」 | 保持 |
| 自動更新 | L91「一切行わない」 | UV-036 L295-296「一切行わない」 | 保持 |
| service restart | L91「一切行わない」 | UV-037 L298-299「一切行わない」 | 保持 |
| human manual | L91の人間、指定Notion手順、手作業 | UV-038 L301-302 | 保持 |
| apt apply時のcheck禁止 | L91 `dry_run=false`時はnon-apt check自体を実行しない | UV-039 L304-305 | 保持 |

P3 L60は5入口の列挙自体を変更許可としない。L68は`prometheus_update_check.yml`を既知不一致入口と明示し、L70は現行実装のupdate / rollback / service restartと旧Policyの禁止が未解決であること、および構造変更で拡大・縮小・解消しないことを記録する。Repository Context L15/L17/L44-48も実装事実とPolicy優先を分離する。playbook / roleに差分はなく、既知不一致の範囲は不変である。

## Ledger外逆検索・自己補正4件

旧HEADの表、番号付きflow、箇条書き、`限定` / `だけ` / `のみ` / `一切` / `場合` / OR / Status非降格 / fail-quiet / single-node / manual confirmation /通知なしを83 UVから独立して逆検索した。ledger外の規範欠落は検出しなかった。

014が記録する自己補正4件も旧HEADへ逆照合した。UV-053は旧L135の方針1だけ・方針2非管理、UV-044/045は旧L108-109の全service/port、UV-076は旧L223-231の7 channel/status表行、UV-038は旧L91の人間・指定手順・手作業へそれぞれ完全到達している。抽象化、条件変更、追加の許可は残っていない。

## Migration・Context・Playbook・group境界

| 観点 | 結果 |
|---|---|
| migration 16候補 | 014 §4に16行。旧表題と§1〜§9を覆い、全行に実移動先とPolicy核到達行がある。旧§8の他system参考scheduleと旧§9 snapshotを生きた規範へ昇格していない。 |
| System Context | L5で非規範・Policy優先を明記。node、group、役割、Ubuntu Pro、reboot管理、service依存の現状に分類。既存inventory/radius/monitoring/overviewへlinkし、実値を正本化していない。 |
| Repository Context | L5で非規範・Policy優先を明記。5入口、apt/non-apt、nightly/healthcheck、report/通知の横断契約に分類。単一taskを逐語複製せず、既知不一致から許可を追加していない。 |
| Operations Context | L5で非規範・Policy優先を明記。monthly判定、manual apply、nightly、healthcheck、schedule、障害時確認の順序に分類。runbookでPolicy gateを迂回しない。 |
| Playbook 5本 | `radius_healthcheck.yml`、`monitoring_healthcheck.yml`、`ubuntu_nightly.yml`、`ubuntu_vm_full_upgrade.yml`、`prometheus_update_check.yml`がP3に各1件、実path欠落0、playbook-map owner参照5件。 |
| group所有権 | full-upgradeはgroup2主入口、Prometheus checkはgroup2関連だが変更許可なし、nightlyはreboot lifecycle従属、Codex updateはowner外、2 healthcheckはgroup1横断参照でも本Policy ownerを維持。groupをPolicy統合や許可拡張に使っていない。 |
| 重複・link | 3 ContextにPolicyへの正しい相対linkがあり、local Markdown link target欠落0。PolicyとContextの規範競合なし。 |

## 独立機械検査

| 検査 | 独立実測 |
|---|---|
| 旧HEAD正本 | HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `bf8cee43f3789dbae1b0a524f84fdb694a5445c7`、289行 |
| 新Policy | 321行。標準8節はL5/L24/L58/L84/L132/L212/L275/L312の順で各1回 |
| UV marker/index | UV-001〜UV-083 marker 83件、欠番・重複0。014 index 83行、実行行番号との不一致0 |
| migration | 16行、番号1〜16、移動先・Policy核の空欄0 |
| Playbook | 5本、重複0、実path欠落0、playbook-map参照欠落0 |
| §3.4凍結 | 独立禁止marker 3、「一切行わない」3、human manual 1、`dry_run=false`禁止1。P3に許可化する文言0 |
| Context | 3本、非規範宣言3、Policy優先3、Policy link 3 |
| scope | `playbooks/` / `roles/`のtracked・untracked差分0。指定外の既存worktree変更は編集していない。レビューでは対象5 pathを変更していない |
| 秘密・実値 | 対象5文書にIPv4 literal、VLAN ID、VM ID、認証・秘密の代入実値0。時刻、service port、version例は旧規範追跡用の非秘密値 |
| whitespace | tracked `git diff --check` PASS。未追跡3 Contextと014は個別 `git diff --no-index --check` PASS |
| runtime | 文書再構成のためAnsible・実機実行なし |

## What Looks Good

- 旧§3.4の3禁止を統合せず、各「一切行わない」とhuman manual、apt apply時check禁止を独立markerで保持している。
- P3の5入口を索引として可視化しつつ、tester/input gateと全UV規範を満たす場合だけ実行可能として、列挙を許可へ変えていない。
- Ubuntu Pro定常更新、monthly read-only判定、確認付きsingle-node manual apply、hold非判断用途、Status非降格、fail-quietを保持している。
- 方針1/2、reboot OR条件、nightly順序、post-check、healthcheck通知、channel/status 7条件を保持している。
- 3 Contextは非規範・Policy優先を明記し、System / Repository / Operationsの分類とgroup所有権が明瞭である。
- 標準8節、16 migration、83 UV、5 playbook、scope、秘密・実値、diff hygieneは要求を満たす。

## Verdict

**Approve**

旧HEADからの独立逐行照合で、許可・禁止・停止・判断条件の意味差はない。旧§3.4の既知実装不一致は意図どおり未解決のまま範囲不変であり、全83 UV、16 migration、5 playbook、3 Context、group所有権、scope、秘密・実値、whitespaceに未解決差異はない。
