# ADR-007: Grafanaのダッシュボード/アラートをrepo正本のprovisioningで配る

**Status:** Accepted(2026-07-30。**Step 1・2・3すべて実装・独立レビュー・実機検証まで完了**し、Policy v4.0(`log_observability_policy.md` LOG-078〜LOG-089)へ規範として反映済み。検証状態の正本は `docs/ai/reviews/grafana_provisioning/` の `008`(Step 1: AC1/AC2/AC5/AC6)・`011`(Step 2: AC3)・`016`(Step 3)。**AC4(実発火時のSlack本文に実測値が入るか)のみ意図的に未検証** — 健全なネットワークでは発火しないため、次回実発火時の観測項目として `docs/ai/status.md` のWatchへ移した(requirement §11で明記済み))

## Context

Grafanaの可視化とアラートが、repoの内容とホストの現物のどちらを正本とするか定まっていなかった。3クラスが別々の方式で管理されていた。

| 対象 | 管理方式 | Ansible管理 |
|---|---|---|
| UniFi 7枚(Techno Tim製) | file provisioning済み(provider `unifi`) | **いいえ** — ホストへのJSON配置とprovider yamlが手作業 |
| `infra_syslog_all_nodes.json` | UI import → DB管理 | いいえ |
| packet error/dropのアラート4件 | UI/DB管理 | いいえ — **発火条件がrepoのどこにも無い** |

**属人性の本体は2つあった。**

1. **アラート4件がUIにしか存在しなかった。** 誰がいつ何を根拠に発火条件を決めたかがrepoに無く、Yoshinobu以外は再現できない。Yoshinobu表明(2026-07-30): 「現行のtechno timダッシュボードのfireについては直接の私が試行錯誤して登録したので属人的になってるのが嫌なのです」
2. **ホスト上のJSONは上流と同一でなかった。** 2026-07-12のGrafana 13.0.2→13.1.0で全パネルが `Data source prometheus not found` になり(復旧はProxmox VMバックアップからの復元)、恒久対応として `jq walk` でdatasource参照をnameベースからUIDへ機械置換した。**この変換手順はNotionの手順書にしか無かった。**

この環境では**datasourceの登録名を変更できない**(Yoshinobu明示: 「実データを送っているのはunpollerであり、登録されるのはprometheus。ここは私が改変できません」)。上流は `__inputs: DS_PROMETHEUS`(label `Prometheus`、大文字P)を宣言し実datasource名は `prometheus`(小文字)であるため、13.0.2までのname fallback(大小無視)で解決できていたものが13.1で解決不能になった — これが07-12の因果である。**UID書き換えは偶発的な対処ではなく、上流取り込みのたびに必要な恒久的工程である。**

## Options Considered

| Option | Pros | Cons |
|---|---|---|
| **(a) file provisioning をAnsibleが所有する** | 既存機構の所有権移転で済み、Grafanaから見て無変化にできる。provisioned化でUI編集が塞がり、変更が必ずgit diffに現れる。追加の秘密を要さない | alerting YAMLの反映にrestartが要る。UIでの試行錯誤が直接はできなくなる |
| (b) HTTP API(service account token)でpushする | restart不要、UI編集も残せる | **vaultにtokenを新設**する。read-onlyにならないためdriftが再発する。「属人性の排除」という目的に逆行する |
| (c) 現状維持(手作業) | 追加実装ゼロ | 属人性がそのまま残る。上流更新時に07-12を再発させる経路も残る |

## Decision

**Option (a)。単一role `roles/grafana_provisioning` が、dashboard JSON・dashboard provider定義・alert ruleのprovisioning配備を所有する。**

以下は本案件で確定した設計判断である。

### 1. 所有権移転は「Grafanaから見て無変化」にする

**provider名(`unifi`)とJSON配置パス(`/var/lib/grafana/dashboards/`)を現行のまま維持する。** provider名を変えるとGrafanaが旧providerのダッシュボードを孤児として扱う経路が生じ、UID保存・folder所属・既存アラートのdashboard参照に影響しうる。

**実測で裏付けが取れた**(Step 1、`008_test_result_step1.md`)。Grafana 13.1はダッシュボードをApp Platformの `resource` テーブルで管理し(**旧 `dashboard` / `dashboard_provisioning` テーブルは空**)、各リソースが provisioning の出所を機械可読な形で持つ。

```
grafana.app/managedBy  = classic-file-provisioning
grafana.app/managerId  = unifi
grafana.app/sourcePath = /var/lib/grafana/dashboards/unifi-sites.json
grafana.app/sourceChecksum = <md5>
```

