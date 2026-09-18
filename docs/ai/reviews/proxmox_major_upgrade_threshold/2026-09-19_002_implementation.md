# Implementation: Proxmox apply major-upgrade threshold

対象: `roles/proxmox_patch_apply_node/defaults/main.yml`。`proxmox_patch_apply_major_upgrade_threshold` を50から100へ変更した。直上のコメントは値や根拠を含まないため変更不要だった。

自己検証: role内で旧値50が残っていないこと、閾値をハードコードしたテスト・fixtureがないことを確認した。`tasks/main.yml`は変数を `length > threshold` で参照するため、100件以下はmajorに分類されず101件で分類される。removeは独立した `length > 0` 判定のままである。未解決事項: なし。

追加実装: `roles/proxmox_patch_dryrun/tasks/apply_forecast.yml` がapply roleのdefaultから閾値を読み、dry-runのmajor判定、remove、各nodeの`node_summaries[*].update_count`を用いて翌朝の自動適用を見送る理由だけを通知本文へ追記する。予告は`_final_status`、終了コード、Slackのchannel/statusを変更しない。

自己検証: `/tmp/proxmox_apply_forecast_fixture.yml`で実taskをroleとして読み込み、100件/101件のnode差、警告なしの単一node、removeがある単一nodeを検証した。101件側だけに警告が出ること、100件の自動適用入力では通知本文が不変なこと、removeでは警告が出ること、各ケースで`_final_status`が不変なことを確認した。未解決事項: なし。

差し戻し修正: 全体を止めるdry-run major/removeの理由とnode別件数超過を通知で分離した。node別予告は翌朝の再dry-runと適用順に依存する見込みとして表現し、他nodeの適用範囲を断定しない。ローカルfixtureでnode件数超過が全体停止を述べないこと、warningなしの本文不変、removeの全体停止表現を再確認した。閾値取得、removeの判定単位、`_final_status`、終了コード、通知経路は変更していない。
