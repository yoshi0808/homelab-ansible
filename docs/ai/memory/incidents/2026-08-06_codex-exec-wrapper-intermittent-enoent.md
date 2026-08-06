# Incident: ansy の recovery-io が二重リスナーになり、Slack 経由の Codex 呼び出しが断続的に失敗した

日付: 2026-08-06
状態: 解決済み
対象: roles/recovery_io(handlers / tasks)/ playbooks/recovery_io_setup.yml / ansy
種別: 動作不具合
原因分類: #製造ミス #テスト不足

## 症状

Slack の @mention から Codex を呼ぶ経路で、次が返る。

```
/usr/local/bin/codex-exec-wrapper: line 35: /usr/bin/codex: No such file or directory
```

- 2026-08-01 は成功していた
- 2026-08-06 に失敗を確認
- **同日、何の操作もせずに再び成功するようになった**

影響したのは Slack 復旧経路と一次調査(`incident_inspect` も `/usr/bin/codex` を絶対パスで持つ)。**どちらもイベント駆動のため、壊れている間もどこも赤くならない。** `failed` は 0 件のまま、`recovery-io.service` も active のままだった。

Proxmox パッチ分類(`scripts/codex-classify.sh`)は影響を受けない。こちらは `codex` を PATH で解決しており、`recovery-exec` の環境でも引けていた。**同じ Codex を呼ぶのに、絶対パス直書きの2経路だけが落ち、PATH 解決の1経路は無傷だった。**

## 原因

**ansy で recovery-io が起動しており、Slack のイベントを quory と奪い合っていた。**

1. `playbooks/recovery_io_setup.yml` は `hosts: dev_nodes:control_nodes` で、`dev_nodes` は ansy である
2. ansy は `recovery_io_service_enabled: false`(defaults)で、`Enable recovery-io service` タスクは正しく起動を避けていた
3. **しかし handler `Restart recovery-io` は `state: restarted` を `when: not ansible_check_mode` だけでガードしていた。** `recovery_io_service_enabled` を見ていない
4. **`systemctl restart` は disabled な unit も起動する。** `disabled` が抑えるのは boot 時の自動起動だけである
5. → env ファイル・unit・スクリプトが変わるたび、**ansy が本番トークンを持つ2つ目の Slack リスナーになっていた**
6. Socket Mode は同一 app token の複数接続を許し、イベントは**どちらか一方へ配られる**。だから症状は「たまに失敗する」形で出た
7. ansy には `/usr/bin/codex` が無かった(作成されたのは 2026-08-06 13:29)。wrapper だけは Jul 5 から配備済みだった。**だから ansy が取ったイベントだけが `line 35: /usr/bin/codex: No such file or directory` を返した**

**確定させた観測**: ansy の `recovery-io.service` を停止した直後、同じ @mention が quory で処理された(13:56:06 `Mention from`、13:56:07 `COMMAND=/usr/local/bin/codex-exec-wrapper`)。停止前の 13:43 の @mention では、Codex の応答が Slack へ返っているのに **quory の journal には1件も記録が無かった**。

### なぜ切り分けに時間がかかったか

**quory 側だけを見ていた。** 「wrapper が失敗した」というメッセージから、wrapper が動いているホストは quory だと決めつけ、quory 上で再現を試み続けた。次はすべて実測で否定したが、**どれも「quory は正常である」ことしか言っておらず、正しかった**。

否定した仮説を残す。同じ切り分けを繰り返さないためと、**この一覧が全部 PASS することが「別ホストを見ろ」という信号だった**ことの記録として。

