# test_result: Phase 3 quory側 受入条件検証

日付: 2026-08-03 (JST)
対象: `roles/dev_investigate`(quoryへ配備済み)、`roles/recovery_exec/files/{incident-bundle-helper,recovery-reports-helper}`
基準: `2026-08-03_008_phase3_check_catalog.md`(D5承認済み)、`2026-08-02_001_requirement.md` §9
検証者: Tester
検証範囲: **quory側のみ**。class G(authy/monnie)・class P(pve1/pve2)は未配備のため対象外。

## 実行環境・手段

- `ssh quory-investigate '<check>'`(`~/.ssh/config` の forced-command dispatch経路。`dev-investigate` ユーザー、`~/.ssh/id_claude_investigate_quory`)— これがClaude Code側の実経路そのもの。
- `ssh quory '<read-only command>'`(`ann` 鍵。quoryは非保護ホストのため状態を変えない確認として直接読取に使用。AC19の原本突合に使用)。
- 実行コマンドと生出力は `/tmp/claude-1000/-home-yoshi-homelab-ansible/15e32143-f25b-4572-9e96-6267ce11e96c/scratchpad/test_log.txt` および同ディレクトリの `dispatch_*` / `orig_*` ファイルへ記録(セッション終了後に失われるtmpのため、以下に実測を転記する)。
- quory上のファイル・ユーザー・unitへの書込は一切行っていない(`cat`/`sha256sum`/`journalctl`/`systemctl status`/`systemctl cat`/`df`/`free`/`uptime`/`ip`/`ss`のみを実行)。

## 判定一覧

| AC | 判定 | 根拠 |
|---|---|---|
| AC8 | **PASS** | 未許可文字列(`this-is-not-a-check`、`rm -rf /` 等)を送るとすべて `denied: unknown command '<token>'` で非ゼロ終了。コマンドは実行されない |
| AC9 | **PASS** | カタログ§0 I-1列挙(`pvesh create/set/delete`、`systemctl start/stop/restart/enable/disable`、`qm start/stop`、リダイレクト、`tee`、`rm`、`mv`、`cp`、`eval`)を19パターンで実行し**全件denied**。有効checkの操作(operand)経由でのリダイレクト・パイプ・セミコロン混入も試行し、すべて `too many parameters` / `invalid parameter count` / `invalid <field>` でdeniedとなり実行前に止まることを確認 |
| AC10 | **判定不能(代替確認でPASS相当)** | quoryにCodex用鍵が存在せず鍵2本での出力一致は構成上とれない(想定どおり)。代替として、Q1〜Q7・Q11の各armが `exec` するヘルパー実体を確認: `bundle-show`/`investigation-*` → `/usr/local/sbin/incident-bundle-helper`(Codex向け `homelab-incident-bundle` も同一バイナリへ `exec`)、`report-*` → `/usr/local/sbin/recovery-reports-helper`(Codex向け `homelab-reports` も同一バイナリへ `exec`)、`semaphore-query` → `/usr/local/bin/homelab-semaphore-query`(`incident_inspect` role配備のCodex用AGENTS.md/codex-config.tomlが同名を許可リストに持つ、同一バイナリ)。Q-C(8種)はquory dispatchとauthy/monnie用 `recovery-investigate-dispatch.sh.j2` を抽出diffし、arity guard行の有無を除き実行コマンド文字列(`systemctl --failed --no-pager` 等8本)が完全一致することを確認。**呼び出し元で分岐する実装は見当たらなかった**が、鍵2本の実出力比較というAC文言どおりの検証は構成上不可能であることを明記する |
| AC19 | **PASS** | `bundle-list`(55件)と `investigation-list` の積集合から `semaphore-473` を選び、`bundle-show summary.json` → `bundle-show semaphore-log.log` → `investigation-show md` の3ファイルをdispatch経由で取得し、`ssh quory` で読んだ原本(`reports/incidents/semaphore-473/{summary.json,semaphore-log.log}`、`reports/incidents/_investigations/semaphore-473.md`)と `diff` で完全一致を確認(3ファイルともbyte単位で差分なし) |
| AC20 | **PASS** | `../` traversal、`semaphore-abc`、絶対パス(`/etc/passwd`)、空文字列、`..`、セミコロン混入の17パターンを `bundle-show`/`investigation-show`/`report-show`/`deployed-hash`/`unit-cat`/`journal-unit` の全operand位置で試行し、**全件denied**(`invalid id`/`invalid file`/`invalid ext`/`invalid playbook`/`invalid filename`/`invalid name`/`invalid unit`)。バンドルディレクトリ外のファイルは1件も取得できなかった |
| R13b | **PASS** | `report-list recovery_investigations sandbox` でJSTタイムスタンプ名(`20260803_053711+0900.json` 等)が列挙され、`report-show recovery_investigations sandbox 20260803_053711+0900.json` で取得。`ssh quory` で読んだ原本と `diff` で完全一致 |

## 正経路の確認(カタログ§1の20 check)

