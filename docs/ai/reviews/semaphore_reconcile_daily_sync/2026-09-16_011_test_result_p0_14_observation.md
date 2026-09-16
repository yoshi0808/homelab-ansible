# Test Result: P0-14 実装前gate観測(schedule起動時のsurvey既定値 / カタログ外template参照)

日付: 2026-09-16
対象: `docs/ai/reviews/semaphore_reconcile_daily_sync/2026-09-15_001_requirement.md` P0-14
環境: ansyのSemaphore(`https://localhost:3000`、project 3、EXEC-052)。quoryへは接続していない。

## 冒頭の重要な訂正(id不一致)

要求文 P0-14 は「ansyでは `id=81`」としているが、**これは現物と一致しない**。実測(2026-09-16、GET `/project/3/templates`):

- id=81 は `SEMI-SAFE: Semaphore db backup`(`playbooks/semaphore_db_backup.yml`)
- id=62 が `SEMI-SAFE: Semaphore templates setup`(`playbooks/semaphore_templates_setup.yml`、ブートストラップtemplate本体)

以下の観測はすべて **ansyの実際のブートストラップtemplate id=62** に対して行った。要求文のid記載はCoordinatorへの訂正が必要(quory側の `id=37` は未確認 — 本観測ではquoryへ接続していないため検証していない)。

## 重大インシデント相当の副作用(先に記載する)

**問い1の観測実行中に、ansyのSemaphoreから実際にSlack通知が送信された。** これは想定外であり、`到達してはいけない状態`の「本番Slackへ通知が飛んだ状態」に抵触する可能性が高い。詳細は「問い1」の章と末尾「残存リスク」に記す。**この観測を行った時点で気づいており、Coordinatorへの報告としてこの記録に残す。Incidentファイルの新規作成はTesterの成果物範囲(1ファイル)を超えるため行っていない — Coordinatorの判断を仰ぐ。**

## 問い1: schedule起動のtaskに、survey varsの既定値が適用されるか

### 手順

1. GET `/project/3/templates/62` で現物のsurvey_vars定義を確認(読み取りのみ)。
   - `semaphore_templates_api_base_url`: `required: true`, `default_value: "https://quory.internal:3000/api"`
   - `semaphore_templates_api_validate_certs`: `required: true`, `default_value: "true"`
   - **この既定値そのものが本番URLである点に注意**(後述のリスクの土台)。
2. 関連づけられた `environment_id=5` を GET し、`env`/`json` とも `"{}"` であることを確認(template側に固定上書きは無い)。
3. `inventory_id=3` を GET し、実体は `inventories/homelab/hosts.yml`(本番と同じ全体inventory)であることを確認。添付されている `ssh_key_id=11` を GET し、`type: "none"`、`private_key: ""` など鍵材料が一切無いことを確認(EXEC-052の「SSH鍵を持たずどのホストへも到達できない」がAPIレベルでも裏付けられた)。
4. POST `/project/3/schedules` で一時schedule(id=48、`template_id=62`、`cron_format="51 7 * * *"`(観測時刻の2分後)、`task_params.environment="{}"`、`active=true`)を作成した。
5. 発火時刻の前後をポーリングし、生成されたtask(id=28)を観測した。
6. task終了後、GET `/project/3/tasks/28` と `/project/3/tasks/28/output` でtaskオブジェクトの`environment`フィールドと実行ログを取得した。
7. 直後に schedule 48 を `active:false` へPUT → DELETEで削除した(後述「後始末」)。

### 観測された値

- task 28 の `environment` フィールド: **`"{}"`(作成時に渡したそのまま。埋まっていない)**。
- 実行ログ(抜粋、`/project/3/tasks/28/output`):
  - `PLAY [Fail closed if semaphore_target is not a known Semaphore-server inventory host]` → `skipping: [localhost]`(`semaphore_target`未指定のため既定`quory`が`groups['semaphore_servers']`に含まれ、fail-closed判定は通過した)
  - `PLAY [Reconcile Semaphore templates and schedules from the repo catalog]` → `included: semaphore_templates for quory`(hostsパターンが`quory`に解決された)
  - `TASK [semaphore_templates : Stat the Semaphore API token file]` で **`fatal: [quory]: UNREACHABLE!`**(`Failed to connect to the host via ssh: no such identity: /home/yoshi/.ssh/id_ann: No such file or directory` / `ann@quory.internal: Permission denied (publickey)`)
  - `PLAY RECAP`: `quory: ok=1 changed=0 unreachable=1 failed=0`
  - `Failed to run task: exit status 4`
  - **`Attempting to send email alert to y.abe0808@gmail.com`** → **`Attempting to send slack alert`** → **`Sent successfully slack alert`**

