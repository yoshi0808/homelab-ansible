# Unpoller verify_ssl 有効化・PKI 検証結果

- 実施日: 2026-07-19 (JST)
- 対象: monnie `/etc/unpoller/up.conf`
- 最終判定: **PASS**
- 最終設定: `verify_ssl = true`
- rollback: 不要
- mute: quory 経由で clear 済み

実 IP は記録していない。

## 1. 結論

ROOT CA の system trust store 配布後、cloudkey の TLS chain を monnie の標準 CA bundle で事前検証し、`Verify return code: 0 (ok)` を確認した。そのうえで `up.conf` の `verify_ssl = false` を literal 完全一致で1回だけ `true` に変更し、semantic gate 合格後に unpoller を restart した。

restart 後は次をすべて確認した。

- unpoller: active、failed ではない
- runtime 表示: `verify SSL: true`
- TLS/x509/certificate verify error: 0
- controller poll / metric export: `Err: 0`
- exporter metric: 継続
- Prometheus active series: source は hostname のみ
- 独立 OpenSSL PKI validation: return 0

前日の ROOT CA 不在による depth 1 / error 2 は解消しており、`verify_ssl=true` を維持した。

## 2. Safety gate / mute

ローカルの `homelab-mute` は使用していない。Ansible 経由で quory 上の status を確認し、monnie に既存 mute があることを変更前に確認した。

```text
monnie  MUTED(55m)
```

全検証 PASS 後、quory 上で次を実行した。

```text
homelab-mute clear monnie
cleared: monnie
```

最終 status:

```text
monnie  -
```

## 3. PKI precondition

設定変更前、monnie から hostname/SNI と system CAfile を明示して cloudkey を検証した。

```text
openssl s_client \
  -connect cloudkey.internal:443 \
  -servername cloudkey.internal \
  -verify_return_error \
  -CAfile /etc/ssl/certs/ca-certificates.crt

Verification: OK
Verify return code: 0 (ok)
S_CLIENT_RC=0
```

これを `verify_ssl=true` 再適用の前提 gate とし、成功後だけ変更へ進んだ。

## 4. Backup

変更前の owner/mode を保持して次へ backup した。

```text
/etc/unpoller/up.conf.bak.20260718T212019Z
```

backup は rollback 用に保持している。

## 5. Literal edit

変更前:

```text
url = "https://cloudkey.internal"
verify_ssl = false
```

Python の bytes literal 置換を使用した。regex と `lineinfile` は使用していない。改行を含む literal `  verify_ssl = false\n` がちょうど1件であることを確認し、`  verify_ssl = true\n` へ1回だけ置換した。

## 6. Pre-restart semantic gate

現在ファイルと backup から生成した期待 bytes を完全比較した。

```text
verify_true_count=1
verify_false_count=0
url_count=1
only_literal_changed=True
before_old_count=1
current mode/uid/gid=640/999/986
backup  mode/uid/gid=640/999/986
```

URL、quote、scheme、hostname、他 key、他 bytes、owner、group、mode は不変。semantic gate 合格後だけ restart した。

## 7. Restart and runtime validation

`systemctl restart unpoller` 後:

```text
ACTIVE=active
FAILED_STATE=active
URL: https://cloudkey.internal (verify SSL: true, timeout: 1m0s)
TLS_X509_ERROR_COUNT=0
NONZERO_ERR_COUNT=0
```

restart 直後から controller poll と metric export が複数回成功した。

```text
UniFi Measurements Exported ... Err: 0
UniFi Measurements Exported ... Err: 0
```

restart 境界以降の journal に `x509`、certificate verify failure、TLS handshake error、unknown authority はなかった。

## 8. Metric and source validation

Unpoller exporter (`localhost:9130/metrics`) の active metric:

```text
EXPORTER_TOTAL=27
EXPORTER_HOSTNAME_SOURCE=27
EXPORTER_OTHER_SOURCE=0
```

Prometheus instant query `unpoller_device_port_transmit_dropped_total`:

```text
PROMETHEUS_SERIES=27
PROMETHEUS_HOSTNAME_SOURCE=27
PROMETHEUS_OTHER_SOURCE=0
```

metric export は継続し、active series の `source` はすべて `https://cloudkey.internal`。IP source への回帰はない。

## 9. Final assessment

| Gate | Result |
|---|---|
| Mute present before change | PASS |
| OpenSSL system CA validation before edit | PASS, return 0 |
| Timestamped backup | PASS |
| Literal single replacement | PASS |
| URL and all other bytes unchanged | PASS |
| Owner/group/mode unchanged | PASS |
| Unpoller active / not failed | PASS |
| Runtime TLS/x509 error absent | PASS |
| Controller poll and export Err 0 | PASS |
| Exporter metrics continuing | PASS |
| Prometheus source remains hostname | PASS |
| Mute cleared through quory | PASS |

`verify_ssl = true` を最終状態として維持した。rollback は実施していない。commit / push も実施していない。
