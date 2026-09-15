# Code Review: semaphore_reconcile_daily_sync Phase 2 第4次査読後の再査読

## Summary

`_009` Blocking 2件はいずれも解消した。run reportから後続markerの成否を除いたことでpublish順序・immutability・参照先の先行存在を同時に満たせる。canonical値をrole変数ではなくfilter pluginのモジュール定数へ移す設計も、現行reserved-name guardの構造上、通常実行を通しつつ廃止名の`-e`指定だけを拒否できる。これまで解消済みの項目にも回帰はない。

## Critical Issues

該当なし。

## Blocking Issues

該当なし。

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_reconcile_daily_sync/2026-09-15_001_requirement.md` | 91 | P0-8aの表とAC13は7ケースなので、見出しに残る「6ケース」を「7ケース」へ揃える。 | Documentation |
| 2 | 同上 | 169 | `semaphore_schedules_would_newly_activate`はdesired=falseなら発火せず、before=true/desired=trueでも発火しない。非canonicalでのfalse強制全体の不変条件ではなく、「false→trueの混入を止める防御」であることへ表現を限定すると、実装者が既存active=trueの倒し忘れまで検出できると誤解しない。 | Correctness |

## `_009` Blocking 2件の解消判定

| `_009` # | 判定 | 根拠 |
|---:|---|---|
| 1 run reportとmarkerの順序 | **解消** | run reportは`status`までを持ち、後続markerの成否を持たない契約へ変更された(P0-8)。これにより、①reportを原子的publish、②既存reportを指すmarkerを原子的差し替え、の順序とreportのimmutabilityが両立する。marker失敗時も、当該runの終了時にはrc非ゼロと通知試行で事象を観測でき、markerが当該`run_id`を指さない状態が成功印を更新できなかった事実を表す。reportの`status=success`はapply/verifyの結果として正しく、marker publish結果との意味の混同もない。AC13a/AC13bは失敗状態と参照先の先行存在をそれぞれ固定している。 |
| 2 canonical変数とreserved-name guard | **解消** | 変数自体をdefaultsから除き、guardのmessage側・when側双方のliteral allowlistからも除けば、通常実行時にはその名前が`lookup('varnames', '^_?semaphore_schedules_.*')`へ現れない。一方、同名を`-e`で渡すと定義済み名として列挙され、allowlist補集合に残ってwrite前にfailする(`roles/semaphore_templates/tasks/schedules_validate_config.yml:55-68,95-130`)。モジュール定数はAnsible変数名ではないためguardの対象にならず、1引数filterの比較相手も`-e`では変更できない。P0-14も同じ定数から値を得るためcanonical値の二重管理を作らない。AC19eが通常実行と廃止名指定の双方を固定している。 |

## 以前に解消した項目の回帰確認

| 出典・項目 | 判定 | 根拠 |
|---|---|---|
| `_008` #1 計画/payload分離 | **回帰なし** | P0-7、AC11、AC11aは変更されていない。write前に対象と合算件数を確定し、新規templateの数値idだけをtemplate apply後に解決する契約を維持している。現行template POSTは作成結果の`json.id`を検証・保持するため、この二段階は成立する(`roles/semaphore_templates/tasks/apply.yml:40-79,113-126`)。 |
| `_007` #3 鮮度閾値 | **回帰なし** | P0-13/AC16は正常位相20時間40分、閾値24時間、1回欠測44時間40分の境界を維持している。marker失敗時も古い成功印を維持するため、鮮度判定の意味を壊さない。 |
| `_007` #4 probe識別子 | **回帰なし** | P0-12/AC17のremove/keep/add対応は変更されていない。 |
| `_007` #5 04:00 schedule | **回帰なし** | P0-14/AC18の5フィールド、bootstrap参照、`params.dry_run`を置かない契約を維持している。canonical値の取得元だけが変数から同一plugin定数へ変わり、期待値自体は変えていない。 |
| `_007` #6 orphan baseline | **回帰なし** | P0-11/AC15の正規化key、sorted list、重複検出、baseline不正時failは変更されていない。 |

## What Looks Good

- marker publish失敗をreconcile本体の`status`から分離したため、`status=success`の意味がapply/verify成功として一貫した。成功印を更新できなかった回をrc非ゼロにし、markerを据え置くため、生存確認も誤って新しい成功と扱わない。
- canonicalの正本を外部変数名前空間から除く設計は、現行guardが変数の出所を識別できない制約を回避している。allowlistからdefaultだけを外して通常実行まで壊す問題は残らない。
- 非canonicalでのeffective active=falseはdiff・POST/PUT・verifyの全段に適用され、既存active=trueだけが異なる場合も書き込み対象になる。`semaphore_schedules_would_newly_activate(False)`はfalseなので正常経路とhelperは矛盾しない。
- 新しいshell/command、秘密値の複製、既存ロジックの別実装は要求しておらず、セキュリティおよび重複・再利用観点の追加findingはない。

## 確認済み事項

- reserved-name guardは現在定義済みのprefix一致名を列挙し、literal allowlistに無い名前を拒否する。出所は判定しないため、対象変数をdefaultsから完全に除く今回の前提が重要である。実装時はallowlistがmessage側とwhen側の2箇所に重複しているため、双方から旧名を削除する必要がある。
- 現行のcanonical比較filterは2引数だが、正規化処理を保持したまま比較相手をモジュール定数へ移して1引数化できる(`roles/semaphore_templates/filter_plugins/semaphore_schedules.py:884-916`)。P0-14から同じ値を得る公開filter等の接続方法は実装差分で確認する。
- marker失敗の3点は、当該run終了時の失敗判定と成功印の健全性監視には足りる。ただしmarkerは可変なので、後続成功がmarkerを進めた後は、その過去runのmarker publish失敗をrun report単体から復元できない。現要件は永続的なmarker試行履歴を要求しておらずblockingとはしないが、将来監査履歴を要するならimmutableな別成果物が必要である。
- 本査読では実ホスト、Semaphore API、Slack、Notionへ接触していない。

## 未確認事項・残存リスク

- module定数の定義、旧defaultとallowlist 2箇所の削除、全呼び出しの1引数化、P0-14の同一定数参照は未実装であり、実装差分レビューで一組として確認する必要がある。
- P0-7の計画用filter/taskとapply後payload確定も未実装であり、実装差分レビューではpending参照、template部分失敗後の再実行、check modeを確認する必要がある。
- schedule起動時のsurvey既定値適用とcatalog外bootstrap template参照可否は、P0-14が指定するansyでの実装前観測待ちである。

## Verdict

**Approve**

`_009`のMajor 2件は閉じた。Suggestion 2件は契約の意味を変えずに文書精度を上げるものであり、Phase 2着手を妨げない。
