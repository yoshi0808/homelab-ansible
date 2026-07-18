# Unpoller verify_ssl 有効化・PKI 検証結果

- 実施日: 2026-07-18 (JST)
- 対象: monnie `/etc/unpoller/up.conf`
- 目標: `verify_ssl=false` を `true` へ変更し、中間 CA を含む PKI 検証を通す
- 最終判定: **FAIL-CLOSED / ROLLBACK 完了**
- 最終設定: `verify_ssl=false`
- mute: **monnie に残置**

実 IP は `https://<controller-ip>` としてマスクする。

## 1. 結論

`verify_ssl=false` から `true` への literal 置換と restart 前 semantic gate は成功した。
Unpoller 自体は `verify SSL: true` と表示し、hostname controller の site discovery、poll、metric export を
error 0 で継続した。

しかし、monnie の標準 CA bundle/path を明示した hostname/SNI の OpenSSL chain validation は失敗した。

```text
verify error:num=2:unable to get issuer certificate
Verify return code: 2 (unable to get issuer certificate)
```

「中間 CA の検証まで通す」という PKI gate を満たさないため、Unpoller の表面的な成功だけでは PASS とせず、
backup へ rollback して `verify_ssl=false` に戻した。元設定で Unpoller を restart し、active/poll/source の
復旧を確認した。

## 2. mute と変更前確認

quory 上で実行した。

```text
homelab-mute set monnie 30 unpoller verify_ssl enable
```

変更前:

- URL: `https://cloudkey.internal`
- URL line: 1 本
- explicit port: なし（実効 443）
- `verify_ssl=false`: 1 本
- owner UID/GID: `999/986`
- mode: `0640`
- Unpoller: active
- active TX drop source: hostname

## 3. backup

```text
/etc/unpoller/up.conf.bak.20260718T214435.verify-ssl
```

backup は原本と owner/mode/size/hash が一致する regular file として作成した。

## 4. literal edit

lineinfile と regex は使用していない。一時 Python editor は byte 列
`verify_ssl = false` が file 内にちょうど1件あり、`verify_ssl = true` が0件、hostname URL が1件であることを
確認してから literal 完全一致で1回だけ置換した。

```text
replacements=1
verify_ssl=true
url=hostname
bytes_delta=-1
```

temporary file へ書き、元の owner/mode を設定したうえで atomic rename した。

## 5. restart 前 semantic gate

独立 verifier が backup の `verify_ssl = false` を `true` へ1回だけ置換した期待 bytes を生成し、
現在の config と完全比較した。

```text
semantic_gate=pass
verify_ssl_lines=1
verify_ssl=true
hostname_url_lines=1
other_bytes_unchanged=yes
mode=640
uid=999
gid=986
```

URL 行、scheme、port 表現、他 key、quote、owner/mode は不変だった。

## 6. verify_ssl=true での Unpoller runtime

`systemctl restart unpoller.service` 後:

| check | result |
|---|---|
| ActiveState | active |
| SubState | running |
| Result | success |
| failed state | failed ではない |
| hostname controller discovery | 成功 |
| journal TLS/x509/certificate error pattern | 0 |
| general auth/DNS/poll error pattern | 0 |
| `Measurements Exported` | 複数回継続 |
| poll/export Err | 0 |
| TX drop active series | hostname 27 / IP 0 |

journal は次の状態を表示した。

```text
URL: https://cloudkey.internal (verify SSL: true, timeout: 1m0s)
UniFi Measurements Exported ... Err: 0
```

Unpoller runtime だけを見ると成功していた。

## 7. PKI chain validation failure

中間 CA を含む PKI 検証を独立確認するため、monnie から hostname/SNI を指定して read-only 実行した。

```text
openssl s_client
  -connect cloudkey.internal:443
  -servername cloudkey.internal
  -verify_return_error
  -showcerts
  -CAfile /etc/ssl/certs/ca-certificates.crt
  -CApath /etc/ssl/certs
```

証明書本文と subject 名は保存していない。結果:

```text
openssl_rc=1
presented_chain_certs=3
depth=1 CN=<redacted>, O=Home, C=JP
verify error:num=2:unable to get issuer certificate
Verify return code: 2 (unable to get issuer certificate)
```

default trust path のみの実行と、CAfile/CApath 明示の実行の両方で同じ failure だった。
monnie の trust store から提示 chain の issuer pathを完成できていない。

Unpoller が `verify SSL: true` で通信を継続した理由は今回の範囲では確定していない。
少なくとも独立した標準 PKI validator は失敗しているため、中間 CA 検証 PASS とは判定できない。

## 8. rollback

PKI failure 検出後、monnie を quory 上で再 mute した。

```text
homelab-mute set monnie 30 unpoller verify_ssl rollback pki failure
```

backup を原本へ復元し、hash 一致、hostname URL 維持、`verify_ssl=false` を確認後、
Unpoller を restart した。

rollback 後:

| check | result |
|---|---|
| config hash | backup と一致 |
| URL | `https://cloudkey.internal` |
| verify_ssl | false |
| ActiveState / SubState | active / running |
| Result | success |
| controller discovery | 成功 |
| metric export | 継続、Err 0 |
| runtime error pattern | 0 |
| TX drop active source | hostname 27 / IP 0 |

retry 用一時 editor/verifier は monnie と controller local `/tmp` の両方から削除済み。

## 9. mute 最終状態

途中の Unpoller runtime gate 合格時に一度 clear したが、追加の独立 PKI chain check で failure を検出したため、
直ちに再 mute して rollback した。

最終 `homelab-mute status`:

```text
monnie MUTED(30m) reason="unpoller verify_ssl rollback pki failure"
```

fail-closed 指示どおり clear していない。

## 10. 次の対応候補

再試行前に、次のどちらが不足しているかを切り分ける必要がある。

- controller が提示する chain の issuer/intermediate 構成
- monnie の system trust store に必要な root/intermediate CA

OpenSSL の `Verify return code: 0 (ok)` を先に確認し、その後に `verify_ssl=true` を再適用するのが安全。
Unpoller が標準 validator と異なる挙動を示す理由も、version/source 実装または trust-store 読み込み経路で
別途確認する。

## 11. 変更範囲

実施:

- backup 作成
- `verify_ssl=true` literal edit
- semantic gate
- Unpoller restart / runtime verification
- OpenSSL chain validation
- PKI failure 後の config rollback / restart / recovery verification
- mute set、再 set

未実施:

- CA certificate install/update
- controller certificate/chain 変更
- `/etc/hosts` 変更
- Prometheus/Grafana 設定変更
- commit / push
- 最終 mute clear
