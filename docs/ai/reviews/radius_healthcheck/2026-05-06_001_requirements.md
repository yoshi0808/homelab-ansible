# radius_healthcheck 要求仕様

## 目的
authy.internal 上の FreeRADIUS 3.2.8 が正常に稼働しているかを確認する。

## 対象
- ホスト: authy.internal
- グループ: radius_servers

## 確認項目
- freeradius サービスが active か
- 1812/udp がListenしているか
- 1813/udp がListenしているか
- journalの直近エラー（1時間以内のERROR/FATAL）
- FreeRADIUSバージョン（情報収集のみ）
- chrony の同期状態（chronyc tracking で確認）

## 制約
- 変更操作なし（read only）
- restart / reload / reboot しない
- レポートは reports/radius-health/ に保存

## 初回除外（将来拡張）
- radtest による疎通確認
- 証明書ディレクトリ確認
- 設定ファイル構文チェック

## 前提
- core.md のルールに従う
- shell は収集とJSON整形のみ、判断はAnsible側
