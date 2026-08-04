# Policy 11本 掃引レビュー(2026-08-02〜08-04 変更に対する)

作成日: 2026-08-04 / 作成: Reviewer(subagent)

対象: `docs/ai/policies/*.md` 全11本。baseline (`docs/ai/reviews/norm_docs_post_phase4_sweep/2026-08-04_001_change_baseline.md`) の各項目を11本全体へ当てた。全文レビューではなく、baseline に挙がった変更点に対する掃引に限定している。

読んだ本数: **11/11**(全文読了)。

- ansible_test_safety_policy.md
- autonomous_recovery_policy.md
- cert_renew_cloudkey_policy.md
- cert_renew_policy.md
- incident_capture_policy.md
- log_observability_policy.md
- proxmox_backup_restore_verify_policy.md
- proxmox_operations_policy.md
- time_sync_check_policy.md
- ubuntu_vm_patch_policy.md
- unifi_backup_fetch_policy.md

## 裏取りの手段

- `grep -rn` によるキーワード横断(`ansy`、`開発`、`SSH`、`incident_sync`/転送段、`claude -p`/無人、`git pull`/`git commit`/`git push`、`worktree`、`schedule`/`environment`)を全11本に実施。
- baseline が指す commit 群のうち `docs/ai/reviews/dev_prod_boundary/` 配下の `2026-08-02_001_requirement.md`、`2026-08-03_015_plan_phase4.md`、`2026-08-03_023_test_result_phase4.md`、`2026-08-03_024_finding_unenumerated_credential.md` を `git show` 相当で読み、**ansy が実際にどのホストへの資格情報を失ったか(pve1/pve2/authy/quory/sophos-fw の5ホスト、`id_rsa_sophos`・`ann`・後日発見された`id_ansible`まで含めて2026-08-03中に解消済み)、どのホストへの資格情報が残ったか(monnie、CloudKeyのVaultパスワード)**を実測記録から確認した。
- 対象Policyが参照する playbook 本体(`playbooks/proxmox_backup_restore_verify.yml`、`playbooks/unifi_backup_fetch.yml`、`playbooks/time_sync_check.yml`、`playbooks/cloudkey_cert_deploy.yml`、`playbooks/proxmox_patch_apply_node.yml`)の `hosts:` / `connection:` 宣言を読み、Policy本文が記す「実行元」が実際にSSH接続を要する構成かを確認した。
- `docs/ai/reviews/dev_prod_boundary/*.md` 全体を `grep` し、本レビューで指摘する5箇所(SB-090、BRV-006/043、TIME-002、UNIFI-003)が dev_prod_boundary 案件のどの文書にも一度も言及されていないことを確認した(=この案件の中で気づかれ改訂された形跡がない)。

## Summary

baseline項目1(ansyから本番ホストへの到達手段の消滅)に照らして、**4本のPolicyが「ansyが開発・CLIとしてpve1/pve2/authy/sophos-fwへ直接実行できる」という、現在は成立しない実行経路を許可済みの経路として記載し続けている**。これがCritical。他の項目(incident_sync退役、無人LLM廃止、git commit/push都度承認化、quory worktree自動追随、配備経路の明文化、Semaphoreテンプレートの正本化)は、11本のPolicy本文に直接抵触する記述を持たない(該当する記述自体が無い、または既に整合していた)。

## Critical Issues

### C1. `proxmox_operations_policy.md` SB-090 — ansyがProxmox操作の実行端末として記載されたまま

> `<!-- SB-090 -->` (§2.3)
> 「Ansible実行端末はansyまたはquoryに限定する。管理対象host自身から実行せず、weekly fullはProxmox nodeからの実行をpreflightで拒否する。」

`proxmox_patch_apply_node.yml`・`proxmox_patch_weekly_full.yml`等はpve1/pve2をSSH接続先(`hosts: "{{ target_node }}"`等、`connection: local`なし)とするため、実行端末はpve1/pve2へSSHで到達できる必要がある。baseline項目1により、**ansyはpve1/pve2/authy/sophos-fwに対する認証情報を1つも持たない**(`id_ansible`の後日発見・削除を含め2026-08-03に確定・実測PASS済み: `docs/ai/reviews/dev_prod_boundary/2026-08-03_024_finding_unenumerated_credential.md`)。SB-090は「ansyまたはquory」という等格の選択肢として記載しているが、現在ansyから実行しても対象nodeへ到達できず成立しない。SB-020の索引にproxmox_backup_restore_verify.ymlも含まれるため、この記述は同Policy配下の複数playbookに及ぶ。

