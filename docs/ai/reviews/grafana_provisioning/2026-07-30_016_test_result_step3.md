# test_result: Step 3 実機配備と検証(U7)

作成: 2026-07-30 / Tester(独立subagent)
対象: `docs/ai/reviews/grafana_provisioning/2026-07-30_004_plan.md` §4 U7(U6実装済み、Reviewer Approve済み)
参照: `2026-07-30_001_requirement.md` R10、`2026-07-30_013_syslog_dashboard_investigation.md`(U5)、
`2026-07-30_014_implement_u6.md`(U6実装)、`2026-07-30_015_review_final.md`(最終レビュー、対象1 Approve)
対象ホスト: monnie(inventory `inventories/homelab/hosts.yml`)。特権read-only確認は `ansible monnie -b`。

実行コマンド(依頼どおり):

```
ansible-playbook playbooks/grafana_provisioning.yml --tags dashboards,provider
```

**`--tags alerting` は含めていない。** alerting配備はStep 2で完了済み・内容不変のため対象外(依頼文どおり)。

## 総括

| 項目 | 結果 |
|---|---|
| 配備の完了 | **完了。** exit code 0、`ok=20 changed=5 unreachable=0 failed=0 skipped=4` |
| UniFi 7枚のdashboard JSON | **`changed=false`(期待どおり)** |
| syslogダッシュボード1枚 | **`changed=true`(新規、期待どおり)** |
| 新ディレクトリ `/var/lib/grafana/dashboards-infra-syslog` | **作成された(`changed`)** |
| `unifi.yaml` | **`changed=false`(期待どおり、異常なし)** |
| `infra-syslog.yaml` | **`changed=true`(新規、期待どおり)** |
| restart | **発生した(mute→restart→port待ちの順で実行、期待どおり)** |
| `configuration_hash` | **不変(`c6c0ff263e3ebf225d478e187c42cd99`のままassert pass)** |
| 手順5・6(4ルール確認・ログ確認) | **skipされた(`grafana_provisioning_alerting_result`が未定義のため)。debugメッセージで明示された。設計どおりで異常ではない** |
| **同一uidの引き取り可否(最重要)** | **引き取り成功。詳細は下記** |
| 再実行の冪等性 | **確認した(`--check --diff`再実行でchanged=0、restart_needed=false)** |
| 作業ツリー | **成果物1ファイル追加のみ。既存stageは無変更** |

---

## 1. 配備手順の詳細

### 事前確認(read-only)

- `ansible monnie -m ping` → `pong`(到達性確認)。
- `ansible-playbook ... --tags dashboards,provider --check --diff` を先に実行し、以下を確認してから本実行した(安全側の追加確認。依頼文が禁じる「別の形での到達」には当たらない — 本実行の前段としてPolicy上も許容されるread-only確認):
  - UniFi 7枚のSHA256比較タスクが全て `match: true`
  - syslogダッシュボードは `host_present: false`(未配備、想定どおり)
  - `--check`下でcopy/restart系タスクが全て`skipping`
- 配備前に、DB上で `infra-syslog-all-nodes-v1` が1件のみ・`folder=''` であることを確認(U5と同じ観測、変化なし)。

### 本実行

```
$ ansible-playbook playbooks/grafana_provisioning.yml --tags dashboards,provider
...
PLAY RECAP
monnie : ok=20  changed=5  unreachable=0  failed=0  skipped=4  rescued=0  ignored=0
```

`changed=5`の内訳:
1. `Ensure the infra-syslog dashboards directory exists on monnie`(新規ディレクトリ作成)
2. `Deploy dashboard JSON to monnie`(item=infra-syslog-all-nodes.json のみ)
3. `Deploy dashboard provider yaml to monnie`(item=infra-syslog.yaml のみ)
4. `Recovery mute | set/extend mute atomically under flock (monnie)`
5. `Restart grafana-server`

UniFi 7枚の`Deploy dashboard JSON`は全て`ok`(changed無し)。`unifi.yaml`(`Deploy dashboard provider yaml`のitem=unifi.yaml)も`ok`。**両方とも異常なし(依頼文が「変わったら異常」としていた項目は不変を確認した)。**

