# Code Review: ubuntu_nightly.yml commit `da05584` / `3fbb9e8` の事後Policy照合

対象: `playbooks/ubuntu_nightly.yml`、`docs/ai/memory/incidents/2026-07-30_ubuntu-nightly-monnie-external-port-wait.md`、`docs/ai/status.md`
方式: 独立Reviewerによる事後照合(Tier 2判定によりcommit前レビューなし)。実ホスト接続・実行なし。`--syntax-check`とscratch decoy(`ansible_connection: local`)のみ使用。

## 適用したPolicy/Context(選定は自分で行った)

- `docs/ai/policies/ubuntu_vm_patch_policy.md`(UV-042〜UV-045、UV-069、AR系との接続点)
- `docs/ai/policies/ansible_test_safety_policy.md`(TS-005〜TS-015、`check-mode-native`の実装方式)
- `docs/ai/policies/autonomous_recovery_policy.md`(AR-077 mute契約)
- `docs/ai/context/operations/healthcheck.md` §1(shell/Ansible責務分離)
- `docs/ai/core.md`「Ansible変更の共通ゲート」
- `skills/incident-recording/SKILL.md`、`docs/ai/memory-classification.md`
- `skills/ansible-implementation-style/SKILL.md`「check_modeの実装上の落とし穴」(TS-028が参照)
- `docs/ai/status.md` 冒頭「このファイルの規律」
- 追加で参照: `docs/ai/roles/reviewer.md`(成果物形式)、既存の`docs/ai/reviews/ubuntu_nightly_reboot_check/2026-07-30_001_test_result.md`(Coordinatorの列挙に無かったが、対象と同ディレクトリに既存する検証記録であり、2commit目の検証有無を判定するために不可欠だったため自分で発見して読んだ)

Coordinatorの列挙に**欠落があった**: `docs/ai/policies/autonomous_recovery_policy.md`のAR-077(mute契約)自体は列挙どおり確認したが、**既存test_resultファイルの存在と、それがcommit 1件分しかカバーしていない事実**はCoordinatorの依頼文に含まれておらず、自分で`ls`して発見した。これが最大の finding の根拠になっている。

## Summary

