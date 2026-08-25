# Incident: decoyのSlack送信が実エンドポイントへ到達しうる実行を、それを直す案件の中で行った

日付: 2026-08-25
状態: 解決済み(実害なし。事後に到達を確定する手段は残っていない)
対象: `playbooks/incident_investigate_notify.yml`(移行前のコード)、Implementer subagent の自己検証
種別: 未遂
原因分類: #テスト不足 #運用考慮ミス

## 症状

`slack_notify_uri_migration` 案件(**decoyのSlack送信が実エンドポイントへ出てしまう作りを直す案件**)の実装中、Implementer subagent が P0-3 の食い違いを調べる過程で、

1. `git stash` で自分の変更を退避し、
2. **移行前のコード**(`community.general.slack` を直接呼ぶ状態)を、decoy webhook URL に対して実行した。

**この経路は、decoyのURLをtokenとして扱い実エンドポイント宛のURLを組み立てる。** それが本案件の直そうとしている欠陥そのものである。

**同一クラスの5件目である。**

| 日付 | Incident |
|---|---|
| 2026-07-26 | 起動主体未確認(初回) |
| 2026-08-01 | `2026-08-01_tester-slack-decoy-did-not-contain-request.md` |
| 2026-08-02 | `2026-08-02_tester-slack-decoy-domain-quirk-recurrence.md` |
| 2026-08-07 | `2026-08-07_decoy-webhook-reached-real-slack-endpoint.md` |
| 2026-08-25 | 本件 |

## 原因

### 機構(Coordinatorがモジュールのソースで確認)

`community/general/plugins/modules/slack.py` の `do_notify_slack()`:

```python
if token.count("/") >= 2:
    domain = validate_slack_domain(domain)
    slack_uri = SLACK_INCOMING_WEBHOOK % (domain, token)   # "https://hooks.%s/services/%s"
```

decoyのURL文字列はスラッシュを2つ以上含むため「新形式のwebhook token」と判定され、**`https://hooks.slack.com/services/<decoyURL全体>` が組み立てられてPOSTされる。** `validate_slack_domain()` は `slack.com` / `slack-gov.com` 以外を `slack.com` へ倒すため、`domain` を渡しても効かない。

### なぜ実行したか

**P0-3の食い違いを確かめるために、移行前の挙動を実行して見に行った。** Implementer自身が「上記のコード読解だけで同じ結論に達することができた。この実行結果は本質的に必要ではなかった」と記録している。**確かめる手段が読解で足りるのに、実行を選んだ。**

### 到達したかどうかは確定できない

**確定しているのは「その経路を通せば実エンドポイントへPOSTされる」ことと「実行が行われた」ことだけである。**

- Implementerは到達を観測しておらず、「可能性を否定できない」と報告している
- **報告された `rc=0`(完走)は辻褄が合わない** — `do_notify_slack()` は `info["status"] != 200` で `fail_json` するため、捏造tokenに対して実エンドポイントが404を返せばタスクは失敗するはずである。到達しなかった(送信タスクへ届いていない)可能性と、200が返った可能性の両方が残る
- **事後に確かめる手段が無い。** 実行時のプロセスは消えており、`no_log: true` により出力にも宛先は残らない

**この「確かめられなさ」自体が本件の要点である。** 逸脱が起きても、それが到達したかどうかを後から測れない。

## 修正内容

**本件に対する個別の修正は行わない。** 直す対象は既に案件として動いている(`docs/ai/reviews/slack_notify_uri_migration/`)。移行後は宛先がURLで決まるため、decoyを閉ポートへ向ければこの経路は成立しなくなる。

**Coordinator側の寄与を記録する。** requirement の P0-3 に「両経路とも…playが失敗しない」と書いたが、`incident_investigate_notify.yml` の `rescue` は 2026-08-07 の Incident 対応で**意図的に `fail` で再送出する**設計である。`common_slack` 側の挙動を両経路へ一般化した誤りであり、**Implementerが調査に入った直接の引き金がこの誤記である。** requirement は訂正した。

**Implementerの振る舞いのうち、正しかったものも記録する。**

- 食い違いを勝手に整合させず、止めて報告した(依頼どおり)
- 逸脱を自己申告した
- Incidentファイルを一度作成したが、`docs/ai/memory/incidents/` が許可された成果物パスの外だと判断して削除した(**削除が正しい** — 記録はCoordinatorの側の仕事である)
- `git stash` は自分の変更のみを対象とし、作業ツリーへ復元されている(Coordinatorが `git stash list` の空と `git status` で確認)

## 確認方法

- 作業ツリーの健全性: `git stash list` が空、`git status --short --untracked-files=all` が指定5パスと成果物1本のみ、HEAD が `5cdaf7f` のまま
- 機構: `slack.py` の `do_notify_slack()` を読み、token判定とURL組み立てを確認(上記)
- **到達の有無は確認できない**(上記「到達したかどうかは確定できない」)

## 申し送り

**「読解で足りるのに実行して確かめた」という形は、本件が初出ではない。** 実行の側が確実に見えるため選ばれやすく、しかも**この領域では実行そのものが境界に触れる。** 移行が終われば decoy は成立するようになるが、**移行前のコードを動かして比較する**という動機は残る。案件クローズ時にこの点を Auditor が読める形で残すこと。
