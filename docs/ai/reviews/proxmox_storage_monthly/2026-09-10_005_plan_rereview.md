## Code Review: 月次ストレージ点検 実装計画(再査読、004 Major #1への対応)

### Summary

004 Major #1(AC8のNotion側「検証時の通知抑止」欠落)は解消を確認した。対応範囲は「Notion公開」節冒頭2段落と検証ステップ2のみで、他節は前版と同一。

### Major Issues

なし(004指摘は解消)。

### 004 Major #1への対応確認

- `native check`または`skip_notifications=true`のいずれかで必ずNotionを抑止し、`slack_force_send`・`check`・`skip_notifications`はいずれのforce変数でも解除不可と明記された。AC8の「native check/通知抑止」両方を満たす。
- CLAUDECODE空のCodex実行では既存AIセッション判定が効かない限界を計画自身が明記し、検証時は`skip_notifications=true`を明示する運用で補っている(環境変数検出だけを安全根拠にしないという自己言及があり、隠れた抜け穴として残らない)。
- module側も`suppress=true`を既定にし`check_mode`ではtoken読取・HTTP・state更新前に戻る二重防御。抑止時は`publication=suppressed`と表示し成功扱いにしない。
- 検証ステップ2に、check/skip/AIセッション/Notion専用force全組合せでの抑止確認(token読取・HTTP呼出・state更新0件)と、他forceでの解除不可確認が追加され、実装前提のテスト網羅性も確保された。

### What Looks Good

- 005で確認した以外の全節(収集契約、判定、ローカル保存・並行性、検証1/3/4/5、AC2/AC3/AC5/AC7/AC9関連の設計)は004査読時から変更なく、004時点で確認済みの整合性は維持されている。

### 確認範囲

- 003計画の全文再読、004からの差分特定(Notion公開節・検証2のみ変更であることを確認)。
- 001要件AC8との突き合わせ。

### 未解決事項

なし。

### Verdict

Approve(Critical/Major無し)。
