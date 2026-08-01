# ADR-006: Proxmox実行ノード選定の共通機構化

**Status:** Accepted(2026-07-29。Step 1・Step 2とも実装と独立レビュー(Critical 0)を完了。**検証は一様ではない** — AC1・AC3は実機PASS、AC2はdecoyのみ(実機は両ノード停止を要するため不実施)、AC4は未実施(pve1起動が要る)。検証状態の正本は `docs/ai/reviews/proxmox_exec_node_selection/2026-07-29_007_test_result_step1.md`)

## Context

Proxmoxクラスタへ入るplaybookが、実行ノードをホスト名リテラルで決め打ちしていた。pve1は夏季平日シャットダウン運用中(`roles/recovery_probe/defaults/main.yml`)のため、これらは平日日中に機能しない。

**2箇所で現に壊れていた。**

1. **自律復旧ラダー3本**(`recovery_vm_reboot.yml` / `recovery_service_restart.yml` / `recovery_ha_failover.yml`)が `hosts: pve1` 固定。2026-07-21の `e9ac523` は `recovery_probe_pve_host` をpve2へ向けたが、そのラダーが起動するplaybook側を更新しておらず、**probe側は生きているのに実行側が死んでいる**非対称な状態だった。発火は未観測。
2. **`proxmox_backup_restore_verify.yml`** が `hosts: proxmox` + `run_once: true` で `ignore_unreachable` を持たず、inventory定義順の先頭(pve1)に `run_once` の担い手が固定されていた。2026-07-28のSemaphore job #469が `exit status 4`(`RUN_UNREACHABLE_HOSTS`)で失敗し、**健全なpve2が一度も使われないまま** `brv_restore_targets` が空になってPlay 2が丸ごとskipされた。加えてrestore先ノードを `prefer<node>` タグだけで `'pve1'`/`'pve2'` のリテラルへ写像しており、到達性を見ていなかった。

先行して `unifi_backup_fetch.yml` だけがADR-001で「pve1優先・pve2フェイルオーバー」のpreflightを持っていた。**同ADRのConsequencesは「同種の要望が他playbookでも繰り返し出た場合はOperations Context化を再検討する」と予告しており、本件がその条件成立**である。

Yoshinobuの方向性(2026-07-29):

> pveはフェイルオーバーしている可能性があることを前提にしているので、どちらかを決め打ちするのは避けたい。優先はこのノードと決めるのは良いですが、どちらかが生きていれば継続できるという考え方が好ましい。

## Options Considered

| Option | Pros | Cons |
|---|---|---|
| (a) 共通roleへ括り出し、各playbookが呼ぶ | 同一ロジックが1箇所に集まる。ノード名リテラルをinventory group + 定義順へ一般化でき、ノードが増えても効く。判定基準の変更が1箇所で済む | roleは自分でPlayを作れないため「候補group全体を`hosts:`に持つPlayから呼ぶ」という呼び出し規約が必要になる。規約違反を静的に防げず、assertで実行時に落とすことになる |
| (b) ADR-001のinline preflightを各playbookへコピーする | 各playbookが自己完結し、読むときに他ファイルを開かなくてよい。呼び出し規約が不要 | 同一ロジックが5箇所に分散する。判定基準を直すときに掃引漏れが起きる — **本件の原因そのものが「1箇所だけ直して他を取り残した」**ことであり、その形を再生産する |
| (c) 各playbookで個別に最小修正する(`ignore_unreachable`を足す等) | 差分が最小 | 「どのノードで実行するか」という同一の問いに対する答えがplaybookごとに違う状態が残る。`proxmox_backup_restore_verify` は`ignore_unreachable`だけでは直らない(restore先の決め打ちが別にある) |

## Decision

**Option (a): 共通role `roles/proxmox_exec_node` を新設し、5箇所がそれを使う。**

選定規則は「**優先ノード(`pen_prefer`)が到達可能ならそれ、でなければ候補groupの定義順で最初の到達可能ノード。全滅なら理由を明記してfail**」とする。

到達性は **fact gatheringではなく明示的な `ansible.builtin.ping` で判定する。** `proxmox_patch_dryrun` が採った `ansible_facts | length > 0` 方式は、fact cachingが有効な実行環境で**停止中のノードをキャッシュ済みfactsから到達可能と誤判定する**(2026-07-26のReviewerが `ANSIBLE_CACHE_PLUGIN=jsonfile` + `ANSIBLE_GATHERING=smart` で再現済み)。Semaphore側の環境変数はリポジトリから確認できないため、**前提を要さない判定方法を選ぶ**。