| # | 仮説 | 否定した根拠 |
|---|---|---|
| 1 | codex が別パスへ移動した | `/usr/bin/codex` は実在。symlink 先の `codex.js` も実在(`command -v` が返る以上リンク切れではない) |
| 2 | node が消えた | `/usr/bin/node` 実在 |
| 3 | sudo の `secure_path` に node が無い | PATH に `/usr/bin` があり、`sudo -H -u recovery-exec /usr/bin/codex --version` が成功 |
| 4 | 2026-07-31 21:39 の codex 入れ替えが原因 | その後の 8/1 に成功している |
| 5 | 配備済み wrapper が repo と異なる | 35行目まで一致 |
| 6 | wrapper に不可視文字(CR 等) | テンプレートは LF のみ。非 ASCII はコメント中の `§` だけ |
| 7 | AppArmor が exec を拒否 | `dmesg` の DENIED は `dig` と `who` のみ |
| 8 | サービスの mount namespace で見えない | `nsenter -t <MainPID> -m` で入って成功 |
| 9 | systemd のハードニング一式 | User / Group / EnvironmentFile / ProtectSystem=strict / ProtectHome / PrivateTmp / PrivateDevices / RestrictSUIDSGID / LockPersonality / ProtectKernel* を全て与えた `systemd-run` の使い捨てユニットから wrapper を実行し成功 |

**この9件がすべて PASS したこと自体が「別のホストを見ろ」という信号だった。** どれも「quory は正常である」ことしか言っていない。

決め手になったのは、Slack へ返った文面 `調査を開始します...` が `roles/recovery_io/templates/recovery-io.py.j2:83` のものだと確認したうえで、**同時刻の quory の journal に該当が1件も無かった**ことである。「recovery-io が応答した。しかしそれは quory の recovery-io ではない」がそこで確定し、`pgrep` で ansy を見つけた。

**ホスト名を含まないエラーメッセージから、無意識に実行ホストを補完していた。**

## 修正内容

**① handler をガードする** — `roles/recovery_io/handlers/main.yml`

`Restart recovery-io` の `when` に `recovery_io_service_enabled | bool` を追加。無効なホストで handler が起動しなくなる。

**② 望ましい状態を明示する** — `roles/recovery_io/tasks/main.yml`

`Enable recovery-io service` の `state` を、無効側 `omit`(=状態を触らない)から `stopped` へ変更。**`omit` では一度起動してしまうと playbook から二度と止められない。** `stopped` なら次の配備で自己修復する。`deployment_drift_check` が既に ansy を `enabled: disabled` / `active: inactive` と期待しており、playbook 側をその期待に合わせる形でもある。

`recovery_probe` の同名 handler は `_running_before` を OR で足しているが、**recovery_io では意図的に足していない**。あちらは「動いているなら新コードを反映したい」だが、こちらは ansy で動いていること自体が事故であり、OR を足すと rogue インスタンスを生かしたまま再起動し続ける。

暫定対応として、ansy の `recovery-io.service` は 2026-08-06 に手動停止済み(`is-active: inactive`)。

## 確認方法

- ansy 停止直後に @mention し、**quory の journal に `Mention from` と `COMMAND=/usr/local/bin/codex-exec-wrapper` が出ること**を確認(13:56:06 / 13:56:07)。停止前の 13:43 の @mention では、Codex の応答が Slack へ返っているのに quory の journal に1件も記録が無かった
- `ansible-playbook --syntax-check playbooks/recovery_io_setup.yml` rc=0、`ansible-lint roles/recovery_io/` は production プロファイルで 0 failure / 0 warning
- 再配備後、ansy の `recovery-io.service` が `inactive` のままであること

### 同種を疑うときの判別手順

失敗した時刻を控え、`ssh quory-investigate "journal-unit recovery-io.service 30m"` を引く。`sudo` が呼び出しを1件ずつ journal へ残すため、次で切り分けられる。

- 該当時刻に `sudo[...] recovery-io : ... COMMAND=/usr/local/bin/codex-exec-wrapper` **がある** → quory 上で起きている。同じ窓に `_run_codex` の `codex exec rc=` も入るので、そこから追う
- **無い** → **quory 以外のリスナーが Slack のイベントを取っている**(二重リスナー)

**無い場合、犯人は自分たちのホストとは限らない。** 流出したトークンで第三者が Socket Mode へ接続しても同じ症状が出る。今回は ansy が犯人だったが、`pgrep` で自分のホストを掃いて見つからなければ、トークン側を疑うこと。

観測上の制約: `journal-unit` は `journalctl -n 300` 固定であり、再接続バーストが起きている間は窓を 24h にしても数分ぶんしか遡れない。**失敗直後に引くこと。**
