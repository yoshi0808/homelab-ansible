# implement: Round 2 バッチC(最終バッチ) — `check-mode-native` への変換

日付: 2026-07-31
requirement: `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md` §4 バッチC、§5 R1〜R6、§6 AC1〜AC5、§7 OQ2
テンプレート: `2026-07-31_007_round2_batchA_implement.md` / `_010_round2_batchB1_implement.md` / `_013_round2_batchB2_implement.md`(手順の正本。本記録は差異と適用結果のみ書く)

対象2 playbook: `playbooks/cert_renew.yml`(7 play)、`playbooks/codex_update_check.yml`(2 play)

## 1. 変更ファイル

- `playbooks/cert_renew.yml`
- `playbooks/codex_update_check.yml`
- `roles/codex_update_check/tasks/main.yml`
- `roles/homelab_cert_renew/tasks/issue.yml`(薄いwrapperに縮小)
- `roles/homelab_cert_renew/tasks/prepare_ca.yml`(薄いwrapperに縮小)
- `roles/homelab_cert_renew/tasks/issue_check.yml`(新設)
- `roles/homelab_cert_renew/tasks/issue_apply.yml`(新設)
- `roles/homelab_cert_renew/tasks/prepare_ca_check.yml`(新設)
- `roles/homelab_cert_renew/tasks/prepare_ca_apply.yml`(新設)

`roles/homelab_cert_renew/tasks/{cleanup,deploy_semaphore,deploy_proxmox,deploy_grafana,deploy_ca_trust,main}.yml`、`roles/homelab_cert_renew/handlers/main.yml`、`playbooks/cert_renew_quory.yml`、`playbooks/cloudkey_cert_deploy.yml`、`playbooks/ca_trust_deploy.yml`は一切変更していない。

## 2. 設計判断: `issue.yml` / `prepare_ca.yml` の分割(最重要の判断)

`roles/homelab_cert_renew`は`cert_renew.yml`(本バッチの対象)だけでなく`cert_renew_quory.yml`(対象外、`tester-gate: check-mode-native`だが「prepare_ca/issue/cleanupは--checkでも常に本実行する」という別設計)とも`issue.yml`/`prepare_ca.yml`を共有している。

`cert_renew_quory.yml`は`import_role: tasks_from: issue|prepare_ca` に `check_mode: false` を付けて呼んでおり、これは対象ファイル内の**すべての**taskへ「実行するなら必ず実物で行う」を強制するだけで、`when:`によるtask skipには一切影響しない(`check_mode: false`と`when:`は独立した属性)。したがって、`issue.yml`/`prepare_ca.yml`の内部taskへ直接`when: not ansible_check_mode`を書き込むと、**cert_renew_quory.yml側で`--check`時にそのtaskがskipされてしまい**、「issue/prepare_caは--checkでも常に本実行する」という対象外playbookの設計を壊す。

これを避けるため、`issue.yml`/`prepare_ca.yml`を「診断部分(check)」と「破壊的部分(apply)」に分割した:

- `issue_check.yml`: `cert_needs_renewal`判定(stat/shell日数計算/set_fact/debug)+ SAN IP解決。破壊的操作を一切含まない。
- `issue_apply.yml`: OpenSSL設定配置・鍵生成・CSR・署名・fullchain作成(すべて`cert_needs_renewal`時のみ)。
- `prepare_ca_check.yml`: CA証明書/鍵の存在・権限・中間CA期限チェック。
- `prepare_ca_apply.yml`: CA証明書/鍵をtmpfsへ展開(3task、TS-033のファイル上連続チェーン)。
- `issue.yml`/`prepare_ca.yml`は「check→apply」を無条件でimportする薄いwrapperに置き換えた。**元の実行順序は一切変えていない**(ファイルを2分割しただけ)。

`cert_renew_quory.yml`は今までどおり`tasks_from: issue`/`tasks_from: prepare_ca`(=wrapper)を`check_mode: false`付きで呼ぶため、check/applyとも無条件で常に本実行される。**cert_renew_quory.yml側のコードは1行も変更していない**。`cert_renew.yml`側は新設の`tasks_from: issue_check`(ゲート無し)と`tasks_from: issue_apply`(呼び出し側で`when: not ansible_check_mode`)を使い分ける。

