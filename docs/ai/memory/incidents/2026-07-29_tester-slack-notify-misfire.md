# Incident: 検証実行でSlack通知が実送信された(`skip_notifications` 付与忘れ)

日付: 2026-07-29(発生・起票とも同日)
起票: Coordinator。Tester(subagent)が `proxmox_exec_node_selection` 案件のAC1検証中に自己申告し、依頼文の書込許可の範囲外と判断して起票をCoordinatorへ委ねた
状態: 解決済み(実害なし)
対象: Tester役の実行手順、`roles/common_slack/tasks/notify.yml`
種別: ヒヤリハット
原因分類: #運用考慮ミス #設計上の欠陥

## 症状

`proxmox_exec_node_selection` 案件のAC1検証で、Testerが

```
ansible-playbook playbooks/recovery_vm_reboot.yml -e target=monnie --check
```

を実行した際、`-e skip_notifications=true` の付与を忘れ、**Slackへ実通知が1件送信された**(`channel=info`、`status=info`)。

対象VM(monnie)への実操作は発生していない。`--check` ゲートは設計どおり機能し、Phase 2以降のshutdown/startは全てskipされている。**実害は「本番のSlackチャンネルにテスト由来の通知が1件混ざったこと」に限られる。**

2回目以降の実行では `skip_notifications=true` を付与しており、以降の実送信はない。一次記録: `docs/ai/reviews/proxmox_exec_node_selection/2026-07-29_007_test_result_step1.md`。

## 原因

**通知を抑止する唯一の手段が、実行者が毎回CLIで渡す変数だからである。**

`roles/common_slack/tasks/notify.yml` L27 / L30 は `tester_mode` または `skip_notifications` が真のときだけ送信を抑止する。どちらも既定は偽であり、**渡し忘れた場合の既定動作が「本番へ送る」**。

```yaml
when: tester_mode | default(false) | bool or skip_notifications | default(false) | bool
```

`--check` の有無は判定に入っていない。したがって `--check` を付けた検証実行であっても、変数を渡さなければ通知は本番へ飛ぶ。

**これは実行者の注意力に依存した安全装置であり、注意力は再現しない。** 同種の事象は2026-07-26にも起きており(`docs/ai/reviews/` 内の当時の記録)、**今回が再発である**。「気をつける」で閉じた前回の対応が効かなかったことが、今回の再発そのもので実証された。

なお、この案件の他の実行(AC2 / AC3)では正しく付与されており、**手順を知らなかったのではなく、1回目だけ落ちた**。知識の欠落ではなく、忘れうる形になっていることが原因である。

## 修正内容

**本Incidentでは構造的な修正を行っていない。** 通知抑止の既定を反転させる(`--check` 実行時は既定で抑止する等)のは `roles/common_slack` の全利用箇所へ波及する設計変更であり、Incident対応として即断せず案件として扱う。`docs/ai/status.md` の Next へ起票した。

今回行ったのは事実の記録のみである。

**Testerの振る舞いについては是正不要と判断した。** Testerは誤送信に気づいた時点で報告し、2回目以降は正しく付与し、さらに `docs/ai/memory/incidents/` への独立ファイル作成を試みたうえで**依頼文の書込許可(test_result の新規作成のみ)に反すると自ら判断して取り下げ**、経緯をtest_resultへ残してCoordinatorへ委ねた。境界の扱いは正しい。

## 確認方法

- 以降の検証実行で `skip_notifications=true` または `tester_mode=true` が付与されていること(test_result に実行コマンドが記録されるため事後に検証できる)。
- 構造的な対処を行う場合は、`roles/common_slack/tasks/notify.yml` の `when:` に `--check` 相当の条件が入っていること。

## 残存リスク

- **同じ形の再発は、次に誰かが変数を渡し忘れた時点で起きる。** 現在の防止手段は依頼文へ明記することだけであり、`docs/ai/memory/lessons/permission-boundaries-must-be-designed-not-prompted.md` が「文章による依頼は境界の段の1つではない」と述べている状態そのものである。
- 誤送信された通知は削除していない。`channel=info` の1件であり、運用上の判断材料を汚さないため放置してよいと判断した。