**提案**(適用はしない): SB-090を「Ansible実行端末はquoryに限定する。ansyからの直接実行は保護対象ホストへの認証情報を持たないため成立しない」等へ改訂し、開発時の代替手段(forced command dispatchのread専用チェック、またはquory側での実行)を明記する。

### C2. `proxmox_backup_restore_verify_policy.md` BRV-006 / BRV-043 — ansyからのmanual実行が記載されたまま

> `<!-- BRV-006 -->` (§2)「monthly productionは`quory`、development / manual CLIは`ansy`を実行元とする。」
> `<!-- BRV-043 -->` (§5)「`ansy`からmanual実行する場合は、人間がmonthly実行と重複しないことを確認する。」
> §3 本文にも「`ansy`からのmanual実行(BRV-006)」への言及あり。

`proxmox_backup_restore_verify.yml`は`hosts: proxmox`→`hosts: brv_query_node`→`hosts: brv_restore_targets`という構成で、いずれも`connection: local`を指定せずpve1/pve2へSSH接続する(`roles/proxmox_exec_node`によるノード選定を含む)。C1と同じ理由で、ansyからのmanual実行は現在到達不能である。BRV-042(quoryからのmonthly schedule実行)は影響を受けない。

**提案**(適用はしない): BRV-006の「development / manual CLIはansy」を削除し、manual実行もquoryから行う旨へ改める。BRV-043の「ansyからmanual実行する場合」という前提文を、影響を受ける形へ改訂する。

### C3. `time_sync_check_policy.md` TIME-002 — ansyが実行元として記載されたまま

> `<!-- TIME-002 -->` (§2)「実行元 | quory（本番）/ ansy（開発・CLI）」

`time_sync_check.yml`は`hosts: quory:pve1:pve2:ansy:monnie:authy:sophos`という単一playで、比較対象6ホスト(自分自身を除く)全てにSSH接続する。ansyを実行元とした場合、比較対象のうちpve1/pve2/authy/sophos-fw(4/6)は認証情報が無く到達不能、quoryも同様に到達不能(quoryも保護対象に含まれる)。到達できるのはmonnieのみで、実質的にこのPolicyが定める「主要ホストの同期状態確認」という目的を満たせない。TIME-004の対象別取得方式表(sophos-fwの「SSH→Advanced Shell経由」、cloudkeyの「SSH（パスワード認証）」)も同じ前提の上に成り立っている。

**提案**(適用はしない): TIME-002の「ansy（開発・CLI）」を削除するか、「quoryのみ」へ改める。開発時の検証手段が別途必要ならその手段を明記する。

### C4. `unifi_backup_fetch_policy.md` UNIFI-003 — ansyが実行元として記載されたまま

> `<!-- UNIFI-003 -->` (§2)「実行元 | quory（本番・週次）/ ansy（開発・CLI）」

`unifi_backup_fetch.yml`は`hosts: proxmox`(ノード選定)→`hosts: unifi_backup_fetch_target`(pve1優先・pve2フェイルオーバー、`become: true`)という構成で、`connection: local`は使わない(playbook冒頭コメントにも明記あり)。実行元がansyの場合、pve1/pve2いずれへもSSH到達できないため実行不能。UNIFI-001の比較表「実行ホスト | localhost（quory / ansy） | pve1優先・pve2フェイルオーバー」の左列(cloudkey_cert_deployの実行ホスト)は`connection: local`なので影響を受けないが、右列(本Policy自身)は影響を受ける。

なお、CloudKeyそのものへのVault認証情報(`cloudkey_api_user`/`cloudkey_api_password`)はansyに残置されている(`docs/ai/reviews/dev_prod_boundary/2026-08-03_015_plan_phase4.md` D7の記述: 「UniFi / CloudKeyは同時に外していない」)。したがって**cert_renew_cloudkey_policy.mdのCCK-003「実行元（開発） | ansy（CLI 実行を許可）」は影響を受けない**(cloudkey_cert_deploy.ymlはCloudKey APIへHTTP直接アクセスするだけで、localhost実行かつpve1/pve2を経由しないため)。UNIFI-003だけがpve1/pve2への到達を前提とする点で異なる。

