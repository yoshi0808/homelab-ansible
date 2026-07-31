# implement: Round 2 バッチA — `check-mode-native` への変換

日付: 2026-07-31
requirement: `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md` §4 バッチA、§5 R1〜R6、§6 AC1〜AC5
対象: `playbooks/incident_capture_setup.yml`(role: `incident_capture`)、`playbooks/incident_investigate_setup.yml`(role: `incident_investigate`)、`playbooks/recovery_probe_setup.yml`(role: `recovery_probe`、および同playbookが呼ぶ`recovery_mute`のinclude_role呼び出し)

## 1. 変更ファイル

- `playbooks/incident_capture_setup.yml`
- `playbooks/incident_investigate_setup.yml`
- `playbooks/recovery_probe_setup.yml`
- `roles/incident_capture/tasks/main.yml`
- `roles/incident_investigate/tasks/main.yml`
- `roles/recovery_probe/tasks/main.yml`
- `roles/recovery_probe/handlers/main.yml`

`roles/recovery_mute/`(対象外role)は一切変更していない。`docs/ai/status.md`が`git status`上modifiedだが、これは本作業開始前からの既存差分であり(`git stash`で退避して確認済み)、本batchの変更ではない。

## 2. 設計判断(次バッチへのテンプレート)

### 2.1 診断task と 破壊的task の二分法

TS-014の文言どおり、**折衷を作らず二値で分ける**:

- **read-onlyな診断task**(結果を後続の`assert`/`set_fact`が消費する)→ `check_mode: false`。対象3roleでは既存の3箇所(`recovery_probe/tasks/main.yml`の`Check whether recovery-probe is already running`と`Collect daemon start time and deployed file mtimes`)が該当し、いずれも変更前から正しく付与済みだった(R5は既に充足)。新規に追加が必要な診断taskは無かった(incident_capture/incident_investigateには`command`/`shell`/`uri`が存在しない)。
- **破壊的task**(host状態を実際に変える)→ **モジュールがネイティブにcheck_modeへ対応しているか否かによらず**、一律`when: not ansible_check_mode`(既存の`when`があれば追加条件としてマージ)+ `tags: [destructive]`を付ける。

### 2.2 「ネイティブsimulateに任せる」を採らなかった理由

`file`/`template`/`copy`/`apt`/`systemd`/`ansible.posix.acl`はいずれも`ansible-doc`で`check_mode: support: full`(`acl`はモジュールソース`supports_check_mode=True`)であり、理論上は`when:`を付けずとも`--check`下で安全にsimulateされ`changed`だけ返す。既存の`playbooks/knowledge_review_timer.yml`→`roles/knowledge_review/tasks/install_timer.yml`はこの「ネイティブsimulateに任せ、`tags: [destructive]`だけ付ける」設計を採っている(`when: not ansible_check_mode`は本当に必要な箇所——simulateされたunitファイルが実際には存在しないため`systemd`のenable/startが失敗しうる箇所——にだけ付いている)。

今回はこれと違う設計を選んだ。理由:

1. **AC1が「破壊的taskは`skipped`に現れる」ことを明示的に要求している。** ネイティブsimulateに任せると`changed`(予測)として現れ、`skipped`にならない。要求文言に忠実に従うなら、全破壊的taskを`when:`で明示的にスキップさせる方が誤読の余地がない。
2. 対象3roleのACL/mode操作には、コメントに書かれている通り**ACL maskの巻き戻り事故(2026-07-28)**のような繊細な副作用履歴がある。ネイティブsimulateの`changed`予測がこの種の相互作用まで正しく予測するかは検証していない(実ホストでの`--diff`実測が要るが、本タスクでは対象playbookの実行そのものが禁止されているため確認できない)。明示的skipは「予測の正しさ」に依存せず安全側に倒せる。
3. 一律ルールの方が**次バッチが機械的に再現しやすい**(モジュールごとにネイティブsimulateの安全性を都度判定する必要がない)。

