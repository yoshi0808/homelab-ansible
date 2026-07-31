# implement: risk-accepted 3本の marker drift 是正 + tester-gate-condition2 マーカー新設

日付: 2026-07-31(初回実装 + 同日の差し戻し対応)
依頼: Coordinatorからの依頼文(本implement記録が対応する唯一の入力。requirement.mdは別途起票されていない)。差し戻しはCoordinatorからのメッセージ(独立レビューのMajor 1件・Suggestion 2件、いずれもCoordinatorが是正と判断)。
根拠: `docs/ai/reviews/check_mode_semantics/2026-07-31_004_classification_audit.md`(棚卸し。risk-accepted維持3本の判定)
Policy: `docs/ai/policies/ansible_test_safety_policy.md` §2・§4・§5・§7(初回TS-005〜TS-035、差し戻しでTS-036追加)

## 対象パス(初回実装時点)

- `playbooks/cloudkey_cert_deploy.yml`
- `playbooks/proxmox_backup_restore_verify.yml`
- `playbooks/unifi_backup_fetch.yml`
- `scripts/check-tester-gate.sh`
- `docs/ai/policies/ansible_test_safety_policy.md`

停止assert・ゲートロジック(`pre_tasks`のassert本体、`check_mode: false`の位置)はいずれも変更していない。触れたのはヘッダのコメント文・新設マーカー行・lintスクリプトの検査ロジック・Policy本文のみ。**この境界は差し戻し対応(下記「差し戻し対応」節)で、Coordinatorの明示指示により`proxmox_backup_restore_verify.yml` Play 3への停止assert追加という形で1件だけ拡張された。** それ以外は初回実装のまま変更していない。

## (1) 3本のヘッダの marker drift 是正

3本とも「`--check`の有無にかかわらず常に本実行する」という、TS-030導入(2026-07-31)以前の記述をそのまま残していた。実態(3本とも`pre_tasks`の停止assertにより`--check`で止まる。停止する場所は`cloudkey_cert_deploy.yml`と`unifi_backup_fetch.yml`は自playの`pre_tasks`、`proxmox_backup_restore_verify.yml`はPlay2の`pre_tasks`で、Play3は`brv_restore_targets`グループがPlay2内でAssert後にしか登録されないため対象ホスト0件で自動的に空実行になる)に合わせ、「--checkを渡すとpre_tasksの停止assert(TS-030)により変更を一切行わずに停止する。--checkなしの通常実行では常に本実行する」という記述へ書き換えた。

`cloudkey_cert_deploy.yml`はさらに、旧文に「community.general.slackはcheck_mode対応モジュールで、素の--checkだと送信せずchangedだけ返して終わるため、通知だけ挙動が変わらないよう明示的に無効化している」という説明を含んでいた。これはTS-030導入前(--checkが最後まで到達しうる設計)の説明で、現在は--checkがpre_tasksで即座に止まるためSlack通知taskへ到達すること自体がなく、この説明は意味を失っていた。TS-031(通知のcheck-mode抑止判定はnotify.yml側が一元的に持つ)への参照に置き換えた。

## (2) `cloudkey_cert_deploy` の分類理由に条件2を書く — 現物確認結果

`roles/cloudkey_cert_deploy/tasks/issue.yml`と`tasks/deploy.yml`を読んで、棚卸しの判定「更新要否チェックを持たず常に新規発行し、`deploy.yml`は各stepの正しさが直前の実API呼び出しが実際に起きたことに依存する非冪等な`uri`連鎖である」を確認した。

- `issue.yml`: `cert_needs_renewal`のような要否判定taskは存在しない。openssl鍵生成・CSR作成・署名まで、実行するたびに無条件で新規のリーフ証明書を発行する(`cert_renew.yml`の`stat`/`shell`日数計算による要否判定とは構造が異なる)。
- `deploy.yml`: login → JWTからCSRF導出 → upload(`register: cloudkey_upload` → `cloudkey_new_id`/`cloudkey_new_fp`を後続taskが直接参照) → activate → `community.crypto.get_certificate`による**実TLSハンドシェイクでの被servedフィンガープリント検証**(upload時の`cloudkey_new_id`ではなく、実際に443番で応答してくる証明書をuntilループで再取得して照合) → 検証OKの場合のみ再フェッチしたリストから旧証明書を削除、という一直線の`uri`/`get_certificate`連鎖。upload/activateをスキップして"プレビュー"しても`cloudkey_new_id`が存在せず後続の検証・削除ロジックが成立しない。