`configuration_hash`のassertは`ok`(pass)。手順5・6(4ルール存在確認・ログ確認)は`skipping`となり、末尾で次のdebugメッセージが出力された(設計どおり、異常ではない):

> このrunではalertingが配られなかった(--tags alertingが指定されていないか、`never`タグでskipされた)ため、4ルールの存在確認とgrafana-serverログのprovisioningエラー確認を実行していない。provider単独のrestartではこの2手順は意味を持たない。

### 再実行による冪等性確認

配備後に`--check --diff`で再実行し、次を確認した:
- SHA256比較タスクで `infra-syslog-all-nodes.json` が `host_present: true, match: true` に変わった(unifi 7枚は変化なし、引き続き全一致)。
- `Determine whether a restart is needed`が`false`相当(copy系タスクは全て`skipping`のまま、`changed=0`)。

---

## 2. 同一uidの引き取り可否(最重要の観測項目)

### 2-1. `resource`テーブルの重複有無

配備前後とも次のクエリで確認した(read-only、`sqlite3 mode=ro`経由のpython3 `sqlite3`モジュール):

```
SELECT name, folder FROM resource WHERE resource='dashboards' AND name='infra-syslog-all-nodes-v1'
```

- 配備前: 1行(`folder=''`)
- 配備後: **1行のまま(`folder=''`)**。**重複していない。**

### 2-2. `metadata.annotations`の`managedBy`/`managerId`

配備後、当該dashboardの`value`列(JSON)を読んだ結果:

```json
{
  "grafana.app/createdBy": "user:ffn82u6q7ka9se",
  "grafana.app/managedBy": "classic-file-provisioning",
  "grafana.app/managerId": "infra-syslog",
  "grafana.app/sourceChecksum": "4934d0e8ac8149e3ca9db6a4d52347f0",
  "grafana.app/sourcePath": "/var/lib/grafana/dashboards-infra-syslog/infra-syslog-all-nodes.json",
  "grafana.app/sourceTimestamp": "1785408975000",
  "grafana.app/updatedBy": "access-policy:service",
  "grafana.app/updatedTimestamp": "2026-07-30T10:56:18Z"
}
```

**`managedBy: classic-file-provisioning` / `managerId: infra-syslog` が付いている。期待値(`classic-file-provisioning` / `infra-syslog`)と完全一致。引き取りは成功したと判断する。**

`metadata.generation`は配備前の`6`(U5記録)から**`7`へ1つ進んだ**(=DBの既存レコードが更新された。新規作成ではない、という点でも「引き取り」の解釈と整合する)。

### 2-3. `grafana.app/folder`

**キー自体が`annotations`に存在しない(空でも不在でもない、という表現をすると誤解を招くので正確に書く: 上記JSON中に`grafana.app/folder`キーが無い)。** U5が観測した配備前の状態(`grafana.app/folder: ""`という明示キー)とは異なり、**配備後はキーそのものが消えている。** `resource`テーブルの`folder`列自体は`''`のままであり(2-1参照)、rootに所属している事実は変わっていない。**annotationsからキーが消えたことの意味(仕様上の正常な省略か、何らかの差か)は判定していない — 判断に迷った点として記録する。**

### 2-4. restart後のログ

`journalctl -u grafana-server`をrestart時刻(`ActiveEnterTimestamp` = 19:56:17 JST)以降で取得し確認した。

- `logger=provisioning.dashboard msg="starting to provision dashboards"` → `msg="finished to provision dashboards"` の2行のみで、**間にエラー・警告は無い。**
- `level=error`で全体を検索した結果、該当したのは次の3件のみで、**いずれもrestart(プロセス再起動)に伴う正常な事象であり、provisioning/dashboardエラーではない**:
  - `plugin process exited`(elasticsearch/zipkinプラグイン、`signal: terminated` — restart時のプロセス終了)
  - `job cleanup controller failed`(`context canceled` — shutdown時のコンテキストキャンセル)
  - `Failed getting data source`(`context canceled`、restart中にブラウザ側の既存リクエストがキャンセルされたもの)
