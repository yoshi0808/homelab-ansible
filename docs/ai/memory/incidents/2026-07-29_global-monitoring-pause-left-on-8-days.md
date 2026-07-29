# Incident: 自律復旧のglobal pauseが8日間解除されずに残っていた

日付: 2026-07-29
状態: 解決済み
対象: recovery_exec(`homelab-monitoring-pause` / `homelab-monitoring-resume`)、recovery_probe
種別: 動作不具合
原因分類: #運用考慮ミス #テスト不足

## 症状

2026-07-29、Slack経由のCodex調査(別案件のAC検証)の副産物として、`homelab-monitoring-status`が`PAUSED (all targets)`を返すことが判明した。**自律復旧のpull probe(authy / monnie / sophos-fw)が全targetでskipされ続けていた。**

pause flagの`stat`(quory、read-only):

```
File:   /var/lib/recovery-exec/workspace/monitoring-paused
size:   0（regular empty file）
Modify: 2026-07-21 18:49:31 +0900
Birth:  2026-07-21 18:49:31 +0900
```

Birth・Modify・Changeがすべて一致しており、**作成以来一度も触れられていない**。2026-07-21 18:49 JST から 2026-07-29 まで、**約8日間**にわたり自律復旧が無効だった。

Lokiの当日ログでも、06:05:29 / 06:06:29 / 06:07:14 と毎probeサイクルで `monitoring paused (global)` によるskipが記録されている。

**8日間、誰も気づかなかった。** この間に自律復旧の発火を要する事象が発生したかどうかは確認していない(残存リスクの項を参照)。

## 原因

**pauseを立てた作業の完了時に、resumeが実行されなかった。**

pause flagの作成時刻(18:49:31)の36分後、`e9ac523 change host name on recovery probe, make playbook catlog`(2026-07-21 19:25:21 JST)がcommitされている。この変更は `roles/recovery_probe/defaults/main.yml` の `recovery_probe_pve_host` を pve1 → pve2 へ向けるもので、pve1の平日日中シャットダウン運用に追随させるものだった。**同一サブシステムに対する作業の直前にpauseが立っている**ため、この作業のためのpauseであった可能性が高い。

ただし**これは時刻とサブシステムの相関に基づく推定であり、確証ではない**。pauseを立てた主体・目的を直接示す記録は残っていない(pause flagは空ファイルで、理由もTTLも保持しない)。

解除忘れが8日間検出されなかった構造的な理由は2つある。

1. **global pauseにTTLが無い。** 同じ系統の`homelab-mute-*`は1〜240分のTTLが必須で自動失効するが、`homelab-monitoring-pause`は明示的なresumeまで無期限に継続する(`AGENTS.md`: "stops **all** targets with **no TTL** (until an explicit resume)")。
2. **未解除を知らせる仕組みが無い。** pause中であることを定期的に通知する経路が存在せず、`homelab-monitoring-status`を誰かが能動的に叩かない限り分からない。

なお、**pause中も生きていた唯一の監視が外部到達性チェックだった**。`recovery-probe.py`の`external_reachable()`はpause判定の外側にあるため、2026-07-29 06:07の「外部到達性の回復」warningは通知された。皮肉なことに、その通知を調査する過程でpauseが発見された。

## 修正内容

pause自体は**解除で復旧する**(`homelab-monitoring-resume`がflagを削除し、次のprobeサイクル=最大60秒で反映される)。解除前に、再開時の復旧ラダー誤発火を避けるため対象の健全性を確認した。

- authy: `freeradius` / `sshd` とも active (running)
- monnie: `prometheus` / `grafana-server` / `loki` / `unpoller` すべて active (running)

構造的な再発防止(global pauseへのTTL付与、または未解除の定期通知)は**本Incidentでは実施していない**。`docs/ai/status.md` の Next へ起票した。この2つは設計判断を含むため、Incident対応として即断せず案件として扱う。

## 確認方法

- `homelab-monitoring-status` が `ACTIVE` を返すこと。
- 以降のprobeサイクルで、Lokiの `job=ubuntu-nodes, host=quory` に `monitoring paused (global)` によるskip記録が現れないこと。

## 残存リスク

- **8日間の空白期間中に自律復旧の発火を要する事象が発生していたかは未確認。追跡はクローズした**(2026-07-29 Yoshinobu判断)。Slack経由のログ調査経路(`recovery_io` → Codex → Loki)が同日に成立し、必要が生じた時点で随時遡れるようになったため、恒久の申し送りとして持たない。`docs/ai/reviews/slack_loki_investigation/` 参照。retentionは有効な削除設定が無いためデータ自体は残っている。
  - **遡るときに`recovery-probe`のログを見ても分からない**(2026-07-29訂正。本Incidentの初版はこれを確認手段として挙げていた)。`roles/recovery_probe/files/recovery-probe.py`のmainループはpause判定をprobeより**前**に置いて`continue`するため、pause中は`monitoring paused (global) — skip`しか残らず、**probe結果そのものが存在しない**。証跡が要るならmonnieのPrometheus(対象VMの`up`の欠落)や、authy / monnie / sophos自身のログなど、probe以外の系から取る。
- pauseを立てた主体・目的の特定は推定に留まる。pause flagが理由を保持しない設計である以上、記録から確定させることはできない。
