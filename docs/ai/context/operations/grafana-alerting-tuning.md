# Operations Context: Grafana発火条件の調整サイクル

本書は、Grafanaのalert ruleの**発火条件**を調整するときの手順を示す非規範Contextである。実行の許可、禁止、停止条件は [`log_observability_policy.md`](../../policies/log_observability_policy.md)(LOG-078〜LOG-089)が正本であり、競合時はPolicyを優先する。設計判断の背景は [ADR-007](../../adr/007-grafana-provisioning-as-code.md)。

**本書が扱うのは「調整」である。移行(UI管理からrepo正本化へ移すこと)は2026-07-30に完了しており、案件記録は `docs/ai/reviews/grafana_provisioning/`。**

## この手順が必要な理由

2026-07-30の移行までは、発火条件がGrafana UIにしか存在せず、**誰がいつ何を根拠に決めたかがrepoに無かった**。Yoshinobu表明(2026-07-30):

> 現行のtechno timダッシュボードのfireについては直接の私が試行錯誤して登録したので属人的になってるのが嫌なのです。

移行によって値はrepoへ移ったが、**「なぜこの値か」を残す仕組みが無ければ属人性はそのまま再発する。** 本書はその再発を防ぐための手順である。

## 用語 — 2つを混同しない

`log_observability_policy.md` LOG-079 が正本。**どちらも単に「閾値」と呼ばない。**

| 用語 | 何を決めるか | 正本 | 属する世界 |
|---|---|---|---|
| **発火条件** | PromQL / LogQL、比較値、評価間隔、`for` | provisioning YAML(repo) | **仕様**。本書の対象 |
| **障害判断の基準** | 発火の頻度を見て障害扱いにするか | 人間の判断(LOG-065) | **運用**。repoに書かない |

Yoshinobu表明(2026-07-30):

> grafanaで発火する条件、これはきちんと仕様として管理しないとなぜ発火したのかがわかりません。ユーザー判断の閾値というのは障害扱いにするかどうか、これは頻度を見て決める。運用ですね。

**境界は固定ではない。** `for` やrate窓を発火条件側へ移すと、それまで運用だった解釈が仕様へ移る。**移した分だけ根拠を書く義務が発火条件側へ増える**(LOG-081)。移すかどうかはYoshinobuが決める。

## 現行の発火条件(2026-07-30時点)

**値は本書に書かない。正本は `roles/grafana_provisioning/files/alerting/unifi-switch-port-errors.yaml` である**(`docs/ai/core.md`「値を二重に持たない」、LOG-080)。調整前には必ずそのファイルを開いて現在値を確認する — **本書の記述を現在値と思って読まないこと。**

構造だけ述べる。4ルール(TX/RX × Drop/Error)はすべて同じ形をしており、**unpollerのport系カウンタに対する `increase()` を、単一の比較値で評価する**。評価間隔と `for` も4件で共通である。

**この素朴さは意図的な設計であり、調整不足ではない**(LOG-065)。**整数カウンタに対する現行の比較値は実質「1つでも増えたら発火」に相当する** — つまり発火条件は極めて敏感で、**少数の発火は様子見**とし同一portで頻発したときに問題ありと判断する、という運用側の解釈と組み合わせて成立している。

**調整とは、この「敏感な発火条件 + 人間の解釈」という組み合わせのどこを動かすかを決めることである。** 発火条件を鈍くするのか、解釈の一部(`for`・rate窓・port別)を発火条件側へ移すのか、あるいは現状を維持するのか。

## 調整の手順

### 1. AIが反実仮想で根拠を作る

**「閾値をXにしたら直近N日で何回発火していたか」を機器/port別に算出する。** Prometheusのrange queryをread-onlyで引く。

この根拠が移行前はどこにも存在しなかった。**ここがAIの担当分である** — データから機械的に出せる部分であり、人間の記憶に頼る必要がない。

対象ホストは `monnie`(Prometheus)。**read-onlyの参照であり、Yoshinobuの確認を要さない**(2026-07-30、`monnie`は非冪等操作でも確認不要と決定済み。`docs/ai/roles/coordinator.md`)。

### 2. Yoshinobuが意味を決める

データから導けない判断がここに集まる。

- どのportが既知のノイズか
- 1時間あたり何回のdropならSlackを鳴らす価値があるか
- 1回のflapを事象と見るか

**AIはこの判断を代行しない。** 1の反実仮想を材料として提示するところまでが役割である。

### 3. 確定値をrepoへ置き、根拠を併記する

**値だけを書かない。** LOG-081が要求する根拠は次の3つである。

- 算出クエリ(1で使ったもの)
- 観測期間
- **反実仮想の発火回数**

これを書かないと、次に見た人が「なぜこの値か」を再構成できず、**移行で解消した属人性がそのまま戻る。**

### 4. 配備する

```
ansible-playbook playbooks/grafana_provisioning.yml \
  --tags alerting -e alert_rules_predecessor_confirmed=true
```

**restartが発生する**(alerting YAMLは起動時読み込み。LOG-086)。muteは自動で張られる。実行時刻は `ubuntu_nightly` のmonnie処理時間帯と重ねない。

配備後の確認は `restart_and_verify.yml` が機械的に行う(`configuration_hash` 不変、4ルールのDB存在、ログのprovisioningエラー無し)。**通知本文まで確認するには実発火が必要**であり、これは待つしかない。

### 5. 現実が想定と違えば1へ戻る

実際の発火頻度という**新しいデータ**が手に入った状態で1をやり直す。

## UIでの試行錯誤について

**禁止しない。ただし正本にしない。**

- **探索は推奨する。** Grafana ExploreとAlert ruleのpreviewはread-onlyであり、データを見るには最適である。
- **provisioned化された4ルールはUIから編集できない**(`provenance = file`)。これは意図した状態である(LOG-078)。
- 試行のために非provisionedの複製ruleを作る場合は、**専用folderに置き、確定後に削除する。**
- **UIの複製から手作業で値を書き写す経路を既定にしない。** 転記は本案件で最も壊れやすい工程だった(移行では、Grafanaが出力したexportを1バイトも触らずに配ることで回避した)。

## 既知の摩擦 — 確認フラグ

**`alert_rules_predecessor_confirmed=true` は現在、守るものを失っている。**

このフラグは移行時にUID衝突を防ぐために置いた(旧UI管理ルールの削除確認)。移行完了後は4ルールが `provenance = file` になったため、**衝突は再発しえない。** それでも実装は毎回フラグを要求する。

**調整サイクルを初めて回すときに、次のどちらかを判断する。**

1. フラグを廃止し、`provenance_type` テーブルを見る実チェックへ置き換える(UI管理のルールが同UIDで存在するときだけ止める)。
2. フラグを残すが、要求条件を「初回のみ」へ絞る。

**放置すると「毎回フラグを打つ」が定着し、なぜ必要かを誰も説明できない儀式になる。** 経緯は `docs/ai/reviews/grafana_provisioning/2026-07-30_001_requirement.md` R8。

## 関連

- 規範: [`log_observability_policy.md`](../../policies/log_observability_policy.md) LOG-065(障害判断は人間の判断)、LOG-078〜LOG-089(配備方式)
- 設計判断: [ADR-007](../../adr/007-grafana-provisioning-as-code.md) 設計判断7(発火の説明可能性)・8(用語の分離)
- 案件記録: `docs/ai/reviews/grafana_provisioning/`
- 発火条件の正本: `roles/grafana_provisioning/files/alerting/unifi-switch-port-errors.yaml`
