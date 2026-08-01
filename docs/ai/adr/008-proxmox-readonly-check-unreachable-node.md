# ADR-008: Proxmox read-only点検playbookの到達不能ノードの扱い

**Status:** Accepted(2026-07-30。実装・差分レビューApprove・AC1〜AC7全PASSまで完了。**本ADRが挙げるPolicy改訂(SB-095)の承認とcommitはYoshinobu待ち**であり、ADRの決定そのものとは別の待ちである)

## Context

夏季の室温対策でpve1を平日日中シャットダウンしている(pve2は常時稼働)。この間、Proxmoxのread-only点検playbook 3本がSemaphoreで毎回`error`になる — `proxmox_healthcheck.yml`(毎日20:40)、`proxmox_hw_check.yml`(毎日20:45)、`proxmox_snapshot_check.yml`(木09:00)。2026-07-30時点で07-22以降のほぼ全発火が赤である(実測: `docs/ai/reviews/proxmox_readonly_check_single_node/2026-07-30_001_requirement.md` §1)。

**点検機能そのものは既に片肺で成立している。** 3 roleとも集約を`ansible_play_hosts`で行っており、pve1が落ちればpve1を除いた結果が正しく出る。壊れているのは終了コードだけで、到達不能ホストが1台あるとAnsibleは`4`(`RUN_UNREACHABLE_HOSTS`)を返し、Semaphoreはそれをタスク失敗として表示する。結果として毎営業日3本が赤く並び、**本物の障害と区別できない**(2026-07-30の#482は、この赤の1つが本物かどうかを人が調査して切り分けた)。

同じ欠陥クラスは2026-07-26に`proxmox_patch_dryrun`で特定・解決済みである(ADR-002 + 追補実装)。解決策は`ignore_unreachable: true`と直後の3タスク(到達判定・全滅時の明示fail・playからの除外)を**1組で**入れる形で、`playbooks/proxmox_patch_dryrun.yml:32`・`:55-79`にある。`ignore_unreachable`だけを1行足すと、到達不能ホストがplayに残ったままrole本体へ進み、UNREACHABLEが読めないFAILED(rc=2)へ化ける。

また2026-07-29のADR-006で、「どのノードで実行するか」を決め打ちしない共通role `roles/proxmox_exec_node`が入っている。到達性は**明示的な`ping` probe**で判定する設計で、理由はSemaphore実行環境のfact cachingの有無がrepo外で確認できないため(有効だとキャッシュ済みfactsで停止ノードを「到達可能」と誤判定する。2026-07-26に再現済み)。

## Options Considered

### (a) 機構の置き場

| Option | Pros | Cons |
|---|---|---|
| a-1: 3本のplaybookへ`ignore_unreachable`+3タスクをそれぞれ直書き | `proxmox_patch_dryrun`と同じ形。roleの新設が要らない | 同一機構が計4箇所(dryrun含む)へ散る。1箇所だけ直す/漏らすドリフトが起きる。4本目を足す者が再発明する |
| a-2: 共通role `proxmox_reachable_nodes`を新設し、3本から呼ぶ | 機構が1箇所。4本目以降は2行で済む。ADR-006が同じ問い(実行ノード)で採った形と一貫する | `meta: end_host`がrole内で機能するかの前例がrepo内に無い(要検証)。play-levelの`ignore_unreachable`はroleでは設定できず、呼び出し側の責務として残る |
| a-3: 既存の`proxmox_exec_node`へmodeを足して兼用する | probeロジックの重複が無くなる | 5 playbook(recovery系3本を含む)が依存する実証済みroleへ分岐を足すことになる。出力の意味(1台を選ぶ / 全部残す)が変数で切り替わり、契約が読みにくくなる |

### (b) 到達性の判定方法

| Option | Pros | Cons |
|---|---|---|
| b-1: `ansible_facts \| length > 0`(fact gatheringの結果を見る) | 追加タスクが1つも要らない | fact cachingが有効だと停止ノードを到達可能と誤判定する(2026-07-26に再現済み)。実行環境の設定がrepo外にあり確認できない |
| b-2: 明示的な`ansible.builtin.ping` probe | 実行環境の設定に依存しない。ADR-006が同じ理由で採用済み | タスクが1つ増える |

### (c) 変更系playbookも同様に扱うか

| Option | Pros | Cons |
|---|---|---|
| c-1: read-only点検だけを片肺継続にし、変更系(`cert_renew.yml`、`ca_trust_deploy.yml`、`time_sync_ntp_reference.yml`)は厳格なまま残す | 「届かなかった配布」が赤で残る。証明書・trust storeの配布漏れは沈黙させてはならない | 変更系も同じ日程で赤くなり得る(現状Semaphoreのschedule対象ではない) |
| c-2: 到達不能を一律に許容する(全playbookへ同じroleを入れる) | 赤が完全に消える | 配布漏れが静かに成功として記録される。**片肺で成立する点検と、片肺では未達である配布を同一視することになる** |

### (d) 点検できなかったノードをどこに出すか

| Option | Pros | Cons |
|---|---|---|
| d-1: 既存のSemaphore summary 1行へ`Unchecked=`を足す | 運用者が実際に読む1行に入る。roleごとの変更は数行 | 3 roleのJinjaへ触る |
| d-2: guard roleが自分で別の1行を出す | 3 roleへ触らない | summaryが2行になり、「1行のSemaphore summary」という既存の読み方(`docs/ai/context/system/semaphore.md`)が崩れる。運用者が2行目を読む保証が無い |
| d-3: report JSONにだけ残す | 機械可読 | 赤/緑とsummaryしか見ない運用では気づけない。今回の目的(片肺の`OK`を全体の`OK`と誤読させない)に届かない |

## Decision

- **(a) a-2を採用**: 共通role `roles/proxmox_reachable_nodes`を新設する。`meta: end_host`のrole内動作は**実装の最初にdecoyで確認**し、機能しない場合はa-1へfallbackする(判断はCoordinatorへ差し戻す)。a-3を採らないのは、recovery系を含む5 playbookが依存する実証済みroleへ、出力の意味が変わる分岐を足すリスクを避けるため。probe 2タスク分の重複は受け入れ、**probeの消費者が3つ目に増えた時点で共通化を再検討する**。
- **(b) b-2を採用**: `ping` probeで判定する。ADR-006と同じ理由・同じ式(`roles/proxmox_exec_node/tasks/main.yml:49-59`)を使う。
- **(c) c-1を採用**: 対象はread-only点検3本に限る。変更系playbookは到達不能で失敗させたままにする。**「点検は片肺でも成立するが、配布は片肺では未達である」**という区別を明示的な線引きとして残す。
  - **2026-08-01追記: `cert_renew.yml`についてはこの決定を見直した。** 当時の前提は「変更系は到達不能で赤くなるだけ」だったが、実測により、`serial: 1` を持つ同playbookでは到達不能nodeがplaybook全体を打ち切り、**CA秘密鍵をtmpfsから削除するcleanup playまで実行されなくなる**ことが判明したため。見直し後も「配布は片肺では未達である」という区別自体は維持しており、未達をSlackのWARNINGとして残す形に置き換えただけである(赤を消す代わりに未達を隠さない)。`ca_trust_deploy.yml`・`time_sync_ntp_reference.yml`についてはc-1のままである。正本は`docs/ai/policies/cert_renew_policy.md` CERT-023、経緯は`docs/ai/reviews/cert_renew_unreachable_node/`。
- **(d) d-1を採用**: summary 1行へ、到達不能ノードがあるときだけ`Unchecked=<node,...>`を足す。無いときは表記自体を出さない(両ノード正常時の出力を変えない)。

## Trade-off Analysis

4つの決定はいずれも「新しい独自機構を増やさず、既に実証済みの形(ADR-002の1組、ADR-006のprobe、既存summary 1行)を再利用する」方針で一貫している。

a-2の代償は、`proxmox_exec_node`とのprobe重複(約2タスク)と、`ignore_unreachable`がroleの中に入りきらないことである。後者は「roleを入れたのにplay-levelキーワードを書き忘れる」という設定漏れの余地を残すが、その症状は**rcが4のまま**という形で受入条件(AC1〜AC3)が直接検出する。無言で壊れる形ではないため受け入れる。

a-1(3箇所inline)を採らないのは、これが**すでに1度掃引漏れを起こしたクラス**だからである。2026-07-26にdryrunだけを直した結果、同じ欠陥が3本に残り4日後まで気づかれなかった。機構が1箇所にあれば「次の1本」は2行で済み、漏れの起点が消える。

c-1は赤を完全に消さない。変更系playbookがpve1停止中に走れば赤くなる。これは意図した残存であり、**赤の意味を「本当に見るべきもの」へ寄せることが目的**である(赤をゼロにすること自体は目的ではない)。

## Consequences

- 新role `roles/proxmox_reachable_nodes`(`tasks/main.yml` + `defaults/main.yml`)が追加される。契約の正本は`docs/ai/reviews/proxmox_readonly_check_single_node/2026-07-30_002_plan.md` §1-1。
- `playbooks/proxmox_healthcheck.yml`・`proxmox_hw_check.yml`・`proxmox_snapshot_check.yml`にplay-levelの`ignore_unreachable: true`と当該roleが入る。**`roles:`リストの先頭に置くことが契約**である(順序が変わると点検roleが到達不能ノードでも走る)。
- 新roleの呼び出し規約は「playの`hosts:`が候補groupの**部分集合**であること」である。**厳密一致にしない** — SB-021が許可する`--limit <node>`単一node実行が壊れるため(2026-07-30の差分レビューCritical #1)。`roles/proxmox_exec_node`のT1は厳密一致のままであり、そちらで`--limit`が許容されるべきかは本ADRの対象外で、申し送りとして残す。
- 3 roleのsummaryに`Unchecked=`が条件付きで入る。`prn_unreachable_nodes | default([])`により、`proxmox_patch_dryrun.yml`が`include_role`で`proxmox_healthcheck`を呼ぶ経路の出力は変わらない。
- `playbooks/proxmox_patch_weekly_full.yml`のStep 1bに、候補ノードが全て到達可能であることの明示ゲートが入る。**停止条件は変えず、停止理由が読めるようにするだけ**である(healthcheckが片肺で完走するようになった帰結として、未定義変数エラーで落ちるのを防ぐ)。
- `docs/ai/policies/proxmox_operations_policy.md` §3.2 にSB-095を新設する(Yoshinobu承認事項)。当時`proxmox_snapshot_check`はpatch domain外でPolicyの置き場が無く、その挙動の根拠は本ADRと当該playbookの冒頭コメントが持つ、という判断だった(2026-08-01のPolicy改名・scope拡張でこの前提は解消し、当該playbookはSB-020の安全度表にも載る。本ADRの記述は決定当時の記録として残す)。
- `playbooks/proxmox_patch_dryrun.yml`のinline実装は今回そのまま残す。将来これを本roleへ寄せ替えると、`docs/ai/status.md` Watchの「Semaphoreでfact cachingが有効だとdryrunが停止ノードを到達可能と誤判定する」がrepo側で塞がる(P1-1)。**寄せ替えるまでの間、同一機構が2つ並存する**ことは既知の負債として残る。
- 変更系playbook(`cert_renew.yml`、`ca_trust_deploy.yml`、`time_sync_ntp_reference.yml`)は対象外であり、pve1停止中に実行すれば失敗する。これは仕様である。**ただし`cert_renew.yml`は2026-08-01に対象外の扱いを見直した(上記Decision (c)の追記を参照)。残る2本については本項のままである。**
