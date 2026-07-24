# Code Review: Autonomous Recovery Policy 標準構造書換

## Summary

旧版正本は `git show HEAD:docs/ai/policies/autonomous_recovery_policy.md`（HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `e141d3eae0be403cc30fd6f905e08d6c2ddc51d7`、288行）から独立取得した。009/010の要約を合格根拠にせず、旧版の許可・禁止・停止・必須・例外・判断条件を原文の規範文、箇条書き、表行単位で新版へ突合した。

初回レビューではreport filenameの許可grammarに1件の厳格化・条件変更を検出し、`Request Changes` とした。再レビューでPolicy、009 ledger、010補正実績/indexを旧L90-93から再突合し、定型3 command、optional target最大1 segment、component grammar、固定`.json` suffix例外、JSON限定の全条件が復元されたことを確認した。全94 AR、22 migration、9 playbook、3 Context、scope、秘密・実値、whitespaceの回帰もPASSしたため、最終verdictは `Approve` である。

## Initial Must-fix (resolved in re-review)

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/policies/autonomous_recovery_policy.md` | 239-240 | **AR-033が旧L93の必須`.json` suffixと両立しない。** 旧L92-93は、定型3 command、optional targetは追加path segment 1つだけ、componentは英数字・underscore・hyphen、filenameは末尾`.json`必須、`list-reports`はJSONだけ、という条件だった。新版は「slash、dotその他の非許可値を拒否する」と例外なしに規定するため、正規の`<filename>.json`も拒否対象に読める。Repository Context L53はJSONだけを扱うとするが、同Context L5で非規範かつ競合時Policy優先なので矛盾を解消できない。これは許可済みreport読取りを不能にし得る厳格化・条件変更である。009 L125のAR-033要約も同じ`.json`例外を落としている。必要な修正: Policyで「componentのdotは拒否するが、filename末尾の固定`.json` suffixだけを許可する」こと、およびoptional targetは最大1 segment、一覧・表示対象はJSONだけであることを明記し、009 ledgerのAR-033要約と010 indexを修正後行へ同期する。 | must-fix |

## Re-review (final)

| 初回差異 | 修正版到達 | 再判定 |
|---|---|---|
| 旧L92-93: 定型3 command、optional target最大1 segment、component grammar、filename末尾固定`.json` suffixだけをdot例外として必須許可、list/showはJSON限定 | Policy L239-240、009 L125/L299-301、010 L184-190。marker/indexはL239で一致 | **保持**。旧条件を個別に復元し、正規JSON filenameを許可しつつ、それ以外のslash/dotを拒否する。初回の厳格化・条件変更は解消。 |

## Suggestions

なし。上記の意味差解消以外に、今回の非ゴールを広げる提案は行わない。

## 旧原文規範行の独立突合

判定は `保持 / 欠落 / 緩和 / 厳格化 / 条件・例外・順序変更` で記録した。旧行欄のセミコロン区切りは、各原文文、表行、箇条書きを個別に確認したことを表す。Contextへ移した具体的な実装値は、Policyに残る許可・禁止・停止条件と合わせて確認した。

| AR | 旧原文単位 → 新版到達行 | 判定 | 所見 |
|---|---|---|---|
| AR-001 | L16前半→L8 | 保持 | 人間承認を待たない限定自律試行。 |
| AR-002 | L16後半→L11 | 保持 | Slackは非承認gate、手動入口と通知だけ。 |
| AR-003 | L24 serviceなし→L18前半; L24 reboot→failover→L18後半/L108 | 保持 | `sophos-fw`の許可段を維持。 |
| AR-004 | L25 service→L20前半; L25 reboot→failover→L20後半/L108 | 保持 | `authy`の許可段を維持。 |
| AR-005 | L26 service→L22; L26 reboot→L22; L26 failoverなし→L22/L69 | 保持 | `monnie`のfailover禁止を維持。 |
| AR-006 | L27 action対象外→L24; L27 read-only調査→L24/L269; L35同条件→L24/L35 | 保持 | Proxmox 2 nodeは調査だけ。 |
| AR-007 | L28→L26; L35 action対象外→L26/L330 | 保持 | `ansy`除外を維持。 |
| AR-008 | L30→L129; L32 service障害class→L29/L129; L33 VM障害class→L32/L129 | 保持 | 2経路を相互代用しない。 |
| AR-009 | L32 service crashのみ→L29; L32 sophos経路なし→L29 | 保持 | service経路の対象条件を維持。 |
| AR-010 | L33 VM単位→L32; L33 `pvesh`確証→L32/L93; L33 running無応答→L32/L102; L33 `hacritical`かつ未復旧→L32/L108 | 保持 | AND条件と順序を維持。 |
| AR-011 | L35 action追加禁止→L35/L269 | 保持 | Proxmoxへの復旧手段追加禁止。 |
| AR-012 | L43定常専用・混用禁止→L179/L206 | 保持 | `ann`分離。 |
| AR-013 | L44 Slack認可のみ→L182; L44 token以外なし→L182 | 保持 | I/O職務分離。 |
| AR-014 | L45 key保持→L185; L45 tokenなし→L185; L45呼出時だけ起動→L185/L194 | 保持 | execution planeの分離。 |
| AR-015 | L46 forced-command着地専用→L188 | 保持 | landing account制限。 |
| AR-016 | L47 pause読取り権限→L191 | 保持 | probe accountを必要最小権限に限定。 |
| AR-017 | L49 recovery-exec非常駐→L194 | 保持 | 常駐process禁止。 |
| AR-018 | L57 parameter可→L197; L57 dispatch allowlist照合→L197/L214 | 保持 | 未検証parameterを実行しない。 |
| AR-019 | L58 parameter不可→L200/L320; L58固定service一式→L200/L235 | 保持 | action keyは無引数。 |
| AR-020 | L59 target固有key→L203/L147; L59固定dispatch→L203; L59引数不可→L203 | 保持 | push着地をtarget固定。 |
| AR-021 | L60 `ann` key非流用→L206/L332 | 保持 | key混用禁止。 |
| AR-022 | L62 2 entryのみ→L209; L62 template排他上書き→L209 | 保持 | investigate/actionだけを維持。 |
| AR-023 | L66 service/journal/extra/common allowlist→L214; L66非一致拒否→L214 | 保持 | 具体一覧はRepository Context L52、許可核はPolicy。 |
| AR-024 | L70 read-onlyだけ追加→L217; L70復旧command追加不可→L217 | 保持 | investigate拡張境界。 |
| AR-025 | L72 target別`investigate_services`→L220 | 保持 | service調査追加先を限定。 |
| AR-026 | L73固定name/command→L223; L73 sudo時個別同期→L223 | 保持 | extra調査の同期条件。 |
| AR-027 | L75共通allowlist source→L226 | 保持 | wrapper/dispatchの単一正本。 |
| AR-028 | L79 Codex説明同期→L229 | 保持 | 認識可能性を維持。 |
| AR-029 | L80正規setup再実行→L60 | 保持 | wrapper/dispatch/説明の同時配備。 |
| AR-030 | L82 common categoryだけ直接追加→L232; L82両template同期→L232 | 保持 | 二側検証を維持。 |
| AR-031 | L86無引数→L235; L86全allowlist service一括→L235; L86個別指定なし→L235 | 保持 | actionの対象拡張なし。 |
| AR-032 | L86 reset-failed後restart→L142 | 保持 | start-limit race回避順序。 |
| AR-033 | L90 local report→Repository L50/L83; L92定型3 command→L240/Repository L53; L92 optional target 1 segment→L240/Repository L53; L93固定base→Repository L50/L83; L93 component grammar→L240/Repository L53; L93 `.json`必須→L240/Repository L53; L93 JSONだけ列挙・表示→L240/Repository L53 | **保持** | 修正版L240が固定`.json` suffixだけをdot例外として明記し、その他のslash/dot拒否と両立。 |
| AR-034 | L94 home traverse ACL→L243/Repository L66; L94 direct read→L243; L94 sudo/setuidなし→L243 | 保持 | no escalationを維持。 |
| AR-035 | L95 wrapper→helper二層再検証→L246 | 保持 | 二層検証。 |
| AR-036 | L99 DB read-only→L249/L252; L101 4 query→L249/Repository L54; L101 `n` 1..200→Repository L54; L101 `id`整数→L249/Repository L54; L101自由SQL禁止→L249 | 保持 | 具体query grammarはContext、固定・範囲検証・自由SQL禁止はPolicy。 |
| AR-037 | L102 ACL→L252; L102 sudoなし→L252; L102 engine read-only→L252 | 保持 | DB write防止を維持。 |
| AR-038 | L103 argv配列→L255; L103文字列連結・再解釈なし→L255 | 保持 | shell injection境界。 |
| AR-039 | L109防御弱化のため解除不採用→L260 | 保持 | `no_new_privileges`解除禁止。 |
| AR-040 | L111直接ACL→L263; L111昇格なし→L263 | 保持 | Codex側no escalation。 |
| AR-041 | L115 remote SSH内sudo例外→L266; L159 Codex sandbox外という条件→L266 | 保持 | 例外経路を限定。 |
| AR-042 | L119-122 read-only調査だけ→L269; L120-122 action追加なし→L269/L330 | 保持 | Proxmox action禁止。 |
| AR-043 | L124専用key 1本→L272; L124両nodeだけ→L272 | 保持 | 目的別key分離。 |
| AR-044 | L125 `ann`非使用→L275; L125 forced-command専用account→L275 | 保持 | account分離。 |
| AR-045 | L126固定12+parameter 9だけ→L278; L127-130固定check→Repository L55; L131-134 parameter check→Repository L56 | 保持 | 列挙範囲だけを許可。 |
| AR-046 | L135-136 wrapper一次filter→L281; L137-140 dispatch本gate・独立再parse・sudo前拒否→L281 | 保持 | gate順序を維持。 |
| AR-047 | L141 dispatch正本/wrapper mirror→L284; L142 regex・limit範囲→L284/Repository L56-57; L143-144 unit/window allowlist→L284/Repository L57; L145変換・300行固定→L284/Repository L57 | 保持 | 形式・範囲・allowlist・出力量を固定。 |
| AR-048 | L146-147 argv順序・no eval→L287; L148-149書込み動詞なし→L287/L293 | 保持 | read-only argv。 |
| AR-049 | L150-152固定check 1:1・限定wildcard→L290; L152-155広いwildcard禁止・dispatch必須→L290 | 保持 | sudoers単独をgateにしない。 |
| AR-050 | L156書込み`pvesh`なし→L293; L157-158 node状態代替→L293/Repository L58 | 保持 | 書込みを構造的に不能化。 |
| AR-051 | L159 path/unit/sudoers/forced-command事前確認→L296 | 保持 | 配備前/tester gate。 |
| AR-052 | L167 60秒間隔・全対象→L132 | 保持 | 数値間隔を保持。 |
| AR-053 | L171 icmp+dns→L76; L171 5回連続→L76 | 保持 | `sophos-fw`閾値。 |
| AR-054 | L172 icmp+tcp→L79; L172同じ5回連続→L79 | 保持 | `authy`閾値。 |
| AR-055 | L173 icmp+tcp→L82; L173同じ5回連続→L82 | 保持 | `monnie`閾値。 |
| AR-056 | L175短縮名不可・FQDN必須→L135 | 保持 | target解決条件。 |
| AR-057 | L179 lock取得済みskip→L85 | 保持 | 重複停止。 |
| AR-058 | L180直近24h 3回以上→L88; L180 ladderなし→L88; L180 escalation通知だけ→L88 | 保持 | flapping条件・動作。 |
| AR-059 | L181 `pvesh`確証→L93; L182 pve到達不能でcriticalのみ→L93 | 保持 | action停止。 |
| AR-060 | L183 stoppedならstart→L96; L183 rebootではない→L96; L183 1回・復旧確認→L96 | 保持 | start分岐。 |
| AR-061 | L184 not-found→L99; L184 criticalのみ→L99 | 保持 | action停止。 |
| AR-062 | L185 running無応答だけ次段→L102 | 保持 | reboot条件。 |
| AR-063 | L186 target固定reboot 1回→L105; L186復旧時ok終了→L105 | 保持 | reboot段。 |
| AR-064 | L187 reboot後未復旧→L108; L187 failover許可targetだけ→L108/L18/L20/L22; L187 failover 1回→L108; L187未復旧escalate→L108 | 保持 | failoverのAND条件と終了。 |
| AR-065 | L191許可service OnFailure→L147/System L20; L195-196 target固有key/forced command→L147 | 保持 | push入口を限定。 |
| AR-066 | L197 target mute→L150; L197 lock取得不可時重複なし→L150 | 保持 | push停止gate。 |
| AR-067 | L198-200 investigate→判断→recover→再investigate→escalation→L153; L200 reboot/failoverなし→L153/L156 | 保持 | 順序と到達限界。 |
| AR-068 | L204 Slack手動依頼→L38; L204限定wrapper job→L38; L204同thread返信→L38 | 保持 | Slack経路。 |
| AR-069 | L210 default deny→L301; L211 target investigate→L301/Repository L59; L212 pve investigate→L301/Repository L59; L213 report→L301; L214 query→L301; L215 recover→L301; L216 monitoring→L301 | 保持 | wrapper categoryを限定。 |
| AR-070 | L217 recover wrapperなし→L304; L218固定read-only named checkだけ→L304; L219二段検証必須→L304 | 保持 | Proxmox復旧経路なし。 |
| AR-071 | L220 execpolicyにreboot/failoverなし→L156; L220 pullのtarget固定呼出し→L156 | 保持 | Codexから後段へ進めない。manual例外はL41/L62-69/L161。 |
| AR-072 | L221 4位置固定→L307/Repository L60; L221不一致拒否→L307; L221 optionをcallerから受けない→L307; L221内部固定→L307/Repository L60 | 保持 | wrapperのcaller境界。 |
| AR-073 | L222 sandbox/execpolicy別層→L310; L222 token/keyを0600・専用owner→L310/Repository L67 | 保持 | 具体modeはContext、OS権限と専用ownerはPolicy。 |
| AR-074 | L223 sudo不可→L313; L223 setuid/file capability不可→L313; L223不足権限は直接ACL→L313 | 保持 | no escalation。 |
| AR-075 | L229独立2機構→L113; L233 target別TTL mute→L113; L234 TTLなし・明示resume pause→L113 | 保持 | gateを統合しない。 |
| AR-076 | L236 mute/pause時skip→L116; L236 counter reset→L116; L236 pushもmute確認→L116 | 保持 | skip時状態処理。 |
| AR-077 | L240 evacuate 3 target/120分→L119; L241 apply 3 target/60分→L119; L242 restore 3 target/90分→L119; L243 nightly 2 target/30分→L119; L244 weekly 3 target/360分→L119; L245 full upgrade 2 target/45分→L119 | 保持 | 6組の対象とTTLを個別確認。 |
| AR-078 | L247 pause後deploy→L122; L247正常時だけresume→L122; L247失敗時pause残留→L122; L247人間の明示resumeまで全target停止→L122 | 保持 | resume例外・順序。 |
| AR-079 | L253自動検知不能class→L41; L255 Codexなし・独立playbook・人間直接→L41 | 保持 | manual例外入口。 |
| AR-080 | L257-259 service playbook→L55/L63; L259 authy/monnieだけ→L63; L259 sophos除外→L63 | 保持 | manual service target。 |
| AR-081 | L257/L260 reboot playbook→L56/L66; L260 3 targetだけ→L66 | 保持 | manual reboot target。 |
| AR-082 | L257/L261 failover playbook→L54/L69; L261 authy/sophosだけ・monnie除外→L69 | 保持 | manual failover target。 |
| AR-083 | L263 probe状態を条件にしない→L161; L263人間判断→L161; L263 target/tag/存在/HA gate→L161 | 保持 | manualでもgate迂回不可。 |
| AR-084 | L263 report/Slack共通→L169; L269 best-effort→L169; L269通知失敗は本処理へ非影響→L169 | 保持 | 通知例外。 |
| AR-085 | L269 trigger受理→L172; L269各段結果→L172; L269最終escalation→L172; L269 JST→L172 | 保持 | 通知時点。 |
| AR-086 | L275 Bash/Write/Edit/Read/Glob/Grep等禁止→L318 | 保持 | 汎用tool禁止。 |
| AR-087 | L276 action key parameter禁止→L320 | 保持 | forced-command境界。 |
| AR-088 | L277未検証値のeval/展開禁止→L322 | 保持 | injection禁止。 |
| AR-089 | L278 `action_services`外変更禁止→L324 | 保持 | action allowlist。 |
| AR-090 | L279各段2回以上禁止→L326 | 保持 | start/reboot/failover各1回と整合。 |
| AR-091 | L280 sophos OS level調査禁止→L328 | 保持 | target除外。 |
| AR-092 | L281 pve1/pve2/ansy action禁止→L330 | 保持 | 対象外3件。 |
| AR-093 | L282 `ann` key・Slack token保持禁止→L332 | 保持 | credential分離。 |
| AR-094 | L288 push失敗後Codexからreboot/failover不可→L164; L288人間escalateで終了→L164; L288 pullはping無応答だけで独立→L164; L288 manualは人間判断→L164 | 保持 | push失敗をpull発火へ流用しない。 |

## Ledger外逆検索

旧HEADの表、番号付き手順、箇条書き、`のみ` / `一切` / `必須` / `許可` / `拒否` / `skip` / `明示resume` / `人間判断`をAR ledgerから独立して逆検索した。初回は旧L92-93のAR-033に含まれる`.json` suffix例外、optional target最大1 segment、JSON限定の不足を検出した。修正版ではPolicy L240と009 L125へ全条件が到達し、ledger外を含む規範の欠落・緩和・厳格化・条件例外順序変更は0となった。

## Migration・Context・Playbook確認

| 観点 | 結果 |
|---|---|
| migration 22候補 | 010 §4に22行。旧§1〜§11を覆い、各行に実移動先とPolicy核到達行がある。修正版AR-033を含め分類・到達に欠落なし。 |
| System Context | L5で非規範・Policy優先を明記。target、account、daemon、依存の現状へ限定し、数値VM IDを転載していない。 |
| Repository Context | L5で非規範・Policy優先を明記。9入口、key、forced command、wrapper、ACL、execpolicyの横断契約を収容。L53のreport現状契約は修正版Policy L240と整合。 |
| Operations Context | L5で非規範・Policy優先を明記。mute / pause、manual、investigate追加、障害後resumeのrunbookに分類され、新しい許可を作っていない。 |
| 重複・link | 3 ContextはPolicyへ到達する相対linkを持つ。単一taskの逐語複製はなく、System / Repository / Operations分類は `context-classification.md` と整合。 |
| Playbook | Policyは9本。setup 5、action 3、notification 1でrequirementと完全一致し、9 pathすべて実在、`context/ansible/playbook-map.md`のowner / role記述と一致。 |
| 数値VM ID除去 | 旧L24-26の数値を転載せず、`sophos-fw` / `authy` / `monnie`の名前、tag gate、経路別action allowlistにより同じ対象許可を維持。 |

## 独立機械検査

| 検査 | 独立実測 |
|---|---|
| 旧HEAD正本 | HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `e141d3eae0be403cc30fd6f905e08d6c2ddc51d7`、288行 |
| 新Policy | 338行。標準8節はL5/L13/L43/L71/L124/L166/L174/L334の順で各1回。AR-033 marker L239 |
| AR marker | 94件。AR-001〜AR-094に欠番・重複なし |
| 010 AR index | 94行。全marker実行行番号との不一致0 |
| AR-033回帰 | 旧L90-93→Policy L239-240、009 L125、010 L184-190。定型3 command、最大1 optional segment、component grammar、`.json`例外、JSON限定を全件保持 |
| migration | 22行、番号1〜22、空の移動先・Policy核0 |
| Playbook | 9本、setup 5 / action 3 / notification 1、実path欠落0、playbook-map欠落0 |
| Context | 3本。非規範宣言3、Policy優先3、Policy link 3 |
| scope | `playbooks/` / `roles/`のtracked・untracked差分0。指定外の既存worktree変更は編集していない。レビューでは指定5 pathを変更していない |
| 秘密・実値 | 対象5文書にIPv4 literal、数値付きVLAN、数値VM ID実値、password/token/secret代入形式0 |
| whitespace | tracked `git diff --check` PASS。未追跡の3 Contextと010は個別 `git diff --no-index --check` PASS |
| runtime | 文書再構成のためAnsible・実機実行なし |

## What Looks Good

- 60秒間隔、target別2 probe、5回連続失敗、24時間3回以上のflapping停止条件が明示されている。
- `pvesh`の到達不能 / stopped / not-found / running無応答の4分岐と、start / reboot / failover各1回の順序・停止条件が保持されている。
- pull / push / manualのtarget allowlistを平坦化せず、pushからreboot / failoverへ進めない制約も維持している。
- mute / global pauseの独立性、skip時counter reset、push mute確認、6組のTTL、失敗時の人間による明示resumeが保持されている。
- account / token / key / forced command / wrapper / ACL / execpolicy / no escalationの防御層が分離され、禁止8件を個別に保持している。
- 標準8節、9 playbook、22 migration候補、3 Contextの分類、秘密・実値除去、diff hygieneは要求を満たす。

## Verdict

**Approve**

初回must-fix 1件は旧HEAD原文から再照合して解消した。全94 AR、22 migration、9 playbook、標準8節、Context境界、scope、秘密・実値、whitespaceの回帰に新たな差異はない。
