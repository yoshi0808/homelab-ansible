# quory稼働systemd unit棚卸し(read-only) — test_result

- 実施者: Tester(subagent)
- 実施日時: 2026-07-28 13:00〜13:10 JST(観測コマンドはすべてこの時間帯)
- 実施範囲: **read-onlyのみ**。`ssh quory`(接続ユーザー`ann`)による`systemctl list-units/list-timers/status`、`sudo -n journalctl -u ...`・`sudo -n git ... log/remote`(いずれも読み取り専用コマンド、`--become-user`等でyoshiのidentityは引き受けていない)、`crontab -l`、`ls`。加えてリポジトリ内の`roles/`・`docs/ai/adr/`をコード検索。ファイル作成・変更・削除、unit起動停止、playbook実行(`--check`含む)は一切行っていない。
- 対象: quoryのみ。Proxmox・Sophos・UniFiへは触れていない。
- `git add`/`git commit`/`git push`は行っていない。

## 結論(先に要約)

**「quoryのサービスがansyへファイルをコピーしている」に該当する動きは、現物観測でもコード読解でも見つからなかった。** quoryで稼働中のhomelab-*/recovery-*系unitは3つ(`homelab-incident-capture.timer`+`.service`、`recovery-probe.service`、`recovery-io.service`)で、いずれもquory**自身のローカルファイルシステム**へ書き込むかSSHで他のProxmox/authy/monnieを操作するだけであり、ansyへの転送処理(rsync/scp/sftp/paramiko/HTTP push等)はコード上に存在しない。

ただし、**設計文書(ADR-005、2026-07-28作成、Status: Proposed)に「quory→ansyのバンドル転送経路」という言葉自体は存在する。** これは実装済みの現状ではなく、Step 2(未着手)の設計制約として**先に固定されただけの将来計画**であり、Consequences節で「経路自体の設計は本件の非ゴール」と明記されている。Yoshinobuの認識はこの設計会話を指している可能性が高いが、**現時点でその経路を実装したroles/playbook/scriptはrepo中に存在しない**(下記2・3で確認)。

## 観測1: quoryで稼働中のhomelab-*/recovery-*系unit

```
ssh quory "systemctl list-units --type=service --type=timer --all --no-pager"
```

| unit | 状態 | 備考 |
|---|---|---|
| `homelab-incident-capture.timer` | active (waiting) | 5分毎起動 |
| `homelab-incident-capture.service` | inactive (dead)、直近実行 exit 0/SUCCESS | oneshot、timerからのみ起動 |
| `recovery-probe.service` | active (running) | 常駐 |
| `recovery-io.service` | active (running) | 常駐(Slackリスナー) |

このリポジトリが配備したその他のunit(`ansible-cert-renew-quory.service/.timer`、`quory-post-upgrade-check.service`)も確認したが、名称・`Documentation=`URLから証明書更新とアップグレード後チェック用途と分かり、ファイル転送とは無関係(中身までは未読解、依頼のスコープ外と判断)。

`knowledge-review`関連unitはquory上に**存在しない**(list-units出力に該当なし)。auto-memoryの記述はansy側のtimerを指しているとみられ、quoryの棚卸しには影響しない。

## 観測2: 各unitのExecStartとその実装 — ansy転送コードの有無

- `homelab-incident-capture.service`: `ExecStart=/usr/bin/flock -n -E 75 /run/lock/homelab-incident-capture.lock /usr/bin/python3 /usr/local/sbin/incident-capture-collector.py`(`roles/incident_capture/templates/incident-capture.service.j2`)。実体は`roles/incident_capture/files/incident-capture-collector.py`(848行)。全文を`ansy`/`scp`/`rsync`/`paramiko`/`requests`/`urllib`/`socket`/`http`でgrepしたが**該当箇所ゼロ**。書き込み先はすべて`incident_capture_bundle_dir`(`{{ reports_base_dir }}/incidents` = `/home/yoshi/homelab-ansible/reports/incidents`)という**quoryのローカルパス**。他ホストへの通信は、`incident_capture_investigate_bin_template`(`/usr/local/bin/homelab-investigate-{host}`)経由でquoryから**pve1/pve2/authy/monnieへSSHで名前付き操作を叩く**方向のみ(ansyは対象ホストのカタログに無く、対象外ホストとして`collection_errors`に記録される設計、`roles/incident_capture/defaults/main.yml:70-77`)。
- `recovery-probe.service`: `ExecStart=/usr/bin/python3 /usr/local/sbin/recovery-probe.py`。実体`roles/recovery_probe/files/recovery-probe.py`。`ansy`/転送系キーワードとも該当なし。
- `recovery-io.service`: `ExecStart={{ recovery_io_install_dir }}/venv/bin/python {{ recovery_io_script }}`。実体テンプレート`roles/recovery_io/templates/recovery-io.py.j2`。`ansy`/転送系キーワードとも該当なし(Slack listener + sudo経由でCodex呼び出しが役割)。

## 観測3: 「reports/incidents/」がquory・ansy双方に同名で存在する理由(誤認の可能性が高い経路)

