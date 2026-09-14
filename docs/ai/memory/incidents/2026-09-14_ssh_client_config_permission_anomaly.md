# Incident: SSHクライアント設定の権限異常と接続成否の揺れ

日付: 2026-09-14
状態: 調査中
対象: ansyのSSHクライアント設定・`quory-investigate`接続
種別: 動作不具合

## 症状

Semaphore #1093のread-only照会中、`ssh quory-investigate ... | sed ...`というパイプ付き照会が`Bad owner or permissions on /etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf`で停止した。一方、同じforced commandをパイプなしで呼ぶと成功し、#1093の結果を取得できた。パイプの有無で実行環境・SSH設定の見え方が異なる可能性があるが、原因は未確認。

Codexのsandbox内からの`stat -c '%U %G %a %n'`は該当ファイルを`root root 777`、親ディレクトリを`root root 755`、`/etc/ssh/ssh_config`を`root root 644`と表示した。sandbox外の実ホスト権限は未確認であり、この`777`を実ホストの設定不備とは断定しない。ファイルの変更やSSH接続経路の変更は行っていない。

## 原因

未判明。

## 修正内容

未実施。

## 確認方法

実ホストのシェルから該当ファイルの所有者・modeを確認し、sandboxと通常のforced command呼出しの差を照合する必要がある。#1093自体は`task-time`でsuccess、パイプなしの`task-output`で`status: ok`を確認済みであり、本件と分けて扱う。
