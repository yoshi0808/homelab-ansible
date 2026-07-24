# Code Review: Proxmox Backup Restore Verify Policy 標準構造書換

## Summary

旧版正本は `git show HEAD:docs/ai/policies/proxmox_backup_restore_verify_policy.md`（HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `9204b94e61d0f3eb652e03406373cbacc5d0af5d`、217行）から独立取得した。017/018の要約を合格根拠にせず、旧版の全規範文、表行、箇条書きを新版へ突合した。旧版の数値restore VMIDは本レビューへ転載せず、旧行番号と「専用固定restore VMID」で追跡する。

全82 BRVとledger外を逆検索し、許可、禁止、停止、正常性、lock、cleanup、ownership、終了code、通知に欠落、緩和、厳格化、条件・例外・順序変更は検出しなかった。manual bypassはrotationだけ、危害防止はlock非依存、ownershipはown / empty / other、cleanupはAND、非ゼロ終了はverification failure OR cleanup failureを保持する。stop / notificationはbest-effortで、other-owner、unlock、report保存を新たな失敗条件へ追加していない。

## Must-fix

なし。

## Suggestions

なし。lock所有権方式の再設計や除外scopeの実装は今回の非ゴールへ広げない。

## 旧原文規範行の独立突合

判定は `保持 / 欠落 / 緩和 / 厳格化 / 条件・例外・順序変更` で記録した。旧行欄のセミコロン区切りは、原文の文、表行、箇条書きを個別に確認したことを表す。

