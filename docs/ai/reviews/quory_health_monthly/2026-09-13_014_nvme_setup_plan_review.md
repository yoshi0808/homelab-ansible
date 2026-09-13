## Code Review: quory NVMe取得ツール配備 実装計画(査読)

### Summary

012要求のAC-S1〜S4に対し、013計画は既存`quory_health_monthly_policy.md`(QHM-011/QHM-020)と整合する設計を示す。setup入口を`check-mode-native`とし対象検査・check時非変更・冪等導入・導入後readbackを分離、Semaphore専用template追加でscheduleは作らない、観測playbookと既存ホストroleを変更しない、実quoryへの操作はcommit/push後にYoshinobuがSemaphoreで行う配備順序になっており、Critical/Major該当の欠陥は見つからなかった。

### Critical Issues

なし。

### Major Issues

なし。

### Suggestions

| # | 該当箇所 | Issue | Severity |
|---|---|---|---|
| 1 | 013計画1「導入後のコマンドreadback」 | AC-S2は「コマンドが使えなければ成功扱いしない(rc非0)」を明示要求するが、計画本文は「readbackを分ける」とフェーズ分離のみ述べ、readback失敗時にjobを非0で終える契約(assert/failの明記)までは書いていない。012要求P1に同旨の記述はあるため実装時に見落とされる可能性は低いが、計画側にも1文残すと再査読の手間が減る | Suggestion |
| 2 | 013計画2「Semaphoreのtemplate catalogへ手動用setupテンプレートを追加」 | 追加するtemplateの`class`(SAFE/SEMI-SAFE等、`roles/semaphore_templates/defaults/main.yml`のclass基準)が計画に明記されていない。パッケージ導入を伴うため実装時にSEMI-SAFE相当になると見込まれるが、計画段階で触れておくと実装・レビューの往復が減る | Suggestion |

### What Looks Good

- AC-S1/AC-S4(check時無変更・schedule非追加): `check-mode-native`分類(`ansible_test_safety_policy.md` TS-014)に沿って対象検査を`check_mode: false`、パッケージ導入を`--check`下で非実行とする設計であり、`playbooks/`に同分類の`setup`系playbook(`alloy_setup.yml`、`recovery_probe_setup.yml`等)が多数存在し確立済みパターンを踏襲している。
- quory限定境界: 001/002の観測roleと同様に「quory限定のsetup playbookとrole」「事前の対象検査」を明記しており、AC-S1の「quory以外へ接続せず」と整合する。
- 既存経路の非破壊: 「観測playbookと既存ホストのroleは変更しない」を明記し、`playbooks/quory_health_monthly.yml`および既存Proxmox月次経路への影響を排除している。
- 実行境界の遵守: ansyから`quory`への到達手段が無い(`execution_boundary_policy.md` EXEC-003)ことを踏まえ、Implementer/CodexReviewerはローカル検証(構文・lint・guard/check境界)に限定し、Testerも実quoryでのパッケージ導入・CLI実行・健康ジョブ再実行を明示的にNot Runとしている。これはEXEC-050(Implementer/Reviewerは実ホストへansibleを実行しない)およびEXEC-052(Testerが使える検証環境に`quory`実機が含まれない)と一致する。実host名入りinventoryを decoy と呼ばない旨も、`docs/ai/core.md`のdecoy 3条件(実host名を書かない)を正しく踏まえている。
- 配備順序: commit/push → Yoshinobuによるtemplate setup check→apply→readback → 専用setup check→apply→readback → 月次ヘルスジョブ`--check`再実行、という順序がAC-S3・AC-S4の前提(setup適用後でなければ`tool_unavailable`解消を確認できない)と一致し、Notion/schedule有効化を別工程のまま維持している。

### 確認範囲

- 012requirement全文、013plan全文、001/002(既存quory月次要求・計画)、`docs/ai/policies/quory_health_monthly_policy.md`全文、`docs/ai/policies/execution_boundary_policy.md`全文、`docs/ai/policies/ansible_test_safety_policy.md`のtester-gate分類節(check-mode-native定義)。
- `playbooks/*.yml`の`tester-gate: check-mode-native`分布(grep)で既存setup系playbookとの整合を確認した。
- Semaphore #1083のtool_unavailable/rc=2観測はrequirement記載を確認したのみで、実際のSemaphoreジョブ・quory実機・APIには接触していない。指定成果物ファイル以外は変更していない。

### 未解決事項

- Suggestion #1・#2はいずれもnon-blockingで、実装/計画確定段階でCoordinator・Implementerが対応してよい。
- 012オープンクエスチョン(`nvme-cli`導入後に実NVMeで`nvme id-ctrl`/`smart-log`が成功するか)は013計画も「配備前に残る判断」として明記しており、実機readback前提を崩していない。

### Verdict

Approve(Critical/Major無し)。