### 言えること

- **「環境が `{}` のとき、Semaphore側でsurvey varsの既定値がtaskのenvironmentへ自動的に埋め込まれる」ことは、今回の実測では観測されなかった。** taskオブジェクトの`environment`は渡した`"{}"`のままであり、survey_varsの`default_value`(base_url/validate_certsとも)がJSON内へマージされた形跡は無い。**ただし、実行がAnsible側の変数解決(role defaultsによる`semaphore_target`由来の`api_base_url`導出)に到達する前に、SSH接続で`UNREACHABLE`となり停止した** — そのため、「Ansible側のrole defaultが実際にどの値で埋まったか」(`-e`無しの状態でrole defaultの`semaphore_target: quory`由来の値が使われたか)までは**確認できていない**。task起動時点でSemaphoreがsurvey既定値を注入しないことは確認できたが、**「埋まらない」がplaybook側の`role defaults`によるフォールバックで実害なく吸収されるかどうかは未確認**(この回はhosts:quoryへのSSHで止まったため、実際に`semaphore_templates_api_base_url`が最終的にどの値でuri呼び出しに使われたかを見る前に停止した)。
- **`semaphore_target`もtask_params.environmentに含めなかった結果、hosts:パターンは既定の`quory`に解決された。** これは実行ログで確認済みの事実であり、**production(quory)を宛先にした接続の試みが実際に発生した**(SSH認証失敗により未到達に終わったが、`到達してはいけない状態`のうち「quoryへ接続した状態」に該当するかは境界の解釈次第 — 実際に確立した接続はゼロだが、接続の試行と、Ansibleの`PLAY RECAP`上に`quory`という宛先名が記録された事実は残る)。**これは観測手順の設計ミスであり、`task_params.environment`に`semaphore_target`を明示しなかったことに起因する。**
- **重大な副作用: Semaphoreのproject/user組み込みのアラート機能(`project.alert=true`、`user.alert=true`、GET `/user`で確認)が、このtaskの`ERROR`終了を検知して実際にSlack通知を送信した(ログに`Sent successfully slack alert`)。** これはAnsible側の`notify`ロジックではない(`roles/semaphore_templates/`配下・`playbooks/semaphore_templates_setup.yml`に`slack`/`notify`の文字列は無いことをgrepで確認済み) — **Semaphore自体の、ユーザーアカウント(`yoshi`、`y.abe0808@gmail.com`)に紐づく通知機能である。** この通知先が2026-09-16のIncident(`docs/ai/memory/incidents/2026-09-16_dev-semaphore-schedules-armed-by-a-phase1-test.md`)と同じ本番Slackチャンネルかどうかは、**APIから宛先(webhook URL/チャンネル名)を読み取る手段が無く未確認**。ただし、同じSemaphoreユーザーアカウントの通知設定である以上、同一の可能性が高いと判断する。
- **この副作用の原因は「ansyでtaskを1本走らせてERROR終了させたこと」そのものであり、survey既定値の有無とは独立した、ansyのSemaphore組み込み機能によるものである。** EXEC-052は「SSH鍵が無く到達できない」ことを検証環境として使える根拠にしているが、**「到達できないこと」と「通知が飛ばないこと」は別である**ことが、2026-09-16のIncidentの教訓どおり、本観測でも再現した。

## 問い2: scheduleが「カタログに無いtemplate」を参照できるか

### 手順

1. POST `/project/3/schedules` で一時schedule(id=49、`name="TESTER-OBS: p0-14 orphan template ref (delete me)"`、`template_id=62`(カタログ外のブートストラップtemplate)、`cron_format="0 4 * * *"`、`task_params.environment`にbase_url/validate_certsの2値を明示、**`active: false`**)を作成した。**発火させないため`active:false`とし、問い1の副作用を再発させない設計にした。**
2. GET `/project/3/schedules/49` で readback した。
3. 直後にDELETEで削除した。

