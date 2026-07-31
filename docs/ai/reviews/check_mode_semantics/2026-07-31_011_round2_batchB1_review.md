# review: Round 2 バッチB-1 — `check-mode-native` への変換

日付: 2026-07-31
requirement: `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md` §4 バッチB-1、§5 R1〜R6、§6 AC1〜AC5
対象diff: `playbooks/{recovery_io_setup,recovery_push_setup,recovery_push_drill_setup,systemd_timers,incident_sync_timer,time_sync_ntp_reference,ca_trust_deploy,incident_inspect_setup}.yml` と対応する8role分のtasks/handlers(`roles/recovery_io/*`、`roles/recovery_push/*`、`roles/systemd_timers/tasks/main.yml`、`roles/incident_sync/*`、`roles/time_sync_ntp_reference/tasks/chrony_hosts.yml`、`roles/homelab_cert_renew/{handlers/main.yml,tasks/deploy_ca_trust.yml}`、`roles/incident_inspect/tasks/main.yml`)
実装記録: `docs/ai/reviews/check_mode_semantics/2026-07-31_010_round2_batchB1_implement.md`(先に現物を独立判定した後に突き合わせた)

## Summary

8 playbook・対応role全てを現物diffと`--syntax-check`、`ansible-lint`、`check-tester-gate.sh`、および3パターンのdecoy実行(fresh host `--check`、通常実行、既存state `--check`)で確認した。**blocking findingは無い。** 依頼が最も懸念した「`roles/homelab_cert_renew`の共有handler経由でバッチC(`cert_renew`/`cert_renew_quory`)へ挙動が漏れる」疑いは、`deploy_ca_trust.yml`の呼び出し経路と`update-ca-certificates`handlerの通知元を独立にgrepし、実装者の主張と一致することを確認した——**漏れていない**。R1〜R6は8本全てで充足していると判定する。suggestionレベルの軽微な指摘が1件ある。

## Critical Issues

なし。

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `roles/recovery_push/tasks/sender_setup.yml` | 126 | `Scan quory host key for push known_hosts` (`command`、`changed_when: false`) は明示ゲートを付けず、moduleネイティブのauto-skipに依存している。唯一の消費者(`Deploy push known_hosts`)がゲート済みなので現状は安全だが、**将来この`command`の結果を別taskが参照するようになった場合、その新taskがゲート済みかどうかを見落とすと壊れる**。コメントで「唯一の消費者」という前提を明記しているのは良いが、次にこのファイルを触る人向けに、消費者が増えたら再検討する旨をコメントへ一言足すと事故予防になる。blockingではない。 | maintainability |

## What Looks Good

- **共有role経由の影響範囲は無い(独立確認済み)。** `grep -n "tasks_from" playbooks/cert_renew*.yml roles/homelab_cert_renew/tasks/main.yml`で、`cert_renew.yml`/`cert_renew_quory.yml`/`roles/homelab_cert_renew/tasks/main.yml`のいずれも`tasks_from: deploy_ca_trust`を使っていないことを確認した。`grep -n notify roles/homelab_cert_renew/tasks/*.yml`で、`update-ca-certificates`をnotifyするのは`deploy_ca_trust.yml`の2taskだけであることを確認した(`issue.yml`/`deploy_semaphore.yml`/`deploy_proxmox.yml`/`deploy_grafana.yml`/`prepare_ca.yml`/`cleanup.yml`はnotifyしていない)。`roles/homelab_cert_renew/handlers/main.yml`の他の2つのhandler(`restart semaphore`/`restart pveproxy`、cert_renew系が使う)は無変更。したがって本batchの変更は`--check`時・通常実行時のいずれも`cert_renew.yml`/`cert_renew_quory.yml`の挙動を変えない。requirement §3の非ゴール(`--check`なしの通常実行の挙動変更)に抵触しない。
- **AC2(通常実行不変)の構造的根拠が揃っている。** 全8 playbookで、新規に追加した`when:`は既存の`when:`を置換せず`and`で合成している(唯一該当する`roles/time_sync_ntp_reference/tasks/chrony_hosts.yml`の`Restart chrony`で確認)。通常実行(`ansible_check_mode == false`)では`not ansible_check_mode`は常にTrueなので、既存のtaskは実質そのまま動く。ロールimportの`check_mode: false`カスケード除去も、通常実行に副作用が無いことを確認した(除去してもtaskへの`when:`ゲートで到達性は保たれている)。
- **TS-015のblock化判定は一貫している。** `roles/recovery_push/tasks/sender_setup.yml`の`Generate push SSH key → Lock down → Slurp → Store in dict`をnamed blockでゲートした判断は、batchAが確立した「後続taskの正しさが先行taskの実際の実行に依存するか」という基準に沿っている。fresh host(state無し)での`--check`をdecoyで再現し、block丸ごとskipによりslurpのfile-not-foundが起きないことを実測確認した(下記自己検証参照)。逆に`systemd_timers`・`incident_inspect`・`incident_sync_timer`・`recovery_io`・`ca_trust_deploy`・`recovery_push_drill_setup`のように後続検証taskが無いroleはTS-014の個別ゲートに留めており、判定基準と結果が整合している。
- **`ca_trust_deploy`と`recovery_push/sender_setup`のslurp非対称は正当。** 前者(`roles/homelab_cert_renew/tasks/deploy_ca_trust.yml`のSlurp ROOT CA)は、この playbook内で新たに生成されたファイルではなく`cert_renew_ca_host`(quory)上に既に存在する独立したソースを読むだけなので、ungateして`--check`下でも実読み取りを検証する設計は理にかなう。後者(`sender_setup.yml`のSlurp push public key)は同じ一連の中で直前に`command creates:`で生成した鍵を読むため、生成taskがskipされた状態でslurpだけ生かすとfresh hostでfile-not-foundになる——ゲートが必要。TS-017が言う「read-onlyでも後続の判定が壊れるものは`check_mode: false`、壊れないものはゲートしてよい」の適用として矛盾がない。
- **`recovery_io`・`incident_sync`のhandler改修が「effectiveでない`check_mode: false`の残存」を再発させていない。** batchAが§2.4で指摘した「handlerは通知元taskのゲートを継承しない」問題への対処として、両roleとも`check_mode: false`単独ではなく`when: not ansible_check_mode`へ**置換**しており(併記していない)、batchB1実装記録が触れている「batchAが1箇所残した『効かない設定』」の再発を避けている(`roles/homelab_cert_renew/handlers/main.yml`のコメントにこの判断が明記されている)。
- **過剰ゲート(TS-017)の点検で不当な事例は見つからなかった。** `incident_sync/tasks/install_timer.yml`の`Query next scheduled run`(`systemctl list-timers`)はTS-017どおり`check_mode: false`+理由コメント付きでungateされている。実際にこの開発機で`systemctl list-timers <存在しない unit名> --all --no-pager`のrcを確認し、rc=0であることを独立に確認した(fresh hostでも失敗しない)。
- **機械チェックは通る。** `scripts/check-tester-gate.sh`(OK, 46 playbooks)、8 playbook全ての`--syntax-check`、`cert_renew.yml`/`cert_renew_quory.yml`の`--syntax-check`(いずれもrc=0)を独立に再実行した。`risk-accepted`宣言数は6本(非ゴール3 + B-2 `recovery_exec_setup` + バッチC 2本)で、AC5の想定(14→6、B-1完了分だけ減少)と一致する。`ansible-lint`の出力は全て役割変数命名(`var-naming[no-role-prefix]`)や`command-instead-of-module`等の既存debtで、本diffのwhen/tagsゲートに起因する新規違反は無かった。