棚卸しの判定は現物と一致していると判断した(合っていた)。ヘッダへ独立した1行`# tester-gate-condition2:`として明記した。

## (3) 条件2の言及を機械検査する

`scripts/check-tester-gate.sh`に、既存の停止assert検査ブロックの直後、`risk-accepted`判定の`if`の中へ追加のチェックを実装した。

```bash
if ! grep -Eq '^# tester-gate-condition2:[[:space:]]*[^[:space:]]' "$pb"; then
  echo "ERROR: playbooks/$(basename "$pb"): risk-accepted なのに '# tester-gate-condition2:' マーカー(理由が空でない1行)がありません"
  fail=1
fi
```

設計は依頼どおり「独立した1行`# tester-gate-condition2: <理由>`の存在」と「理由が空でないこと」のみを検査する形にした。正規表現は行頭`# tester-gate-condition2:`の後に空白文字以外が最低1文字続くことを要求し、行自体が無い場合と、行はあるが理由が空/空白のみの場合の両方を弾く。

**この検査の限界(「著者が条件2を述べたこと」の確認であり「その主張が正しいこと」の確認ではない)を、スクリプト冒頭のコメント・エラー時のガイダンス文・Policy(TS-035)の3箇所に明記した。**

## (4) Policy への反映

`docs/ai/policies/ansible_test_safety_policy.md`に2つのIDを新設した。

- **TS-034**(§2、TS-006の直後): `risk-accepted`が独立した1行`# tester-gate-condition2: <理由>`をヘッダに持つことを定める。マーカー形式の話なのでTS-006の並びに置いた。
- **TS-035**(§7、TS-019の直後): `scripts/check-tester-gate.sh`がこのマーカーの存在と非空を検査すること、およびその限界(主張の正しさは機械判定できず、レビュー工程または棚卸しが判定する)を定める。機械チェックの話なのでTS-019の並びに置いた。

§8変更履歴に1行追加した。

## 自己検証

### 両方向のlint検証(スクラッチディレクトリ、実装後に削除済み)

`/tmp/claude-1000/.../scratchpad/tester-gate-lint-check/`配下に`scripts/`+`playbooks/`構成の使い捨てディレクトリを作り、`scripts/check-tester-gate.sh`をコピーして走らせた(リポジトリ本体のファイルは一切壊していない)。

- **弾く方向**: `risk-accepted`だが`# tester-gate-condition2:`行が無いfixtureと、行はあるが理由が空(`# tester-gate-condition2:`のみ)のfixtureを同時に置いて実行 → 両方とも`ERROR: ... risk-accepted なのに '# tester-gate-condition2:' マーカー(理由が空でない1行)がありません`でrc=1。
- **通す方向**: `risk-accepted`+停止assert+非空の`# tester-gate-condition2:`を持つfixtureと、無関係の`safe-readonly`fixtureのみを別ディレクトリに置いて実行 → `[tester-gate-lint] OK (2 playbooks)`でrc=0。
- 実際に編集した3playbookのヘッダだけを抜き出して同様に独立実行 → `[tester-gate-lint] OK (3 playbooks)`でrc=0(本体側のscript実行結果と整合)。
- 検証後、スクラッチディレクトリは`rm -rf`で削除した。

### 現行46 playbookでの本体lint実行

```
$ bash scripts/check-tester-gate.sh
[tester-gate-lint] OK (46 playbooks)
```
rc=0。`ls playbooks/*.yml | wc -l`も46で一致。

### 3本の`--syntax-check`

```
ansible-playbook -i inventories/homelab/hosts.yml playbooks/cloudkey_cert_deploy.yml --syntax-check          → rc=0
ansible-playbook -i inventories/homelab/hosts.yml playbooks/proxmox_backup_restore_verify.yml --syntax-check → rc=0(brv_query_node/brv_restore_targets未定義グループのWARNINGのみ、動的add_host対象なので想定どおり)
ansible-playbook -i inventories/homelab/hosts.yml playbooks/unifi_backup_fetch.yml --syntax-check            → rc=0(unifi_backup_fetch_target未定義グループのWARNINGのみ、同上)
```

### ヘッダ記述と実際の挙動の一致

