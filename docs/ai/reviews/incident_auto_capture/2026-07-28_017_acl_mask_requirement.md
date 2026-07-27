# 収集器がspoolを削除できない — requirement(Coordinator)

- 起票: 2026-07-28 Coordinator
- Tier: **3**
- 案件フォルダ: `docs/ai/reviews/incident_auto_capture/`
- 進捗・課題の記録先: 同フォルダ `progress.md`(`docs/ai/roles/techlead.md`「進捗・課題の記録」)

## Tier判定と根拠

**Tier 3。** 判定軸は `skills/delegation-tier/SKILL.md` の2軸。

| 軸 | 判定 |
|---|---|
| 実装の専門性 | **要る。** POSIX ACLのmaskと名前付きACEの相互作用、およびAnsibleの `file` / `ansible.posix.acl` モジュールが既存ACLへ与える副作用という、狭く踏み外しやすい領域 |
| 自己検証で見えない欠陥 | **ある。** 現に見えていなかった。収集器のrescueとcollection_errorsが失敗を吸収するため、症状はサービスのexit codeとjournalにしか出ず、W6の受入時点では検出できなかった |
| 対象範囲の選定を含むか | **含む。** 同じ欠陥クラスがリポジトリ内の他箇所にあるかの掃引が必要 |

破壊的操作は含まないが、3軸すべてが該当するためTier 3とする。

## 事実(一次記録: `2026-07-28_016_t1_production_observation_test_result.md`)

Testerが2026-07-28朝に本番quoryで読み取り専用観測して確認した事実。

- `_spool/1785185420-30cddc4d.json` が05:50に書かれて以降、**05:55〜06:45に5分毎・11回連続で同一レコードが再バンドル化**されている(`spool-1785185420-*` が11個、中身は同一)。
- 直接原因: 収集器の `os.remove()` が `[Errno 13] Permission denied` で失敗し続けている(`_runs/run-*.json` の `collection_errors` に11件同一内容で実測)。
- `getfacl` 実測: `_spool/` は `owner=yoshi group=homelab-ansible mode=0755`。ACLに `user:recovery-exec:rwx` を持つが、**`mask::r-x` が実効権限を `r-x` へ切り詰めている**(getfaclが `#effective:r-x` と明示)。
- `homelab-incident-capture.service` は05:45以降のすべてのサイクルで `status=2/INVALIDARGUMENT`(`EXIT_COLLECTION_ERRORS`)。**05:45より前は正常終了していた。**
- 情報欠落はない(重複バンドルの中身自体は正しい)。問題は運用ノイズとディスク圧迫。

**進行中の事象である。** 放置すると重複バンドルが約288件/日で増え、サービスは `failed` のまま運用される。

## Coordinatorの仮説(未検証 — 裏付けまたは反証はTech Leadの仕事)

**この節は参考情報であり、実装方針の指定ではない。** 誤っている可能性があるので、現物で確かめて反証してよい。

`roles/incident_capture/tasks/main.yml` の `_spool/` に対する `file` タスクは `mode: "0755"` を指定している。ACLを持つディレクトリではchmodのgroupビットがACL maskそのものになるため、`file` モジュールが実際にディレクトリを変更した回で mask が `r-x` へ落ちた可能性がある。後続の `acl` タスクは `user:recovery-exec:rwx` エントリが既に存在して一致するため changed=False となり、maskを戻さない。

兄の `reports/incidents/` は同じ `mode: "0755"` を持つがバンドル生成は成功しているため、mask が壊れていないと推測される。両者の差は **W6で `_spool/` 側にだけ `group: homelab-ansible` を追加した**ことで、それが `file` モジュールに実変更を起こさせた、という説明が成り立つ。

つまり **2026-07-27のW6修正が引き金だった可能性がある。** もしそうなら、これは「整合性のための小さな修正」が別レイヤの前提を壊した事例であり、記録する価値がある。

## 受入条件(何が達成されればよいか。どう作るかは指定しない)

| # | 条件 |
|---|---|
| AC1 | 収集器がspoolレコードを処理後に削除でき、同一レコードの重複バンドルが発生しない |
| AC2 | `homelab-incident-capture.service` が正常終了する(`failed` の解消) |
| AC3 | **`incident_capture` roleを再実行しても再発しない。** 一度直して終わりではなく、role実行のたびに壊れる構造なら構造の側を直す |
| AC4 | 既に生成された11件の重複バンドルと肥大した `_runs/` の後始末方針が決まり、実施されている |
| AC5 | **同じ欠陥クラスの掃引が済んでいる。** `file`(またはchmod相当)とACLを併用している箇所がリポジトリ内に他にないか確認し、結果を記録する。`roles/recovery_exec/` は候補 |
| AC6 | `incident-capture-collector.py` のdocstring(51-70行)が述べる前提「ディレクトリへの書込権があれば所有者に関係なくunlinkできる」は、maskの存在下で成立しなかった。**記述を現実に合わせる** |

## scope外

- Step 2(`claude -p` による第一報の起票)。
- R8(Semaphore外ジョブの保険)。
- シェルとPythonでstaged mode取得を二重実装している負債。
- Proxmox healthcheck(task 466)が `notify.yml` へ到達したかの切り分け(`2026-07-28_016` の未実施項目)。**関連するが別件**であり、この案件で混ぜない。

## 制約・安全境界

- **quoryへの適用はCoordinatorが承認する。** 判断根拠: 本件は Yoshinobu が承認済みの「障害の自動捕捉(Step 1)」の欠陥修正であり、対象はquory(Proxmox / Sophos / UniFi のいずれでもない)、かつACL/権限の変更は逆操作で戻せる(`docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」)。
- **`git commit` / `git push` はしない。** 常にYoshinobuが実施する。
- 実ホストでの検証はTesterのみが行う。Implementerは実ホストへ触れない。
- Tester観測時に判明した運用上の注意: quoryの `journalctl` と `homelab-semaphore-query` は接続identity `ann` 単独では権限不足で、`-b` が要る。

## Tech Leadへの依頼事項

1. 上の受入条件を満たす分解と、**単位ごとの見積もり**(subagent起動回数、Role別想定規模、工程配分と根拠)。
2. **単位ごとの「未決定の設計判断の一覧」**(何が決まっておらず、誰が決めるのか)。PMOはこれを数えるだけで判定できる必要がある。
3. 60分を超える単位を作らない(理想30分)。1単位に未決定を2つ以上残さない。
4. Implementer / Reviewer / Testerへの割り当て計画。起動はCoordinatorが行う。
5. 着手後は `progress.md` へチェックポイントごとに追記する。
