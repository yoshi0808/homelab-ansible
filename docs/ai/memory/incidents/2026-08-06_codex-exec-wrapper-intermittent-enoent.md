# Incident: Slack 経由の Codex 呼び出しが ENOENT で失敗した(自環境に原因なし)

日付: 2026-08-06
状態: 解決済み
対象: roles/recovery_exec(codex-exec-wrapper)/ recovery-io.service / quory
種別: 動作不具合
原因分類: 該当なし(自環境に原因が無いため。**月次のタグ集計に数えない**)

## 症状

Slack の @mention から Codex を呼ぶ経路で、次が返る。

```
/usr/local/bin/codex-exec-wrapper: line 35: /usr/bin/codex: No such file or directory
```

- 2026-08-01 は成功していた
- 2026-08-06 の朝に失敗を確認(これが発端)
- **同日、何の操作もせずに再び成功するようになった**

影響したのは Slack 復旧経路と一次調査(`incident_inspect` も `/usr/bin/codex` を絶対パスで持つ)。**どちらもイベント駆動のため、壊れている間もどこも赤くならない。** `failed` は 0 件、`recovery-io.service` も active のままだった。

Proxmox パッチ分類(`scripts/codex-classify.sh`)は影響を受けない。こちらは `codex` を PATH で解決しており、`recovery-exec` の環境でも引けていた。**同じ Codex を呼ぶのに、絶対パス直書きの2経路だけが落ち、PATH 解決の1経路は無傷だった。**

## 原因

**自環境に原因は無いと判断した**(Yoshinobu、2026-08-06)。下記のとおり自環境側の要因は実測で網羅的に否定されており、症状は無操作で消えた。

**具体的な外部要因までは特定していない。** 特定できていないことを理由に開いたままにしない、という判断である。

調査の途中で **ansy が二重の Slack リスナーになる欠陥**を発見し、当初これを原因と断定して本ファイルを `解決済み` にしたが、**それは誤りだった**(その欠陥自体は実在し、別Incidentで扱う — `2026-08-06_production-runtime-deployed-to-dev-host.md`)。**いま `解決済み` である理由は当時と別物である**ため、混同しないこと。

その欠陥が説明できるのは **13:43 の失敗1件だけ**である。そして**その ansy のインスタンスは、同日 11:57 と 13:17 にCoordinatorが指示した配備が起動させたもの**であり、調査の過程で作り出された事象である。

**発端(同日朝)の失敗を、この欠陥は説明しない。** 根拠は次の実測。

- ansy は **2026-08-01 12:16:31 に起動**している(`uptime -s`)。ansy の `recovery-io.service` は `disabled` であり、**disabled な unit は boot 時に上がらない**
- 8/1 の再起動から同日 11:51 まで、`Recovery io setup` は **1度も走っていない**(Semaphore task id 536〜592 を走査、該当0件。593 が当日の初回)
- したがって **今朝、ansy に Slack リスナーは存在しなかった**

### 実測で否定した仮説

いずれも quory を対象にした検証であり、**発端の失敗に対してはいまも有効な否定**である。

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

**この9件がすべて PASS したことを、Coordinator は「quory 以外を見ろ」という信号として読み、ansy を見つけた。** そこまでは正しい。**誤ったのは、見つけた欠陥を発端の説明として採用したこと**である。9件が否定しているのは「quory 側の静的な要因」であって、発端の失敗の原因が特定されたわけではない。

## 修正内容

**無し。** 自環境に直す対象が無い。

## 確認方法

同種を疑うときは、失敗した時刻を控えて `ssh quory-investigate "journal-unit recovery-io.service 30m"` を引く。`sudo` が呼び出しを1件ずつ journal へ残すため、

- 該当時刻に `sudo[...] recovery-io : ... COMMAND=/usr/local/bin/codex-exec-wrapper` **がある** → quory 上で起きている。同じ窓に `_run_codex` の `codex exec rc=` も入る
- **無い** → quory 以外が Slack のイベントを取っている

観測上の制約: `journal-unit` は `journalctl -n 300` 固定であり、再接続バーストが起きている間は窓を 24h にしても数分ぶんしか遡れない。**失敗直後に引くこと。**

**「無い」場合、犯人は自分たちのホストとは限らない。** 流出したトークンで第三者が Socket Mode へ接続しても同じ症状が出る。