トレードオフとして、`--check`実行時の`PLAY RECAP`の`changed`は3playbookとも**常に0**になる(診断task・`assert`・`set_fact`はいずれも状態を変えないため)。「変更されるはずの件数」を`changed`の数値では示さず、`skipped`件数だけで示す設計である。AC1の「changedが...変更されるはずの件数を示す」との厳密な整合は、Reviewer/Coordinatorに確認してほしい未解決事項として3節に残す。

### 2.3 role外(scope外)の破壊的処理は呼び出し側で丸ごとゲートする

`recovery_probe_setup.yml`は`roles/recovery_mute`(対象外role)の`deploy_cli`タスクをincludeしている。roleファイル自体は変更できないため、playbook側の`include_role`task自体に`when: not ansible_check_mode`+`tags: [destructive]`を付け、**inclusion全体を1つの破壊的単位としてゲート**した。`recovery_mute`側に保存すべき診断taskが無い(`command creates:`+`copy`のみ)ことを確認した上での判断であり、もし将来そのroleに診断taskが増えるなら、この「呼び出し側で丸ごとゲート」は不適切になる(roleを直接編集できるバッチで個別に見直すべき)。

対して`recovery_probe`role自体(scope内)は、`include_role`側を無条件のまま(`when:`なし)にして、role内部の個々のtaskへ`when: not ansible_check_mode`を配った。理由: `recovery_probe`roleには`Assert recovery_probe_pve_hosts...`や`Check whether recovery-probe is already running`のような**`--check`でも本実行すべき診断task**があり、inclusion自体を丸ごとゲートすると診断taskまで消えてしまう(それは`risk-accepted`の停止と同じ「無」に戻ることになり、check-mode-nativeの意味が無くなる)。

**次バッチへの教訓:** role importをどのレベルでゲートするかは、そのroleに「`--check`でも走らせたい診断task」があるかどうかで決める。あれば個別task単位、無ければimport呼び出し単位で構わない。

### 2.4 handlerは通知元のゲートに依存せず、handler自身にも明示的なwhenを足す

`roles/recovery_probe/handlers/main.yml`の`Restart recovery-probe`は元々`check_mode: false`を単独で持っていた(常に実restartを強制)。通知元task(`Deploy probe config`等)を`when: not ansible_check_mode`でゲートした結果、`--check`下ではこれらのtaskが`changed`を報告しなくなり、`notify`は原理上発火しなくなる——が、**それだけに依存せず、handler自身のwhenにも`not ansible_check_mode`を足した**(`docs/ai/reviews/check_mode_semantics/2026-07-31_004_classification_audit.md`§2.12の指摘どおり)。スキルの落とし穴4(「handlerは通知元の`check_mode: false`を継承しない」)の裏返しとして、**通知元のゲートも継承されない**ため、handler側で独立に閉じる必要がある。

`incident_capture`/`incident_investigate`のhandler(`daemon_reload: true`のみ)はこの種の明示的`check_mode: false`を持たないため、同じ手当ては不要と判断し変更していない(通知元が全てゲート済みなので、原理上notifyされない)。

### 2.5 事前に見つけた「網羅性の穴」

依頼文が観測事実として挙げた既存の`ansible_check_mode`参照箇所は網羅的ではなかった。実際に見つけた穴:

- **`roles/recovery_probe/tasks/main.yml`の`Enable and start recovery-probe (production only)`**(変更前の`when: recovery_probe_service_enabled | bool`のみ)には`not ansible_check_mode`が無かった。`incident_capture`/`incident_investigate`の同種task(timerのenable+start)は既に`not ansible_check_mode`を持っていたのに対し、`recovery_probe`だけ欠けていた。今回追加した。
- **`Verify the running daemon is not older than the deployed files`ブロック**は非破壊的だが、check-mode下では「今回の配備が実際に行われていない」ことを踏まえて丸ごとskipすべきと判断した(`docs/ai/reviews/check_mode_semantics/2026-07-31_004_classification_audit.md`§2.12の推奨に従った)。既存の`when`条件に`not ansible_check_mode and (...)`をマージした。
- **handler `Restart recovery-probe`の`check_mode: false`**単独では`--check`下で誤って実restartを強制しうる潜在的な穴だった(2.4節)。