## Trade-off Analysis

- **(b)を退けた理由が本件の核心である。** 今回の欠陥は「pve1決め打ちを1箇所だけ直し、同じ問題を持つ他の箇所を取り残した」ことで生まれた。同じロジックを5箇所へ複製する選択は、次に判定基準を変えるときに同じ失敗を再生産する。
- (a)の代償である「呼び出し規約」は実在するリスクである。roleの先頭で `ansible_play_hosts_all` と `groups[pen_candidate_group]` の一致をassertして実行時に落とす形にした。**静的には防げない**ため、これは受け入れた制約である。副作用として `--limit` を使った実行がassertに掛かる。現行の5つの呼び出しはいずれも`--limit`を使わないため実害はないが、将来の運用制約として記録する。
- ラダー3本は `pen_prefer` を**空**にした。pvesh・ha-managerはクラスタ全体APIであり入口ノードがどれでも結果が同じなので、優先を持つ意味がない。`unifi_backup_fetch` だけが `pen_prefer: pve1` を維持するのは、ADR-001の決定を挙動として変えないためである(この置き換えは挙動の変更ではなく実装の共通化である)。
- **`recovery-probe.py`(Python側)はAnsibleのpreflightを使えないため別実装になる。** ここでは「操作ごとにフォールバックする」方式を**採らなかった**。`pvesh_vm_start` は非冪等(VMを起動する)であり、候補Aで実際にstartが走った後にAへの接続が切れて候補Bで再実行される二重発行が起こりうるためである。代わりに**ラダー発火のたびに先頭で1度だけread-onlyのprobeでノードを選び、以降のpvesh呼び出しは全てそのノードへ送る** — Ansible側と同じ「先に選んでから動く」構造にした。probe成功後・pvesh実行前にノードが落ちる競合窓は残るが、その場合pveshが失敗して既存のラダー失敗経路(critical通知)へ落ちるだけであり、**現行と同じ挙動**で二重発行は起きない。
- **接続失敗とコマンド失敗を文字列で判別する初版設計は、計画査読で反証されて廃棄した。** `ansible.cfg` が `display_failed_stderr` を設定しておらず既定が `no` のため、UNREACHABLEもstdoutへ出る。「stderrに `UNREACHABLE` を含むか」で判定する設計は**一度も発火しなかった**。実装前に潰せたのは計画査読の層2が現物を確かめたためである。

## Consequences

- `roles/proxmox_exec_node` が実行ノード選定の正本になる。今後Proxmoxクラスタへ入るplaybookを追加するときは、ノード名を書かずこのroleを使う。
- `recovery_probe_pve_host`(単数)を廃止し `recovery_probe_pve_hosts`(候補リスト)にした。**pve1を平日常時起動へ戻す際に変数を書き換える作業が不要になった** — 決め打ちを消したことで、申し送り自体が消滅した。
- **ADR-001はSupersedeしない。** 本ADRはADR-001の決定(pve1優先・pve2フォールバック)を一般化したものであり、`unifi_backup_fetch` の選定方針そのものは変えていない。ADR-001は当該playbookの選定方針の根拠として有効なまま残る。
- **Operations Context化(ADR-001が予告していた選択肢)は行わなかった。** 機構がroleとして実在し、呼び出し規約がrole先頭のassertとコメントに書かれている以上、同じ内容を文書へ複製すると正本が二重化する。ADRを判断の記録として残すに留めた。
- `proxmox_patch_weekly_full.yml` の per-node 固定(`hosts: pve1` / `hosts: pve2`)は**対象外とした**。各ノードを順にパッチする意図的な固定であり、片系だけで適用すると版数driftを作る(`docs/ai/policies/proxmox_operations_policy.md` SB-027 / SB-028)。ここは決め打ちのままが正しい。
- 既存の `proxmox_patch_dryrun` は引き続き `ansible_facts | length > 0` 方式のままである。**本ADRの判断(明示probe)とは異なる方式が1箇所残る。** 統一するかはSemaphore側のfact caching設定の確認結果次第であり、`docs/ai/status.md` のWatchが持つ。
