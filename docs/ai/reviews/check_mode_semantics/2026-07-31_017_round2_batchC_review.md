# review: Round 2 バッチC(最終バッチ) — `cert_renew` / `codex_update_check` の `check-mode-native` 変換

日付: 2026-07-31
requirement: `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md` §4 バッチC、§5 R1〜R6、§6 AC1〜AC5、§7 OQ2
対象diff: `playbooks/cert_renew.yml`(7 play)、`playbooks/codex_update_check.yml`(2 play)、`roles/codex_update_check/tasks/main.yml`、`roles/homelab_cert_renew/tasks/{issue.yml, prepare_ca.yml}`(wrapper化)、新設`roles/homelab_cert_renew/tasks/{issue_check.yml, issue_apply.yml, prepare_ca_check.yml, prepare_ca_apply.yml}`
実装記録: `docs/ai/reviews/check_mode_semantics/2026-07-31_016_round2_batchC_implement.md`(先に現物を独立判定した後に突き合わせた)

## Summary

対象9ファイル(変更5・新設4)の`git diff`/全文を通読し、`cert_renew.yml`7 playすべての破壊的task網羅性と、`roles/homelab_cert_renew`の`issue.yml`/`prepare_ca.yml`分割が対象外playbook(`cert_renew_quory.yml`、`ca_trust_deploy.yml`)へ影響しないことを、コード読解と`ansible_connection: local`のdecoy inventory実行の両方で独立に確認した。`--syntax-check`(cert_renew/cert_renew_quory/ca_trust_deploy/codex_update_check)・`ansible-lint`・`scripts/check-tester-gate.sh`はいずれも通過し、AC4・AC5(risk-accepted 3本)を満たす。**blocking findingは無い。**

**共有role分割の判定: 妥当。** `cert_renew_quory.yml`が`import_role`に付ける`check_mode: false`は task の`when:`評価には影響しない独立した属性であり(decoyで実測)、共有ファイル内に直接`when: not ansible_check_mode`を書くと`cert_renew_quory.yml`側の「issue/prepare_caは`--check`でも常に本実行する」設計を壊す。分割せずゲートする簡易な代替(呼び出し元でロール変数を切り替える等)は、共有task fileへ暗黙のcaller依存契約を持ち込む点で分割より劣ると判断した。`issue.yml`/`prepare_ca.yml`は`import_tasks`で元の順序をそのまま保持する薄いwrapperになっており、静的include(`import_tasks`)のため register scope・`when:`評価タイミングは分割前と同一である。

**R1〜R6を超えた2件の判定: いずれも必要、副作用なし。**
1. `codex_update_check`の`would_update`分岐 — `codex_update_check_all_failed_hosts`は`selectattr('status', 'in', ['update_failed', 'collection_failed'])`で判定しており、`would_update`はこのリストに含まれないため誤fail化を防ぐ。追加前のロジックでは`--check`下でinstallタスクがskipされ`.rc | default(1)`が1のまま`update_failed`に落ちてAC1(exit 0)を破ることを確認した。
2. `cert_renew.yml`サマリJinjaの`ansible_check_mode`分岐 — decoy実行で実測: 分岐が無い版に相当する状態(issue_apply/deploy_*がskipされ`cert_renewed`が未定義)では対象ホストが"issue FAILED"と誤表示されることを確認した。分岐追加後は"would renew and deploy..."が正しく表示され、通常実行時の分岐（`skipped`/`issue FAILED`/`renewed and deployed`/`renewed but deploy FAILED`）はいずれも変更されていない。

## Critical Issues

なし。

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `docs/ai/reviews/check_mode_semantics/2026-07-31_016_round2_batchC_implement.md` §7-1 | - | `issue.yml`/`prepare_ca.yml`が薄いwrapperであることは各ファイル冒頭コメントで明記されているが、強制力はコメントのみ。将来`cert_renew_quory.yml`側の担当が`issue_check.yml`/`issue_apply.yml`を直接編集し分割前提(check/applyとも無条件)を崩すリスクは実装記録が自ら指摘済みで、同意する。ブロッキングではないが、Coordinatorが構造的な強制(例: ファイル冒頭に「このファイルを直接editする前にissue.ymlを確認」という警告以上の何か)を検討する価値がある。 | maintainability |
| 2 | `roles/codex_update_check/tasks/main.yml` | 265-301 | Slack通知本文の"Codex CLI 更新実施:"ループは`status == 'updated'`のみを対象とし、`--check`下で`would_update`になったホストは列挙されない(`Print codex_update_check summary`のdebug出力にのみ現れる)。R1〜R6・AC1〜AC5の文言上は必須ではなく実装記録も未解決事項として明記済みだが、TS-018の「dry-runの結果を通知に反映する」趣旨には部分的に届いていない。blockingではない。 | completeness |

## `slurp`の扱いについての判定

