# quory Semaphore 2.18.4 → 2.19.8 手動アップグレード手順

作成: 2026-08-18 / Coordinator
実行: Yoshinobu(quory 上)
決定: **今回は playbook 化せず手動で行う**(Yoshinobu、2026-08-18)。未知が残る状態で `systemd-run` の2段構えを重ねると、失敗したときにマイグレーション由来か機構由来かを切り分けられないため。

**ansy で 2026-08-18 に同じ順序を実行し、全項目が緑になっている。** ansy と違う点だけ各段に注記した。

---

## 0. 実施前に確認する

```bash
# 定期実行の窓に入っていないこと。窓の正本は Notion「バッチ処理工程管理表」で、
# Semaphore のカタログだけで判定しない。
# 走行中の job が無いこと:
semaphore-query running 5
```

**版の確認と、`.deb` の変種の確定**(ansy と同じ非 community 版か):

```bash
semaphore version
sha256sum /usr/bin/semaphore
```

| 期待値 | 意味 |
|---|---|
| `2.18.4-7ca373d-1779131064` | ansy と同じ版 |
| `eeea8b9ef3a8bb8cb1d70903e9a2ba4cec0b007378b655e7c8e5573fdce39abf` | **非 community 版**。ansy で upstream の `semaphore_2.18.4_linux_amd64.deb` と照合して確定した値 |

**sha256 が違ったら止める。** community 版が入っている可能性があり、その場合は `semaphore_community_2.19.8_...deb` を使わないと版が入れ替わる。

## 1. 基準値を記録する

**戻すかどうかを後で判断する材料になる。** 上げた後に同じものを取って突き合わせる。

```bash
sudo -u <semaphore実行ユーザー> sqlite3 /var/lib/semaphore/semaphore.db \
  "select 'templates='||count(*) from project__template;
   select 'schedules='||count(*) from project__schedule;
   select 'active_schedules='||count(*) from project__schedule where active=1;"
```

**quory は ansy と違い schedule が有効である。** ansy は R15 の allowlist により全件 `active=0` で、**有効化の経路は ansy では一度も通っていない**。`active_schedules` の値は必ず控える。

**実測した基準値**(2026-08-18、Yoshinobu が quory 上で取得):

| | quory | ansy(参考) |
|---|---|---|
| `templates` | **52** | 52 |
| `schedules` | **20** | 20 |
| `active_schedules` | **20** | 0 |

**オブジェクトの集合は ansy と一致している** — ansy での検証が同じ規模の上で走っていたことを意味する。違うのは有効状態だけである。**6. ではこの3つと突き合わせ、特に `active_schedules=20` が保たれていることを見る。**

## 2. 退避する

**既存の `SEMI-SAFE: Semaphore db backup` を Semaphore UI から1回実行する**(`semaphore.db` / `config.json` / projects export の3点セットが NFS へ出る)。成功を確認してから次へ進む。

そのうえで、ローカルにも即座に戻せる形で置く:

```bash
mkdir -p ~/semaphore-pre-2.19.8
sudo sqlite3 /var/lib/semaphore/semaphore.db ".backup '$HOME/semaphore-pre-2.19.8/semaphore.db'"
sudo cp -a /etc/semaphore/config.json  ~/semaphore-pre-2.19.8/
sudo cp -a /usr/bin/semaphore          ~/semaphore-pre-2.19.8/semaphore-2.18.4.bin
sudo chown -R "$USER" ~/semaphore-pre-2.19.8
ls -l ~/semaphore-pre-2.19.8
```

**バイナリだけでは戻らない。** `semaphore server` は起動時にマイグレーションを実行するため、restart した時点でスキーマが上がる。**戻すときは `semaphore.db` の書き戻しが要る。**

## 3. `.deb` を取得して照合する

```bash
cd ~/semaphore-pre-2.19.8
curl -fsSLO https://github.com/semaphoreui/semaphore/releases/download/v2.19.8/semaphore_2.19.8_linux_amd64.deb
sha256sum semaphore_2.19.8_linux_amd64.deb
```

期待値: `5080dfd9701adcf2fe238d1144d3a663df807074940b03de0487e4acc2873f51`

**一致しなければ止める。**

## 4. install する(ここではまだ何も起きない)

```bash
PID_BEFORE=$(systemctl show semaphore -p MainPID --value); echo "before=$PID_BEFORE"
sudo NEEDRESTART_MODE=l apt-get install -y ~/semaphore-pre-2.19.8/semaphore_2.19.8_linux_amd64.deb
PID_AFTER=$(systemctl show semaphore -p MainPID --value);  echo "after =$PID_AFTER"
```

**`NEEDRESTART_MODE=l` を必ず付ける。** 付けないと `needrestart` が `systemctl restart semaphore.service` を打ち、**この時点でマイグレーションまで走る**(ansy で実測。`.deb` 自身は maintainer script を持たないが、apt hook が再起動する)。

