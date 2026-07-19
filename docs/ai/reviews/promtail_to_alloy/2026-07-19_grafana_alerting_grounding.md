# Alloy Phase 3 — Grafana alerting grounding survey

調査日: 2026-07-19 JST  
対象: `monnie` / Grafana  
調査種別: read-only

## 結論

Phase 3 の rule-only file provisioning は、現行の UI/DB 管理アラートおよび Slack contact point と共存できる。

| 必須事項 | 確定値 / 方針 |
|---|---|
| Loki datasource UID | `ffn86ietu7jeoc` |
| ルーティング先 | contact point name `slack-homelab`、integration UID `cfoig7vuapczkf`、type `slack` |
| policy tree 非上書き策 | YAML は `groups` だけを定義し、各 rule の `notification_settings.receiver: slack-homelab` を明示する。`policies`、`resetPolicies`、`contactPoints` は一切含めない |
| 配置先 | `/etc/grafana/provisioning/alerting/<phase3専用名>.yaml` |
| 反映 | 配置だけでは不十分。Grafana restart、または Basic Auth を用いた `POST /api/admin/provisioning/alerting/reload` のいずれか。今回どちらも実行していない |

現行 root notification policy の receiver は通知設定を持たない `empty` で、子 route もない。そのため、新規ルールが `notification_settings` を持たない場合、既存 Slack には届かない。現行の4ルールと同じ rule-local routing を採用するのが、policy tree を変更せず Slack に届ける具体策である。

## 調査方法と非変更保証

- `/etc/grafana/grafana.ini`、`/etc/default/grafana-server`、systemd の起動定義、`/etc/grafana/provisioning/**` をそのまま参照した。
- DB は `/var/lib/grafana/grafana.db` を Python標準 `sqlite3` の URI `mode=ro` で開いた。対象ホストに `sqlite3` CLI は未導入だったため、パッケージ追加やDBコピーは行っていない。
- 認証付き Grafana HTTP API は使用していない。
- Grafana/DBへの書込み、ファイル追加、provisioning reload、サービスrestartは行っていない。
- Slack webhookの値は取得・出力せず、暗号化フィールド `url` が存在することだけを確認した。本書にIPアドレスは記録していない。

## 1. Grafana version、paths、unified alerting

### Version

- Grafana `13.1.0`
- build表示: release `13.1.0#patched`
- 出所: `grafana-server -v`（runtime/file）

### Effective paths

`grafana.ini` の `[paths]` はコメント既定値のままだが、Debian package の systemd 起動引数が `/etc/default/grafana-server` の値を `cfg:default.paths.*` として渡している。

| 項目 | Effective value | 出所 |
|---|---|---|
| config | `/etc/grafana/grafana.ini` | systemd + `/etc/default/grafana-server` |
| data | `/var/lib/grafana` | systemd + file |
| DB | `/var/lib/grafana/grafana.db` | `[database]`既定 `grafana.db` + effective data path |
| provisioning root | `/etc/grafana/provisioning` | systemd + `PROVISIONING_CFG_DIR` |
| alerting provisioning | `/etc/grafana/provisioning/alerting` | provisioning root + directory layout |

alerting directoryには `sample.yaml` のみがあり、その内容は全てコメントされたパッケージサンプルである。したがって、現時点で classic file-provisioned alerting resource はない。

### Unified alerting

有効である。

根拠:

- `grafana.ini` の `[unified_alerting] enabled` はコメント状態で、既定値は `true`。
- 同じく `execute_alerts` はコメント状態で既定値 `true`。
- DBに4件の `alert_rule` があり、Grafanaの unified alerting rule endpoint が現在利用されていることをservice logで確認した。
- Grafana公式設定仕様も `[unified_alerting].enabled` の既定値を `true` としている。

出所: file、DB、runtime log、[Grafana configuration documentation](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/)。

## 2. Datasources

| Org | Name | UID | Type | Default | Source |
|---:|---|---|---|---|---|
| 1 | `loki` | `ffn86ietu7jeoc` | `loki` | no | DB `data_source` |
| 1 | `prometheus` | `ffn83gysyghs0c` | `prometheus` | yes | DB `data_source` |

