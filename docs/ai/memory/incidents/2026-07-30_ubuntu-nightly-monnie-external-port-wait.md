# Incident: ubuntu_nightly の monnie リブート後チェックが外部非公開ポートを外から叩いていた

日付: 2026-07-30(直接の契機は2026-07-30 03:35 JST。**2026-07-23 03:35 JST=`semaphore-412`にも同一の失敗が既発生していたことが後日判明**、起票は2026-07-30)
状態: 解決済み
対象: `playbooks/ubuntu_nightly.yml`(monitoring_servers / radius_servers 両ブロック)
種別: 動作不具合
原因分類: #テスト不足 #設計上の欠陥

## 症状

Semaphore job #476(nightly)が monnie で失敗し、Slackへ critical が飛んだ。

```
🔴 [ubuntu_nightly] reboot FAILED - monnie
Host: monnie
reboot タイムアウトまたは SSH 接続不能。手動確認が必要。
Time: 2026-07-30T03:35:04+09:00
```

**この文面は誤りである。** リブート自体は成功し、SSH も生きていた。実際に失敗したのは `Wait for monitoring services to be ready after reboot`(`wait_for`)である。

monnie 側の UFW ログに、コントローラからの TCP 接続が落とされた記録が残っていた。

| ポート | 待ち開始 | 120秒後 | 結果 |
|---|---|---|---|
| 9090 | 03:31:02 | 03:33:02 | timeout(UFW BLOCK。最終ログ 03:32:43 はUFWのログ抑制) |
| 3000 | 03:33:02 | — | 即通過 |
| 3100 | 03:33:03 | **03:35:03** | timeout(UFW BLOCK) |

3100 の timeout 期限 03:35:03 と Slack 送信 03:35:04 が一致する。サービス側は健全で、Prometheus は 03:30:52 に listen 済み、以後も `prometheus` / `grafana-server` / `loki` / `unpoller` はすべて active だった。**復旧操作は不要だった。**

## 原因

**UFW は正しく振る舞っていた。誤っていたのは playbook である。**

`playbooks/ubuntu_nightly.yml` の該当タスクは、コントローラから monnie の各ポートへ**外部接続**していた。

```yaml
- name: Wait for monitoring services to be ready after reboot
  ansible.builtin.wait_for:
    host: "{{ ansible_host }}"
    port: "{{ item }}"
    timeout: 120
  delegate_to: localhost        # ← 接続元がコントローラになる
  loop: [9090, 3000, 3100]
```

しかし **Prometheus 9090 と Loki 3100 は外部公開していない。** リポジトリ内でこの2ポートに触る他のすべての箇所はローカル参照である。

| 参照元 | 接続先 |
|---|---|
| `roles/monitoring_healthcheck/files/monitoring-healthcheck.sh:13,19,25` | monnie 上で `ss -H -ltn` により listen 状態を見るだけ |
| `roles/prometheus_update_check/defaults/main.yml:15` | `http://localhost:9090/-/healthy` |
| `roles/ubuntu_vm_full_upgrade/defaults/main.yml:21` | `http://localhost:9090/api/v1/status/buildinfo` |
| `roles/recovery_exec/defaults/main.yml:78,82` | `http://localhost:9090/...` / `http://localhost:3100/metrics` |
| `roles/alloy/defaults/main.yml:21` | `http://localhost:3100/loki/api/v1/push` |

外部から到達するのは Grafana 3000(Web UI)だけであり、9090 / 3100 が落とされるのは**設計どおり**である。この `wait_for` はリポジトリ内で唯一、この2ポートへ外部接続していた箇所だった。

さらに、この待ちは**重複していた**。直後の `Run monitoring healthcheck`(`roles/monitoring_healthcheck/tasks/check.yml`)が、同じ3ポートの listen 状態を monnie 上の `ss` で正しく確認している。外部 `wait_for` が足していたのは「待つ(リトライする)」ことだけだった。

### 発生頻度の訂正(2026-07-30、本Incident初版から訂正)

初版は「2026-06-28の共通化以降、約1か月潜在し2026-07-30が初回顕在化」としていたが、**これは誤りだった**。quoryからansyへ同期済みのSemaphoreログ(`reports/incidents/quory/semaphore-412/semaphore-log.log`)を確認したところ、**1週間前の2026-07-23 JSTにも同一の失敗が記録されていた**。

```
=== semaphore-412 (2026-07-23 JST / 下記ログ行はUTC表記) ===
2026-07-22 18:33:03 +0000 UTC  Origin: .../ubuntu_nightly.yml:393:11 (当時の行番号。同一のwait_for)
2026-07-22 18:35:03 +0000 UTC  Origin: .../ubuntu_nightly.yml:393:11
2026-07-22 18:35:26 +0000 UTC  [ERROR] reboot or post-reboot check failed on monnie
```

timeoutの間隔(120秒×2ポート分、JSTで03:33:03→03:35:03)まで2026-07-30 JST(=今回)と一致する。

**この節は初版でJST/UTCを混同していた**(Semaphoreログの日付をそのままJSTの日付として書き、`2026-07-22` / `2026-07-29` としていた)。Semaphoreの表示はUTC、`reports/` 配下のレポートと本リポジトリの記述はJSTであり、`docs/ai/status.md` Nextの「時刻表記JST規約をrepoへ明文化」が指摘している混在がそのまま実害として現れた実例である。**JSTでの発生日は2026-07-23と2026-07-30の2回**である。

**この欠陥は確率的ではなく決定論的である。** monnieの9090/3100はUFWで恒常的に外部非公開のため、サービス起動の遅延という「運」の要素は無く、`reboot_required=true`になった夜は**毎回確実に**失敗する。「普段エラーが来ていない」ように見えたのは、`reboot_required`がfalseの日は`meta: end_host`(L331)でホストごとにplayが終わり、この`wait_for`に到達しないためである。

