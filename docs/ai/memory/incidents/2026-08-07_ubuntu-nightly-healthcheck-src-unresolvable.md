# Incident: パスincludeでrole contextが消え、healthcheckスクリプトを配れなかった

日付: 2026-08-07
状態: 解決済み
対象: `roles/monitoring_healthcheck/tasks/check.yml` / `playbooks/ubuntu_nightly.yml`
種別: 動作不具合
原因分類: #製造ミス #テスト不足

## 症状

Semaphore ジョブ #607(`SEMI-SAFE: Ubuntu nightly`、2026-08-07 03:30:01〜03:31:04 JST)が monnie で失敗し、赤で終わった。

```
Copy monitoring healthcheck script | monnie
Could not find or access 'monitoring-healthcheck.sh'
Searched in:
  <repo>/roles/monitoring_healthcheck/tasks/files/monitoring-healthcheck.sh
  <repo>/roles/monitoring_healthcheck/tasks/monitoring-healthcheck.sh
  <repo>/playbooks/files/monitoring-healthcheck.sh
  <repo>/playbooks/monitoring-healthcheck.sh
```

**monnie 自体は健全だった。** リブートは成功しており(03:30:45 に起動、prometheus / grafana / loki / unpoller はいずれも active、failed units 0、ディスクにも余裕あり)、証拠バンドルの `collection_errors` も空である。落ちたのはリブート後の healthcheck 工程で、**スクリプトを Ansible Controller 側で見つけられなかったことだけ**が原因でジョブが赤くなった。

Semaphore の UI が見出しに出すのは `Re-raise reboot failure`(`playbooks/ubuntu_nightly.yml:540`)である。これは rescue の最後に置いた**意図的な再送出**で、文言(`reboot or post-reboot check failed on monnie`)は固定であり何が壊れたかを含まない。実際の失敗タスク名は Slack 本文と `semaphore-errors.log` の側にある。**2026-07-30 の Incident(`2026-07-30_ubuntu-nightly-monnie-external-port-wait.md`)で「固定文言を SSH 障害と誤読した」ことへの対策として失敗タスク名を載せる形に直してあり、その対策が今回機能した。**

## 原因

`roles/monitoring_healthcheck/tasks/check.yml` の `copy` は `src: monitoring-healthcheck.sh` という**裸の相対名**だった。この task ファイルには呼び出し元が2つある。

| 呼び出し元 | 呼び方 | `roles/monitoring_healthcheck/files/` を探すか |
|---|---|---|
| `playbooks/monitoring_healthcheck.yml` | `roles:` で role として | **探す**(role context がある) |
| `playbooks/ubuntu_nightly.yml:453` | `include_tasks` にパスを与えて | **探さない** |

**パスを与えた include には role context が無い。** Ansible は task ファイルの隣と playbook の隣しか探さず、role の `files/` は候補に入らない。症状に出た4つの探索パスがそのまま裏付けになっている。

**なぜ今まで露見しなかったか。** ubuntu_nightly のこのブロックは monnie の `reboot_required` が true の夜にしか実行されない。role 経由の日次 healthcheck は同じ task を正しく解決するため緑のままで、**「同じコードが片方の呼び出し元でだけ壊れている」状態が観測されなかった。** 昨夜が、この分岐を実データで通した最初の機会である(`docs/ai/status.md` の Watch「ubuntu_nightly の monnie / authy リブート経路の**成功側**が実機で通るか」がまさにこれを待っていた。待っていた検証対象とは別の理由で落ちた)。

## 修正内容

`src` を明示パス(`{{ playbook_dir }}/../roles/monitoring_healthcheck/files/monitoring-healthcheck.sh`)へ変更した。`playbook_dir` は include する playbook の位置で決まるため、**role 経由・パス include 経由のどちらでも同じファイルへ解決する。** `roles/recovery_push/tasks/drill_setup.yml:8` が同じ形を既に採っており(こちらはパス include 専用)、リポジトリ内の前例に合わせた。

なぜこの形かを、次に読む人が縮めないよう task の直上にコメントで残した。

**横断確認**: パス include される role task ファイルは5本(`common_slack/tasks/capture.yml` / `notify.yml`、`monitoring_healthcheck/tasks/check.yml`、`recovery_mute/tasks/set.yml`、`recovery_push/tasks/drill_setup.yml`)。相対 `src` を持っていたのは `check.yml` の1本だけで、`drill_setup.yml` は既に明示パス、残る3本はファイル参照を持たない。**同型は他に無い。**

## 確認方法

案件記録は `docs/ai/reviews/ubuntu_nightly_healthcheck_src/`。

- 2つの呼び出し元の**両方**で `Copy monitoring healthcheck script` が skip されずに解決することを実測した(2026-08-07、Tester)。sandbox で本実行し配られたファイルが `roles/monitoring_healthcheck/files/monitoring-healthcheck.sh` と md5 一致、本番 monnie は `--check` で sha1 照合し mtime・checksum とも不変。**4パターンとも `Copy` は `ok` / `changed` であり、skip を成立と読んでいない。** なお `ubuntu_nightly.yml` 本体は `--check` では当該ブロックが `when: not ansible_check_mode` でまるごと skip されるため、`playbook_dir` を揃えた使い捨て playbook を `playbooks/` 配下へ一時的に置いて path include の形を再現している(検証後に削除済み)。
- 実運用での最終確認は、次に monnie の `reboot_required` が true になる夜に `[ubuntu_nightly] OK - monnie` が info へ飛ぶこと。**これは `docs/ai/status.md` の既存 Watch 行がそのまま担う** — 今回の修正で、その Watch が本来問うていた条件(サービスとポートの判定)へようやく到達できるようになる。
