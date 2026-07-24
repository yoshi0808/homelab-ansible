# Repository Context: Log observability

本書はlog collectionを構成する複数playbook / role / configの関係を示す非規範Contextである。許可、禁止、停止条件は [`log_observability_policy.md`](../../policies/log_observability_policy.md) が正本であり、競合時はPolicyを優先する。単一task、default値、template本文、dashboard JSONはcodeを正本とする。

## 入口とrole

| Playbook | 主role | tester-gate | 横断責務 |
|---|---|---|---|
| `alloy_setup.yml` | `alloy` | check-mode-native | monnie receiver、logrotate、Alloy install / config、Promtail cutover、runtime validation |
| `rsyslog_forward_to_monnie.yml` | `rsyslog_forward_to_monnie` | check-mode-native | Ubuntu sender package / config、staging validation、single-host activation |

両入口のAPPLYはproduction logging pathを変更する。Context上の列挙から実行許可を導かず、Policyとplaybook先頭のgateを確認する。

## collection dataflow

```text
remote Linux journal -> local rsyslog ----+
syslog-only appliance -> sender GUI ------+-> monnie rsyslog -> normalized files
monnie journal ---------------------------+-> Alloy pipelines -> local Loki -> Grafana
```

- receiver側roleは既存UniFi routeを保持したままadditional remote sources、rotation、Alloy file / journal pipelinesを構成する。
- sender側roleは許可されたsingle hostへcandidate configをstagingし、complete configuration validation後にpromote / activateする。
- inventory、defaults、templatesがsource、destination、service、label、severity、drop、tail behaviorの値を供給する。
- runtime name resolutionからallowlistを生成するが、配置後にDNSを継続監視して自動更新する機構ではない。

## label、message、dashboard

- receiver templateはsource別のjob / host contractと4-value level extractionを構成する。
- normalized sourcesはlevel / hostをlabelsへ移し、messageだけをLoki bodyへ残す。
- monnie journalのself-noise dropはexact unitとlow severityの組合せだけに適用する。
- dashboard JSONはhost / level / search variables、line format、display limitを保持する。
- config contractの具体token、file path、port、unit list、query式はrole defaults / templates / dashboard JSONを正本とする。

## validated cutoverとrollback

```text
preflight and candidate render
  -> package / runtime contract
  -> candidate validate
  -> Promtail stop
  -> Alloy start
  -> active / ready / journal / real-stream validation
  -> failure: restore Promtail and previous receiver config
```

- check modeではcandidate / native changesを確認し、production cutoverとservice activationを行わない。
- receiver configはstaging、native complete-config validation、promotionの順で扱う。
- Alloy cutoverはpackage auto-startを抑止し、validation合格後だけservice ownershipを切り替える。
- previous configとPromtail assetsはrollback用に保持する。
- sender rolloutはexplicit single-host limitを要求し、前hostのend-to-end gate後に次hostへ進む。
- production change前後のmute / resumeは [Autonomous Recovery Operations Context](../operations/autonomous-recovery.md) を参照する。

## 現行notification実装

2 playbook / 2 roleにはcommon Slack、Grafana contact point、alert rule、Loki ruler、Alertmanagerの配備がない。dashboardのPhase 3 alert説明はfuture design noteであり、current notification implementationではない。

## 関連

- [Policy](../../policies/log_observability_policy.md)
- [System Context](../system/monitoring.md)
- [playbook map](playbook-map.md)
- [role map](role-map.md)
- [Phase 1 investigation](../../reviews/policy_standardization/2026-07-25_021_investigation_remaining_policies_rewrite.md)