いずれも`docs/ai/reviews/check_mode_semantics/2026-07-31_004_classification_audit.md`§2.5・§2.7・§2.12が事前に指摘していた内容と一致することを確認した上で反映した(独自の再判定ではなく、既存監査結果の追認)。

## 3. R1〜R6充足状況

| # | 内容 | 充足 |
|---|---|---|
| R1 | ヘッダを`check-mode-native`へ変更し、TS-009条件1・条件2の両方に言及 | 3playbookとも実施。条件1(実害軽微)は満たすが条件2(本体操作省略に検証価値なし)は満たさない、という構成で明記した |
| R2 | Round1の`--check`停止assertを除去 | 3playbookとも`[migration] --check has no dry-run here...`assertを削除した |
| R3 | role importの`check_mode: false`カスケードを除去 | 3playbookとも除去。`recovery_probe_setup.yml`は`block: / check_mode: false`構造自体を解体し、2つの独立taskへ分けた |
| R4 | 破壊的task全てに`when: not ansible_check_mode`+`tags: [destructive]` | 3role全task・3playbookのinclude呼び出しに適用(2.1〜2.3節の判断基準どおり) |
| R5 | check_mode非対応moduleの診断taskに`check_mode: false`+理由コメント | 新規追加は無し。既存3箇所(recovery_probeのみ)が既に条件を満たしていることを確認した |
| R6 | 停止assert除去に伴う`skip_notifications`案内の除去 | 該当なし。3playbookの停止assertの`fail_msg`に`skip_notifications`への言及はそもそも無かった(`grep`で確認済み) |

## 4. 自己検証

- 3role全taskを通しで読み、`command`/`shell`/`uri`モジュールの有無を`grep`で確認した(`incident_capture`に2箇所、`recovery_probe`に1箇所、`incident_investigate`には無し)。全て既存のcheck_mode扱いを確認済み。
- `ansible-doc`および実際のモジュールソース(`ansible.posix.acl`)で`assert`/`set_fact`/`systemd`/`apt`/`file`/`copy`/`template`/`ansible.posix.acl`のcheck_mode対応を`support: full`と確認し、`command`の`creates:`は`support: partial`と確認した。
- 3playbookとも`ansible-playbook <playbook> --syntax-check`が通ることを確認した。
- `bash scripts/check-tester-gate.sh`が`OK (46 playbooks)`で通ることを確認した(AC4)。
- `grep -h "^# tester-gate: risk-accepted" playbooks/*.yml | wc -l`が17→14になったことを確認した(バッチA単体では3本減、最終目標の3本はB・C完了後)。
- **値を目視するだけで終えず、消費側まで通す検証**として、対象playbookそのものは実行禁止のため、`/tmp`のscratchpad上に構成の異なる代替playbook(`ansible_connection: local`、実host名なし)を2つ作り、実際に`ansible-playbook`を通常実行と`--check`実行の両方で走らせて確認した:
  1. `recovery_probe/handlers/main.yml`の`Restart recovery-probe`と同型の`when: not ansible_check_mode and (A or B)`という複合Jinja式が、通常実行では`ran`、`--check`では`skipping`になることを実測(意図どおり)。
  2. `include_role` + `when: not ansible_check_mode` + `tags: [destructive]`という組み合わせが、通常実行では対象roleのtaskを実行し、`--check`では**roleにincludeすら行わず**丸ごと`skipping`になることを実測(`recovery_mute`ゲートの前提が正しいことの確認)。
- 参照した全パス・行番号(`roles/incident_capture/tasks/main.yml`、`roles/incident_investigate/tasks/main.yml`、`roles/recovery_probe/tasks/main.yml`・`handlers/main.yml`、`docs/ai/reviews/check_mode_semantics/2026-07-31_004_classification_audit.md`§2.5・§2.7・§2.12)は実在を`grep`/`Read`で確認済み。

**行っていない検証(Testerの領域、AC1〜AC3):** 対象3playbookそのものを`--check`付き/無しで実行し、終了コード・`PLAY RECAP`・ホスト状態の前後比較を確認すること。契約上、対象playbookの実行(`--check`の有無を問わず)は禁止されているため、Implementerとしては行っていない。

## 5. 未解決事項

