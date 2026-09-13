# Quory Monthly Health Policy

本書はquory月次ヘルスレポートの観測、判定、保存、公開、NVMe取得ツール配備の許可・禁止・停止条件の正本である。実行主体の権限は`execution_boundary_policy.md`、Ansibleのテスト分類は`ansible_test_safety_policy.md`を正本とし、ここでは重複させない。

## 1. 目的

<!-- QHM-001 -->
quory自身の容量、メモリ、swap、NVMe健康情報を月次で確認可能にする。死活監視や自動修復ではない。JSONを機械比較の正本、MarkdownとNotionを人向けの記録、Slackを短報とする。

## 2. 対象と実行範囲

<!-- QHM-010 -->
観測対象はinventory上の`quory`だけとする。Semaphoreの実行コンテキストが実際にquoryを観測していることを初回配備で確認する。他ホストの観測、ディスクのself-test・scrub・trim・修復、reboot、容量整理をこの入口へ含めない。

<!-- QHM-011 -->
月次観測はread-only収集とcontroller側の保存・公開だけを行う。NVMe取得ツールが足りなければ、観測playbookは導入せず取得不能として報告する。パッケージ導入は別のquory限定setup入口で、必要な実機確認と本番実行判断を経る。

## 3. 対応するPlaybook

<!-- QHM-020 -->
`playbooks/quory_health_monthly.yml`を観測・再送の入口とする。ツール導入が必要な場合のsetup入口は観測から分離する。各playbookの`# tester-gate:`分類は当該ファイル先頭を正本とし、本書は分類を複製しない。

## 4. 判断軸

<!-- QHM-030 -->
ファイルシステムは種別、総量・使用量・空き、`df`自身の使用率を記録する。メモリはtotalとavailable、swapはtotalとusedを区別する。NVMeデバイスの存在と健康指標の取得成否を別にし、取得不能・未解釈・値欠損をゼロや正常に補完しない。観測結果と比較基準の出所をレポートから追跡できるようにする。

<!-- QHM-031 -->
健康判定(`OK`/`WARNING`/`CRITICAL`/`UNKNOWN`)とジョブの処理成否は別軸とする。健康上の異常だけなら保存・公開が完了したジョブを失敗にしない。取得不能、必須値の解釈不能、履歴破損、保存・Notion公開失敗は理由を示して非0終了し、全体`OK`に畳まない。Slackは既存`common_slack`のbest-effort契約に従い、ジョブrcから送信成功を推定しない。

<!-- QHM-032 -->
比較は保存済みの成功観測を基準とし、初回、比較元欠損・破損、デバイス交換、累積counter減少を区別する。重大事項は人向け本文と件数制限のある短報で先頭側に示し、重要な異常を「ほかN件」へ埋没させない。

## 5. ライフサイクル・処理フロー

<!-- QHM-040 -->
保存先は`reports_base_dir`配下のquory専用領域とし、JSONとMarkdownを同一report IDで照合できるようにする。失敗時も既に保存できた証跡を失わせない。保持削除は本roleの正規ファイルだけを対象とし、比較基準、未公開、状態不明の記録を保全する。

<!-- QHM-041 -->
NotionはProxmoxの「ストレージ月次点検」と別のquory専用親ページへ公開する。月単位の重複作成と古いreportへの巻戻しを避け、作成応答が不明な場合は無条件に再POSTしない。再送は保存済みreport IDを指定し、実ホストを再収集しない。Notion障害でローカルJSONを消さない。tokenは権限制限付きファイルからのみ読み、Git、引数、ログ、通知へ露出しない。

<!-- QHM-042 -->
最初は手動検証する。保存、実行先、Notion、Slackのreadbackと、Semaphoreおよびquory上の定期処理との時刻照合が終わるまで、月次scheduleを有効化しない。scheduleの日時とactive状態は実Semaphoreでreadbackする。

## 6. 通知方針

<!-- QHM-050 -->
通常実行のSlack短報は日本語で結論、対象、対応要否、report IDと正式記録への導線を示す。`--check`時は保存・保持削除・token読取・Notion・Slack送信・ホスト変更を行わない。`skip_notifications`時はSlackとNotionを共に抑止する。AIセッション検出やforce指定を設けても、`--check`と明示的抑止を解除してはならない。

## 7. 制約・禁止事項

<!-- QHM-060 -->
観測入口からパッケージ導入、self-test、修復、既存timer変更をしない。quory実ホストのツール、権限、デバイスをrestricted sessionの観測値から推定して固定しない。専用Notionページの親IDとIntegration権限を実測せず公開を開始しない。

## 8. 変更履歴

| 日付 | 内容 |
|---|---|
| 2026-09-13 | quory月次ヘルスレポートの実装前に新設。要求は`docs/ai/reviews/quory_health_monthly/2026-09-13_001_requirement.md`。 |