**この`managerId`が当初の判断(provider名を変えない)の正しさを実測で示している** — provider名はGrafana内部のリソース所有者識別子として実際に使われており、変えれば所有関係が切れる。

### 2. 配備は複製に限る。変換・生成を配備時に行わない

`ansible.builtin.copy` のみを使い `template` を使わない。gitにあるものがホストにあるものと一致する状態を保ち、`--check`での差分読みとSHA256突合を成立させる。**07-12のUID書き換えは「上流取り込み時」の工程であり、配備時ではない。**

**その代わり、nameベースのdatasource参照が1つでもあればpreflightで停止する。** 判定条件は精密でなければならない(実測: `.datasource.type` の値が `"prometheus"` である正当な文字列が18〜283件/枚存在する)。

| 判定 | 対象 |
|---|---|
| 止める | `${DS_...}` プレースホルダ、`.datasource` の値が**文字列**であるもの |
| 通す | `.datasource.type: "prometheus"`(プラグイン種別で必須)、`__inputs`/`__requires` の名残、`.datasource.uid: "grafana"`(組み込み)、表示テキスト中の `unifi-poller` |

### 3. UniFi 7枚をGrafanaのexportで作り直さない

7枚はディスク上にclassic形式の原本が存在し、repoとバイト一致している。一方Grafanaはロード時にschemaを移行して扱うため、`Model: Classic` でexportすると**移行後の内容**が出てくる。

**実測で確定した**(Yoshinobu提供の `unifi-switches.json` Classic export とrepo版の機械diff)。

| 項目 | 結果 |
|---|---|
| PromQLクエリ | 18/18完全一致 — データ取得式は壊れない |
| panel型 | **18枚中15枚が書き換わる**(`graph`→`timeseries`、`table-old`→`table`) |
| `schemaVersion` | export=42 / repo=39 |
| panel個別キー | `links`・`timeFrom`/`timeShift`・`cacheTimeout` 等が消える |

**07-12のような派手な破壊ではなく、見た目では検出できない体裁の劣化である。** 「機能を使っていないから安全」という確認では防げない — 消えたキー自体が「元は使われていたか」の証拠であり、事前のgrepでは判定できない。**7枚の正本はディスク上の原本であり、Grafanaの出力ではない。**

Classic export経路を使うのは、**classic原本が存在しない** syslogダッシュボード(Step 3)だけである。

### 4. reloadはrestart一本。案件全体で1回に集約する

反映機構が3種類で異なる(Step 1で実測)。

| 配る物 | 反映機構 | restart |
|---|---|---|
| dashboard JSON | dashboard providerが `updateIntervalSeconds`(10秒)間隔でpoll | **不要** |
| provider yaml | 起動時読み込み | 必要 |
| alerting YAML | 起動時読み込み | 必要 |

dashboard JSONがrestart無しで反映されることは実測で確認した(配布17:27:43 → Grafana内部更新17:27:49、`generation` 2→3)。**これによりStep 1(JSON配布)を本番無風で通し、restartをStep 2の1回に絞れる。**

**admin資格情報 / service account token を新設しない。** hot reload API(`POST /api/admin/provisioning/alerting/reload`)はBasic Authを要するため、restartを選んだ。代償はrestart時のサービス中断であり、`roles/recovery_mute` でmonnieのmute窓を張って自律復旧の誤発火を防ぐ。

### 5. alert ruleはrule-only YAML。notification policy treeに触れない

現行のroot notification policyは `receiver: empty` で child route を持たない(2026-07-19 grounding)。**labelでのroutingは成立しないため、各ruleの `notification_settings.receiver: slack-homelab` で直接送る**(既存4ルールと同じ方式)。

provisioning YAMLのtop-levelキーは `apiVersion` と `groups` **のみ**とし、`policies` / `resetPolicies` / `contactPoints` / `deleteContactPoints` を書かない(単一のpolicy treeを置換する危険がある)。preflightで機械検査する。

非回帰は `alert_configuration.configuration_hash` の不変で機械的に示す。**この値はYoshinobuがcontact pointやpolicyを意図的に変更したとき正当に変わる** — そのときは値を更新するのが対応であり、assertを外すことではない(手順は `defaults/main.yml` に記載)。

### 6. 移行は「無編集配備」を最優先する。そのために削除を先に置く

正本はYoshinobu提供のUI export(`003_ui_export_alert_rules.yaml`)である。**Grafana自身が出した形を1バイトも触らずに配る。** UID・folderも書き換えない。

