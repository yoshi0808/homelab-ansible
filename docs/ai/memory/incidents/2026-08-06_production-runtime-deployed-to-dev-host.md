# Incident: 本番ランタイムが開発機へ配備され、ansy が二重の Slack リスナーになった

日付: 2026-08-06
状態: 調査中(repo 側の対象縮小が未了)
対象: playbooks/recovery_io_setup.yml ほか3本 / roles/recovery_io / ansy
種別: セキュリティ事故
原因分類: #要件定義ミス #運用考慮ミス

## 症状

2026-08-06、**ansy で `recovery-io`(Slack リスナー)が本番トークンを持って稼働していた。** quory のものと同一の Slack app token で Socket Mode に接続しており、イベントを奪い合っていた。

- 13:43 の @mention は **ansy が処理**し、`No such file or directory` を返した(ansy には当時 `/usr/bin/codex` が無く、`codex-exec-wrapper` だけが Jul 5 から置かれていた)。**quory の journal には該当が1件も無い**
- ansy を停止した直後、同じ @mention が quory で処理された(13:56:06 `Mention from`、13:56:07 `COMMAND=/usr/local/bin/codex-exec-wrapper`)

あわせて、**ansy の `/etc/recovery-io/recovery-io.env` に、当時有効な本番 Slack トークンが平文で置かれていた**(ディレクトリ mtime 13:17:35)。

## 原因

**本番ランタイムを開発機へ配る設計。**

1. `playbooks/recovery_io_setup.yml` は **`hosts: dev_nodes:control_nodes`**。`dev_nodes` は ansy である
2. Semaphore は quory で動くが、**適用先を決めるのは playbook の `hosts:` である。** ansy は `ansible_host: ansy.internal` で `ansible_connection: local` を持たないため、**quory から ansy へ SSH で入って role を適用する**
3. ansy が対象に入っている以上、ansy 向けに `recovery-io.env.j2` が描画される。**そのために vault が復号され、平文が ansy へ書かれる**
4. `recovery_io_service_enabled` は ansy で `false` であり、`Enable recovery-io service` タスクは起動を避けていた。**しかし handler `Restart recovery-io` は `state: restarted` を `when: not ansible_check_mode` だけでガードしていた**
5. **`systemctl restart` は disabled な unit も起動する**(`disabled` が抑えるのは boot 時の自動起動だけ)

**dev/prod boundary の Phase 1〜4 で閉じたのは「ansy → 本番」の向きだけである。「本番 → ansy」は開いたままだった。**

### Coordinator が引き金を3回引いた

**この事故は、トークン流出(`2026-08-06_slack-token-leak-via-environ-dump.md`)の対応中に、Coordinator が配備を指示して起こした。**

| 時刻 | 事実 |
|---|---|
| 11:51:50–11:52:08 | Coordinator の指示で task 593 |
| **11:52:06** | **ansy の `recovery-io.service` が書き換わる**(593 の実行窓の中)。この時点で「ansy も配備対象」は現物に出ていた |
| 11:56:52 | 同じく指示で task 594。env に差分 → handler 発火 |
| **13:17:35** | **ansy の `/etc/recovery-io/` が更新** — 新アプリの本番トークンが平文で着弾 |
| 13:17:37 | ansy の recovery-io が起動 |
| 13:43 | その ansy が @mention を処理 |
| 14:05 | 同じく指示で task 604 |

**Coordinator は、資格情報のローテーション手順を設計しておきながら、その資格情報がどこへ着地するかを一度も確認しなかった。** 配備を指示する前に読むべき最初の1行が `hosts:` だった。同一セッション中に2回この playbook をファイルとして開いており(vault 変数名の確認、handler の調査)、目に入る位置にありながら配備先を問わなかった。

**結果として、資格情報のローテーションが露出を広げた。** 流出したのは quory の環境変数だったが、新しい資格情報は開発機へ平文で置かれ、そこで本番のイベントを処理するサービスが動いた。

## 修正内容

**撤去(実施済み、2026-08-06)** — ansy 上で Yoshinobu が実行。

```
/etc/recovery-io              削除済(平文トークンを含んでいた)
/etc/systemd/system/recovery-io.service  削除済(unit は not-found)
/opt/recovery-io              削除済
/usr/local/bin/recovery-io    削除済
```

**多重防御(実施済み、commit `614016f`)** — `roles/recovery_io/handlers/main.yml` の `Restart recovery-io` に `recovery_io_service_enabled | bool` を追加し、`Enable recovery-io service` の無効側 `state` を `omit` から `stopped` へ変更した。**これは原因の修正ではない。** 入り込んだ後に止める仕掛けであり、根治は playbook の対象から `dev_nodes` を外すことである。

**未了 — repo 側の対象縮小。** 直さない限り、次の配備で撤去したものが平文トークンごと書き戻される。

```
recovery_io_setup.yml       hosts: dev_nodes:control_nodes
recovery_exec_setup.yml     hosts: dev_nodes:control_nodes
recovery_probe_setup.yml    hosts: dev_nodes:control_nodes
incident_inspect_setup.yml  hosts: dev_nodes:control_nodes
```

ansy には現に `codex-exec-wrapper` / `codex-investigate-wrapper` / `recovery-probe.py` が残っている(資格情報は含まない)。**「開発機に何が要るか」の線引きを伴うため、Coordinator の一存で外さない。** `docs/ai/status.md` の Next へ起こした。

## 確認方法

- ansy で上記4パスが存在しないこと、`systemctl is-enabled recovery-io.service` が `not-found` であること(確認済み)
- ansy 停止直後の @mention が quory で処理されること(13:56、確認済み)
- **未検証**: handler のガードは、task 604 では notify が飛んでおらず一度も評価されていない(quory が再起動されていないのがその証拠)。**配備物が実際に変わる次の実行が受入条件**。`docs/ai/status.md` の Watch に載せた