3本とも`pre_tasks`の`ansible.builtin.assert: that: not (ansible_check_mode | bool)`が既存のまま残っていることを確認済み(今回変更していない)。ヘッダの新しい記述はこのassertの存在を正しく反映している。

### 差し戻し対応後の再検証(lint両方向・syntax-check・全体lint)

差し戻し対応(Major 1・Suggestion 2・Suggestion 3)を反映した後、`scripts/check-tester-gate.sh`自体は変更していないが、Coordinatorの指示どおり両方向の検証をもう一度実施した。

**両方向lint(スクラッチディレクトリ、検証後`rm -rf`で削除済み)**:

- 弾く方向: `# tester-gate-condition2:`行が無いfixtureと、行はあるが理由が空のfixtureを同一ディレクトリに配置して実行 → 両方とも同じERROR文言でrc=1(初回と同じ結果、再現性確認)。
- 通す方向: 非空の`# tester-gate-condition2:`を持つfixture1件 + 差し戻し後の実3playbook(`cloudkey_cert_deploy.yml`・`proxmox_backup_restore_verify.yml`・`unifi_backup_fetch.yml`、Play 3のassert追加を含む現物)を同一ディレクトリに配置して実行 → `[tester-gate-lint] OK (4 playbooks)`でrc=0。

**本体での全体lint**:

```
$ bash scripts/check-tester-gate.sh
[tester-gate-lint] OK (46 playbooks)
```
rc=0(playbook数は初回実装時と同じ46のまま変化なし)。

**3本の`--syntax-check`(再実行)**:

```
ansible-playbook -i inventories/homelab/hosts.yml playbooks/cloudkey_cert_deploy.yml --syntax-check          → rc=0
ansible-playbook -i inventories/homelab/hosts.yml playbooks/proxmox_backup_restore_verify.yml --syntax-check → rc=0(Play 3に追加したpre_tasksを含めて構文エラーなし。brv_query_node/brv_restore_targets未定義グループのWARNINGのみ、動的add_host対象なので想定どおり)
ansible-playbook -i inventories/homelab/hosts.yml playbooks/unifi_backup_fetch.yml --syntax-check            → rc=0
```

## 差し戻し対応(独立レビュー Major 1件・Suggestion 2件、Coordinatorが是正と判断)

初回実装完了後、Coordinatorから独立レビューの指摘3件を受けて差し戻された。以下、指摘ごとに対応した。

### Major 1 — role側の重複マーカーが陳腐化したまま

`roles/cloudkey_cert_deploy/tasks/main.yml` L12-16に、TS-030導入前の前提(「`--check`込みで常に本実行する、dry-run区分はない」)を述べた`# tester-gate: risk-accepted — ...`マーカーがそのまま複製されて残っていた。これは初回実装時に私自身が未解決事項として報告した箇所で、Coordinatorはscopeの切り方(「playbookヘッダ3本」)が狭すぎたと認め、是正を指示した。

- `roles/incident_sync/tasks/install_timer.yml`と`roles/ubuntu_vm_full_upgrade/tasks/main.yml`を読み、両者とも分類名・理由を複製せず「呼び出し元playbookのtester-gateマーカー/ヘッダを参照」という1行の言及に留めている形を確認した(例: `tester-gate: check-mode-native, see the playbook header for the full classification rationale`)。
- `roles/cloudkey_cert_deploy/tasks/main.yml`のL12-16を、同じ「参照のみ・複製しない」形へ書き換えた。分類名(risk-accepted)・理由文字列(worst case ...)を削除し、`playbooks/cloudkey_cert_deploy.yml`のヘッダを参照する1文とTS-030/TS-036への言及に置き換えた。
- **同型の記述が他のroleに無いかを確認した**: `grep -rn "^# tester-gate:" roles/`で、リテラルな`# tester-gate: <種別> — <理由>`形式の複製マーカーは`roles/cloudkey_cert_deploy/tasks/main.yml`の1件のみだったことを確認済み(是正後は0件)。`grep -rln "risk-accepted\|check-mode-native\|dry-run-aware\|safe-readonly\|role-guarded" roles/`ではさらに広く17ファイルがヒットしたため、該当箇所を1件ずつ`-B2 -A2`で確認したが、いずれもTS-014/TS-015/TS-030/TS-031の実装パターンを理由づけるtask単位のローカルなコメント(例: 「これはblock化せずindividual gateにした理由」「handlerがcheck_mode:falseを継承しない」)であり、playbookの分類宣言(種別名+条件1/条件2の理由)をヘッダ形式で複製しているものではなかった。`roles/unifi_backup_fetch`・`roles/proxmox_backup_restore_verify`にはtester-gate関連の記述自体が無い(0件)ことも確認した。
- 対応してPolicyへ**TS-036**を新設した(§7「マーカーの扱い」節、TS-026の直後)。roleやtask fileへ分類名・理由を複製しないこと、参照に留めること、`scripts/check-tester-gate.sh`が`playbooks/`配下しか検査しないため複製は機械チェックの外で陳腐化することを明記した。§8変更履歴にも1行追加した。