**UID衝突は、旧4ルールの削除を配備の前に置くことで回避する。** 当初は「新UIDで並走 → 確認後に旧を削除」としていたが、UI exportの実物が手に入り無編集配備が可能になったため順序を逆にした。**編集はこの案件で最も壊れやすい工程であり、Grafanaの出力を1文字も触らないことが最良の防御である。**

通知の空白は削除→配備→確認の間(数分)に限られ、かつ**ほぼ自己修復する** — 発火条件が `increase(...[15m])` で15分遡るため、空白中に発生したdropも復帰後の評価で窓に入る。ただしこの性質に依存しきらず、一連を連続して行う。

**旧4ルールの削除はAnsibleに実装しない。** DB/UI管理リソースの削除であり、admin資格情報の新設か非冪等なDB操作を要する。Grafana DBへの破壊的操作をAnsibleに持たせない方が残存リスクが小さい。代わりに `alert_rules_predecessor_confirmed` フラグを実配備時に毎回要求する。

### 7. 発火の説明可能性は「なぜこの条件か」と「なぜ今回か」に分ける

| 問い | 満たす手段 |
|---|---|
| なぜ**この条件で**発火する設計なのか | 発火条件の根拠(算出クエリ・観測期間・反実仮想の発火回数)をrepoに残す |
| なぜ**今回**発火したのか | 通知本文に機器名・port・**実測値**が入る |

調査で現行4ルールの `annotations` は機器とportを含むが**実測値を含まない**ことが判明したため、`{{ $values.A.Value }}` の追加を要件に含めた。**これがexportに加える唯一の意図的な変更**であり、gitでは「無編集のexportをcommit」→「実測値を追加」の2コミットに分けて、忠実な移行と意図的な改善を混ぜない。

### 8. 用語を分ける — 「発火条件」と「障害判断の基準」

| 用語 | 何を決めるか | 正本 | 属する世界 |
|---|---|---|---|
| **発火条件** | PromQL、比較値、評価間隔、`for` | provisioning YAML | **仕様** |
| **障害判断の基準** | 発火の頻度を見て障害扱いにするか | 人間の判断 | **運用** |

Yoshinobu表明(2026-07-30): 「grafanaで発火する条件、これはきちんと仕様として管理しないとなぜ発火したのかがわかりません」「ユーザー判断の閾値というのは障害扱いにするかどうか、これは頻度を見て決める。運用ですね」

**1つの語(「閾値」)が2つの世界を指していたことが、この論点を曖昧にしていた。** 発火条件は仕様として管理するが、値をPolicy文書には書かない — **provisioning YAML そのものが仕様書**である。Policyが規定するのは管理の作法(正本の所在・根拠の併記義務・UI編集不可)だけで、値は持たない。

**境界は固定ではない。** `for` やrate窓をルール側へ移すと、それまで運用だった解釈が仕様へ移り、その分だけ根拠を書く義務が増える。現行4ルールは「素朴な発火条件 + 人間側の障害判断」という**意図的な設計**であり(`log_observability_policy` LOG-065が明文化済み)、調整不足ではない。

## Trade-off Analysis

- **(b)を退けた理由が目的そのものである。** 「UIで編集できる」ことは利便性だが、この案件の目的は属人性の排除であり、編集可能性を残せばdriftが再発する。tokenの新設も秘密の増加という恒久的なコストを持つ。
- **provisioned化により、UIでの試行錯誤が直接できなくなる。** これは受け入れた代償である。代わりに調整サイクルを定義した — AIがPrometheusのrange queryで反実仮想(「閾値をXにしたら直近N日で何回発火していたか」)を算出し、Yoshinobuが意味を決め、確定値を根拠つきでrepoへ置く。**探索(Explore・alert preview)はread-onlyなので推奨する。** UIの複製ruleから手作業で値を書き写す経路を既定にしない — 転記が最も壊れやすい。
- **restartを選んだ代償**はサービス中断である。mute窓と実行時刻の調整(`ubuntu_nightly` のmonnie処理と重ねない)で緩和するが、ゼロにはならない。hot reload APIが必要になるほど頻繁にalertingを変更するなら、そのときtokenの新設を再検討する。
- **`folder: UniFi` をalerting provisionerが参照できるかは事前確認が不可能だった。** 公式ドキュメントに記述がなく(Reviewerも独立に確認して未確認)、実機で試すこと自体が本番適用と同一操作になる。**失敗の形が安全側である**ことを根拠に受容した — folderが参照できない場合はルールのloadに失敗してログに残り、既存資源は壊れない。検出手段(ルール不在 + ログ確認)と代替(専用folderへ1行変更)を用意した。

## Consequences

