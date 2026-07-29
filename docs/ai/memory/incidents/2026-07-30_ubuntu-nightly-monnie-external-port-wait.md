# Incident: ubuntu_nightly の monnie リブート後チェックが外部非公開ポートを外から叩いていた

日付: 2026-07-30(発生 2026-07-30 03:35 JST、起票同日)
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

### なぜ約1か月気づかれなかったか

`reboot_required` が false の日は `meta: end_host`(L331)でホストごとに play が終わるため、**リブートしない日はこの `wait_for` に到達しない。**

```
L317/325/330  when: not reboot_required  → SKIPPED レポート
L331          meta: end_host             ← リブート不要ならここで終わり
L383-402      reboot → wait_for 9090/3000/3100
```

初出は `3fdafbc`(2026-05-28)、現在の形は `35979b8`(2026-06-28、healthcheck を `check.yml` へ切り出して共通化したとき)。**共通化で正しい内部チェックを足した際に、誤った外部 `wait_for` を消さなかった。** 以後 monnie にリブートが必要な夜が来なかったため、2026-07-30 の初回リブートで初めて顕在化した。「普段エラーが来ていない」のは正常だったからではなく、その分岐に入っていなかったからである。

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

- **リブート経路の実機検証は、次に `reboot_required` が true になる夜まで行えない。** monnie を検証目的で意図的にリブートすることはしていない(監視スタック全体を止めるため)。`docs/ai/status.md` の Watch が持つ。
- radius_servers 側はリブート直後に `systemctl is-active` を即座に確認しており、待ちが無い。`failed_when: false` のため rescue ではなく CRITICAL になる経路で、今回の修正対象ではないが、freeradius の起動が遅い場合に誤 CRITICAL になりうる。未着手。