commit `da05584`(wait_for修正+rescue文面修正)は既存test_resultで`--check`完走とrescue Jinjaの3パターンをdecoy検証済みで、check-mode-native分類・recovery mute窓との矛盾は無い。一方 commit `3fbb9e8`(authy側`until`/`retries`追加+Incident重大度訂正)は**検証記録が一切無いまま本番playbookへ入った**。実装ロジック自体はdecoyで独立に再現し正しいことを確認できたが、これは今回のReview時点で初めて行った検証であり、commit時点では未検証だった。さらに、severity訂正の根拠であるIncident記録に**日付の内部不整合**があり、その誤りが`docs/ai/status.md`のWatch行へそのまま転記されている。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| 1 | `docs/ai/reviews/ubuntu_nightly_reboot_check/` (存在しないファイル) | - | commit `3fbb9e8`(`until`/`retries`追加、authy側)に対応する test_result / review 記録が存在しない。同ディレクトリの`2026-07-30_001_test_result.md`は`da05584`時点の変更(2項目)だけを対象にしており、日時(commit 06:33、test_result同時刻帯)から見てもcommit 1のみをカバーする。commit 2は本番playbookの`tasks/*.yml`相当部分(reboot直後の破壊的block内)に新規の制御フロー(`until`/`retries`)を追加したにもかかわらず、`--check`実行・decoy検証のいずれの記録も無い。Tier 2判定でReviewerを通していない以上、この2点目の変更は**一度も他者の目にも機械的検証にも触れないまま本番投入された** | Critical |
| 2 | `docs/ai/memory/incidents/2026-07-30_ubuntu-nightly-monnie-external-port-wait.md` | 3, 62-73 | 日付の内部不整合。冒頭(L3)は「2026-07-23 03:35 JST」を前回発生日とするが、本文(L64)は同じ事象を「1週間前の2026-07-22」と書き、ログブロックの見出し(L67)も`semaphore-412 (2026-07-22)`とラベルしている。ログの実タイムスタンプは`18:33:03 UTC`(2026-07-22)= **2026-07-23 03:33 JST**であり、L3のJST変換が正しく、L64/L67のみUTC日付を event date として誤用している。さらにL73「timeoutの間隔(...)まで**2026-07-29**と一致する」は文脈上どのイベントとも一致せず(現在事案は2026-07-30、前回は2026-07-23)、孤立した誤記と判断される。severity訂正(commit `3fbb9e8`のcommit meta自体が"correct incident severity"と明言)の根拠になっている「決定論的に毎週発生している」という主張の日付が文書内で3通り(07-22/07-23/07-29)に割れている状態であり、再発頻度の主張そのものの信頼性を損なう | Critical |
| 3 | `docs/ai/status.md` | Watch行「ubuntu_nightly の monnie / authy リブート経路...」 | 上記finding 2の誤った日付(`2026-07-22`・`2026-07-29`)がそのまま転記されている(「2026-07-22・07-29の2回を semaphore ログで確認済み」)。正しくは07-23・07-30のはずである。加えて、この転記自体が`status.md`冒頭の規律4「値を二重に持たない。他に正本があるものは参照だけ書く」に反する — Watch行は一次記録(Incidentファイル)へのリンクを既に持っているにもかかわらず、具体的な日付という一次記録側の値を複製し、しかもその複製元の誤りをそのまま増幅している | High |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `playbooks/ubuntu_nightly.yml` | 155-159, 165-169, 175-179 (radius_servers)、コメントL147/L144 | `retries: 12` × `delay: 10`の実際の最大待ち時間は(retries-1)×delay=110秒であり、コメントや Incident 記録が主張する「最大120秒」「monnie側`wait_for timeout:120`と揃えた」は正確には一致しない(110秒 vs 120秒)。実害はないが、"揃えた"という主張が事実と10秒ズレている | correctness-of-comment |
| 2 | `docs/ai/memory/incidents/2026-07-30_ubuntu-nightly-monnie-external-port-wait.md` | 100 | 「既存の同型実装は`roles/proxmox_backup_restore_verify/tasks/main.yml:311`」という引用は行番号(311)自体は正確だが、その実装は`ansible_failed_result.msg`だけを使い、`ansible_failed_task.name`もループ`results`のselectattr処理も持たない。"同型"は言い過ぎで、参照する実装のカバー範囲を過大に主張している | duplication-reuse-check |
| 3 | Policy側の欠落確認(該当なし) | - | `docs/ai/policies/ubuntu_vm_patch_policy.md`(UV-044/045)、`docs/ai/policies/ansible_test_safety_policy.md`、`docs/ai/policies/autonomous_recovery_policy.md`のいずれにも、reboot後post-checkの**待ち時間・リトライ回数・タイムアウト値**に関する規定は無い。今回実装が持ち込んだ`retries:12`/`delay:10`/`timeout:120`は完全に実装判断の値であり、Policyとの数値的な矛盾は存在しない(比較対象が無いため)。AR-077のmute値(120分)とも矛盾しない(下記What Looks Good参照)。**追記を検討するかはCoordinator/Yoshinobuの判断**であり、本Reviewは欠落の指摘のみに留める | policy-gap-note |

## What Looks Good