| BRV | 旧原文単位 → 新版到達行 | 判定 | 所見 |
|---|---|---|---|
| BRV-001 | L16 monthly実restore/boot→L8; L17-18 silent corruption・本番無影響→L8 | 保持 | 目的と非影響条件。 |
| BRV-002 | L20専用固定restore先→L11/L19; L20本番config readだけ→L11/L262 | 保持 | 数値実値なしで固定先と本番禁止を保持。 |
| BRV-003 | L28 `verify` tag→L16; L28 monthly rotation→L16; L28 1台→L16 | 保持 | 対象のAND条件。 |
| BRV-004 | L29固定restore VMID→L19; L29検証専用・使い捨て→L19 | 保持 | `verify_restore_vmid`を値の正本とする。 |
| BRV-005 | L30 `prefer<node>` tag→L63; L72 tagなしfail→L63/L87 | 保持 | restore node決定と停止。 |
| BRV-006 | L31 production/quory→L22; L31 development/manual/ansy→L22 | 保持 | 実行元分離。 |
| BRV-007 | L32 source未指定→L66; L32 NFS type→L66; L32 backup content→L66 | 保持 | storage自動検出条件。 |
| BRV-008 | L33 restore storage固定→L25; L33現行storage名→Repository L27/System L53 | 保持 | storage値はvars/code、専用storage条件はPolicy。 |
| BRV-009 | L34 controlled apply→L28; L34専用restore VM create/start/delete→L28; L34本番reboot/migrateなし→L28 | 保持 | 変更対象を分離。stopはBRV-071で保持。 |
| BRV-010 | L41 inventory/group_vars/host_vars非変更→L31; L41 tag動的決定→L31 | 保持 | 対象source。 |
| BRV-011 | L43-47対応playbook 1本→L51/L54 | 保持 | 入口列挙はL47で許可と分離。 |
| BRV-012 | L53 cluster resources→L69; L53-54 Ansible listなし→L69; L54 tagだけで増減→L69 | 保持 | 動的選定。 |
| BRV-013 | L58 `verify` tag付きQEMUだけ→L72 | 保持 | monthly候補allowlist。 |
| BRV-014 | L59 VM ID昇順→L75; L59 deterministic順序→L75 | 保持 | rotation順。 |
| BRV-015 | L60 `(現在月 - 1) % list長`→L78 | 保持 | 自己補正対象。`-1`を含む式を保持。 |
| BRV-016 | L62 tagだけで増減/index再計算→L34; L63月番号固定・履歴不要→L34/L288 | 保持 | 現行非永続化を将来禁止へ拡張しない。 |
| BRV-017 | L67 target指定→L81; L67 rotation無視→L81/L95; L67 direct manual対象→L81 | 保持 | bypassはrotationだけ。 |
| BRV-018 | L68 manual対象不存在fail→L84 | 保持 | existence gate。 |
| BRV-019 | L72 `prefer<node>`決定→L87; L72 tagなしfail→L87 | 保持 | manualでも迂回不可。 |
| BRV-020 | L73-74本番config read→L90; L74 agent `1` OR `enabled=1`→L90; L74それ以外agent無し→L90 | 保持 | expectation判断。 |
| BRV-021 | L75 `add_host` dynamic group→L177; L75-77 Play 2は選定nodeだけ→L177 | 保持 | dynamic host handoff。 |
| BRV-022 | L83 NFS accessのためroot→L37 | 保持 | 権限をPolicy外許可へ拡張しない文言を追加。 |
| BRV-023 | L86 minimal lockが先→L182; L87開始前残骸guardが次→L182/L126 | 保持 | lifecycle先頭順序。 |
| BRV-024 | L87既存restore残骸→L126; L87非接触→L126; L87 critical通知・中断→L126 | 保持 | 自己補正対象。停止条件を復元。 |
| BRV-025 | L88 latest backup→L93; L96 storage API ctime最新→L93 | 保持 | backup selection。 |
| BRV-026 | L89 restore→L184 | 保持 | 専用固定restore先だけ。 |
| BRV-027 | L89 restore後owner token刻印→L186 | 保持 | ownership順序。 |
| BRV-028 | L90 boot前NIC device削除→L188; L90 IP指定なし→L188/L268 | 保持 | isolation条件。 |
| BRV-029 | L91 NIC切断後start→L190 | 保持 | start順序。 |
| BRV-030 | L92 start後health判定→L192 | 保持 | 正常性判定順序。 |
| BRV-031 | L93 failureをrescue捕捉→L195 | 保持 | verification failure記録。 |
| BRV-032 | L94 always→L198; L94 cleanup→unlock→report→notify→conditional re-fail→L198 | 保持 | 成否に関係なく順序を維持。 |
| BRV-033 | L98-99 restore/set/start/stop/destroy/guest command条件→L201; L99 OK/NG/fail制御→L201 | 保持 | Ansible task責務。 |
| BRV-034 | L100専用shellなし→L235 | 保持 | 破壊・判断をshellへ移さない。 |
| BRV-035 | L106 expectationは本番agent→L100; L106実測はrestore VM→L100; L107期待到達で合否→L100 | 保持 | 正常性の比較軸。 |
| BRV-036 | L111 agent対応→L103; L111 osinfo成功→L103 | 保持 | agent有り基準。 |
| BRV-037 | L112 agent無し→L106; L112 settle後もrunning→L106 | 保持 | agent無し基準。 |
| BRV-038 | L114 running継続だけ→L238; L114特定製品を特別扱いしない→L238 | 保持 | 現行合格基準。 |
| BRV-039 | L115-116判定block分離→L241; L115-116将来serial差替え→L241; 現行へ追加なし→L241 | 保持 | future scopeを現行化しない。 |
| BRV-040 | L124同時実行を運用で禁止→L244 | 保持 | operational prohibition。 |
| BRV-041 | L124-125 lockは補助minimal guard→L111; L124-125完全distributed排他でない→L111 | 保持 | lockへ危害防止を依存させない。 |
| BRV-042 | L127 monthly/quory→L40; L127固定時刻single schedule→L40 | 保持 | production scheduling。 |
| BRV-043 | L128 manual/ansy→L114; L128人がmonthly非重複確認→L114 | 保持 | human gate。 |
| BRV-044 | L132 official pmxcfs lock→L117; L132-133 atomic mkdir→L117 | 保持 | minimal lock取得。 |
| BRV-045 | L133 existing lock→L120; L133即fail/通知/非ゼロ→L120; L133待機なし→L120 | 保持 | stop・notification・exit。 |
| BRV-046 | L134 empty directory→L123; L134-135 pmxcfs 120秒stale回収→L123; L135 crash lock自動回収・manual削除不要→L123 | 保持 | 自己補正対象。時間とmanual不要を保持。 |
| BRV-047 | L136 refresherなし→L247; L136期限更新なし→L247; L136生存監視なし→L247; L136孤児管理なし→L247 | 保持 | minimal design。 |
| BRV-048 | L137取得時だけrelease→L204; L137 empty directory rmdir→L204; release失敗だけでfailureにしない→L204/L155 | 保持 | ownership付きunlock。 |
| BRV-049 | L139-141危害防止をlockでなくguardへ→L250 | 保持 | lock非依存原則。 |
| BRV-050 | L143 destroy先hard assert→L253; L143専用固定restore先以外を絶対destroyしない→L253 | 保持 | 独立hard guard。 |
| BRV-051 | L144開始前既存restore→L129; L144非接触→L129; L144 critical通知・停止→L129 | 保持 | residue guard。 |
| BRV-052 | L145-147 own tokenだけdestroy→L134 | 保持 | ownership own分岐。 |
| BRV-053 | L145-147 unmarked→L137; L146 no-overlap前提の自run途中失敗→L137; L146 destroy許可→L137 | 保持 | empty例外。 |
| BRV-054 | L146-147 other token→L140; L147非接触→L140; otherだけでfailure追加なし→L140/L155 | 保持 | other-owner禁止と非失敗条件。 |
| BRV-055 | L151 stale回収窓超過→L256; L151低頻度overlap→L256; L151-152一時検証1 cycle損失を受容→L256 | 保持 | residual riskの条件。 |
| BRV-056 | L152本番影響なし→L259; L152-153運用判断として受容→L256/L259 | 保持 | 自己補正対象。最悪影響を検証resourceへ限定。 |
| BRV-057 | L159 restore試行→L143; L159 AND開始前残骸でない→L143; L159両方の場合だけ→L143 | 保持 | cleanup AND gate。 |
| BRV-058 | L160 live state再取得→L146 | 保持 | stale stateを使わない。 |
| BRV-059 | L160 restore VM現存→L149; L160 ownership true→L149; L160 stop best-effort→L149; L160-161 destroy/purge→L149 | 保持 | stopとdestroyを同じbest-effortにしない。 |
| BRV-060 | L162 destroy失敗かつVM残存→L152; L162 cleanup false→L152 | 保持 | cleanup failure。 |
| BRV-061 | L163 verification failure→L155; L163 OR cleanup failure→L155; L163いずれかで非ゼロ→L155 | 保持 | 終了OR。other/unlock/reportは追加しない。 |
| BRV-062 | L169 common Slack task→L209; L169 best-effort→L209; 通知失敗で結果/exit不変→L209 | 保持 | notification非失敗条件。 |
| BRV-063 | L169-170 priority critical > error > ok→L212 | 保持 | 通知優先順位。 |
| BRV-064 | L174 verification OK→L221; L174 info/ok→L221 | 保持 | 通知表1。 |
| BRV-065 | L175 restore失敗/health未達→L224; L175 alerts/error→L224 | 保持 | 通知表2。 |
| BRV-066 | L176開始前残骸/destroy失敗→L227; L176 alerts/critical→L227 | 保持 | 通知表3。 |
| BRV-067 | L178 JSON report→L230; L178 configured directory→L230/Repository L63-66; report失敗だけでnon-zero追加なし→L230/L155 | 保持 | report非失敗条件。 |
| BRV-068 | L184本番VMはconfig readだけ→L262 | 保持 | §9制約1。 |
| BRV-069 | L185秘密を扱わない→L265 | 保持 | §9制約2。 |
| BRV-070 | L186 IP literal禁止→L268; L186-187 NICはdevice削除→L268; L187 IP指定なし→L268 | 保持 | §9制約3。 |
| BRV-071 | L188変更系→L271; L188-189専用restore create/start/stop/deleteだけ→L271; L189本番config read-only→L271 | 保持 | §9制約4。 |
| BRV-072 | L195-198 rotation/latest/restore/NIC/health/destroy/safety/lock/Slack→L43 | 保持 | 旧§10.1 current scope。 |
| BRV-073 | L202 serial console matchを次phase→L274 | 保持 | 旧§10.2除外1。 |
| BRV-074 | L203 freshness checkを別playbook/取得側整備後→L277 | 保持 | 旧§10.2除外2。 |
| BRV-075 | L204月番号固定でhistory不要→L288; 将来永続化禁止へ拡張しない→L288 | 保持 | 旧§10.2除外3。 |
| BRV-076 | L210 lock ownership深掘りより本質重視→L160 | 保持 | §11 review方針。 |
| BRV-077 | L212 latestかつ正しいtarget backup→L163 | 保持 | §11現役判断1。 |
| BRV-078 | L213 NIC切断後boot+有効health→L166 | 保持 | §11現役判断2。 |
| BRV-079 | L214 destroy先が構造的固定→L280 | 保持 | §11現役判断3。 |
| BRV-080 | L215 failure時の安全cleanup→L169 | 保持 | §11現役判断4。 |
| BRV-081 | L216 Slack/report/exit codeが実結果と一致→L172 | 保持 | §11現役判断5。 |
| BRV-082 | L217本番VMへ変更なし→L283 | 保持 | §11現役判断6。 |

