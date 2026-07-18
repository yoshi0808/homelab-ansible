# Unpoller source hostname 変更結果

- 実施日: 2026-07-18 (JST)
- 対象: monnie `/etc/unpoller/up.conf`
- 目標: `[unifi.defaults].url` の host 部を `cloudkey.internal` へ変更
- 最終判定: **PASS（初回失敗を rollback 後、literal retry 成功）**
- mute: clear 済み

実 IP は `https://<controller-ip>` としてマスクする。

## 1. 結論

初回の `lineinfile` 試行は既存 URL 行に一致せず hostname URL を追記したため、restart 前の
semantic gate で URL 2 行を検出した。不正設定を読み込ませず backup へ即時 rollback し、
元設定で Unpoller を restart して active/poll/source の復旧を確認した。

Claude の再試行指示後、regex/lineinfile を使わない literal bytes 置換へ変更した。
既存 URL 文字列を一意に特定して host 部だけを `cloudkey.internal` へ1回置換し、別 verifier で
backup から期待 bytes を再構築した結果と原本が完全一致することを restart 前に確認した。

retry 後は次を満たす。

- config URL: `https://cloudkey.internal` 1 行のみ
- IP URL: 0 行
- scheme: `https` 維持
- explicit port: なしを維持（実効 443）
- `verify_ssl=false`: 不変
- URL host 部以外: byte 不変
- owner/mode: 不変
- Unpoller: active/running、failed ではない
- controller poll / metric export: 継続、Err 0
- active TX drop series: hostname 27、IP 0
- mute: quory 上で clear 済み

## 2. 変更前確認

```text
scheme:         https
host:           <controller-ip>
explicit port:  なし
effective port: 443
verify_ssl:     false
```

- `cloudkey.internal` は monnie の `/etc/hosts` に登録済み。
- `getent ahostsv4` で現 controller host と `cloudkey.internal` の解決先集合が完全一致。
- `/etc/unpoller/up.conf`: regular file、owner UID/GID `999/986`、mode `0640`。
- Unpoller: active。
- Prometheus `source` values: IP URL 1 件。
- `unpoller_device_port_transmit_dropped_total`: 27 series。

port は元から明示されていないため、変更後 URL は `https://cloudkey.internal` とした。

## 3. backup と mute

backup:

```text
/etc/unpoller/up.conf.bak.20260718T213037
```

backup は原本と owner/mode/size/hash が一致する regular file。初回 rollback と retry の byte gate に使用した。

mute は quory 上で設定した。

```text
homelab-mute set monnie 30 unpoller url change
```

初回 failure 時は mute を残し、retry の全 gate 合格後に quory 上で clear した。

## 4. 初回試行と rollback

`ansible.builtin.lineinfile` は `changed=true`, `msg="line added"` を返した。
restart 前の semantic gate:

```text
url_line_count=2
ip_url_count=1
hostname_url_count=1
```

ここで即停止し、backup を原本へ復元した。

```text
rollback_hash_match=yes
url_line_count=1
hostname_url_count=0
```

元設定で Unpoller を restart し、active/running、controller/site discovery、metric export Err 0、
Prometheus source が元の IP URL であることを確認した。bad config での restart は行っていない。

## 5. literal retry

一時 Python editor は次を edit 前に検証した。

- URL 行がちょうど1本
- URL scheme が `https`
- host が IP address
- explicit port がない
- URL bytes が file 内で一意
- hostname URL が edit 前に存在しない

その後、既存 URL bytes を `https://cloudkey.internal` へ literal 完全一致で1回だけ置換し、
owner/mode を保った temporary file を atomic rename した。

```text
replacements=1
old_scheme=https
old_host_kind=ip
old_port=none
new_url=https://cloudkey.internal
```

## 6. restart 前 semantic gate

独立 verifier は backup の旧 URL bytes を hostname URL bytes へ1回置換した期待内容を生成し、
現在の `/etc/unpoller/up.conf` と byte 比較した。

```text
semantic_gate=pass
url_lines=1
hostname_url_lines=1
ip_url_lines=0
other_bytes_unchanged=yes
scheme=https
explicit_port=none
mode=640
uid=999
gid=986
```

これにより URL host 部以外の全 byte、quote、scheme、port 表現、`verify_ssl`、metadata が
不変であることを restart 前に確認した。

## 7. restart と runtime 検証

`systemctl restart unpoller.service` 後:

| check | result |
|---|---|
| ActiveState | active |
| SubState | running |
| service Result | success |
| failed state | failed ではない |
| controller/site discovery | 成功 |
| TLS/auth/DNS error | 0 |
| poll/export error | 0 |
| measurements export | 継続 |

restart 後 journal は `cloudkey.internal` controller を認識し、約 1 分周期の
`UniFi Measurements Exported ... Err: 0` を継続した。

raw Unpoller exporter:

```text
unpoller_device_port_transmit_dropped_total{source="https://cloudkey.internal", ...}
```

Prometheus instant query:

```promql
unpoller_device_port_transmit_dropped_total
```

```text
series=27
hostname_source=27
ip_source=0
sample source=https://cloudkey.internal
```

Grafana alert が評価する active instant vector から IP source は消え、hostname source のみに切り替わった。

## 8. label values API の履歴挙動

`/api/v1/label/source/values` は active series だけでなく Prometheus TSDB/head に残る過去 series の
label postings も列挙する。このため変更直後の結果は次だった。

```text
total=2
hostname=1
historical_ip=1
```

短い start/end window と metric matcher を付けても旧 head series の posting が残った。
これは active TX drop series ではなく、instant query では IP series が 0 である。

旧値を label-values API の全集合から即時消去するには TSDB aging/retention またはデータ削除が必要だが、
本変更の範囲外であり実施していない。alert 文面の source hostname 化は active vector で確認済み。

## 9. cleanup と mute clear

retry 用の一時 editor/verifier は monnie と controller local `/tmp` の両方から削除した。

最終 gate:

```text
final_gate=pass
active=yes
failed=no
poll_err=0
tx_active_hostname=all
temp_scripts=absent
```

全 runtime gate 合格後、quory 上で実行した。

```text
homelab-mute clear monnie
```

`homelab-mute status` で monnie の state が `-` であることを確認した。

## 10. 変更範囲

実施:

- `/etc/unpoller/up.conf` の controller URL host 部変更
- backup 作成
- Unpoller restart
- runtime/Prometheus 検証
- mute set/clear

未実施:

- `verify_ssl` 変更
- `/etc/hosts` 変更
- Prometheus/Grafana 設定変更
- TSDB delete/retention 変更
- commit / push
