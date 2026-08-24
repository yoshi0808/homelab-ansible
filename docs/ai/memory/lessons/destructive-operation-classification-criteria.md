# playbookをrisk-accepted/check-mode-nativeに分類する基準

Policy `docs/ai/policies/ansible_test_safety_policy.md`「risk-accepted の許可条件」へ昇格済み(2026-08-25の月次Knowledge振り返りで、既に移送されていたことを確認して縮約した)。**実行コストを分類理由にしない**という判断もそちらが持つ。

基準が決まったのは、tester_mode廃止・`ansible_check_mode`移行のときの `proxmox_backup_restore_verify.yml` の分類判断。「実際のqmrestoreは重い」という実行コストを理由にcheck-mode-nativeへ倒す案が出たが、**このplaybookの存在意義そのものがリストアの実地検証であり、本体を省いたテストには意味がない**として却下された経緯がある。