`deploy_semaphore.yml`/`deploy_proxmox.yml`の計4 slurp task(no_log付き)は無変更ファイルだが、いずれも呼び出し元(`cert_renew.yml`)で`when: not ansible_check_mode`の block内からimportされるため、`--check`下ではimport_role自体がskipされ、slurp taskへ到達しない。これはTS-017の「check_mode非対応moduleは`check_mode: false`で診断価値を残す」の対象外(slurpの読み取り元であるfullchain/keyファイル自体がissue_apply/prepare_ca_apply skip時に存在しない可能性があり、無理に読ませると失敗するため、丸ごとskipが正しい)。decoy実行で実際にこれらのtaskが`skipping`になることを確認した。

## TS-033適用についての判定

`issue_apply.yml`(7task連鎖: OpenSSL config→keygen→CSR→署名→fullchain)と`prepare_ca_apply.yml`(3task連鎖: ディレクトリ作成→CA証明書/鍵コピー)は、分割前から既にファイル内で連続しておりTS-033の「連続していればblockにする」基準に沿ってそのまま1つの`when: not ansible_check_mode`でゲートされている。`cert_renew.yml`側では、ansy/proxmox/monnie各playで`issue_apply`+`deploy_*`(+monnieのみpause/resume monitoring)を1つの named block(コメントで"TS-015 chain"と明記)にまとめており、TS-015の「相互依存する一連はblock単位でゲートする」に沿っている。個別ゲートを選んだ箇所は無く、TS-033が求める理由コメントの要否は生じない。

## What Looks Good

- **cert_renew.yml 7 playすべてのゲート網羅。** prepare_ca_apply/issue_apply(×3play)/deploy_semaphore/deploy_proxmox/deploy_grafana/cleanup、およびmonnie playのPause/Resume monitoring commandまで、破壊的操作はすべて`when: not ansible_check_mode`(block levelまたは個別)+`tags: [destructive]`でゲートされている。`hosts: proxmox`(pve1/pve2)のplayも例外なくゲート済み。
- **AC2回帰なし。** 追加された`when: not ansible_check_mode`はすべて既存条件へのAND追加(listまたはblock+task両方の`when`併存)であり、既存の`when: cert_needs_renewal`(issue_apply.yml各task)・`when: codex_update_check_needs_update`(codex install task)・`when: cert_needs_renewal | default(false) | bool`(pause/resume monitoring)を置換していないことを`git diff`のcontext行で確認した。
- **共有ファイルへの影響なし。** `ca_trust_deploy.yml`は`tasks_from: deploy_ca_trust`を使いissue/prepare_caを一切呼ばないため無関係。`cert_renew_quory.yml`は`tasks_from: issue|prepare_ca|cleanup`を`check_mode: false`付きで呼び続けており、wrapperが両半分を無条件importするため挙動は不変。`--syntax-check`は両playbookとも通過。
- **decoyでの実機能検証(AC1・AC3相当)。** `ansible_connection: local`のdecoy inventory(実host名なし、`/tmp`scratchpad)で`cert_renew.yml`を丸ごと実行(hostname assertのみdebugへ置換)し、`--check`でexit 0、prepare_ca_check/issue_checkは実行、prepare_ca_apply/issue_apply/deploy_*/pause-resume/cleanupはすべて`skipping`、`Build renewal summary`が"would renew and deploy..."を正しく生成することを実測した。破壊的操作が一切実行されていないことをtask結果(`changed=0`、apply系は全skip)で確認した。
- **`no_log`の保存。** `issue_apply.yml`のkeygen/署名task、`prepare_ca_apply.yml`のCA鍵コピー、`issue_check.yml`のCA鍵stat相当箇所の`no_log: true`は分割前後で欠落なく保持されている。
- **機械チェック。** `scripts/check-tester-gate.sh` → `OK (46 playbooks)`。`grep -h "^# tester-gate: risk-accepted" playbooks/*.yml`→3本(非ゴール3本のみ、AC5一致)。`ansible-lint`の指摘(var-naming[no-role-prefix]、risky-shell-pipe、line-length、name[casing])はすべて分割前から存在する既存debtの再配置または無関係な既存行であることを`git diff`のcontext確認で照合した(新規導入の指摘なし)。

## 自己検証(実施内容)