1. **AC1の「changedが変更されるはずの件数を示す」との厳密な整合。** 今回の設計(全破壊的taskを`when:`で明示的にスキップ)では、`--check`実行時の`changed`は3playbookとも常に0になり、「変更されるはずの件数」を`changed`の数値としては示さない(`skipped`件数でのみ示す)。これがAC1の意図と一致するかはCoordinator/Reviewerに確認してほしい。一致しない場合、2.2節で退けた「ネイティブsimulateに任せる」設計(`knowledge_review_timer`方式)への作り直しが必要になる。
2. **`recovery_mute`role自体の分類。** `recovery_mute`はbatchA/B/Cいずれの対象にも明示されていない。`recovery_probe_setup.yml`からのみ`deploy_cli`がincludeされる形で本バッチに登場したが、role自体のheader・他の呼び出し元(`roles/recovery_mute/tasks/set.yml`等)は今回一切見ていない。将来的にこのroleを直接check-mode-native化する場合、`recovery_probe_setup.yml`側の「呼び出し側で丸ごとゲート」は不要になる可能性がある。
3. **ACLモジュールのネイティブcheck_mode simulateの実測はしていない。** `ansible.posix.acl`が`supports_check_mode=True`であることはソースで確認したが、ACL mask絡みの複雑な既存状態に対して`--check`時の`changed`予測が正確かどうかは実ホストでしか確認できない(かつ対象playbook実行禁止のため確認していない)。今回の設計はこの予測精度に依存しない(丸ごとskip)ため実害は無いはずだが、判断の前提として記録しておく。

## 6. 差し戻し対応(2026-07-31 独立レビュー ラウンド2)

独立レビューで、`roles/recovery_probe/tasks/main.yml`の一連(config/daemon/unit配備→enable+start→freshness verify)がTS-015(相互依存する破壊的taskはblock単位でゲートする)に反し、個々のtaskへ`when: not ansible_check_mode`を分散して付けていた点を指摘された。以下、本節のみ追記する(§1〜5は書き直していない)。

### 6.1 相互依存の範囲をどう判定したか

レビュー指摘は「config/daemon/unitの配備 → enable+start → freshness verify」という括りを提示していたが、これは提案であり判定はこちらで行う指示だったため、現物(`roles/recovery_probe/tasks/main.yml`)を読み直して独自に確認した。

判定基準: **後続taskの正しさ・意味が、先行taskが実際に(simulateでなく)実行されたことに依存しているか**。依存していれば1つのnamed blockにまとめてblock単位でゲートする(TS-015、"reboot→post-reboot検証→報告"と同型)。依存しておらず、各taskが独立に冪等な作成・配備であれば、個々のtaskへ`when: not ansible_check_mode`を配る(TS-014)ままでよい。

この基準で読み直した結果:

- **`Deploy probe config` → `Deploy probe daemon` → `Deploy systemd unit` → `Enable and start recovery-probe` → `Flush handlers` → `Verify the running daemon is not older than the deployed files`** は1本の依存チェーンである。`Verify...`は「configファイル/daemon本体/unitファイルの実際のmtime」と「daemonの実際の起動時刻」を比較する検証であり、直前の配備・起動taskが本当に実行されていない限り無意味(`--check`下でこの検証だけ生かして配備側だけ止めると、配備されていない旧ファイルのmtimeと配備されていない旧daemonの起動時刻を比べる、という空虚な比較になる)。レビュー指摘の括りをそのまま採用し、1つのnamed block(`Deploy, activate, and verify recovery-probe`)にまとめ、block自体に`when: not ansible_check_mode`+`tags: [destructive]`を1回だけ付けた。
- **`Install dig (dnsutils) for DNS probe`・`Ensure config directory exists`・`Ensure probe state directories exist`** はレビュー指摘の括りに含まれておらず、読み直した結果もこれに同意した。理由: これらは互いに独立な冪等作成(パッケージ・ディレクトリ)であり、どれか1つが実行されなかったことが他のtaskの結果の意味を変えない。TS-015が指す「相互依存」ではないため、個々の`when: not ansible_check_mode`のまま据え置いた。
- **`incident_capture`/`incident_investigate`は変更していない。** 両roleの最終taskである「timerのenable+start」は、この一連の中で唯一の本番作用taskであり、**その後に結果を読み返して検証する後続task(freshness verify相当)が存在しない**。「配備→起動」の2段はあるが「配備→起動→検証」という3段目が無いため、TS-015が例示する"reboot→post-reboot検証→報告"の形には該当しないと判断した。個々のtaskへの`when: not ansible_check_mode`(TS-014)のままで一貫している。