```
ssh quory "ls -ld /home/yoshi/homelab-ansible /home/yoshi/homelab-ansible/reports/incidents"
```

quoryには`/home/yoshi/homelab-ansible`という**独立したgit checkout**が存在し(owner yoshi:yoshi)、`reports_base_dir`(`inventories/homelab/group_vars/all.yml:1` = `/home/yoshi/homelab-ansible/reports`という**絶対パスのgroup_vars値**)がansyと同じ絶対パス文字列であるため、**quory上のincident-capture収集器はquory自身のディスク上の`reports/incidents/`へ書いているだけ**であり、ネットワーク越しにansyへ転送しているわけではない。この構造(両ホストが同一絶対パスに独立したrepo checkoutを持つ)を知らずに「同じ場所にファイルが増える」観測をすると、あたかもquoryからansyへコピーされているように見える可能性がある。

なお`sudo -n git -C /home/yoshi/homelab-ansible log -1`は`fatal: detected dubious ownership`(root実行でyoshi所有dirを触るためのgit安全機構)で失敗した。**回避策(`git config --global --add safe.directory`等)は状態変更にあたるため実行していない。** そのためquory側checkoutの現在のcommit/remoteは確認できていない(下記「観測できなかったこと」参照)。ディレクトリの存在とowner/mtimeのみ`ls`で確認済み。

## 観測4: systemd以外の経路

```
ssh quory "crontab -l; sudo -n crontab -l -u yoshi; ls -la /etc/cron.d/; systemctl --user list-timers --all"
```

- `ann`・`yoshi`とも個人crontabなし(`no crontab for ann/yoshi`)。
- `/etc/cron.d/`は`.placeholder`と`e2scrub_all`のみ(OS標準、本件と無関係)。
- systemd user timerは`launchpadlib-cache-clean.timer`(Ubuntu標準)のみで、homelab関連の常駐プロセスは無い。

## 観測5: 収集器の実行ログにansy/転送語彙が出ていないか

```
ssh quory "sudo -n journalctl -u homelab-incident-capture.service --since '2026-07-28 00:00' --no-pager | grep -iE 'ansy|rsync|scp|copy|transfer'"
```

該当なし(0件)。

## 判断が確定できなかった点・観測できなかったこと

- **quory側`/home/yoshi/homelab-ansible`のgit remote/HEADは未確認。** `sudo -n git`が「dubious ownership」で失敗し、回避には`git config`変更(状態変更)が要るため実行しなかった。`ann`権限のまま(sudoなし)での`git`実行も試していない(所有者yoshiのファイルを`ann`が読めるかは別途要確認)。**quoryのcheckoutが実際にGit経由で更新されているか(=「Gitから取得した確定済みコード」という共通原則どおりか)は、今回の観測範囲では確認できていない事実として残る。**
- **`ansible-cert-renew-quory.service/.timer`と`quory-post-upgrade-check.service`の`ExecStart`実体は読んでいない。** 依頼の主眼(ansyへのファイル転送の有無)への該当可能性が名称上低いと判断し、時間配分の都合で優先度を下げた。転送に無関係と断定はできない。
- **quory→ansyの実ネットワーク経路(ファイアウォール、SSH到達性)そのものは調べていない。** 送信元コードが存在しない以上、経路の有無を調べる意味が薄いと判断した。
- **ADR-005本文が「非ゴール」と明記する転送経路の設計・実装は、この案件(incident_auto_capture_step2)の後続作業として別途requirement/implementが立つ想定であり、今回はその有無をrepo検索で確認したに留まる**(`roles/`・`playbooks/`全体をキーワード`ansy`+転送語彙でgrepし、`unifi_backup_fetch.yml`のコメント1件以外に該当なしを確認済み)。

## 該当unit・経路の有無(依頼への直接回答)

1. quoryで有効・稼働中のhomelab-*/recovery-*系unit: `homelab-incident-capture.timer`(active)/`.service`(oneshot、直近成功)、`recovery-probe.service`(常駐)、`recovery-io.service`(常駐)の3系統。
2. このうちansyへファイルを送る・取りに行かせる動きを持つものは**無い**(3系統ともExecStart実体のソースコードを読み、転送系キーワード0件、書込先はすべてquoryローカルパスまたは他ホストへのSSH操作のみと確認)。
3. systemd以外の経路(cron、systemd user timer、常駐プロセス)にも該当は**無い**(crontab空、`/etc/cron.d/`はOS標準のみ、user timerはUbuntu標準1件のみ)。
4. 該当が見つからなかったため、項目4(いつから・直近実行結果・何をどこへ)は該当なし。
5. 「無い」と断定できる範囲: quory上のsystemd unit全件の一覧化、homelab関連3 unit全ての実装コード全文検索、cron相当3経路の確認。断定できない範囲: quory側git checkoutの実際の同期状態(観測できなかったことの1点目)、証明書更新・post-upgrade-check 2 unitの実装中身、将来設計(ADR-005)が今後実装されうる可能性そのもの。