**`PID_BEFORE` と `PID_AFTER` が同じであることを確認する。** 違っていたら再起動済みで、この手順の 5. は済んでいる。

```bash
/usr/bin/semaphore version   # 2.19.8-3449a04-1786894505
ls -l /proc/$PID_BEFORE/exe  # `/usr/bin/semaphore (deleted)` = 旧バイナリを実行中
ps -o lstart= -p $PID_BEFORE # install より前の起動時刻
```

**`semaphore version` で稼働プロセスの版は分からない。** このコマンドは**ディスク上のバイナリを実行するだけ**で、install 後に打てば restart していなくても 2.19.8 を返す。**稼働プロセスに版を尋ねる手段はこのCLIには無い。** 再起動されていないことの根拠は `MainPID` が変わっていないことであり、上の2行はその裏取りである。

## 5. 止めて、最後のスナップショットを取り、上げる

**ここがマイグレーションの瞬間であり、後戻りできなくなる点である。**

```bash
sudo systemctl stop semaphore
sudo sqlite3 /var/lib/semaphore/semaphore.db ".backup '$HOME/semaphore-pre-2.19.8/semaphore-final.db'"
sudo systemctl start semaphore
sudo journalctl -u semaphore --since "-2min" --no-pager | tail -30
```

journal に次が出ること:

- `Executing migration v2.18.6` 〜 `v2.19.14`(**7本**: 2.18.6 / 2.18.7 / 2.18.15 / 2.19.2 / 2.19.11 / 2.19.12 / 2.19.14)
- `Migrations Finished`
- `Semaphore 2.19.8-3449a04-1786894505`
- `Server is running`

**`Migrations Finished` が出ないまま落ちたら 8. のロールバックへ。**

> **ansy で確かめられなかったのはここである。**
> - マイグレーションは `task` テーブルを copy-rebuild し、`user_id` / `project_id` の外部キーを `ON DELETE SET NULL` / `CASCADE` へ変える。**ansy の task は1行、quory は675行以上**(2026-08-11時点)。制約を満たさない行があれば copy で落ちる。**2.19.7 が壊し 2.19.8 が直したのがこの経路である。**
> - 鍵(`access_key`)の移行。**ansy の鍵は `type=none` の1本だけ**で、これは ansy を無害にしている性質そのものである。quory の鍵は本番の認証経路そのものである。

## 6. 確認する

**まずエディションが変わっていないことを確かめる。**

```bash
sha256sum /usr/bin/semaphore
```

**0. で控えた変種と同じ側であること。** 期待値は upstream の該当リリースの `.deb` を展開して求める(版ごとに変わるため、この文書に固定値を書かない)。**入れる前の照合は「どちらを取るか」を決めるだけで、意図した方が入ったことの確認にはならない。**


```bash
semaphore version                      # 2.19.8-...
systemctl is-active semaphore          # active
curl -s -o /dev/null -w "%{http_code}\n" https://quory.internal:3000/   # 200
```

1. の基準値と突き合わせる:

```bash
sudo -u <semaphore実行ユーザー> sqlite3 /var/lib/semaphore/semaphore.db \
  "select 'templates='||count(*) from project__template;
   select 'schedules='||count(*) from project__schedule;
   select 'active_schedules='||count(*) from project__schedule where active=1;"
```

**3つとも 1. と同じであること。** 特に `active_schedules` が減っていたら、定期実行が止まっている。

読み取り経路(dispatch / incident 調査が使う):

```bash
semaphore-query recent-failed 3
semaphore-query template-list 1
```

reconcile(カタログとの差分が出ないこと。**`--check` を付ける**):

```bash
cd /home/yoshi/homelab-ansible   # quory 側の作業ツリー
ansible-playbook playbooks/semaphore_templates_setup.yml --check
```

`failed=0` で完走し、差分が報告されないこと。

## 7. 完了後

- **次の schedule 実行が緑で終わること**を1サイクル見る。ここまでが版上げの完了である
- 結果を Coordinator へ伝える(`docs/ai/context/system/semaphore.md` と `docs/ai/status.md` を現物に合わせる)

## 8. ロールバック

**5. を実行した後は、バイナリだけ戻しても直らない。**

```bash
sudo systemctl stop semaphore
sudo cp -a ~/semaphore-pre-2.19.8/semaphore-2.18.4.bin /usr/bin/semaphore
sudo cp -a ~/semaphore-pre-2.19.8/semaphore-final.db   /var/lib/semaphore/semaphore.db
sudo chown <semaphore実行ユーザー>:<group> /var/lib/semaphore/semaphore.db
sudo systemctl start semaphore
semaphore version && systemctl is-active semaphore
curl -s -o /dev/null -w "%{http_code}\n" https://quory.internal:3000/
```

`config.json` は dpkg 管理外で変化しないため、通常は戻す必要がない。

---

## この手順の裏付け

ansy で 2026-08-18 に同じ順序を通し、全項目が緑になっている。**実測値の正本は `2026-08-18_003_result.md`「ansy と quory の差(実測)」である。**