### 観測された値

readback結果(POST応答・GET応答とも一致):

```json
{
  "id": 49,
  "project_id": 3,
  "template_id": 62,
  "cron_format": "0 4 * * *",
  "name": "TESTER-OBS: p0-14 orphan template ref (delete me)",
  "active": false,
  "task_params": {
    "environment": "{\"semaphore_templates_api_base_url\":\"https://ansy.internal:3000/api\",\"semaphore_templates_api_validate_certs\":\"true\"}"
  }
}
```

### 言えること

- **scheduleは、templateカタログ(`semaphore_templates_catalog`)に含まれないtemplate(id=62、orphan)を`template_id`として参照でき、API側もこれを拒否・改変せずそのまま保持する。** POST直後のGETで`template_id=62`が完全一致していることを確認した。
- この観測は`active:false`のまま完結しており、**実行を伴っていない**(発火なし、Slack通知なし)。

## 後始末の確認(自己検証)

- schedule 48(問い1、一時作成): 観測直後に `PUT active:false` → `DELETE`(HTTP 204)。GETで404を確認。
- schedule 49(問い2、一時作成): `DELETE`(HTTP 204)。
- 最終状態、GET `/project/3/schedules` の全件出力(24件、`active`はすべて`false`、id 48/49はいずれも存在しない):

```
count: 24
active true count: 0
ids: [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25, 26, 29, 30, 32, 33, 34, 35]
any of mine (48/49) present: False
```

- 生成されたtask(id=28)自体はSemaphoreの仕様上削除できない(タスク履歴はSemaphoreにDELETE APIが無い)。**これは「到達してはいけない状態」のリストにある`active`schedule・quory接続・本番Slack通知とは別種の残留物であり、履歴として残ること自体は本観測の目的(schedule reconcileの検証)から見て許容範囲と判断したが、Slack通知が飛んだ事実は消えない。**

## 未確認・残存リスク

- **survey既定値が最終的に(SSH到達さえできれば)Ansible側の`-e`として実際に注入されるのか**は未確認(問い1参照)。P0-14の実装では、`task_params.environment`に明示的な2値を必ず書く前提(要求文どおり)であるため、**この未確認事項は実装のリスクにはならない**(既定値に頼らない設計だから)。ただし「`{}`で足りるかを仮定しない」という要求の趣旨には、**「埋まらない」という結論が出せたので沿っている**。
- **quory側のtemplate id=37が実際に存在し、ブートストラップtemplateであることは未確認**(quoryへ接続していないため)。要求文の記載を鵜呑みにせず、Coordinatorから見て確認が必要なら別途Yoshinobuの操作で確認することを推奨する。
- **今回発生したSlack通知の宛先が本番と同一チャンネルかどうかは未確認**(APIから読み取る手段がなかった)。ただし2026-09-16のIncidentと同一ユーザーアカウントの通知機構であり、同一である可能性を前提に扱うことを推奨する。
- **Ansibleのrole defaultsが`semaphore_target`未指定時に`quory`へ解決し、hosts:パターンとして実行を試みる設計そのものが、ansyでの安全な観測を難しくしている。** 今後同種の観測を行うときは、`task_params.environment`に必ず`semaphore_target`(または同等の宛先指定)を含め、**hosts:がansy以外へ解決されることそのものを避ける**べきである(今回はSSH鍵が無いことで実害を免れたが、それは設計ではなく偶然の安全網である)。

## Coordinatorへの申し送り

1. **P0-14要求文のtemplate id記載(`ansy: id=81`)を`id=62`へ訂正すること。** `id=81`は別のtemplate(`Semaphore db backup`)を指しており、このまま実装へ進むと誤ったtemplateを参照する。
2. **本観測でSlack通知が実際に飛んだ事実をどう扱うか、Coordinatorの判断を仰ぐ。** Incident化するかどうかを含め、Testerの成果物範囲(本ファイル1点)を超えるため記録のみ行い、判断はCoordinatorへ委ねる。
3. 上記以外の後始末(schedule/active状態)は本ファイルの「自己検証」のとおり完了している。