## 自己検証(実施内容)

- `git diff`で対象8 playbook・対応role・handlerの全差分を通読した。
- `grep -n "tasks_from\|notify"` で`roles/homelab_cert_renew`のtask fileと呼び出し元playbook(`ca_trust_deploy.yml`/`cert_renew.yml`/`cert_renew_quory.yml`)の対応を独立に確認し、共有role経由の影響範囲が無いことを確認した(実装者の主張を鵜呑みにせず現物で再確認)。
- 8 playbook全てで`ansible-playbook <playbook> --syntax-check`を再実行しrc=0を確認した(`cert_renew.yml`/`cert_renew_quory.yml`も含む)。
- `bash scripts/check-tester-gate.sh`を再実行し`OK (46 playbooks)`を確認した。
- `grep -h "^# tester-gate:" playbooks/*.yml`の分布と`risk-accepted`宣言ファイル一覧を確認し、AC5の期待値と一致することを確認した。
- `ansible-lint`を変更対象playbook・role一式に対して実行し、出力が全て既存debt(var-naming、command-instead-of-module等)であることを確認した。変更前(`git stash`)との比較でも新規違反が増えていないことを確認した。
- **実行して確かめる検証**(値の目視で終わらせない): `/tmp`のscratchpad上に`ansible_connection: local`・実host名なしのdecoy playbookを作成し、削除済み。
  1. fresh host(依存ファイル未生成)での`--check`: 破壊的task・TS-015 block全体(ネストしたslurp含む)が丸ごと`skipping`になり、rc=0で完走することを確認(slurpのfile-not-foundは起きない)。
  2. 通常実行: 全taskが`changed`し、registered変数・set_factが正しく埋まることを確認。
  3. 既存state(通常実行後)での`--check`: 再度全skip・rc=0で完走し、部分適用が起きないことを確認(AC3相当の構造確認。実ホストでのAC1〜AC3自体はTesterの領域であり本レビューでは実施していない)。
  4. registered taskが`when:`でskipされたときの`.changed`が`False`になることを確認(`time_sync_ntp_reference/chrony_hosts.yml`の`Restart chrony`の`and`条件が安全に倒れることの裏付け)。
  - decoyディレクトリ・一時ファイルはすべて削除済み(作業ツリー外に残留なし)。
- 対象playbook自体(実host向け)は一切実行していない。実host・ansyへの適用も行っていない。`git add`/`git commit`/`git push`は行っていない。

## 未解決事項

- Suggestions #1(`Scan quory host key`のauto-skip依存)はblockingではないため、対応を次のバッチや将来の改修へ持ち越してよい。
- AC1〜AC3の実host確認はTesterの領域であり本レビューでは行っていない(依頼のscope外)。
- `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md`の差分(OQ1決着・バッチB内訳追記)はCoordinatorの成果物であり本レビューの対象外として扱った(依頼の除外指定どおり)。

## Verdict

**Approve**

---

## Coordinatorの処理(2026-07-31)

| Suggestion | 扱い |
|---|---|
| `roles/recovery_push/tasks/sender_setup.yml` の `Scan quory host key` はauto-skip依存で現状安全だが、将来消費者が増えたときの再検討を促すコメントを足すべき | **同意・採用。** Coordinatorが直接コメントを追加した(挙動は変えていないためTester検証の結果に影響しない)。「このtaskの結果を読む箇所を増やすなら、その消費者が `--check` で到達しないことを確かめること」を明記した |

**共有role経由の影響範囲について**: Reviewerの判定(`deploy_ca_trust.yml` の2taskだけが `update-ca-certificates` を notify し、`cert_renew` 系へは届かない)は、Coordinator と Tester がそれぞれ独立に再確認して一致した。**3者が別々に同じ結論へ到達しているため、この点は決着とみなす。**