`deploy_semaphore.yml`(cert_renew.yml/cert_renew_quory.yml共有)は分割不要と判断した — 全task が破壊的で診断的価値が無く、かつ`cert_renew_quory.yml`自身も既にこのimportを`when: not ansible_check_mode`で個別ゲートしている(`check_mode: false`は使っていない)ため、`cert_renew.yml`側で同じ条件を呼び出し側に付けても両playbookの挙動は一致し、矛盾しない。`deploy_proxmox.yml`/`deploy_grafana.yml`は`cert_renew_quory.yml`から一切呼ばれないため制約が無く、`cleanup.yml`も全task destructiveのため、いずれも呼び出し側(`cert_renew.yml`)で`when: not ansible_check_mode` + `tags: [destructive]`をimport_role呼び出しに直接付け、ファイル自体は変更していない。

## 3. R1〜R6充足状況

| # | 内容 | 充足 |
|---|---|---|
| R1 | ヘッダを`check-mode-native`へ変更、TS-009条件1・2両方に言及 | 両playbookとも実施。cert_renewはissue_check/prepare_ca_checkの分離可能性を条件2不成立の根拠として明記、codex_update_checkはバージョン収集とnpm installの分離を根拠に明記 |
| R2 | Round1の`--check`停止assertを除去 | 両playbook・全playで除去 |
| R3 | role importの`check_mode: false`カスケードを除去 | cert_renew.yml: 8箇所(prepare_ca/issue×3/deploy_semaphore/deploy_proxmox/deploy_grafana/cleanup)すべて除去。codex_update_check.yml: 1箇所除去 |
| R4 | 破壊的task全てにwhen+tags | cert_renew: issue_apply/prepare_ca_apply/deploy_*/cleanupをすべて呼び出し側でゲート(§2)。codex_update_check: npm installの2taskに個別付与 |
| R5 | check_mode非対応moduleの診断taskにcheck_mode:false+理由コメント | cert_renew: `issue_check.yml`の日数計算shell・SAN解決command、`prepare_ca_check.yml`の中間CA日数計算shellに付与。codex_update_check: バージョン収集command 6箇所すべてに付与(分類監査が明示した6箇所と一致) |
| R6 | 停止assert除去に伴うskip_notifications案内の除去 | 両playbookとも該当なし(fail_msgに記載なし、grep確認済み) |

## 4. R1〜R6を超えて行った修正(正当化を含む)

R1〜R6の機械的適用だけでは、`--check`実行時に**誤った失敗判定**が生じる箇所が2つあり、AC1(終了コード0)を壊すため修正した(いずれも「値の目視でなく消費側まで通す」検証で発見した)。

1. **`roles/codex_update_check/tasks/main.yml`の状態判定set_fact(codex/npm 両方)**: `needs_update=true`かつ`--check`(install taskがskip)の場合、既存ロジック(`install_result.rc | default(1) != 0` → `update_failed`)がそのまま`update_failed`に分類し、最終`fail:`task(`codex_update_check_all_failed_hosts`)を誤発火させ、正常な`--check`実行がexit 1で終わる。`ansible_check_mode`を最優先で見る`would_update`分岐を追加し、通常実行(`ansible_check_mode`は常にfalse)の分類ロジックはAND追加のみで変更していない(AC2不変)。
2. **`playbooks/cert_renew.yml`の`Build renewal summary`Jinja**: `--check`下ではissue_apply/deploy_*が丸ごとskipされるため`cert_renewed`/`cert_deployed`が実態を反映しなくなり、既存ロジックのままだと「issue FAILED」または「renewed but deploy FAILED」という誤った文言がSlack通知本文に載る(exit codeには影響しないが、TS-018の「plan-only分岐を必ず含める」に反する)。`ansible_check_mode`分岐を`not needs_renewal`の直後に追加し、CA cleanup行も同様に分岐した。

いずれもrequirementの明文条件(R1〜R6、AC1〜AC5)から論理的に要求される修正であり、scope外の機能追加ではないと判断した。

## 5. OQ2についての所見

`cert_renew.yml`と`cloudkey_cert_deploy.yml`の現物を読み直して確認した。