### Suggestion 2 — Policy変更履歴の行が壊れている

`docs/ai/policies/ansible_test_safety_policy.md`の変更履歴表で、初回実装時に追加した行(TS-034/TS-035の行)が表の他行と異なり末尾の`|`を欠いていた。該当行に`|`を追加して表構造を修復した(TS-036の行を追加する際に合わせて修正)。

### Suggestion 3 — `proxmox_backup_restore_verify` Play 3 に停止assertが無い

Play 3(実際にqmrestoreする本体play)は自身の`pre_tasks`に停止assertを持たず、Play 2のassert失敗により`add_host`が実行されず`brv_restore_targets`が空になるという間接的な機構でのみ`--check`から守られていた。TS-030は「変更を行う各playのpre_tasksに置く」「停止の有無はplay単位で確認する」と定めており、字義には従っていなかった。Coordinatorの指示によりPlay 3にも同じ停止assert(Play 2と同一の`ansible.builtin.assert: that: not (ansible_check_mode | bool)`、同一の`fail_msg`)を追加した。ゲートロジックへの変更だが、安全性を強化する方向の追加であり、かつCoordinatorから明示的に指示された変更である。

あわせて、ヘッダの「pre_tasksの停止assert」という単数形の記述が「1つあれば足りる」と誤読されうるという指摘を受け、「変更を行う各play(Play 2 / Play 3)のpre_tasksに置かれた停止assert」という複数play明示の書き方に修正した。

### 変更していないこと(契約要素の維持確認)

- `# tester-gate-condition2:`マーカーの文言(3本とも)とTS-034/TS-035の本文は変更していない。
- `scripts/check-tester-gate.sh`のロジックは差し戻し対応で一切変更していない(Major/Suggestion対応はいずれもヘッダコメント・role内コメント・playbookのpre_tasks追加・Policy文書のみで完結した)。

### 差し戻し後の追加対象パス

- `roles/cloudkey_cert_deploy/tasks/main.yml`(Major 1)
- `playbooks/proxmox_backup_restore_verify.yml`(Suggestion 3、追加のpre_tasks assertとヘッダ文言の複数play化)
- `docs/ai/policies/ansible_test_safety_policy.md`(Suggestion 2の表修復、TS-036新設)

## 実行していないこと

- 対象3playbookおよびfixture以外のplaybookの`--check`付き/なし実行はしていない。実ホスト・ansyへの適用は一切行っていない。
- `git add` / `git commit` / `git push`は行っていない。

## 未解決事項

- **作業ツリー内に、本依頼のscope外の変更が既に存在していた**: `docs/ai/status.md`(差分あり)、`docs/ai/reviews/check_mode_semantics/2026-07-31_019_round2_batchC_quory_test_result.md`、および差し戻し対応中に新たに出現した`docs/ai/reviews/check_mode_semantics/2026-07-31_021_round2_close_review.md`(いずれも未追跡または差分あり、作業開始前には無かった)。ファイル内容とファイル名から、別のTester subagentによるRound2バッチCのquory実機検証、および今回の差し戻しの根拠となった独立レビューの成果物と判断した。**私はこれらに一切触れていない**(読んでも編集してもいない)。
- 棚卸し文書(`2026-07-31_004_classification_audit.md`)§4が指摘した2件の未解決事項(cert_renewとcloudkey_cert_deployの線引きの妥当性、systemd_timers/recovery_push_drill_setupの「ゲート対象が実質ゼロ」の扱い)は、今回のscope(marker drift是正・条件2記述・機械検査・Policy反映)には含まれないため未着手のまま。