## 重点条件の独立確認

| 観点 | 旧HEAD | 新Policy | 判定 |
|---|---|---|---|
| manual bypass | L67-68はrotationだけを迂回し、存在しなければfail。L72-74等の後続gateは残る | L81/L84/L87/L90/L95。存在、restore node、agent期待、本番非変更、固定restore/destroy guardを迂回しない | 保持 |
| lock非依存guard | L139-147のfixed destroy assert、開始前residue、owner token | L125-140/L249-253。lockは補助で、3 guardを独立保持 | 保持 |
| ownership | L145-147 own / unmarked / other | L133-140。ownはdestroy、emptyはno-overlap前提、otherは非接触 | 保持 |
| cleanup | L159「restore試行」AND「開始前残骸でない」、L160 live/ownership | L142-152でAND、live state、existence、ownership、destroy failureを順に保持 | 保持 |
| 終了code | L163 verification failure OR cleanup failure | L154-155。同じORだけを非ゼロ条件とする | 保持 |
| best-effort /非失敗 | L160 stop、L169 notificationはbest-effort。L163のOR以外を終了条件にしない | L149 stop、L209 notification。L140/L155/L204/L230でother-owner/unlock/reportを新規failureにしない | 保持 |
| risk-accepted | 実playbook先頭のtester-gateがrisk-accepted、roleは`check_mode: false` | L47/L56。`--check`でも本実行、`tester_mode=true`拒否、Yoshinobu明示判断 | 保持 |