- **Grafanaの可視化とアラートがrepoから配備できるようになる。** 発火条件の変更がgit diffに現れ、UIでの直接編集が塞がる。
- **`log_observability_policy.md` を v4.0 へ改訂した(2026-07-30、実施済み)。** 旧LOG-073/074は「metrics系統の検知ルールは本Policyで定義せず将来別Policyへ集約する」「alert ruleの実体はGrafana UI側にありGit管理外」と明文で決めており、**後者は本案件の完了をもって事実として偽になった**。Yoshinobu判断によりscopeを観測プレーン全体へ拡張し、**LOG-073を退番・LOG-074を方針変更**、配備方式の規範として**LOG-078〜LOG-086を新設**した。あわせてLOG-047の「2 playbook / 2 roleでは配備しない」という限定を外し(`grafana_provisioning.yml`がalert ruleを配備するため数え上げでは表現できない)、**Loki参照かどうかで未実装性を判断する**形へ変えた。§3へ入口を追加しLOG-087で起動とrestartの関係を明記した。
- **上流取り込み(upstream → repo)は別案件として残る。** UID書き換え変換のコード化を含む。`product_inventory` 残ギャップ2(「Techno Timダッシュボードの上流追跡手段が無く13.1破損を事前に拾えない」)と統合して起票する。
- **Step 3では「実ホスト適用前にcommit」の順序が崩れた**(2026-07-30、Auditorが検出)。実ホスト適用を含む案件では、Yoshinobuのcommit/pushを工程上の待ちとして計画に入れる必要がある(当時の`docs/ai/roles/coordinator.md`「計画受領ゲート」項目5。**同節は2026-07-31の簡素化で廃止し、工程の組み立てはCoordinatorの裁量へ移した**)。当時のゲートは、それを確認事項として定める。**Step 1・Step 2では守られていた** — Tester実機実行の前にYoshinobuが `c37cffa`(18:02)・`a2b0367`(19:02)をcommitしており、`011` はそれを明記している。**しかしStep 3では、`roles/grafana_provisioning/` の変更が未commitのまま実配備・restartが実行された。** 一時的に「monnieで動いているコードとgit HEADが一致しない」状態が生じた。

  **計画(`004`)にも計画査読(`005`)にもこの項目への言及がなく、崩れたこと自体もどの記録にも書かれていなかった。** Coordinatorが自己検出して記録した「AC1/AC2をCoordinator自身が実行した逸脱」(`008`)とは対照的に、**こちらは誰も気づいていない** — Coordinator・Reviewer・Testerの全員が見落とし、案件クローズ時のAuditorが初めて拾った。

  **申し送り**: 実ホスト適用を含む案件では、**計画の段階で「commitはどのStepの前に入るか」を明示する**。Step 1・2で守れたのは意識していたからではなく、たまたまYoshinobuがそのタイミングでcommitしたためである。順序を人の記憶に依存させると、Stepが増えたときに崩れる。

- **記録の書き換えが下流の引用を壊しうる**という規律を得た。調査記録を「最新の状態を指すよう更新する」(`core.md`)過程で、下流(計画・実装コメント)が引用していたlistingが落ち、レビューで「引用先が存在しない」と検出された。**書き換えで消す前に、その記録が引用されていないかを確認する。**
- **Grafana 13.1のApp Platform移行**という環境事実を把握した。旧 `dashboard` / `dashboard_provisioning` テーブルは空であり、それを見て「provisioningされていない」と判断すると誤る。alert ruleは従来どおり `alert_rule` テーブルにある。

## 関連

- 案件記録: `docs/ai/reviews/grafana_provisioning/` — 001 requirement / 002 investigation(**R1-2b・R1-4bは後から追補**) / 003 UI export(alert rules) / 004 plan / 005 plan_review / 006 implement_u1 / 007 review_u1 / 008 test_result_step1 / 009 implement_u3 / 010 review_u3 / **011 test_result_step2** / **012 classic export(syslog dashboard)** / **013 syslog dashboard investigation** / **014 implement_u6** / **015 review_final(実装+Policy)** / **016 test_result_step3**
- 調整サイクルの手順: `docs/ai/context/operations/grafana-alerting-tuning.md`(非規範Context)
- 先行調査: `docs/ai/reviews/promtail_to_alloy/2026-07-19_grafana_alerting_grounding.md`
- 07-12のIncident経緯: `docs/ai/reviews/ubuntu_vm_full_upgrade/2026-07-12_028_investigation.md`
- 改訂対象Policy: `docs/ai/policies/log_observability_policy.md`(LOG-063 / 073 / 074 / 065)