20 checkすべてを実行し、正経路(有効operand)・負経路(無効operand/arity超過)の両方を通した。

| check | 正経路 | 負経路 |
|---|---|---|
| Q1 `bundle-list` | 55件のバンドルID列挙(`^semaphore-[0-9]{1,9}$` 一致) | 余分operandでdenied |
| Q2 `bundle-show` | 4種ファイル名すべて取得成功(AC19で実証) | id/file不正でdenied(AC20で実証) |
| Q3 `investigation-list` | ID列挙成功 | 余分operandでdenied |
| Q4 `investigation-show` | md/json取得成功 | id/ext不正でdenied |
| Q5 `report-playbooks` | 14playbook列挙 | 余分operandでdenied |
| Q6 `report-list` | `recovery_investigations`→`sandbox/`,`monnie/`、`sandbox`→ファイル一覧 | playbook/target形式不正でdenied |
| Q7 `report-show` | JSON取得成功(R13bで実証) | playbook/target/filename不正でdenied |
| Q-C 8種(`failed`/`disk`/`memory`/`load`/`network`/`ports`/`journal-system`/`dmesg`) | 全件出力確認(実データ) | 余分operandでdenied |
| Q8 `status` | 8unit分の`systemctl status`出力確認 | 余分operandでdenied |
| Q9 `journal-unit` | 有効unit×`1h`で出力取得 | 未列挙unit・不正window(`99h`)でdenied |
| Q10 `unit-cat` | `semaphore.service`のunit定義取得 | 未列挙unitでdenied(AC20側で実証) |
| Q11 `semaphore-query` | `recent-failed 3`で実データ3件取得 | 未列挙query・非数値nでdenied |
| Q12 `deployed-hash` | 8 name中 `recovery-probe`/`investigate-dispatch-quory`をsha256sum取得、`ssh quory`直読と一致確認 | 未列挙nameでdenied |

## 残存リスク

- **journal読取のグループ付与(M1)**: `2026-08-03_012_review_phase3.md` で指摘されたが、`2026-08-03_008_phase3_check_catalog.md` §1冒頭の表で「2026-08-03、独立レビューの指摘(M1)を受けてYoshinobuが全4件を承認し、ここへ明記した」と記録されており、**カタログへの追記という形で既に解消済み**(Testerが新たに確認した事実ではなく、記録の突合で確認)。粒度がenumより粗い(全journal読取)ことはカタログ自身が明記しており、forced commandが唯一の授権境界である前提の上でYoshinobuが受容済み。
- **`bundle-grep`(横断検索)は未実装**: カタログ・requirementとも初期リリースから意図的に除外(R14c)。今回のテストでも存在しないことを確認した(case文に該当armなし、`bundle-list`/`bundle-show`/`investigation-list`/`investigation-show`の4本のみ)。`incident_sync` 退役後に横断検索が必要になった場合は別途起票が要る(リスク11、AC19は個別ファイル取得の範囲でPASS)。
- **AC10は構成上「同一出力の実測比較」ができない**: quoryにCodex鍵が存在しないため。代替確認(ヘルパー実体の共有・Q-Cの文字列一致)は静的一致を示すのみで、実行時の権限差(dev-investigateとrecovery-exec/Codex sandboxのUID・ACLの違い)による出力差の可能性までは潰していない。将来Codexがquory上で同一チェックを実行した実績が取れれば、より強い確認になる。
- **`deployed-hash` の8 nameのうち実測したのは2件**(`recovery-probe`、`investigate-dispatch-quory`)。残り6件(`incident-capture-collector`/`incident-investigate`/`recovery-push-dispatch`/`reports-helper`/`bundle-helper`/`semaphore-query`)はcase文のenum一致とpath存在は確認したが、`ssh quory`側との値突合は行っていない。負経路(未列挙name)はAC20で確認済み。

## 今回確認できなかったこと(範囲外)

- **class G(authy/monnie)・class P(pve1/pve2)への配備確認・AC実行**: 未配備のため実施していない。requirement上も本タスクの範囲外(Yoshinobuの作業として残存)。
- **Q-CがQ-CをQ-Cへ委譲する構造上、authy/monnie側のQ-C実出力とquory側Q-C実出力の値そのもの(disk使用率等)を比較する意味は無い**(ホストが異なるため値は一致しない前提)ので、AC10の代替確認はコマンド文字列の一致のみで判断した。
- **`incident_sync` の退役作業そのもの**: 依頼文の範囲外どおり、AC19/AC20の結果を待つ次工程であり本結果には含めない。

## 到達してはいけない状態への抵触

- quory上のファイル・ユーザー・unitの状態変更: なし(全コマンドがread-only語彙のみ)。
- 保護対象ホスト(pve1/pve2/authy/sophos-fw/UniFi)への到達: なし。
- 本番Slackへの通知: なし(通知経路を持つコマンドを一切実行していない)。
- リポジトリ内ファイルの変更: 本ファイル以外の変更なし。