**提案**(適用はしない): UNIFI-003の「ansy（開発・CLI）」を削除するか、「quoryのみ」へ改める。

## Suggestions

なし(baselineスコープ内で追加の軽微な指摘なし)。

## What Looks Good

- **incident_capture_policy.md**: baseline項目2(incident_sync退役、パイプライン4段→3段)・項目3(月次無人LLMセッションの廃止)を精査した結果、本文は既に正確に改訂済みであることを確認した。IC-002/003が3段(捕捉→一次調査→見直し)を正しく記述し、§4「転送の規律」は宣言どおり節ごと消滅し、IC-043/044が新設され、ADR-005への参照には「転送段の消滅により前提ごと成立しない」という正しい注記が付いている。変更履歴(2026-08-03行)も実態と一致する。移設宣言と実内容の突き合わせ(欠陥クラス2)も行い、消失は見当たらなかった。
- **incident_capture_policy.md IC-023**: baseline項目4(git commit/push全面禁止→都度承認)についても、「Yoshinobuの都度承認を要し、自動化がこれを行うことはない」という現行の枠組みと一致する記述になっている。11本中、commit/pushに言及するPolicyはこの1本のみで、他10本には抵触する記述がない。
- **baseline項目5(quory worktree自動追随)・項目6(配備経路の明文化)・項目7(Semaphoreテンプレートの正本化)**: 該当する記述(worktree、手動pull前提、schedule/inventory/environmentの管理主体)が11本のPolicy本文のいずれにも存在しないことをgrepで確認した。これらはPolicyの管轄外(Context/roles領域)であり、抵触なし。
- **baseline項目8(core.md本文の書き換え)**: 「quoryに触れるか」「本番の状態を変えるか」「判断者であって実行者ではない」といったcore.md固有の文言・判断基準を複製している箇所は11本中に無い。Policy側がcore.mdの言い回しを引用して古くなるリスクを抱えていない。
- **cert_renew_cloudkey_policy.md**: CCK-003「実行元（開発） | ansy（CLI 実行を許可）」は、CloudKeyへのVault認証情報がansyに残置されたままであること(`connection: local`でpve1/pve2を経由しない)から、現在も成立している。C4で指摘したunifi_backup_fetch_policy.mdとは実行経路の構造が異なるため、同じ「ansy（開発）」という文言でも結論が割れる ——この対比は欠陥クラス「同名の機能が複数経路に存在する領域では、片方で無いことを確認しても他経路の存在を否定しない」の裏側(片方で有効なことが他方の有効性を含意しない)の実例。
- **autonomous_recovery_policy.md**: AR-092「pve1 / pve2 / ansyを復旧action対象にしてはならない」等、recovery_exec関連の記述はもともとquory側forced command dispatchを前提に設計されており、baseline項目1の変更と矛盾する記述は見当たらなかった。
- **ansible_test_safety_policy.md / ubuntu_vm_patch_policy.md / log_observability_policy.md**: baseline該当項目に抵触する記述なし。

## 未解決事項・確認できなかったこと

- **cert_renew_policy.md**の§10「初回 Home-TLS-CA 移行時の実行手順」に載るコマンド例(`ansible-playbook ... cert_renew.yml -e force_renew=true`)は実行元ホストを明示していない。CERT-004本文は「Semaphoreから実行する」と明記しているため矛盾はないと判断したが、この手順が過去に「ansyから手動で叩く」運用を想定していたかどうかまでは確認していない(commit履歴を遡っていない)。
- **proxmox_operations_policy.md SB-075**(「分類CLIはansy、quory、macOSだけで実行する」)は、AI分類CLIがdry-run結果ファイルをローカルで読むだけでpve1/pve2へのSSHを要しない可能性が高いと判断し、Critical指摘から除外した。ただし実装コード(`roles/proxmox_patch_dryrun`等の分類スクリプト)までは読んでおらず、SSH接続を内部で行わないことをコードレベルで確認していない。
- CloudKeyへのVault認証情報がansyに残っているという前提(C4の除外根拠)は、`docs/ai/reviews/dev_prod_boundary/2026-08-03_015_plan_phase4.md`の記述を根拠にしており、2026-08-04時点で実機のVaultファイルを確認したわけではない。
- 11本全てを全文読了したが、baselineスコープ外の一般的な整合性(用語統一・番号の重複等)は意図的に見ていない(依頼範囲外のため)。