```
L317/325/330  when: not reboot_required  → SKIPPED レポート
L331          meta: end_host             ← リブート不要ならここで終わり
L383-402      reboot → wait_for 9090/3000/3100
```

前回(2026-07-23 JST)は、`rescue`の誤った固定文言(「reboot タイムアウトまたは SSH 接続不能」)のせいで原因が特定されないまま見過ごされたと考えられる。初出は `3fdafbc`(2026-05-28)、現在の形は `35979b8`(2026-06-28、healthcheckを`check.yml`へ切り出して共通化したとき)。共通化で正しい内部チェックを足した際に、誤った外部`wait_for`を消さなかった。

### reboot モジュールの再接続間隔(参考情報として調査)

`ansible.builtin.reboot`の`reboot_timeout: 300`は、固定間隔でのリトライではなく**指数バックオフ**(`ansible/plugins/action/reboot.py` `do_until_success_or_timeout`: `1, 2, 4, 8, 12(上限)`秒+ジッター)で接続を試みる。「60秒間隔・5回」という区切りではない。

本番ログ(`semaphore-412`)でauthyの実測が取れた: `Reboot host`開始から`Check freeradius service status`開始まで約20秒。想定より薄い余裕で、freeradiusの起動にはこれまで間に合っていた。この間隔は起動の速いサービスであれば十分だが、保証された値ではない。

### 誤った通知文面の原因

`rescue:` が block 全体(reboot / `wait_for` / healthcheck / report / notify)を覆っており、**どこで失敗しても同じ固定文言**を送っていた。同じ形が radius_servers 側(旧 L243)にもあった。

この文面のせいで初期の切り分けが reboot / SSH 方向へ引っ張られ、さらに UFW を原因と見る方向へ進んだ。**通知が誤った対象を名指しすると、人間のゲートは機能しない。**

## 修正内容

1. **外部 `wait_for` を monnie 上での実行に変えた。** `delegate_to: localhost` を外し、`host` を省略して既定のループバックへ接続させる。ループバックで到達できることは、リポジトリ内の `http://localhost:9090/...` / `http://localhost:3100/...` の既存利用が根拠になる。外部公開を増やさずに待ちの機能だけを残した。
2. **`rescue` の文面が失敗したタスク名と理由を含むようにした**(monitoring_servers / radius_servers の両方)。`ansible_failed_task.name` と `ansible_failed_result` を使う。既存の同型実装は `roles/proxmox_backup_restore_verify/tasks/main.yml:311`。

`roles/monitoring_healthcheck` 側は変更していない(元から正しい)。

## 確認方法

- `reboot_required` が true になる次の nightly で、monnie のリブート後チェックが完走し `[ubuntu_nightly] OK - monnie` が飛ぶこと。
- 失敗時の通知に、失敗したタスク名が含まれること。
- monnie の UFW を変更していないこと(9090 / 3100 の外部非公開を維持する)。

## 残存リスク

- **リブート経路の実機検証は、次に `reboot_required` が true になる夜まで行えない。** monnie を検証目的で意図的にリブートすることはしていない(監視スタック全体を止めるため)。決定論的な欠陥である以上、修正が正しければ次回は確実に通るはずである。`docs/ai/status.md` の Watch が持つ。
- radius_servers 側は当初「未着手」としていたが、**同日中に是正した**(下記「追加修正」参照)。
- **2026-07-23 JSTの発生時、原因を特定できず見過ごされていたこと自体が別の問題である。** `rescue` の固定文言が原因調査を誤った方向へ導いたためで、今回その文言は是正した(上記「修正内容」2.)。同種の「固定文言のせいで1回分の発生が捨てられる」構造が他のplaybookに残っていないかは未調査。

## 追加修正(2026-07-30、radius_servers側)

freeradius/1812/1813のチェックにも**待ちが無い**ことが判明した(`Check freeradius service status` / `Check 1812/udp listening` / `Check 1813/udp listening` はいずれも1回きりで `failed_when: false`)。UDPポートのため `ansible.builtin.wait_for` は使えない(モジュールがTCP connectのみを実装しており、UDPのlisten判定機能を持たない。`ansible/modules/wait_for.py` の `TCPConnectionInfo` で確認)。

本番ログ(`semaphore-412`、2026-07-23 JST)では reboot開始から約20秒でfreeradiusが `active` になっており、これまでは通っていた。しかしこの間隔はコード上保証されたものではなく(`reboot`モジュールの再接続は固定間隔でなく指数バックオフであり、環境やタイミング次第で変動する)、**運が良かっただけで壊れていないと確認されたわけではない**。monnie側と実装を揃え、`until`/`retries`で待つ形にした。

```yaml
- name: Check freeradius service status
  ansible.builtin.command:
    cmd: systemctl is-active freeradius
  register: freeradius_active
  until: freeradius_active.stdout.strip() == 'active'
  retries: 12
  delay: 10
  changed_when: false
  failed_when: false

- name: Check 1812/udp listening
  ansible.builtin.shell:
    cmd: ss -ulnH 'sport = :1812'
  register: port_1812_output
  until: port_1812_output.stdout | length > 0
  retries: 12
  delay: 10
  changed_when: false
  failed_when: false
```

1813/udpも同様。`retries: 12` × `delay: 10` = 最大120秒で、monnie側の`wait_for timeout: 120`と揃えた。`failed_when: false`は維持している(`until`はregisterした値で再判定するため、タスク自体の成否とは独立に両立する)。