### 6.2 次バッチへの規則(確定版)

3role通しての一貫した判定基準はこうなる: **「後続に、先行taskの実際の完了を前提とする検証・報告taskが続くか」を見る。続くなら一連をnamed block化しblock単位でゲートする(TS-015)。続かない(各taskが独立、または最後が単発の本番作用taskで終わる)なら個々のtaskへ`when:`を配る(TS-014)。** recovery_probeが前者、incident_capture/incident_investigateが後者に該当し、両パターンが3role中に共存すること自体は矛盾ではない——同じ判定基準を適用した結果として形が違う。

### 6.3 実装内容

`roles/recovery_probe/tasks/main.yml`の該当range(旧: `Deploy probe config`〜`Verify the running daemon...`の6taskが個別に`when: not ansible_check_mode`等を保持)を、1つのnamed block `Deploy, activate, and verify recovery-probe (destructive; TS-015 chain)` に統合した。

- block自体: `when: not ansible_check_mode` + `tags: [destructive]`。
- block内の各taskは、block conditionとのAND評価に依存し、個別に`not ansible_check_mode`を繰り返さない。`Enable and start recovery-probe`は`when: recovery_probe_service_enabled | bool`のみ、内側のネストblock`Verify the running daemon...`は`when: recovery_probe_service_enabled | bool or recovery_probe_running_before | default(false) | bool`のみに簡素化した(block/nested block/task の`when:`はAnsibleが自動でAND評価する——後述6.4で実測確認)。
- `roles/recovery_probe/handlers/main.yml`の`Restart recovery-probe`はこの変更の影響を受けない(notify元が全てblock内に収まったため、`--check`下でnotifyされない構造は変わらず、handler自身の`not ansible_check_mode`ゲートもそのまま有効)。

### 6.4 追加の自己検証

対象playbook自体は実行できないため、`/tmp`のscratchpad上に今回のblock構造そのもの(外側block `when: not ansible_check_mode` → `notify`付きtask → `enable+start`相当task → `meta: flush_handlers` → ネストしたverify block)を再現した decoy playbook(`ansible_connection: local`、実host名なし)を作り、通常実行と`--check`実行の両方で走らせた。

- 通常実行: 外側blockの全task(configデプロイ相当・enable+start相当)が実行され、`changed`によりhandlerが発火し、ネストしたverify blockも実行されることを確認した。
- `--check`実行: 外側blockの`when: not ansible_check_mode`により、config/enable+start/flush/ネストverifyの**全て**が`skipping`になり、handlerも発火しないことを確認した。これにより「block/nested block/task の`when:`が自動でAND評価される」という6.3の前提(ネストしたverify blockから`not ansible_check_mode`を除いても外側blockのconditionが効く)を実測で裏付けた。

### 6.5 機械チェックの再確認

- `ansible-playbook playbooks/recovery_probe_setup.yml --syntax-check` を再実行し、通ることを確認した。
- `bash scripts/check-tester-gate.sh` を再実行し、`OK (46 playbooks)`のままであることを確認した。
- `ansible-lint roles/recovery_probe/tasks/main.yml roles/recovery_probe/handlers/main.yml playbooks/recovery_probe_setup.yml` を実行し、fatalな指摘が無いことを確認した(既存のrisky-file-permissions系の指摘は`incident_capture`/`incident_investigate`側のみで、`recovery_probe`関連ファイルには無い)。

### 6.6 requirementの訂正について

差し戻し時に、requirement本体の2箇所訂正(AC1から「changedが変更予定件数を示す」の削除、§4バッチ分割への`incident_inspect_setup`追加)を通知された。前者は本記録§3の未解決事項1で指摘した点と整合し、後者はバッチBの範囲であり、いずれも本バッチAの実装物には変更を要さない。
