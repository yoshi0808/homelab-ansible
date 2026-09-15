# Incident: テンプレートのドリフト検査が毎日鳴り続ける(収束しないreconcile)

日付: 2026-09-15
状態: 解決済み
対象: `roles/semaphore_templates`(templateカタログ)と日次ドリフト検査
種別: 動作不具合
原因分類: #製造ミス

## 症状

日次ドリフト検査(00:40)が `DRIFT 2件` をSlackへ通知した。少なくとも2026-09-14と2026-09-15の2日連続である。

```
- [quory] semaphore_template SEMI-SAFE: Proxmox storage monthly
    期待: SEMI-SAFE: Proxmox storage monthly
    実際: SEMI-SAFE: Proxmox storage monthly
    Semaphore実物(id=59)がカタログ定義と食い違っている(UIでの手編集、または未反映の可能性)
```

**期待と実際に同じ文字列が出るため、通知だけを見てもどのフィールドが違うのか分からない。** 対象はid=59(Proxmox storage monthly)とid=60(Quory health monthly)の2つ。

`semaphore_templates_setup` を実行しても解消しない。applyのたびにtemplateを書き込み、翌日の検査がまた差分として報告する。

## 原因

**Semaphore APIは `survey_vars` のfalsyなフィールドを保存・返却しない。** カタログがそれを明示的に書いているため、書き込んでも読み返すと消えており、**カタログ定義と実物が原理的に一致しない。**

| | `*_report_id` のsurvey var |
|---|---|
| カタログ(repo) | `name` / `title` / **`required: false`** / **`default_value: ""`** |
| 実物(API、`semaphore-query template-list`で取得) | `name` / `title` のみ |

この2キーを書いているのは新しい2テンプレートだけで、古いエントリは書いていない。したがって鳴るのもこの2つだけだった。

**reconcileが「変更あり」と判定していることは実測で裏づけた** — ジョブ#1097(check)の出力で両templateが `~` として挙がり、`name` / `args` / `desc` は左右同一、`survey` の行だけが違っていた。

## 修正内容

カタログの当該2エントリから `required: false` と `default_value: ""` を削除した。**省略時の意味(必須でない・既定は空)は変わらない。** 同じ罠を次に踏まないよう、カタログ側へ理由をコメントで残した。

## 確認方法

`semaphore_templates_setup` をcheck modeで実行し、**id=59 / id=60 が `~`(変更あり)として挙がらないこと**、次の日次ドリフト検査で `semaphore_template` の2件が出ないことを確認する。

## 残る弱点

- **通知と検査結果が「どのフィールドが違うか」を運ばない。** 期待と実際にtemplate名を出すだけで、原因の特定には実物のAPI応答とカタログを手で突き合わせる必要があった。
- **比較そのものは、APIが落とすfalsyフィールドを正規化していない。** 今回は書く側を実物へ合わせて回避したが、**同じ形(欠落とfalseを区別せずに比較する)は残っている。** `docs/ai/status.md` にある「template の reconcile が `false` / `{}` を空配列へ畳む」と同じ家族であり、そちらの案件で扱う。