## §9・§10統合と§11

旧§9 L184-189の4規範はBRV-068〜071としてP7 L261-271へ全量統合され、本番非変更、秘密禁止、IP literal禁止/NIC device削除、専用restoreだけの変更許可を保持する。

旧§10.1 L195-198はBRV-072としてP2 L42-43、旧§10.2のserial / freshness / historyはBRV-073〜075としてP7/P8 L273-288へ分割した。現行除外を許可へ変えず、history不要を将来の永続化禁止へ厳格化していない。

旧§11 L212-217の6判断はBRV-077〜082へ一対一で到達する。review方針自体もBRV-076へ残り、lock ownershipだけを過度に深掘りして本質的な6判断を落としていない。

## Ledger外逆検索・自己補正

旧HEADの表、lifecycle、番号付きrotation、箇条書き、`だけ` / `のみ` / `絶対` / `場合` / AND / OR / best-effort / 非ゼロ / fail /中断を82 BRVから独立して逆検索した。ledger外の規範欠落は検出しなかった。

018が記録する自己補正も旧HEADへ逆照合した。BRV-024は旧L87の残骸非接触・critical・中断、BRV-015は旧L60のmonth index式の`-1`、BRV-046は旧L134-135のempty・120秒・manual削除不要、BRV-056は旧L151-153の使い捨て検証1 cycleだけ・本番無影響という残余risk境界へ完全到達している。

