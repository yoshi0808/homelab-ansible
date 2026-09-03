# Incident: 停止を防ぐために入れた `timeout` が、apt を無期限に停止させた

日付: 2026-09-03
状態: 解決済み(復旧完了、恒久対策も実施・本番実績あり)
対象: `roles/ubuntu_vm_full_upgrade/tasks/apply.yml`(monnie、Semaphoreジョブ #938)
種別: 動作不具合
原因分類: #設計考慮ミス

## 症状

月次 full-upgrade の apply が `Run apt full-upgrade` で停止し、**自力では二度と終わらない状態になった。**

- `timeout` と `apt-get` の**両方**がプロセス状態 `T`(停止)
- 子プロセス(`dpkg` / `dracut` / `update-initramfs`)は残っていない
- monnie のローカル journal は 08:10:06 を最後に無音、load は下降、ミラーへの通信なし
- **`timeout` に設定した3600秒は発火しない** — 停止中のプロセスは `SIGKILL` と `SIGCONT` 以外を処理しないため

## 原因

1. playbook は `become: true` で走るため、**Ansibleが制御端末(pty)を割り当てる**
2. **`timeout` は配下をまとめて kill するために新しいプロセスグループを作る**
3. そのグループは同じ端末を持つが**フォアグラウンドではない**(Ansibleのpythonが `S+` で前景を占める)
4. **バックグラウンドのプロセスグループが制御端末に触ると `SIGTTOU` / `SIGTTIN` で停止する。** `tcsetattr` 系の呼び出しは `tostop` の設定に関係なく必ず `SIGTTOU` を出す
5. `timeout` も同じグループなので一緒に止まり、自分のアラームを処理できない

## この Incident の形

**2026-08-22 の停止(conffile プロンプト)を防ぐために入れた `timeout` が、別の経路で同じ「無期限に止まる」を作った。**

**conffile の修正自体は成功している** — term.log にプロンプトは1つも出ておらず、`--force-confold` は効いていた。**塞いだ穴の隣に、塞ぐために使った道具が新しい穴を開けた。**

安全網として入れたものが、**その安全網自身の前提(タイマーが発火すること)を壊す**形で失敗した点が本質である。「必ず終わる」と記録に書いたが、**その保証はこの失敗モードを覆っていなかった。**

## 発見の経緯

Yoshinobu が「5分経過」と報告し、Coordinator が停止か進行かを判定しようとした。

- **Loki 経由の観測では判別できなかった** — 更新対象に `alloy` が含まれるため、「ログが来ない」が「止まっている」と「ログ送出が止まっている」の両方を意味した
- **monnie のローカル journal を直接読む read-only チェックで、alloy を経由しない観測が取れた**(08:10:06 以降無音)。これで転送の問題は消えた
- **term.log は Operator の `ann` identity では読めなかった**(`root:adm 0640`)。OPREQ は NG で返り、**Yoshinobu が root で読んで**初めてプロンプトが無いことが分かった
- 決め手は `ps -o pgid,sid,tty,stat` の1行だった。**プロセスグループと前景/背景の別を見るまで、原因は特定できなかった**

## 復旧

`kill -9` → `dpkg --configure -a`(**設定待ちは1つも無かった**)→ `loki` / `unpoller` の再起動で完了した。**適用は実質的に終わっており、止まっていたのは後片付けだけだった。**
実測は `docs/ai/reviews/ubuntu_vm_apply_timeout_sigttou/2026-09-03_002_recovery_result.md`。

## 恒久対策

apt 実行を `setsid -w` の内側へ移し、`timeout` は既定モードのまま使う(commit `41a55ae`)。制御端末を持たせないので job control signal 自体が発生せず、`timeout` は既定モードのままなのでプロセスグループごと閉じられる。**`--foreground` は独立レビューで否決された** — 停止は消えるが子孫が残り、上限が実効しない。

**本番で3台が完走した** — quory #943(108秒)/ authy #944(88秒)/ ansy #945(116秒)。ただし**3台の apt が実際に端末へ触ったかは測っていないため、「修正が無ければ止まっていた」の証明ではない。** 機構の根拠は sandbox の実測である。

案件記録は `docs/ai/reviews/ubuntu_vm_apply_timeout_sigttou/`(closeout は `_005`、監査は `_006`)。

## 残る弱点

- **Operator は apt のログを読めない。** 本番で apt が止まったときに、運用側から中身を確かめる手段が無い
- **`timeout` を同じ形で使っている箇所は repo 内で1つだけ**だが、`become: true` + 長時間コマンドの組み合わせは他にもありうる
- **回帰テストはプロセス木側だけを見ている。** `setsid -w` を消して素の `timeout` に戻しても localhost では通るため、**この直接原因の再導入を機械では検出できない**