`/etc/grafana/provisioning/datasources/sample.yaml` はコメントだけで、Loki/Prometheusのfile定義はない。両datasourceの `read_only` DB値も `0` であるため、現行datasourceはDB/UI管理と判断できる。

Phase 3 rule の Loki queryは、nameではなく必ず次を使用する:

```yaml
datasourceUid: ffn86ietu7jeoc
```

rule model内の datasource UID も同じUIDに揃える。

## 3. Contact points

実integrationを持つ既存contact pointは1件。

| Name | Type | Integration UID | Secret | Source |
|---|---|---|---|---|
| `slack-homelab` | `slack` | `cfoig7vuapczkf` | `url: <encrypted/masked>` | DB `alert_configuration` |

DB Alertmanager configには `empty` というreceiver名もあるが、配下のintegration configが0件で、UID/typeもない。これはroot policyの空の受け皿であり、実用contact pointとして数えない。

`provenance_type` には Slack integration UID の `contactPoint` recordがあるがprovenance値は空である。またfile側にcontact point定義はない。このため `slack-homelab` は現行DB/UI管理である。

## 4. Notification policy tree

DB `alert_configuration.alertmanager_configuration` の現行tree:

```yaml
receiver: empty
group_by:
  - grafana_folder
  - alertname
routes: []
matchers: []
```

- default/root receiver: `empty`
- child routes: なし
- label matchers: なし
- `empty` receiver: integrationなし

出所: DB。

重要な含意:

1. labelに `severity` 等を付けるだけでは Slack にrouteされない。
2. root policyを `slack-homelab` に変えると既存動作範囲を広げ、要求の「policy不変」に反する。
3. Phase 3 YAMLに `policies` を書くと、単一treeである既存policyを置換する危険がある。
4. 各ruleの `notification_settings.receiver: slack-homelab` は、既存ruleと同じ直接選択方式であり、user-visible policy treeを上書きしない。

配置ファイルには次の形だけを使用する:

```yaml
apiVersion: 1
groups:
  - orgId: 1
    name: <phase3-group>
    folder: <phase3-dedicated-folder>
    interval: 1m
    rules:
      - uid: <unique-rule-uid>
        # ...
        notification_settings:
          receiver: slack-homelab
```

次のtop-level keyは含めない:

- `policies`
- `resetPolicies`
- `contactPoints`
- `deleteContactPoints`
- `deleteRules`（初回追加では不要）
- その他、既存notification resourceを変更・削除するkey

## 5. Existing alert rules and Slack routing

現行ruleは4件で、全てfolder `UniFi`、group `Evaluation interval: 1m`、org 1、paused=false。folder `UniFi` は dashboard file provider `unifi` が作成したfolderであるが、alert rule自体にはfile provisioning provenanceがないためUI/DB管理である。

| Rule title | Rule UID | Query datasource | Routing |
|---|---|---|---|
| `UniFi Switch RX Drop` | `bfoii89j7l88wf` | Prometheus `ffn83gysyghs0c` | direct `slack-homelab` |
| `UniFi Switch RX Error` | `dfoiiku15evi8e` | Prometheus `ffn83gysyghs0c` | direct `slack-homelab` |
| `UniFi Switch TX Drop` | `dfoih9pbfckxsf` | Prometheus `ffn83gysyghs0c` | direct `slack-homelab` |
| `UniFi Switch TX Error` | `dfoiihloh6hogd` | Prometheus `ffn83gysyghs0c` | direct `slack-homelab` |

全4ruleのDB値:

```json
notification_settings = [{"receiver":"slack-homelab"}]
labels = ""
alert_routing_policy = null
```

したがってTX Dropを含む既存ruleは、root default policyやlabel matcher routeではなく、rule-local contact point selectionでSlackへ送る。

## 6. File-provisioned rules and UI-managed rules coexistence

共存可能で、専用のenable設定は不要。

