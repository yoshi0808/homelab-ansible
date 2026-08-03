# 配備と実機での稼働確認

実施日: 2026-08-03 / 配備の実行: Yoshinobu(Semaphore / ansible-playbook)/ 確認: Coordinator(ansyから `quory-investigate` dispatch 経由)

**この案件で実ホストに触れた記録はこのファイルだけである。** `002` `003` `004` はいずれも `/tmp` のdecoyと静的検証に閉じており、`004` §3 は明示的に「実ホストへは触れていない」と書いている。**その記述は当時の事実として正しく、書き換えない。**

## 1. 配備の手順(実際に行われた順)

| # | 実施 | 内容 |
|---|---|---|
| 1 | Yoshinobu | quoryで `git pull --ff-only`(手作業。**この案件が自動化しようとしている当のものなので、初回だけは手で行う必要があった**) |
| 2 | Yoshinobu | `playbooks/worktree_sync_setup.yml` を実行 |
| 3 | Coordinator | timerの存在を確認 → **`worktree-sync.timer` が `enabled`、`worktree-sync.service` が `static`** |
| 4 | Coordinator | `journal-unit worktree-sync.service` が **拒否されることを発見**(dispatchのunit許可リストに無い)。`c9d64b8` で許可リストへ追加し push |
| 5 | Yoshinobu | `recovery_exec_setup.yml -l quory -e recovery_exec_setup_targets=false` → `dev_investigate_setup.yml -l quory` の順で実行 |

**手順4は配備の途中で見つかった欠落である。** 「配備したものを観測する手段」を配備物の一部として数えていなかった。Phase 4 の D6 が同じ理由で「必要なチェックは着手と同時に決める」としていたのを、この案件では踏襲できていなかった。**気づいたのが dispatch 再配備の直前だったため追加コストはゼロで済んだが、それは偶然である。**

## 2. 配備物の一致

`deployed-hash` で repo と quory の実物を突き合わせた(**説明ではなく現物のハッシュで確認**)。

| 配備物 | repo | quoryの実物 | 判定 |
|---|---|---|---|
| `recovery-investigate-dispatch-quory.sh` | `90f17069a6295847fe70ce1facb3d045c3cf0b189c288348c5e3c86c063df7a6` | 同一 | 一致 |
| `homelab-semaphore-query` | `b6ccef1c22a6ec6f71e593d154009c988b66cac077881eb93db4a2347953b4bb` | 同一 | 一致 |

**配備前は両方とも不一致だった**(dispatch `1a3baa86…` vs `13c4facd…`、query `b6ccef1c…` vs `6dc73712…`)。これは `docs/ai/status.md` が記録している「repoを直しても配備物は古いまま」というクラスそのもので、**`git pull` では配備物は更新されない**ことを実測で再確認したことになる。

## 3. timerの稼働(`journal-unit worktree-sync.service 1h`)

- **毎分 :04 に発火**。`AccuracySec=5s` が効いている。
- **観測した全周期が `Deactivated successfully`**(rc=0)。失敗ゼロ。
- 所要は通常 ~2秒、通知を伴う周期で ~5秒(CPU 2.8s / メモリ 114〜116MB peak)。
- 通知が走った周期では `reports/incidents/_spool/*.json` への書き込みが見える(`common_slack` の証跡取得)。**このパスは `.gitignore` の `reports/incidents/` で除外されるため、通知そのものが作業ツリーを汚して同期を止める、という循環は起きない。** 事前の読みどおりであることを実機で確認した。

## 4. 自動同期が働いたことの証明

`#info` に届いた2通(Yoshinobuがスクリーンショットで提示)。

| 時刻 | 内容 |
|---|---|
| 2026-08-03T18:10:08+09:00 | `68f40b40170e` → `4ede63bf1241` |
| 2026-08-03T18:14:08+09:00 | `4ede63bf1241` → `c9d64b86044c` |

**`c9d64b8` は 18:13 に push したものであり、その約1分後に quory が自分で取り込んでいる。** この間に手作業のpullは行っていない。したがって **timerによる自動同期が実際に成立した**。

時刻表記は `+09:00`(JST)であり、リポジトリの規約に合致している。

## 5. requirement の観測待ち4点の解消

| 観測待ちだったこと | 結果 | 何が証拠か |
|---|---|---|
| systemd配下で `git fetch` がGitHubへ通るか | **通った** | 2回のpullが成立していること |
| systemd配下でvaultが解けるか | **解けた** | Slackへ実際に届いたこと。**journalに残る「通知playbookが起動した」だけでは足りない** — `common_slack` は送信の前に証跡を取るため、spoolにレコードがあることは送信成功を意味しない |
| `semaphore.db` のスキーマが `task.status` のままか | **現行のまま** | スキーマが違えばクエリが失敗し、`running_count=1` にフォールバックして**見送っていたはず**。実際にはpullされている |
| timerが期待どおり回るか | 回っている | §3 |

あわせて `semaphore-query running 20` が `denied` にならず実行され、空を返すこと(=実行中ジョブなし)を確認した。

## 6. 確認できていないこと

- **異常系4経路(汚れたツリー / fetch失敗 / 履歴分岐 / 30分超の見送り)は、実機では一度も起きていない。** すべて `/tmp` のdecoyでのみ通っている(`004` §3)。
- **「Slackが鳴らない」を稼働の根拠にできない。** 異常系の通知はエッジ検出+1時間の抑止つきであり、**沈黙は「正常」と「抑止中」の両方を意味する**。一次情報は journal である。
- 1分ごとのfetch(1日1440回)がGitHub側の制限に触れないかは、初日の稼働が正常だったことしか言えていない。