- `infra-syslog`という文字列を含むログ行は、上記の`sourcePath`記録以外では、後の時刻(restartから離れたタイミング)にブラウザから当該dashboardへアクセスした`Request Completed`行が数件出るのみで、エラーは含まれない。

**結論: provisioningエラーは見つからなかった。**

---

## 3. Yoshinobuへの依頼事項(Testerは判定しない)

1. **syslogダッシュボードがUI上で正常に描画されるか**(パネル3枚: Event Timeline / Infra Events / Network Device Events)。
2. **UI上でどのfolderに見えるか、Provisioned表示になっているか。** DB上は`folder=''`(root)で`managedBy`/`managerId`が付いているためProvisioned表示になる可能性が高いが、これは推測であり、UIでの実見た目確認をお願いしたい。
3. **UniFi 7枚が引き続き正常に描画されるか**(restartを挟んだため。2026-07-12は`grafana-server`がactiveのまま全パネルが真っ白になった前例がある)。

DBの確認(2-1〜2-4)だけでは「描画OK」と結論していない。

---

## 4. 残存リスク・未解決事項

1. **`grafana.app/folder`アノテーションキーが配備前後で「明示的な空文字列」→「キー不在」に変わった(2-4)。** 意味的にrootである点は変わらないと判断しているが、この変化自体の理由(Grafana内部仕様か、provisioning経由の書き込みが省略記法を使うためか)は確認していない。実害は観測されていない(重複無し・folder列は不変)ため停止する理由はないが、**判定に迷った点として記録する。**
2. **`generation`が6→7へ進んだことは「更新(引き取り)」の直接証拠として扱ったが、Grafana内部でこの値がどう定義されているかのソースコード確認はしていない。** U5の未解決事項3と同種の留保。
3. **`id`フィールド(`1914057286721536`)を配ったことによるGrafana側の挙動**は、今回のログ・DB確認の範囲では異常が見当たらなかった(provisioning成功、重複なし)。ただしU5・U6が留保していた「未検証」という位置づけ自体は今回の観測で完全には解消されていない(挙動の"理由"までは確認していない)。
4. **手順5・6(4ルール存在確認・ログ確認)は今回のrunでは実行されなかった。** これは`--tags alerting`を含めない今回の起動では設計どおりの分岐であり、異常ではない(playbookのdebugメッセージで明示された)。Step 2で既にこの2手順は実施・pass済み。
5. 新ディレクトリのowner/mode(`grafana:grafana 0755`)は、U6実装記録・レビューの双方が既にCoordinator追補の実測値(`002_investigation.md` R1-2b)と一致することを確認済みであり、本Stepで新たな懸念はない(再確認はしていない)。

---

## 5. 実行環境・安全境界の遵守

- `--check`無しの実配備は1回のみ実行した(依頼どおりのコマンド)。事前・事後の`--check --diff`確認は安全側の追加確認であり、本実行の代替や回避ではない。
- DB参照は全て`sqlite3?mode=ro`のread-onlyオープン(python3経由)。書き込みは発生していない。
- `tester_mode`/`skip_notifications`のフラグは対象外(本playbookはR9により完了通知をSlackへ送らない設計であり、そもそも通知経路を持たない。実行中もSlack通知は観測されなかった)。
- `git add`/`commit`/`push`は行っていない。既存のstage(Coordinator用意のcommit候補)は本作業の前後で完全に不変であることを`git diff --cached --stat`で確認した。
- IPアドレス: 本ファイルおよび作業ログへの転記前に`grep -E '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b'`を実行し、該当なしを確認した(journalctl生ログには接続元IPが複数含まれていたため、本文への転記時に数値・生ログの引用を避け、ログの意味的な要約のみを記載した)。

## 対象パス一覧

- 対象role: `/home/yoshi/homelab-ansible/roles/grafana_provisioning/`
- 対象playbook: `/home/yoshi/homelab-ansible/playbooks/grafana_provisioning.yml`
- 本ファイル(成果物): `/home/yoshi/homelab-ansible/docs/ai/reviews/grafana_provisioning/2026-07-30_016_test_result_step3.md`
- 対象ホスト: monnie