- Grafanaはfile provisioningされたresourceにprovenanceを付け、UIではProvisioned/read-onlyとして扱う。
- UI/DB管理resourceは引き続き編集可能で、異なるUID・folder/groupならfile-provisioned rulesと共存する。
- 現行の4 rule UIDと衝突しない固定UIDをPhase 3側で割り当てる。
- 専用folder/groupを使用し、既存 `UniFi` folder/groupには追加しない。
- 既存resourceと同じUIDをimportするとconflictになるため、UIDの一意性をpre-deployで検査する。
- alerting YAMLをrule-onlyにすれば、DB管理contact point/policyのprovenanceと所有権を奪わない。

Grafana公式資料でも、file provisioned alert resourcesはUIで直接編集できず、手動作成resourceと区別して表示されると説明されている。[Provision Alerting resources](https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/)

## 7. Placement and reload

### Placement

Effective scan directory:

```text
/etc/grafana/provisioning/alerting/
```

推奨は既存 `sample.yaml` を編集せず、Ansible管理の専用ファイルを追加すること。例:

```text
/etc/grafana/provisioning/alerting/homelab-loki-phase3.yaml
```

owner/modeは実装時に既存Grafana packageの設定ファイル規約へ合わせる。今回ファイルは作成していない。

### Reload behavior

alerting file provisioningはGrafana起動時に読み込まれる。稼働中のファイル変更を自動pollして反映する前提にはできず、次のどちらかが必要:

1. `grafana-server` restart
2. Admin API hot reload:
   `POST /api/admin/provisioning/alerting/reload`

Grafana公式仕様ではhot reload endpointはBasic Authenticationを要求し、処理完了時にはprovisioned entitiesがDBへ格納済みとなる。[Admin HTTP API — Reload provisioning configurations](https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/api-legacy/admin/)

Phase 3のAnsible実装判断:

- 既存Vault等にGrafana admin Basic Auth資格情報が安全に管理され、ログへ露出させず使える場合はhot reloadがservice interruptionを避けられる。
- その前提がない現在は、認証情報やtokenを新設せず、既存運用経路で `grafana-server` restartする方が構成追加を最小化する。
- どちらの場合も、配置前にYAML validationとUID衝突検査を行い、反映後にrule loadと既存4rule/policyの非回帰を確認する。
- 今回はreload endpointを呼ばず、restartもしていない。

## Source-of-truth matrix

| Item | File | DB | Runtime / docs | 判定 |
|---|---|---|---|---|
| Version | package binary | — | `grafana-server -v` | runtime |
| Effective provisioning path | `grafana.ini`, `/etc/default/grafana-server` | — | systemd ExecStart | file + runtime |
| Unified alerting | commented default=true | unified rule records | current alerting endpoint use + official default | enabled |
| Loki/Prometheus datasource | sample only | `data_source` | — | DB/UI managed |
| Slack contact point | no file definition | `alert_configuration`, `provenance_type` | — | DB/UI managed |
| Notification policy | no file definition | `alert_configuration` | — | DB/UI managed |
| Existing alert rules | no alerting rule file | `alert_rule` | current alert UI/ruler access | UI/DB managed |
| UniFi folder | dashboard provider file | App Platform `resource` | provider manager `unifi` | dashboard file-provisioned folder |
| Phase 3 reload method | alerting scan directory | — | official Admin API | restart or authenticated hot reload |

## Pre-implementation guardrails

- Loki UID `ffn86ietu7jeoc` をAnsible assertionまたはread-only preflightで再確認する。
- `slack-homelab` と integration UID `cfoig7vuapczkf` の存在を再確認するが、webhook値は取得・比較しない。
- Phase 3 YAMLのtop-level keyが `apiVersion` と `groups` のみであることを検査する。
- 全ruleに `notification_settings.receiver: slack-homelab` があることを検査する。
- dedicated folder/groupと固定unique UIDを使い、既存UID 4件と衝突しないことを検査する。
- reload前後でpolicy treeのserialized value/hash、既存4rule、Slack contact point UIDが不変であることをread-onlyに比較する。
- service interruptionを伴うrestartを選ぶ場合は、既存のmonitoring mute手順とmaintenance windowを使う。

