# Incident: 月次ストレージ実行状態がworktree同期を停止

日付: 2026-09-11
状態: 解決済み
対象: proxmox_storage_monthly / worktree_sync
種別: 動作不具合
原因分類: #製造ミス #テスト不足 #運用考慮ミス

## 症状

quoryの22:18/23:18のSlack通知でdirty worktreeによりpull未実施。Yoshinobuのgit statusは未追跡reports/proxmox-storage-monthly/のみ、追跡ファイルのdiff statは空だった。

## 原因

既存.gitignoreはJSON/log/Markdownを除外するが、storage_files.pyが永続作成する.lockを除外していなかった。ansyのgit check-ignoreで.lockのみ非該当を確認。quoryの未追跡ファイル名の展開は未確認のため、実際の全内訳は未確定。

## 修正内容

専用runtimeディレクトリreports/proxmox-storage-monthly/を.gitignoreで除外する。比較基準・公開記録・ロックを削除せず、worktree_syncのdirty guardも変更しない。

## 確認方法

修正後git check-ignoreで.lock/JSON/Markdownが専用ディレクトリ規則に一致することを確認。配下の追跡済みファイルはゼロ。git diff --check実施。

同期はdirty guardで止まるため、quory管理者が当該ディレクトリのみを.git/info/excludeへ追加して記録を保全し、worktree-sync.serviceを起動。quoryでHEAD/origin/mainが修正commitに一致、git status出力なし、Result=success、ExecMainStatus=0を確認した。レポートは削除していない。
