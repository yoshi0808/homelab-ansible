# 検証記録: commit `3fbb9e8`(authy側の `until`/`retries` 追加)

作成: 2026-07-30 / Coordinator
対象commit: `3fbb9e8` Add retry to authy's post-reboot service checks, correct incident severity

## このファイルが存在する理由

**commit時点でこの変更の検証記録が存在しなかった。** 既存の `2026-07-30_001_test_result.md` は commit `da05584`(monnie側の外部 `wait_for` 解消と `rescue` 文面)だけをカバーしており、`3fbb9e8` はTesterを通さず、Coordinatorのローカル確認だけでcommitされた。

事後のPolicy照合(`2026-07-30_002_policy_review.md` Critical 1)がこれを検出した。本ファイルは**遡って記録を残すもの**であり、「検証が済んでいた」ことを主張するものではない。実施していない検証は下記「未実施」に明示する。

Tier 2 と判定したためReviewer / Auditorは工程に含まれないが、**Tier 2 は「Testerにだけ実機検証を依頼する」レーンであり**(`skills/delegation-tier/SKILL.md`)、その依頼を行わなかったことは判定に沿っていない。increment（追加修正）を同一セッション内の続きとして扱い、Tier判定と工程の宣言を省いたことが原因である。

## 実施した検証(Coordinatorによる、decoyのみ)

`until` が `failed_when: false` と併用しても正しくリトライするかを、scratch上のstubスクリプトで実測した。読解だけで済ませていない。

| # | 確認したこと | 方法 | 結果 |
|---|---|---|---|
| 1 | `until` の条件が偽のあいだリトライされる | 3回目に初めて非空を返すstubを `command` で呼び、`until: stdout \| length > 0` / `retries: 5` / `delay: 1` / `failed_when: false` を付けて実行 | **PASS**。`FAILED - RETRYING`が2回出力され、`attempts: 3` で条件成立、`failed=0` |
| 2 | `failed_when: false` が `until` を無効化しない | 同上(両方を同時に指定した状態で1を確認) | **PASS**。両立する |
| 3 | 変更後のplaybookが構文的に妥当 | `ansible-playbook --syntax-check playbooks/ubuntu_nightly.yml` | **PASS** |
| 4 | IPアドレスの混入が無い | 変更ファイルに対する `grep -E '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b'` | **PASS**(0件) |

独立照合として、事後Policy照合のReviewerが同じ `until`/`retries`/`failed_when` の組み合わせをdecoyで再検証し、**リトライの収束とリトライ使い切り時に fail しないことの両方**を確認している(`2026-07-30_002_policy_review.md`)。

## 未実施

- **実機での検証を行っていない。** authy を検証目的でリブートしていないため、`reboot` 直後に `until` が実際に何回リトライするか、freeradius / 1812 / 1813 が待ちの範囲内で揃うかは未観測である。
- `--check` 実行も行っていない(`da05584` のTester検証では実施済みだが、`3fbb9e8` の変更後には流していない)。**変更箇所は `when: not ansible_check_mode` のblock内にあり `--check` では到達しないため、`--check` を流しても今回の変更は検証できない。** これは省略ではなく、この経路では取得不能な観測である。

実機での確認は `docs/ai/status.md` のWatch行が持つ。次に authy の `reboot_required` が true になる夜に、`[ubuntu_nightly] OK - authy` が飛ぶことで確認される。

## 数値の根拠

`retries: 12` / `delay: 10`(最大120秒)は**Policyに規定が無く、実装判断である**。事後Policy照合で `ubuntu_vm_patch_policy.md`(UV系)・`ansible_test_safety_policy.md`(TS系)・`autonomous_recovery_policy.md`(AR系)のいずれにも reboot後post-checkの待ち時間・リトライ回数の規定が無いことが確認された。

根拠は「monnie側の `wait_for timeout: 120` と揃える」という一点のみである。本番ログ(`semaphore-412`)ではfreeradiusは約20秒で `active` になっており、120秒は実測に対して6倍の余裕がある。

Policyへ数値規定を追記するかは未決。`docs/ai/status.md` へ起票済み。
