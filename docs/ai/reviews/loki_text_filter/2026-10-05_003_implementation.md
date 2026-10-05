# Implementation: Loki固定文字列検索

## Result

- `loki-text <job|all> <since> <window> <text>`を追加した。`text`は英数字と`:` `.` `_` `-`だけからなる1〜64文字に限定し、quory wrapper、target dispatch、helperでそれぞれ検証する。
- helperは固定文字列LogQL filter (`|=`)だけを使う。`all`はjob/level selectorを含めず全jobを対象にする。windowは`1h` / `6h` / `24h` / `3d` / `7d`で、既存語彙のwindow allowlistは広げていない。
- 新語彙は既存の`QUERY_LIMIT`、`MAX_LINES`、時刻範囲を示す切り詰め通知を共有する。`MAX_LINE_LENGTH`は既存の本文表示にも適用される1000文字へ更新した。
- 配備されるAGENTSとcatalog §9を同期し、L4、`all`、固定文字列の制限、level無し行への到達経路、およびhelperがLoki有効target（現状monnie）だけへ配備されることを記録した。

## Self-verification

- `PYTHONDONTWRITEBYTECODE=1 python3 roles/recovery_exec/tests/test_loki_text_filter.py -v`: 6 tests passed。wrapper、直接dispatch、helperを独立に確認し、許可4例、拒否値、長いwindow、固定文字列LogQL、全job selector、切り詰めと1000文字上限、既存window allowlistの不変を確認した。テストはHTTPをmockし、Lokiへは問い合わせない。
- `PYTHONDONTWRITEBYTECODE=1 python3 roles/recovery_exec/tests/test_operator_investigate_key.py -v`: 6 tests passed。直前案件のidentity別鍵・known_hosts選択を含む既存testを再実行した。
- `git diff --check`を通過した。実ホスト、SSH、Loki、Semaphore、本番Slack、git commit/pushには触れていない。

## 差し戻し対応

- job固有の`loki-text` queryについて、`unifi`指定時に`{job="unifi"} |= "kicked"`となり、level selectorを含まないことを確認するoffline testを追加した。
