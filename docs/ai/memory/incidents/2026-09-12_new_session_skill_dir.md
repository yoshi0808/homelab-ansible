# Incident: new-session が SKILL_DIR 未設定で起動失敗

日付: 2026-09-12
状態: 解決済み
対象: new-session.sh（Git管理外のローカル起動補助）
種別: 動作不具合
原因分類: #製造ミス #テスト不足

## 症状

monitor 有効化後、role-session.sh の必須変数チェックで終了し、tmux セッションを作成できない。

## 原因

呼び出し側がライブラリの必須変数 SKILL_DIR を設定していない。

## 修正内容

起動障害の小規模な緊急修正として Coordinator が直接対応する。既存の AGMSG パスから skill root を導出する。

## 確認方法

`bash -n new-session.sh` が成功。スクリプトから初期化と seat 検査ブロックを抽出し、SKILL_DIR の設定なしでは同じエラーを再現、修正後はライブラリ読み込みと homelab / homelab-ops の非空・同一 seat 検査が成功した。その後Yoshinobuが `./new-session.sh --reset` を実行し、Coordinator / Implementer / Reviewer / Auditorのtmux pane起動と各Claude RoleのREADY応答まで確認した。