- **`cert_renew`は分離可能で、`check-mode-native`への変換が正しい。** `issue.yml`は「`cert_needs_renewal`判定(stat + shellの日数計算)」と「実際のkeygen/CSR/署名」が明確に別タスク群であり、前者は破壊的操作を一切伴わず、それ単体で「更新が必要か」という意味のある情報を返す。これは分類監査(`2026-07-31_004_classification_audit.md`§2.2)の判定どおりで、実装（`issue_check.yml`/`issue_apply.yml`への分割）で問題なく実現できた。
- **`cloudkey_cert_deploy`は分離不能で、`risk-accepted`維持が正しい。** `roles/cloudkey_cert_deploy/tasks/{issue,deploy}.yml`を読み直したが、(a) `issue.yml`に「更新要否」を判定する分岐が存在しない(常に新規のリーフ証明書を発行する設計)。(b) `deploy.yml`はログイン→CSRF抽出→アップロード→有効化→**実際にTLSで served証明書を再取得して検証**→(検証成功時のみ)旧証明書削除という一本の`uri`連鎖で、後続の各stepは前段のAPI呼び出しが実際に行われたことに構造的に依存する(例: `Activate`は`Upload`が返した実IDを使う、`served証明書検証`は`Activate`が実際に行われたことが前提)。この一連を`--check`で安全に一部だけ実行する分割点が存在しない。分類監査の判定と一致することを独立に確認した。変換はしていない(非ゴール)。

## 6. 自己検証

- 対象2playbookの**7 play + 2 play全て**を通しで読み、破壊的taskの漏れがないことを確認した(prepare_ca_apply/issue_apply/deploy_semaphore/deploy_proxmox/deploy_grafana/cleanup、および`Pause`/`Resume`monitoring command、codexの`npm install`2箇所)。`notify:`は`roles/homelab_cert_renew/handlers/main.yml`の`update-ca-certificates`のみが使われており(grep確認)、`deploy_semaphore.yml`/`deploy_proxmox.yml`の`systemd restart`は`notify:`ではなく直接taskであることを確認した(=handler経由のcheck_mode考慮は不要)。`loop:`(`prepare_ca_apply.yml`のディレクトリ作成、`deploy_proxmox.yml`の一時ファイル削除)、`always:`(`deploy_proxmox.yml`)を含めて、いずれも呼び出し元の`when: not ansible_check_mode`ゲートの配下に収まることを確認した。`rescue:`は対象範囲に存在しない。
- `git diff`/`git status`で、変更が対象2playbook + `roles/homelab_cert_renew`の5ファイル(3変更+2新規×2=4新規、実際は issue/prepare_ca各1変更+2新規)+ `roles/codex_update_check/tasks/main.yml`のみであることを確認した。`cert_renew_quory.yml`/`cloudkey_cert_deploy.yml`/`proxmox_backup_restore_verify.yml`/`unifi_backup_fetch.yml`/`ca_trust_deploy.yml`/`roles/homelab_cert_renew/tasks/{cleanup,deploy_semaphore,deploy_proxmox,deploy_grafana,deploy_ca_trust,main}.yml`/`handlers/main.yml`は無変更(`git status`に出ていないことで確認)。
- 変更・新設した全ファイルで`ansible-playbook <playbook> --syntax-check`(4 playbook: cert_renew/cert_renew_quory/ca_trust_deploy/codex_update_check、いずれも共有roleの間接確認のため含めた)が通ることを確認した。
- `bash scripts/check-tester-gate.sh` → `OK (46 playbooks)`(AC4)。
- `grep -h "^# tester-gate: risk-accepted" playbooks/*.yml | wc -l` → 5→3(AC5、round2最終値。残る3本は非ゴール`cloudkey_cert_deploy`/`proxmox_backup_restore_verify`/`unifi_backup_fetch`)。
- `ansible-lint`を変更前後(`git stash`)で比較し、新規に導入した違反が無いことを確認した。分割による`import_tasks`の`name[missing]`が一時的に4件増えたため、`issue.yml`/`prepare_ca.yml`のwrapper importに`name:`を追加して解消した(最終的に`name[missing]`はbaselineと同じ3件)。`var-naming`/`risky-shell-pipe`は既存debtの再配置のみ(個別ファイル指定でのlintで内容確認済み)。
- **値の目視で終えず、実際に完走させる検証**として、`/tmp`のscratchpad上にdecoy playbook(`ansible_connection: local`、実host名なし)を作り、実行後に削除した:
  1. codexロールの状態判定ロジックを再現し、`needs_update=true`かつ`--check`で`would_update`(型はstr)になり最終failタスクがskipされexit 0になること、通常実行では`updated`になり同じfailタスクがskipされること(rc=0)を実測した。修正前ロジック(`ansible_check_mode`分岐なし)だと`update_failed`に落ちてexit 1になることも別途確認した。
  2. `cert_renew_quory.yml`方式(`import_tasks`ラッパーに`check_mode: false`)を再現し、`--check`実行下でも「診断shell(check_mode:false付き)」「破壊的shell(`when:`にansible_check_mode言及なし)」の両方が実際にファイルへ書き込みを行うことを実測した(cert_renew_quory.ymlの「常に本実行」設計が split後も保たれることの裏付け)。
  3. `cert_renew.yml`方式(issue_check無条件+issue_apply/deploy相当を1つの`when: not ansible_check_mode`ブロックで包む)を再現し、fresh host状態で`--check`実行がrc=0で完走し(診断taskのみ実行、破壊的task/後続の「slurp相当」taskとも`skipping`)、通常実行では破壊的taskが`changed`になることを実測した。
  4. `cert_renew.yml`の`Build renewal summary`Jinjaを4ホスト分の`hostvars`込みでそのまま切り出し実行し、`--check`時に全対象ホストが"would renew and deploy..."文言になること、通常実行時に"issue FAILED"/"renewed and deployed"/"skipped"/"check FAILED"の各分岐が正しく選択されること、`slack_status`の算出(`FAILED`文字列判定)がクラッシュしないことを実測した。
  5. decoyディレクトリ・一時ファイルはすべて検証後に削除済み(`/tmp/claude-1000/.../scratchpad/decoy`、`decoy2`)。

