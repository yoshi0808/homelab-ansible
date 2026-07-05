# WAL Investigation

対象:
- `/var/lib/semaphore/semaphore.db` on `quory`

目的:
- `homelab-semaphore-query` の sudo 廃止 / ACL 直読み再設計前に、Semaphore DB の WAL モード有無を確認する。

## 実行した確認

```bash
ansible quory -b -m ansible.builtin.command -a "sqlite3 /var/lib/semaphore/semaphore.db 'PRAGMA journal_mode;'"
```

結果:

```text
delete
```

```bash
ansible quory -b -m ansible.builtin.command -a "ls -la /var/lib/semaphore/"
```

結果:

```text
total 11516
drwx------  2 yoshi yoshi     4096 Jul  5 06:54 .
drwxr-xr-x 53 root  root      4096 Jun 28 20:18 ..
-rw-------  1 yoshi yoshi 11780096 Jul  5 06:54 semaphore.db
```

補足: Ansible ad-hoc の `command` module 表示上は `CHANGED` になるが、実行内容は `PRAGMA journal_mode` と `ls` の read-only 確認のみ。

## 結論

Semaphore DB は WAL モードではなく `delete` journal mode。

`/var/lib/semaphore/` に `semaphore.db-wal` / `semaphore.db-shm` は存在しない。

したがって、今回の確認時点では「DB本体だけ読めて `-wal` / `-shm` が読めない場合の `sqlite3 -readonly` 挙動」は該当しない。WAL 専用の一時ACL確認は不要と判断し、ACL変更は行っていない。

## 未実施

- `setfacl` による一時ACL付与 / 削除。
- `immutable=1` / `nolock=1` 等の URI 接続文字列の比較。

理由: WAL モードではなく、`-wal` / `-shm` ファイルも存在しないため。
