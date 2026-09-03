# result: monnie の復旧完了と、そこで分かったこと

日付: 2026-09-03
実行: Yoshinobu(monnie 上、root)/ 観測と記録: Coordinator
対象: Semaphoreジョブ #938 の停止からの復旧

## 1. 結論

**適用は実質的に完了していた。止まっていたのは apt-get の後片付けだけである。** 手当ては3手で終わった。

| # | 操作 | 結果 |
|---|---|---|
| 1 | `kill -9` で `apt-get` と `timeout` を終了 | ジョブ #938 は失敗して終了 |
| 2 | `dpkg --configure -a` | **即座に無出力で返った = 設定待ちのパッケージは1つも無かった** |
| 3 | `systemctl restart loki unpoller` | 08:57 に再起動。`NEEDRESTART_MODE=l` は再起動しない設定のため、それまで旧プロセスが動いていた |

## 2. 復旧後の実測

| 確認点 | 結果 |
|---|---|
| loki | `3.7.7`、`active`、08:57:15 再起動 |
| unpoller | **`5.2.2+git`**、`active`、08:57:14 再起動 |
| unpoller のメトリクス | **`unpoller_` で始まる系列が 1815本。** 実データあり(`usw-1f Port 8` → `u7-1f`、`source` は CloudKey)。**収集できている** |
| failed unit | 0件 |
| 待受ポート | loki / grafana / prometheus / unpoller / alloy すべて生存 |
| alloy | 08:09:58 に再起動、全ソースの追跡を再開 |
| ログ転送 | 正常。monnie のjournalは job `loki.source.journal.system` で毎分届いている |
| 再起動要求 | **無し**(`/var/run/reboot-required` が存在しない) |
| initramfs | `/boot/initrd.img-7.0.0-30-generic` 43MB、08:10 生成。dracut のトリガは完走していた |

## 3. 分かったこと

### 3.1 conffile の修正は成功している

**term.log に conffile プロンプトは1件も出ていない。** `python3-apt` 以降の設定がすべて素通りしており、`--force-confold` は意図どおり働いた。**2026-08-22 の欠陥は塞がっている。**

### 3.2 止まったのは dpkg ではなく apt-get の最終段

`dpkg --configure -a` が即返したことから、**dpkg の作業は停止時点で完了していた**。`dpkg` / `dracut` / `update-initramfs` のプロセスもすべて消えていた。残っていたのは `timeout` と `apt-get` の2つだけである。

**終了時に端末の状態を戻そうとして `SIGTTOU` を受けた、という説明が観測と最もよく合う**(原因の機構は `2026-09-03_001_requirement.md` §2)。

### 3.3 `--force-confold` は、手動管理の設定をメジャー版更新でも黙って保持する

`/etc/unpoller/up.conf` は手動管理(Notion手順書)でローカル変更がある。今回 unpoller は **4.0.0+git → 5.2.2+git** とメジャー版を2つまたいだが、**設定は 4.x のまま保持された。**

**今回はそれで動いた** — メトリクス1815本が出ている。**ただしこれは観測であって保証ではない。** プロンプトを出さない設計にした以上、**非互換があっても誰も聞かれない。** 手動管理の設定 × メジャー版更新は、この経路の残存リスクである。

### 3.4 `MAJOR_UPGRADE_DETECTED` は個々のパッケージのメジャー版差を見ていない

信号は3つだけである(`roles/ubuntu_vm_full_upgrade/tasks/classify.yml`)。

1. ディストリの codename drift
2. install + remove の合計が閾値(既定100)を超える
3. remove が閾値(既定30)を超える

**個々のパッケージの版差は入力になっていない。** したがって unpoller の 4.x → 5.x は、この信号では検出されない。**欠陥ではなく守備範囲の違い**であり、名前から期待するものとは別物である。人のゲートは `REVIEW_REQUIRED` と、通知に載る old→new の版一覧が担っている。

**2026-08-22 の 3.3.4 → 4.0.0 が専用案件になったのは人の判断であって、機構が上げた警報ではない。**

## 4. 申し送り

- **ジョブ #938 は失敗のまま残る。再実行しない。** 8/22 は再実行(#803)で締めたが、**当時はまだ `timeout` が入っていなかった**。いま同じテンプレートを流すと、apt が即座に終わる場合でも終了時の端末操作で同じ停止を踏みうる。**再実行は `2026-09-03_001_requirement.md` の修正が入ってから**
- **Operator は apt のログを読めない**(`/var/log/apt/term.log` は `root:adm 0640`、`ann` identity では拒否)。本番で apt が止まったとき、運用側から中身を確かめる手段が無い。今回のOPREQはこれでNGになった
- recovery mute は 10:09 頃まで有効だった。復旧作業はその内側で完了している