**行っていない検証(Testerの領域、AC1〜AC3)**: 対象2playbookそのものを`--check`付き/無しで実行し、終了コード・`PLAY RECAP`・実ホスト(quory/ansy/authy/monnie/pve1/pve2)状態の前後比較を確認すること。契約上、対象playbookの実行(`--check`の有無を問わず)は禁止されているため行っていない。特に`cert_renew.yml`はpve1/pve2(保護対象ホスト)への`delegate_to`と`serial: 1`を含み、`codex_update_check.yml`はansy/quory双方への`npm install -g`(sudo)を含むため、実ホストでの`--check`/通常実行検証はTesterが計画すべき領域として残す。

## 7. 未解決事項

1. **`issue.yml`/`prepare_ca.yml`分割によるファイル数増加。** `roles/homelab_cert_renew/tasks/`が8ファイルから12ファイルに増えた。動作は§2・§6で検証済みだが、将来`cert_renew_quory.yml`側を触る担当が「issue.ymlはただのwrapper」であることに気づかず`issue_check.yml`/`issue_apply.yml`を直接編集して意図せず分割の前提(「check/applyとも無条件」)を崩す可能性がある。各ファイル冒頭にコメントで明記したが、構造としての強制力は無い。
2. **codex_update_check.ymlのSlackメッセージ本文は`would_update`ホストを列挙しない。** `codex_update_check_updated_hosts`(status=='updated')のみをテンプレートでループしており、`--check`下では常に空になる。`--check`実行時に「実際には何が更新対象だったか」を知りたい場合は`Print codex_update_check summary`(debug、全hostのstatusを含む)を見る必要がある。R1〜R6・AC1〜AC5の文言上は必須ではないため追加しなかったが、Coordinator/Reviewerの確認を求める。
3. **`cert_renew_quory.yml`側の`--check`実測は行っていない(実行禁止のため)。** §2の分割設計は decoy再現(§6-2)で機能的に確認したが、cert_renew_quory.yml自身を実際に`--check`付きで走らせて「issue/prepare_ca/cleanupが変わらず本実行される」ことを確認するのはTesterの領域として残る。対象外playbookのため、本バッチでは変更されていないことの確認(diffが無いこと)のみをもって「壊していない」根拠としている。

以上、対象2 playbook・関連role(homelab_cert_renew 5ファイル変更・4ファイル新設、codex_update_check 1ファイル変更)の変換は完了。Round 2(14本の`risk-accepted`→`check-mode-native`変換)はこれで全バッチ完了、`risk-accepted`は3本(非ゴール分のみ)になった。