## Migration・Context・Playbook確認

| 観点 | 結果 |
|---|---|
| migration 20候補 | 018 §4に20行。旧表題と§1〜§11、数値restore VMID横断除去を覆い、全行に実移動先とPolicy核到達行がある。§9+§10の統合・分割も上記どおり。 |
| System Context | L3へ非規範宣言、patch Policyとbackup restore Policyそれぞれの正本・競合時優先を追加。HEAD比で既存L1-40を削除・改変せず、既存patch分類追記L41-46も保持したままbackup環境事実L48-54だけを追加している。 |
| Repository Context | L3で非規範・Policy優先を明記。1入口、2-play data flow、role lifecycle、lock/ownership/cleanup、report/通知のcross-file契約に分類し、単一taskのcommand・式・既定値はcode/varsを正本とする。新しい許可・failure条件なし。 |
| Playbook | `proxmox_backup_restore_verify.yml`がP3に1件、実pathあり、playbook-map owner/role/typeと一致。tester-gateはrisk-acceptedで、3箇所の`check_mode: false`を確認。 |
| link /重複 | Policy、System Context、Repository Context、018のlocal Markdown link target欠落0。Contextは同一規範の第二正本を作らず、環境事実とRepository横断契約を分離。 |

## 独立機械検査

| 検査 | 独立実測 |
|---|---|
| 旧HEAD正本 | HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `9204b94e61d0f3eb652e03406373cbacc5d0af5d`、217行 |
| 新Policy | 293行。標準8節はL5/L13/L45/L58/L174/L206/L232/L285の順で各1回 |
| BRV marker/index | BRV-001〜BRV-082 marker 82件、欠番・重複0。018 index 82行、実行行番号との不一致0 |
| migration | 20行、番号1〜20、移動先・Policy核の空欄0 |
| Playbook | 1本、実path欠落0、playbook-map owner参照1、risk-accepted marker 1、`check_mode: false` 3 |
| Context | 2本、非規範/Policy優先宣言2、Policy link 2。System既存patch差分の削除・上書き0 |
| scope | `playbooks/` / `roles/`のtracked・untracked差分0。他Policyの既存差分は編集していない。レビューでは対象4 pathを変更していない |
| 秘密・実値 | 対象4文書にIPv4 literal、VLAN ID、数値VM ID、認証・秘密の代入実値0。旧数値restore VMIDは019にも転載していない |
| whitespace | tracked `git diff --check` PASS。未追跡Repository Contextと018は個別 `git diff --no-index --check` PASS |
| runtime | 文書再構成のためAnsible・実機実行なし |

## What Looks Good

- manual bypassをrotationだけに限定し、存在、restore node、agent期待、本番非変更、固定restore/destroy guardを明示的に維持している。
- lockを運用上の同時実行禁止の補助とし、fixed destroy assert、residue、owner tokenによる危害防止をlockから独立させている。
- own / empty / other、cleanup AND、verification failure OR cleanup failureを平坦化せず、stop / notificationとdestroy failureを区別している。
- rescue / alwaysの順序、other-owner / unlock / report非失敗条件、3通知状態、§11の6判断を保持している。
- risk-accepted入口が`--check`でも本実行になることを明示し、P3列挙をdry-run許可へ読み替えていない。
- 標準8節、82 BRV、20 migration、1 playbook、2 Context、scope、秘密・実値、diff hygieneは要求を満たす。

## Verdict

**Approve**

旧HEADからの独立逐行照合で、許可、禁止、停止、正常性、lock、cleanup、ownership、終了code、通知の意味差はない。§9+§10統合、§11現役6判断、82 BRV、20 migration、1 playbook、Context境界、scope、秘密・実値、whitespaceに未解決差異はない。