- `docs/ai/core.md`・`docs/ai/roles/reviewer.md`・`docs/ai/policies/ansible_test_safety_policy.md`§4・§5(TS-033含む)、`skills/code-review/SKILL.md`・`skills/duplication-reuse-check/SKILL.md`・`skills/ansible-security-review/SKILL.md`を読んだ。requirement本体を通読した。
- `git status`/`git diff --stat`で対象ファイル(変更5・新規4・実装記録1)を確認し、`git diff`全量を読んだ。新設4ファイル・変更後の`cert_renew.yml`全文をReadで通読した。
- `grep -rn "tasks_from: issue\|tasks_from: prepare_ca\|tasks_from: cleanup"`で`cert_renew.yml`/`cert_renew_quory.yml`の呼び出し箇所を突き合わせ、`ca_trust_deploy.yml`が別task file(`deploy_ca_trust`)を使うため無関係であることを確認した。
- `ansible-playbook <playbook> --syntax-check`をcert_renew/cert_renew_quory/ca_trust_deploy/codex_update_checkの4本で実行し、いずれもrc=0を確認した。
- `bash scripts/check-tester-gate.sh`→OK、`grep -h "^# tester-gate:" playbooks/*.yml | sort | uniq -c`→risk-accepted 3本(AC5)。
- `ansible-lint`を対象ファイル群に実行し、指摘全件を`git diff`のcontext行と突き合わせて新規導入でないことを個別に確認した。
- **実行して確かめる検証**(値の目視で終わらせない): `/tmp`のscratchpadに`ansible_connection: local`のdecoy inventory(ansy/quory/monnie/proxmoxグループをlocalhostへマップ)を作成し、`cert_renew.yml`のコピー(hostname assertのみdebugへ置換、他は無変更)を`--check`で実行した。
  1. prepare_ca_checkが実行されopensslによる実際の有効期限計算(364日)が動くこと、prepare_ca_apply(ディレクトリ作成・CAコピー2件)が`false_condition: not ansible_check_mode`で`skipping`になることを確認した。
  2. issue_check(cert_needs_renewal判定・IPv4解決)が全4ホストで実行され、issue_apply〜deploy_*〜pause/resume monitoring〜cleanupのnamed block配下がすべてskipされることを確認した。
  3. `Build renewal summary`が4ホスト分とも"would renew and deploy...(check-mode preview...)"を生成し、"CA cleanup: not applicable (check-mode preview)"を生成すること、Slack通知がTS-031どおり`ansible_check_mode`でreal送信されず`[tester_mode] 通知スキップ`のdebugに落ちることを確認した(`common_slack`roleへsymlink経由で到達)。
  4. `capture.yml`側の`reports_base_dir`未定義エラーはこのdecoy環境固有のfixture不足でありrescueブロックに吸収されてplay全体はrc=0で完走した(cert_renewの変換対象コードではない)。
  - decoyディレクトリ・symlink・vars fileはすべて検証後に削除し、`git status`で作業ツリーに残留が無いことを確認した。
- `codex_update_check`側は`would_update`分岐が`codex_update_check_all_failed_hosts`のselectattrに含まれないことをコード読解で確認し(ネットワーク呼び出し(`npm view`)を伴うため実行はしていない)、除去前の状態を仮定した場合の分類(`update_failed`→fail誘発)をロジックとして裏取りした。
- 対象playbook自体を実ホスト・ansy問わず`--check`の有無にかかわらず実行していない。`git add`/`git commit`/`git push`は行っていない。作業ツリー外への残留ファイルなし。

## 未解決事項

- Suggestions #1・#2はいずれもblockingではなく、Coordinatorの裁量判断として残す。
- AC1〜AC3の実ホスト確認(quory/ansy/pve1/pve2/monnie)はTesterの領域であり本レビューでは行っていない。特にAC3(部分適用が起きないこと)は`cert_renew.yml`が`serial: 1`でpve1/pve2(保護対象ホスト)へ到達する構造上、Testerが慎重に計画すべき領域として実装記録・本レビューとも一致して指摘する。
- `codex_update_check.yml`のAC1〜AC3実測(npm installを伴う)は、ネットワーク呼び出しと実インストールを伴うためTesterの領域として残す。

## Verdict

**Approve**

---

## Coordinatorの処理(2026-07-31)

| Suggestion | 扱い |
|---|---|
| #1 `issue.yml` / `prepare_ca.yml` が薄いwrapperであることの強制力がコメントのみ | **受容(現状維持)。理由を記録する。** このwrapperは、対象外の `cert_renew_quory.yml`(`tasks_from` で元のファイル名を参照している)を今回のscopeで触らないために置いた**互換のための層**である。恒久的な設計ではない。**次に `cert_renew_quory.yml` を触る案件で、参照先を `*_check.yml` / `*_apply.yml` へ直接向けてwrapperを削除できる。** その時点までは、wrapperへ直接taskを足すとバッチCの分割の意味が消えるため、コメントの警告が唯一の防波堤である。**強制機構を今作らないのは、wrapper自体が一時的だからであり、「コメントで足りる」と判断したからではない。** |
| #2 `codex_update_check.yml` のSlack通知本文が `--check` 下の `would_update` ホストを列挙しない | **受容(現状維持)。** TS-031により `--check` ではSlackへ送信されないため、本文の内容が人に届く経路は `debug` 出力のみであり、そこには情報が出ている。診断価値の薄れは小さく、Round 2のクローズを遅らせてまで直す差ではない。**ただし「`--check` で更新予定ホストを一覧したい」という要求が出たら、この本文が直す場所である。** |

**共有roleの分割について**: Reviewerは「分割せずcaller依存の変数で切り替える代替案」も検討したうえで、暗黙契約を持ち込む点で劣ると判断している。Coordinatorもこの判定に同意する。**ファイルを増やす構造変更が本案件で唯一ここだけであること自体は、テンプレートからの逸脱ではなく、共有roleに対象外の利用者がいるという事実に由来する。**