- **`check-mode-native`分類は維持されている。** 破壊的block(reboot / wait_for / until-retry check / report / notify)は`when: not ansible_check_mode`で丸ごとゲートされており、2commitとも このblock境界の外へは手を入れていない。ヘッダのtester-gateマーカー文言(L2-6)は現在の実装と整合している。
- **recovery mute窓との矛盾なし。** `Set recovery mute before reboot`は`recovery_mute_minutes: 120`のまま変更されていない(AR-077の「`ubuntu_nightly.yml`はreboot対象へ120分」と一致)。今回延びた待ち時間の理論上の最大値は、authy: reboot_timeout(300s)+ 3チェック直列最大(110s×3=330s)=630s、monnie: reboot_timeout(300s)+ wait_forループ3ポート直列最大(120s×3=360s)=660s。いずれも120分(7200s)に対し十分な余裕があり、mute失効前に完走する。AR-077が`proxmox_patch_weekly_full.yml`にだけ360分の例外を設けている理由(「reboot後のhealthcheck retry等」で段階muteが切れる懸念)は、この程度の秒オーダーの延びには当てはまらない。
- **`until`+`failed_when: false`+`retries`の組み合わせは実装として正しい。** decoy(`ansible_connection: local`、scratch内、実system非干渉)で2パターン検証: ①3回目で条件成立するcommandが正しく`until`でリトライされ最終的に`ok`になること、②条件が最後まで成立しないケースで`retries`を使い切っても`failed_when: false`によりタスクが`ok`のまま継続し、`rescue`が誤発火しないこと。両方とも実装の想定どおりに動作した(下記参照)。
- **`ss`/`systemctl`のUDPチェックにコマンドインジェクション相当の懸念なし。** ポート番号・unit名は固定文字列で、外部入力を埋め込んでいない(`skills/ansible-security-review/SKILL.md`の観点上、この差分には該当する懸念なし)。
- **healthcheck.md §1の責務分離に抵触しない。** 今回追加された`until`条件はリトライの継続条件であり、判定・分類(`nightly_criticals`の算出)は既存どおり後段の`Evaluate service and port results`が担う。shellファイル(`files/*.sh`)自体への変更はない。
- **`wait_for`のhost省略がloopbackにfall backすることを`ansible-doc`で確認済み**(`ansible-doc`の既定値がループバックアドレス)。Incident記録の技術的主張と一致する。
- 既存test_result(`2026-07-30_001_test_result.md`)がカバーする範囲(`--check`完走、rescue Jinjaの3パターン)は妥当な検証で、承認された操作範囲(実リブート無し、Slack実送信無し、UFW非接触)の遵守記録も明確。

## Verdict

**Request Changes**(ドキュメント/記録側の是正が対象。playbook本体の追加ロジックはdecoy再検証の結果、機能的には正しいことを確認したため、コード自体へのRequest Changesではない)。

- 必須: commit `3fbb9e8`のauthy側変更に対する検証記録(最低限`--check`完走確認、可能ならdecoyでの`until`/`retries`/`failed_when`挙動確認)を追加する。本Reviewで代わりに実施した decoy 検証(下記)を転記・正本化してよい。
- 必須: Incidentファイルの日付(L3/L64/L67/L73)を`2026-07-23`(前回)・`2026-07-30`(今回)に統一する。
- 必須: `docs/ai/status.md` Watch行の日付表記を修正後のIncidentファイルに合わせる。
- 任意: retries×delayの実際の最大待ち時間(110秒)の表記訂正、および`proxmox_backup_restore_verify`引用のカバー範囲の言い過ぎ訂正。

## 実施したdecoy検証(本Review内、scratch限定)

- `decoy_until_retry_test.yml`: `ansible_connection: local`、3回目で`echo active; exit 0`になる`shell`を`until`/`retries:5`/`delay:1`で実行 → `FAILED - RETRYING`×2の後`ok`、`attempts=3`で正しく収束。
- `decoy_until_exhaust_test.yml`: `/bin/false`を`until`/`retries:2`/`failed_when: false`で実行 → `retries`使い切り後もタスクは`ok`として扱われ、`rescue`は発火しなかった(`rescued=0`)。
- いずれも実ホスト名・実IPを含まず、`/tmp/claude-.../scratchpad/`配下のみに作成し、リポジトリへは書き込んでいない。

## 未解決事項

- commit `3fbb9e8`の実機検証(monnie/authyの次回reboot)は`docs/ai/status.md` Watchが引き続き持つ。今回のReviewはリポジトリ内照合とdecoyに閉じており、実機到達性を新たに確認したものではない。
- Incident記録の日付訂正自体をこのReviewerが直接書き換えることはしない(対象実装を自ら変更しない、というReviewer制約による)。findingとして返す。
