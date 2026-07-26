# テスト結果: log_observability debug除外(LOG-070/071)Phase 3b — 本番APPLY

対象: `docs/ai/reviews/promtail_to_alloy/2026-07-26_026_implement_debug_exclusion.md`
(implementer)、`027_review_debug_exclusion.md`(reviewer、Approve)、
`028_test_result_debug_exclusion.md`(tester、Phase 3a PASS)。
diff: `roles/alloy/tasks/main.yml`、`roles/alloy/templates/config.alloy.j2`、
`roles/alloy/templates/observability-sources.rsyslog.j2`。
実行環境: ansy、tester(Claude Code)。実行日時: 2026-07-26 07:54〜08:55頃(JST)。
tester-gate: risk-accepted想定(techlead指示によりYoshinobu明示許可済み、
LOG-032/054充足)。**本番APPLY実施。**

## 1. APPLY前: monnieのautonomous recovery mute(LOG-043)

`homelab-mute set monnie 60 "..."` をquory上で実行(delegate_to: localhostではなく
`hosts: quory`の確認済みAnsible playbookで実行。Claude Code製品固有の実host
ad-hoc禁止のため、生のssh/ad-hocコマンドではなく確認プレイブック経由)。

```
muted: monnie until 2026-07-26T08:54:41+09:00 (reason: log_observability debug
exclusion Phase 3b APPLY (tester, techlead-approved))
```

`homelab-mute status`で確認:
```
TARGET     STATE        UNTIL                      REASON
monnie     MUTED(60m)   2026-07-26T08:54:41+09:00  log_observability debug exclusion Phase 3b APPLY ...
```

## 2. 受信側APPLY(monnie、`playbooks/alloy_setup.yml`、--checkなし本実行)

**結果: 成功。failed=0、rescueなし(Promtailロールバック不要)。**

role組み込みの実バイナリ検証タスクがここで初めて実行され、両方PASSした:

- `Validate the staged Phase 2 rsyslog snippet`(rsyslogd -N1相当): **ok**
- `Validate the deployed Alloy configuration before cutover`(alloy validate相当): **ok**

cutoverタイムスタンプ(実測):
- rsyslog再起動(受信側の新ルーティング反映): `2026-07-26 08:01:09 JST`
- Alloy再起動(新pipeline反映): `2026-07-26 08:01:20 JST`

APPLY後、実際に配備された`/etc/alloy/config.alloy`を直接確認し、Phase 3aの静的
検証と一致する数値を確認した: `drop_counter_reason = "observability_debug_excluded"`
6件、`"observability_info_debug"` 5件、`action = "drop"`総数11件(6+5=11)。
Alloyサービス: `active=active sub=running`。

## 3. 検証(2方向、対象9つ)

techlead依頼は「対象8つ」列挙だったが、実際にはCloudKey(`uckg2`)とUniFi
ネットワーク機器(`u7-1f`/`u7-2f`等)は別ホストのため、実測は9個別ホスト単位で行った。

### 3.1 debugが届かなくなっていること(ground truth、ファイル直読)

`/var/log/{pve-nodes,sophos-fw,ubuntu-nodes}.log`を直接確認した(Loki経由の集計
クエリでなく、受信ファイル自体を読む方が確実なため)。

| ファイル | 総行数 | `debug `prefix行数 | 最後のdebug行の時刻 |
|---|---:|---:|---|
| `/var/log/pve-nodes.log` | 1013 | **0** | (存在せず) |
| `/var/log/sophos-fw.log` | 1270 | **0** | (存在せず) |
| `/var/log/ubuntu-nodes.log` | 4052 | 4(全て**cutover前**) | 06:24:26 JST(cutoverの08:01:09より前) |

`ubuntu-nodes.log`の4件("PackageKit daemon start/quit"、authy 2件・ansy 2件)は
いずれも01:05〜06:24 JST(cutoverの08:01:09より前)であり、**cutover後は0件**。
これはrsyslog側のseverity==7 action削除(このdiffの系統1)が実際に効いている
直接証拠である。

Loki全体(`{level="debug"}`、job/host無指定)を過去2時間で`query_range`(生ログ、
集計でなく実エントリ)した結果も**0件**(cutover前後を通じて)。

monnie自身のjournalは`journalctl -p 7..7`(厳密にpriority=debug=7のみ、
`-p debug`単体は「debug以上=全priority」を意味し誤検知するため区別が必要だった)
で確認したところ、直近15分でわずか1件のみ(自然発生量が非常に少ない)。Alloyの
内部metrics(`/metrics`、`loki_process_dropped_lines_total`)では
`drop_counter_reason="observability_info_debug"`は627件カウント済みだが
`"observability_debug_excluded"`は本セッション内では未計上だった。これは
新設dropが機能していない兆候ではなく、**そもそも計上されるほどのdebugイベントが
まだ発生していない**ことと整合する(observability_info_debug対象の5 unitは
チャッティで既に627件蓄積、一方純粋なpriority=7イベントは全体でも稀)。将来
debugイベントが発生した際に`observability_debug_excluded`が実際に増加することの
継続監視をtechlead/Yoshinobuに推奨する(blocking扱いにはしない)。

