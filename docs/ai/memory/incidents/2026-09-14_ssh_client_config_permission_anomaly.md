# Incident: SSHクライアント設定の権限異常と接続成否の揺れ

日付: 2026-09-14
状態: 未解決(権限異常は否定。実害が無く再現もしないため、再発するまで調査を進めない)
対象: ansyのSSHクライアント設定・`quory-investigate`接続
種別: 動作不具合

## 症状

Semaphore #1093のread-only照会中、`ssh quory-investigate ... | sed ...`というパイプ付き照会が`Bad owner or permissions on /etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf`で停止した。一方、同じforced commandをパイプなしで呼ぶと成功し、#1093の結果を取得できた。

Codexのsandbox内からの`stat -c '%U %G %a %n'`は該当ファイルを`root root 777`と表示した。

## 原因

未判明。ただし**権限異常という当初の仮説は否定された。**

- 該当パスは`/usr/lib/systemd/ssh_config.d/20-systemd-ssh-proxy.conf`への**symlinkであり、`777`はsymlink自身のmode**(`lrwxrwxrwx`)である。`stat`はsymlinkを既定で追わないため、実体ではなくlink自身の値が出ていた。実体は`stat -L`で`root root 644`。
- このsymlinkは`systemd`パッケージが`.deb`の時点でsymlinkとして配っている(`dpkg-deb -c`で確認)。ローカルで書き換えられたものではない。

残るのは「Codexのsandbox内からの呼び出しでだけ失敗した理由」で、これは未確認である。

## 修正内容

無し(直すべき対象が無い)。

## 確認方法

2026-09-14のansy再起動後、通常のシェルから確認した。

- `ls -l /etc/ssh/ssh_config.d/` — symlinkであること
- `stat -L -c '%U %G %a %n' /etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf` — `root root 644`
- `dpkg-deb -c systemd_*.deb | grep ssh_config.d` — パッケージがsymlinkとして配っている
- `ssh quory-investigate semaphore-query task-time 1093` を**パイプ有り・無しの両方**で実行し、どちらも成功。`Bad owner or permissions`は再現しない
