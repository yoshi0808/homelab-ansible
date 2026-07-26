# 実測調査: UniFiスイッチLink Up/Downログの収集経路到達状況(LOG-066裏取り)

対象: claudeからの検証依頼(読み取りのみ)。Yoshinobuが本日UniFiデバイスの
ログ出力レベルをdebug→Normalへ変更し、usw-coreのport 0/11でLink Up
(09:08:41 JST)→Link Down(09:12:41 JST)を実際に発生させた事象の裏取り。
`docs/ai/policies/log_observability_policy.md` v3.0 LOG-066(syslog系統の検知対象に
portのflapping・接続断の繰り返しを想定)の前提が実在するかの確認。
実行環境: ansy、tester(Claude Code)。実行日時: 2026-07-26 09:1x頃(JST)。
実host変更なし(ファイル読み取り・Lokiクエリのみ)。

## 依頼された2点への回答

### 1点目: monnieの`/var/log/unifi-devices.log`での実際の行形式

両イベントとも到達しており、実際の行は次のとおり(そのまま転記、実IPは
含まれていない):

```
2026-07-26T09:08:41+09:00 usw-core 245a4ca89601,USW-Pro-Aggregation-7.4.1+16850: switch: TRAPMGR: Link Up: 0/11
2026-07-26T09:08:41+09:00 usw-core 245a4ca89601,USW-Pro-Aggregation-7.4.1+16850: switch: DOT1S: Port (11) inst(0) role changing from ROLE_DISABLED to ROLE_DESIGNATED
...
2026-07-26T09:12:41+09:00 usw-core 245a4ca89601,USW-Pro-Aggregation-7.4.1+16850: switch: TRAPMGR: Link Down: 0/11
2026-07-26T09:12:41+09:00 usw-core 245a4ca89601,USW-Pro-Aggregation-7.4.1+16850: switch: DOT1S: Port (11) inst(0) role changing from ROLE_DESIGNATED to ROLE_DISABLED
```

**行頭の形は、依頼文が想定していた`usw-coreローカルの/var/log/messages`形式
(`Jul 26 09:08:41 usw-core daemon.notice switch: ...`)とは異なる。** monnie側で
受信・保存された行は、`rsyslog`が独自に付与したISO8601タイムスタンプ+ホスト名+
MAC,モデル/バージョン文字列で始まり、**`daemon.notice`に相当するテキストは
どこにも含まれていない**(そもそも消えている。トークン4番目に押し出されて
スキップ漏れする、という想定より手前の問題)。トークン分割すると:

```
1: 2026-07-26T09:08:41+09:00
2: usw-core
3: 245a4ca89601,USW-Pro-Aggregation-7.4.1+16850:
4: switch:
5: TRAPMGR:
6: Link
7: Up:
8: 0/11
```

`config.alloy.j2`のbest-effort正規表現`(?i)^(?:\S+\s+){0,3}(?:notice|info)(?:\s|:)`は、
0〜3個のトークンをスキップした直後に`notice`または`info`を要求する。上記トークン列の
1〜4番目(0〜3スキップの着地点)はいずれも`notice`/`info`ではなく(timestamp/
hostname/mac-model/switch:)、**そもそもマッチ対象となる`notice`という文字列自体が
行内に存在しない**。したがって「4個目に押し出されてスキップ漏れする」という
仮説の機構ではなく、「`notice`という語自体がmonnie受信時点で失われている」ことが
実際の理由である(結論は同じくマッチしないことだが、原因の所在が異なる)。

### 2点目: Loki `job="network-devices"`への到達状況とlevelラベル

両イベントとも到達している。`query_range`で実際のstream labelを確認した結果:

```
stream labels: {detected_level="unknown", filename="/var/log/unifi-devices.log",
                host="usw-core", job="network-devices", service_name="network-devices"}
```

**カスタムの`level`ラベルは付与されていない**(1点目の解析どおり、best-effort
正規表現が不一致のため`stage.static_labels`/現行の`action=drop`判定のどちらの
分岐にも入らず、levelキー自体が存在しない状態で通過する)。`detected_level="unknown"`
はLoki自身が持つ組み込みのlevel自動検出機能によるラベルであり、Alloy
pipeline側で付与している`level`ラベルとは別物(構造化metadataとして
Lokiが独自に付加する)。

Link UpとLink Downの両方について、**同一の扱い**(levelラベルなし、
`detected_level="unknown"`)であることを確認した。片方だけ落ちる、片方だけ
levelが付く、といった非対称は見られなかった。

## 追記: 4通りの切り分け(claude追加依頼への回答)

claudeから、Lokiに無い場合の原因切り分け(1: usw-core未送信、2: monnieのallowlistで
拒否、3: 受信・書込みされているがbest-effort正規表現不一致でlevel未付与、
4: すべて正常)の依頼を受けた。すでに収集済みの事実で以下のとおり切り分けられる。

- `/var/log/unifi-devices.log`の直近行(tail)には、usw-core由来の行が**Link Up/Down
  以外にも多数**存在する(`DOT1S: Port (11) inst(0) role changing ...`、
  `mcad[1004]: ace_reporter...`、`dropbear[3188]: Child connection ...` /
  `Pubkey auth succeeded ...`)。usw-core以外の機器(`u7-1f`、`u7-2f`、`usw-1f`)由来の
  行も同じ時間帯に混在している。
- これにより**1(usw-core未送信)と2(monnieのallowlistで拒否)は否定される**:
  usw-core由来の行は現に届いており書き込まれている。allowlistで弾かれていれば
  そもそもファイルに一切現れない。
- 一方、Loki側で確認した`level`ラベルは付与されていない(`detected_level="unknown"`
  のみ)。これは**3(受信・書込みされているがbest-effort正規表現が不一致でlevel
  未付与)に一致する**。
- 結論: **原因は3。** 1・2・4は事実によって否定される。usw-core・monnieの受信経路
  自体は健全に機能しており、問題はAlloy pipelineのbest-effort level判定正規表現が
  monnie側の実際の行形式(元のsyslog facility.severityテキストが失われた形式)に
  一致しない、という1点に絞られる。

## 事実のまとめ

| 確認項目 | Link Up (09:08:41) | Link Down (09:12:41) |
|---|---|---|
| monnie `/var/log/unifi-devices.log`への到達 | 到達(原文どおり) | 到達(原文どおり) |
| 行頭に`daemon.notice`相当の文字列があるか | ない | ない |
| Lokiの`job="network-devices"`への到達 | 到達 | 到達 |
| Alloy pipelineのlevelラベル | 付与なし | 付与なし |
| Lokiの`detected_level` | `unknown` | `unknown` |

対処案は書かない(claude/Yoshinobu判断に委ねる)。事実確認のみ。

## Next step files

- docs/ai/policies/log_observability_policy.md(LOG-066)
- roles/alloy/templates/config.alloy.j2(best-effort level正規表現)
- /etc/rsyslog.d/10-unifi.conf(monnie、UniFiデバイス受信設定、今回変更なし)
- docs/ai/reviews/promtail_to_alloy/2026-07-26_030_investigation_unifi_linkup_level_match.md(本ファイル)