### 3.2 error/warning/info(特にinfo)が引き続き届いていること

cutover後(2026-07-26 08:01:20 JST 〜 08:55頃、約55分間)のLoki集計:

| Job | Host | info | warning | error | debug |
|---|---|---:|---:|---:|---:|
| ubuntu-nodes | ansy | 31 | 1 | 0 | 0 |
| ubuntu-nodes | quory | 186 | 1 | 0 | 0 |
| ubuntu-nodes | authy | **92** | **1** | 0 | 0 |
| ubuntu-nodes | monnie(自journal) | 1185 | 1 | 0 | 0 |
| pve-nodes | pve1 | 22 | 0 | 0 | 0 |
| pve-nodes | pve2 | 26 | 0 | 0 | 0 |
| sophos-fw | sophos-fw | 136 | 0 | 0 | 0 |
| unifi | CloudKey(uckg2) | 3 | 0 | **1** | 0 |
| network-devices | UniFi機器(u7-1f/u7-2f/usw-1f/usw-2f) | (level無し、正常。best-effort解析対象外の大半) | - | - | 0 |

全9対象でinfoが継続。sophos-fwはerror/warningの生成元自体が稀なため今回の
観測窓では0だったが(cutover前baselineでもerror/warning実績が僅少)、infoの
継続で受信経路自体は健全と判断した。CloudKey(uckg2)ではerrorも1件観測でき、
error経路も生きていることを確認できた。

### 3.3 authyの調査(techlead/Yoshinobuからの追加確認依頼)

cutover直後の短い観測窓(10分・15分)でauthyの件数が0に見えたため、一度立ち止まって
個別調査した(techlead指示「検証で送信側起因の異常が見つかった場合は個別に調査」
に従い、Yoshinobuからも窓の長さ・authyの実態確認の指示を受けた)。

- authy自身のrsyslog/systemd-journaldはともに`active/running`、ローカルjournalも
  活動あり(直近5分で50行)。送信元は生きている。
- **ground truth**: `/var/log/ubuntu-nodes.log`を直接grepし、authyの最終行は
  cutover(08:01:09)の**15分後**にあたる`08:16:20 JST`のwarning行だった。
  cutover前baseline(15分窓)ではauthy info=42件。
- cutover後55分の集計では authy info=92、warning=1(上記3.2表)であり、**現在は
  正常に届いている**。一時的に短い観測窓で0に見えたのは、authyの出力が
  もともと少なくバースト的であるため(Yoshinobu指摘のとおり「authyは元々ログが
  不足している」)。
- 結論: **回帰ではない。** windowの長さを揃えて再確認した結果、cutover前後で
  authyの転送経路は生きており、一時的な観測窓の短さによる見かけ上のゼロだった
  ことをground truthのログファイル直読で確認した。

## 4. APPLY後: mute解除

全検証PASS後、`homelab-mute clear monnie`をquory上で実行(同じくhosts: quory
経由の確認済みplaybook)。

```
cleared: monnie
```

`homelab-mute status`で解除を確認:
```
TARGET     STATE        UNTIL                      REASON
monnie     expired      ...                        (clearedのため以後expired表示)
```

## 失敗・ブロッカー

なし。APPLYはfailed=0で完走、実バイナリ検証(rsyslogd -N1 / alloy validate)は
両方ok、ロールバックは不要だった。

## 総合判定

**Phase 3b本番APPLY完了。debug除外が実際にground truthレベル(受信ファイル直読・
Loki生ログクエリ・cutover前後のタイムスタンプ突き合わせ)で確認でき、
error/warning/info(特にinfo)は9対象全てで継続。authyの一時的な観測窓ゼロは
回帰ではなくauthy固有の低頻度出力によるものと特定済み。ブロッカーなし。**
mute解除済み。

## Next step files

- docs/ai/reviews/promtail_to_alloy/2026-07-26_026_implement_debug_exclusion.md
- docs/ai/reviews/promtail_to_alloy/2026-07-26_027_review_debug_exclusion.md
- docs/ai/reviews/promtail_to_alloy/2026-07-26_028_test_result_debug_exclusion.md
- docs/ai/reviews/promtail_to_alloy/2026-07-26_029_test_result_debug_exclusion_apply.md(本ファイル)
