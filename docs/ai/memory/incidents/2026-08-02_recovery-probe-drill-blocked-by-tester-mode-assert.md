# Incident: recovery-probe の drill が、渡した `tester_mode=true` 自身のassertで落ちる

日付: 2026-08-02
状態: 解決済み
対象: `roles/recovery_probe/files/recovery-probe.py`、`playbooks/recovery_vm_reboot.yml`(および同じassertを持つ27本)
種別: 動作不具合

## 症状

`recovery-probe` の drill(`state_dir/drill/<target>` を置いて強制発火させる訓練モード)は、ラダー実行時に `-e tester_mode=true` を付けて対象playbookを呼ぶ。

- `roles/recovery_probe/files/recovery-probe.py:292` — `extra = [f"target={target}"] + (["tester_mode=true"] if drill else [])`
- `roles/recovery_probe/files/recovery-probe.py:375` — `run_playbook(cfg, "recovery_vm_reboot.yml", extra)`

一方 `playbooks/recovery_vm_reboot.yml:74-80` は、**`tester_mode=true` が渡されたら停止する**assertを持つ(`that: not (tester_mode | default(false) | bool)`、fail_msg「This playbook no longer supports -e tester_mode=true. Re-run with --check instead」)。

したがって drill は、ラダー本体に到達せずこのassertで落ちる。にもかかわらず `recovery-probe.py:377-382` は結果を **status `ok`** の「drill 完了」通知として送り、rcを本文の文字列に埋めるだけである。**drillは成功した形で報告されるが、vm_reboot経路を一切検証していない。**

drillが到達している範囲は、強制発火・flapping判定・pveノード選定・`pvesh` によるVM状態確証まで。ラダーの実行そのものは未検証のまま残る。

同じassertは `recovery_service_restart.yml` / `recovery_ha_failover.yml` を含む28本のplaybookが持つため、ラダーの他の段も同様である。

原因分類: #テスト不足

## 原因

**移行漏れ。** drill は `740f8fe`(2026-07-02)で入り `-e tester_mode=true` を渡す設計だった。`f925905`(2026-07-08、`Replace tester_mode/tester_gate with native ansible_check_mode`)がその変数を拒否するassertを入れたが、**`recovery-probe.py` の drill 経路は移行対象から漏れた**。

壊れたまま約4週間気づかれなかったのは、drill通知が **rcによらず `status: ok`** を送り、rcを本文の文字列に埋めるだけだったためである。**失敗が失敗として観測できない作りだった**ことが、移行漏れそのものより長く効いた。

背景として `tester_mode` は現在3つの異なる意味を同時に持っている。

| 場所 | 意味 |
|---|---|
| `docs/ai/policies/ansible_test_safety_policy.md` TS-003 | 「廃止済み」 |
| 28本のplaybookのassert | 渡されたら**停止する**(禁止フラグ) |
| `roles/common_slack/tasks/notify.yml:28-45` | 通知抑止フラグとして**今も有効** |
| `inventories/homelab/group_vars/all.yml:3-5` | 「実変更・外部副作用ゼロを保証する不変条件フラグ。tester は `-e tester_mode=true` で上書きする」= 旧方針のまま |

## 修正内容

**probe drill機構ごと削除した**(2026-08-02 Yoshinobu決定)。`--check` へ移して残す案は採らなかった。「何も検証していないのに成功と報告する仕組み」は無いより悪く、4週間気づかれなかったこと自体が依存されていない証拠でもあるため。

削除したのは `roles/recovery_probe/files/recovery-probe.py` の drill 関連一式と、`roles/recovery_probe/tasks/main.yml` が作る `/var/lib/homelab-recovery/probe/drill` ディレクトリ。`recovery_push` の drill は別物であり触れていない。案件記録は `docs/ai/reviews/tester_mode_full_removal/`。

**代償として、probe → pveノード選定 → `pvesh` 確証 → ラダー起動 という配線を訓練する経路が無くなった。** 代わりの検証方法は別途決める(`docs/ai/status.md` Next)。

## 確認方法

- assertの挙動は、`localhost` + `connection: local` の使い捨てplaybookに同じassertだけを写して `-e tester_mode=true` で実行し、**rc=2 で失敗する**ことを確認した(検証後削除)。
- 削除後は、Testerが `grep -ni drill` で不在を、`py_compile` で構文を、`fire_ladder()` をdecoyのstub越しに呼んで通常経路(running→reboot、stopped→start)が壊れていないことを確認した(`docs/ai/reviews/tester_mode_full_removal/2026-08-02_006_test_result.md` AC4 / AC7)。
- **drill自体を回した観測は最後まで無い。** 症状の判定は静的読解とassert単体の再現による。過去にdrillが成功した記録があるかも未確認のままである。
