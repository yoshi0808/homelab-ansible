# レビュー(構造変更側 / R1)— core.mdの圧縮と、Knowledgeの渡し方

2026-08-05 / Reviewer(独立subagent)。対象は未commitの `git diff` 全体(8ファイル)。担当範囲はCoordinatorの依頼どおり構造4点(規範の消失/宙ぶらりん参照/削らなかったことの妥当性/実装中の判断2件)のみ。I1/S1/R1/R2/T1/T2/A1/C1として追加された留意事項の中身の是非は範囲外とし、評価していない。

## Summary

構造変更として重大な欠陥は見つからなかった。旧「AI間連携と成果物」節の全項目(4bullet + 冒頭文 + 末尾段落)を逐項目で突き合わせた結果、すべて到達先を確認できた。`memory-classification.md` §4の表→本文化も、旧表が述べていた内容(Coordinatorの参照範囲、Auditorの「読まない」、Role別粒度の廃止)を欠落なく引き継いでいる。宙ぶらりん参照は規範層・実装層とも検出しなかった(完全パス・略記・散文言及を別々に検索)。`§1`の8項判定表は現物と一致し、「落とせる1件」(quory直接編集・commit禁止)を残した判断も2026-08-04の先例と整合する。実装中の判断2件(着手時への統一、lessons参照2件の解消)はいずれも既存の矛盾を解消する妥当な選択であり、`document-norm-review`の扱いとの差にも一貫した理由がある。

Minor 1件のみ指摘する。blocking findingは無い。

## 確認済み事項(確認手段を明示)

- `git show HEAD:docs/ai/core.md` を取得し、`docs/ai/core.md` の現在の内容と逐項目で突き合わせた(旧「AI間連携と成果物」4bullet + 冒頭文 + 末尾段落、旧「安全機構がブロックしたとき」、旧「Ansible変更の共通ゲート」冒頭2行)。
- `git diff docs/ai/memory-classification.md docs/ai/role-context-matrix.md docs/ai/roles/ skills/ansible-implementation-style/SKILL.md` を読んだ。
- `git grep` で以下を完全パス表記・略記の両方で検索し、規範層(`.claude/agents/`、`docs/ai/roles/`、`docs/ai/role-context-matrix.md`、`skills/*/SKILL.md`、`docs/ai/policies/`、`docs/ai/context/`、`playbooks/`、`roles/`、`inventories/`、`CLAUDE.md`、`AGENTS.md`)に残存が無いことを確認した。
  - `"AI間連携と成果物"`(規範層への残存ゼロ。過去のreview記録2本と`status.md`のNext行のみ、いずれも履歴/未クローズ案件の記述であり許容範囲)
  - `"subagentが共通して守ること"`(全4 agent定義・`skills/subagent-briefing/SKILL.md`・`roles/semaphore_templates/filter_plugins/semaphore_templates.py`のいずれも有効)
  - `"必要時(対象関連)"`(規範層への残存ゼロ。`status.md`のNext行のみ)
  - `"Role別Knowledge参照範囲"`(残存ゼロ)
  - `core.md#`形式のアンカー参照(ゼロ件、見出しレベル変更`###`→`##`の影響なし)
- `docs/ai/memory/lessons/dynamic-include-escapes-static-and-rescue.md`、`docs/ai/memory/lessons/verify-through-the-consuming-filter.md` の全文を読み、`skills/ansible-implementation-style/SKILL.md` へ差し替えられた本文と突き合わせた。
- `docs/ai/roles/implementer.md` L12 を読み、`verify-through-the-consuming-filter` の実質(`repr`確認、`None`と空文字列の区別、消費側フィルタまで通す)が既にRole文書へ昇格済みであることを確認した(分析§2「不採用」表の記載どおり)。
- `docs/ai/roles/{tester,auditor}.md` を全文読み、Knowledge/lessonsへの読取依存が残っていないことを確認した(`implementer.md`/`reviewer.md`も同様に確認済み)。
- `docs/ai/role-context-matrix.md` を全文読み、「Auditorの参照範囲」節が無傷であること、`memory-classification.md` §4への言及が節番号(4節)であり旧見出し文言に依存していないことを確認した。
- `.claude/agents/*.md` の全文を読み、4本とも `docs/ai/core.md`「subagentが共通して守ること」への言及が正しく有効なままであることを確認した。
- `python3 scripts/check-doc-consistency.py` を実行し、check1/2/3すべてOK(104/8/91件比較)であることを独立に再現した(implement記録の主張どおり)。
- `docs/ai/roles/coordinator.md` を全文読み、実ホストへの非冪等操作の承認境界節・quory到達不能の記述(L71-72, L79)が、分析§1の判定表の前提(能力4種の現存)と矛盾しないことを確認した。
- `docs/ai/memory/incidents/2026-08-02_auditor-reverted-coordinator-uncommitted-edits.md` を読み、判定表項目#2(「自分が作った変更以外を元に戻さない」)が「2026-08-02に実際に踏まれている」という分析の主張の裏付けを確認した。
- `docs/ai/reviews/norm_docs_post_phase4_sweep/2026-08-04_005_disposition.md` を参照し(implement記録・分析からの引用先)、`core.md` L52「quory上でコードを直接編集・commitしない」を残す判断が同日の先例と同型であることを確認した(該当ファイルの当該記述の存在のみ確認。ファイル全体は読んでいない)。
- `docs/ai/reviews/knowledge_delivery_and_core_compression/2026-08-05_001_analysis.md`、`2026-08-05_002_implement.md` を全文読んだ。

## 1. 規範の消失

**消失なし。** 旧「AI間連携と成果物」節の内容を項目単位で突き合わせた結果:

| 旧項目 | 到達先 |
|---|---|
| 冒頭文(Role間連携の定義、対話ログ非永続) | 新節冒頭へそのまま移動 |
| 成果物本文と監査証跡はリポジトリ内へ保存 | 新節の1項目目に verbatim で存在 |
| 報告には対象パス・短い結果・判断・未解決事項を載せる。中間ログや長い引用を貼らない | 新節の2項目目に verbatim で存在 |
| 受信側は報告の説明だけを信頼せず、指定ファイルと現在のdiffを読む | 「先行成果物・先行subagentの主張を、現物で確かめずに引き継がない」の項目へ「説明だけを信頼せず、指定されたファイルと現在のdiffを自分で読む。」として吸収 |
| 不一致や競合を見つけた場合は勝手に統合せず、停止してCoordinatorへ返す | 末尾項目「上記に反しそうな状況になったとき、および記録どうしの不一致や他Agentの変更との競合を見つけたとき」へ吸収 |
| 文書の長さは案件が必要とする範囲に合わせる(段落) | 報告の項目(2項目目)へ畳まれ、既存節更新の指示も含めて全文残存 |

旧「安全機構がブロックしたとき」の2項統合(「被ブロック側が判定しない」「Coordinatorも解除できない」→1文)も、両者の主語(被ブロック側・Coordinator)がともに残る形で1文化されており、意味の欠落はない。

「subagentが共通して守ること」8項目(元の判定表対象)は全項目が新節に現存する。#5(先行成果物の主張を鵜呑みにしない)へ1文追加された以外、文言はほぼ不変。

**論点として検討し、問題なしと判断したもの**: 旧「AI間連携と成果物」は`##`レベルの親節で、その4bulletは体裁上「Role間連携」全般(Coordinator自身が受信者になる場合を含みうる)に読める書き方だった。統合後はすべて「subagentが共通して守ること」という、明示的にsubagent向けの節の中に位置する。これにより「受信側は報告を鵜呑みにしない」という一般原則が、Coordinator自身の行動規範としてはcore.mdから見えなくなる可能性を検討したが、`docs/ai/roles/coordinator.md` L101(本diff対象外、既存)が「先行成果物・先行subagentの主張を、現物で確かめずに引き継がない。記録に書かれた判定・引用・残存リスクは、それ自体が検査対象である。」を独立に持っており、Coordinator向けの適用範囲は別途担保されている。**実害なし。**

`memory-classification.md` §4 の表→本文化も同様に逐項目突き合わせた。旧表の5行(Coordinator/Auditor/Implementer/Reviewer/Tester)のうち、Auditorの「読まない、参照範囲は role-context-matrix.md「Auditorの参照範囲」が正本」という記述は新文面から見出しへの直接参照が消えているが、`role-context-matrix.md`「Auditorの参照範囲」節自体は無傷で現存し、かつその節はもともとKnowledgeについて何も述べていない(案件フォルダ/status.md/参照先の3項目のみ)ため、参照を落としても実害はない。Implementer/Reviewer/Testerの個別粒度(「対象role/playbookに関連する」「過去レビューで見つかった」「障害・テスト関連の」)は、①の方針変更(全subagent一律「読まない」)により意味を持たなくなったための意図的な削除であり、消失ではなく方針転換の反映として妥当。

## 2. 宙ぶらりん参照

**検出ゼロ。** 完全パス表記・略記の両方で以下を確認した。

- `"subagentが共通して守ること"` — `.claude/agents/`4本、`skills/subagent-briefing/SKILL.md` L12、`roles/semaphore_templates/filter_plugins/semaphore_templates.py` L12の3系統いずれも有効。実装記録の主張と一致。
- `"AI間連携と成果物"` — 規範層に残存ゼロ。ヒットしたのは過去案件記録2本(履歴として妥当)と`docs/ai/status.md`のNext行(未クローズの当該案件自身の記述であり、実装記録が「案件クローズ時に削除する」と明言・計画済み)。
- `"必要時(対象関連)"` — 規範層に残存ゼロ、`status.md`のNext行のみ(同上)。
- `docs/ai/memory` / `lessons` への参照を`skills/`・`docs/ai/roles/`・`.claude/agents/`横断で洗い直した。`skills/incident-recording/SKILL.md`(書き込み先としての言及、読取依存ではない)、`skills/document-norm-review/SKILL.md`(「根拠:」形式の帰属表記、本文が自己完結)、`docs/ai/roles/coordinator.md`(Coordinator自身は引き続きKnowledgeを読む)の3ファイルのみがヒットし、いずれも新方針と矛盾しない。実装記録が「2件検出し是正」と報告した`skills/ansible-implementation-style/SKILL.md`の2箇所以外に、見落としは無い。
- Markdownアンカー形式(`core.md#...`)の参照はゼロ件で、見出しレベル変更(`###`→`##`)による実害はない。

`scripts/check-doc-consistency.py` を独立実行し、check1/2/3すべてOKを確認した(実装記録の主張を追試)。

## 3. 削らなかったことの妥当性

分析§1の8項判定表を現物で検算した。

- 判定表が前提とする「ansyに残る能力4種」(①repo file r/w ②git全操作 ③Slack webhook ④monnie/ansy到達)は、`docs/ai/core.md`「開発と本番の境界」節と`docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」表(L71-73、L79)の記述と矛盾しない。特にL72「到達手段が無いホスト(`pve1`/`pve2`/`authy`/`quory`/`sophos-fw`)」とL73「上記以外(`monnie`/`ansy`)への非冪等操作は確認不要」の対比が、判定表の前提と正確に一致する。
- 8項目のうち#1・#2・#4・#6・#7・#8は能力の不在では代替できない(いずれもansy上で技術的に実行可能な操作の禁止であり、規則側でしか塞げない)。#5は能力の問題ではないという整理も妥当(「先行主張を鵜呑みにしない」は判断規律であり、鵜呑みにする能力自体は常に存在する)。#3(「削除・整形は#1/#2へ畳めるが報告しないは畳めない」)という分析の指摘どおり、diff上も#3はまとめられずそのまま独立項目として残されている。**8項目のうち実際に落とされたものは無く、分析の結論(「7項は能力が残り、1項は一部しか畳めない」)と現物が一致する。**
- 「落とせる1件」= `core.md` L52「quory上でコードを直接編集・commitしない」は、diff上変更されていない(現存)。**分析の推奨どおり削除されておらず**、2026-08-04の先例(`docs/ai/reviews/norm_docs_post_phase4_sweep/2026-08-04_005_disposition.md`)と同型の判断が踏襲されている。判断そのものも妥当と考える — 認証情報が復活した場合に備えて意図を保持するという理由は、コストが「1行を残す」だけであり、リスクとの釣り合いが取れている。

判定表・推奨のいずれについても、現物との齟齬は見つからなかった。

## 4. 実装中に判断した2件

### 4-1. `role-context-matrix.md` Coordinator列「起動時」→「着手時」

**妥当と判断する。** `docs/ai/memory-classification.md` の旧表は変更前から一貫して「**着手時**にCoordinator自身が確認する」と書いており(このdiffで新規に着手時化したのではなく、元々着手時だった)、`role-context-matrix.md`側だけが「起動時」で食い違っていた。①の対象行を書き換える以上どちらかへ寄せる必要があり、より整合の取れている側(`memory-classification.md`)へ揃えたのは合理的。加えて、Coordinatorのセッションは複数案件を跨ぐことがあり、「重要Decisionを常に前提とする」という将来性は残しつつ、案件ごとの着手時点で確認し直す設計のほうが、セッション起動時1回きりの確認より Decision の鮮度維持に資する。**新たな矛盾は生じていない**(`memory-classification.md`との整合を`git grep`で再確認済み)。

### 4-2. `skills/ansible-implementation-style/SKILL.md` のlessons参照2件の解消

**妥当と判断する。** 2件とも、①によってImplementerがKnowledgeを読まなくなった結果、参照が実質「読めない指示」になる状態(規範の消失または宙ぶらりん化の予備軍)だった。

- `dynamic-include-escapes-static-and-rescue.md`: 分析では蒸留候補として不採用(発火機会が稀)だったが、参照が既存であったため掃引で拾われた。本文へ要点(静的検査もrescueも届かない、ファイル欠落のみ捕捉可、影響範囲を数える)をインライン化しており、原文の要点(3制約のうち1・2、帰結、適用)を欠落なく圧縮できている。原文の詳細(PLAY RECAPのfailed数の変化、適用4項目目「防御を置かない理由をコメントに残す」)は落ちているが、いずれも実装スタイルの中核指示ではなく、Minor扱いとする(下記)。
- `verify-through-the-consuming-filter.md`: 現物を確認したところ、`skills/ansible-implementation-style/SKILL.md`側の元の参照は「同型の観点」という比喩的な引用であり、実質的な指示内容(`repr`確認、`None`と空文字列の区別、`default('', true)`の第2引数必須)はそもそもこのSKILL.mdには書かれておらず、`docs/ai/roles/implementer.md` L12に既に完全な形で昇格済みだった(分析§2「不採用」表の記載を現物で確認)。参照を落として一文へ言い換えても実害はない。

**`document-norm-review`との扱いの差の一貫性**: `document-norm-review/SKILL.md`が保持した4件のlessons参照は、いずれも「根拠:」という帰属表記であり、本文が規則そのものを自己完結して述べたうえで出典を添えるだけの形になっている(`grep`で該当4箇所を確認)。対して`ansible-implementation-style/SKILL.md`の旧2参照は、規則そのものをlessonsファイル側に委ねる「参照して従え」型だった(動的include側は「〜を参照」という指示文、consuming-filter側は当時「同型」とだけ述べて実質を委ねていた)。**「本文が自己完結しているか」という一貫した基準で扱いが分かれており、矛盾はない。**

## Suggestions(Minor)

1. **`skills/ansible-implementation-style/SKILL.md` のインライン化で、`dynamic-include-escapes-static-and-rescue.md` の適用節にあった「防御を意図的に置かない箇所には、置かない理由をコメントに残す」という運用上の指示が抜け落ちている。** 動的include以外にも一般化できる指摘だが、現状SKILL.md内の他箇所にも同等の記述は無い。ブロッキングではないが、次にこのSKILL.mdを触る機会に一文足すことを推奨する。

## What Looks Good

- 旧「AI間連携と成果物」節(冒頭文+4bullet+末尾段落)の全項目が、逐語または明確な吸収先を伴って新節「subagentが共通して守ること」へ到達していることを確認した。**規範本体に消失は無い。**
- `memory-classification.md` §4の表→本文化は、旧表がRole別に定めていた粒度(Auditorの「読まない」を含む)を、方針転換(全subagent一律「読まない」)に沿って整合的に書き換えており、**意味変化や条件の緩みは無い。**
- 節の統合・見出しレベル変更(`###`→`##`)・表の削除いずれについても、規範層(`.claude/agents/`4本、`skills/subagent-briefing/SKILL.md`、`roles/semaphore_templates/filter_plugins/semaphore_templates.py`)、実装層(`playbooks/`、`roles/`、`inventories/`)のいずれにも**宙ぶらりん参照は検出しなかった**(完全パス・略記・散文言及を別々に検索)。
- `docs/ai/core.md`「subagentが共通して守ること」8項目は、能力の不在を根拠に落とせるという分析の主張が現物と一致し、**判定表どおり全項目が維持され、削除・後退は無い。**
- `core.md` L52(quory直接編集・commit禁止)は分析の推奨どおり維持されており、2026-08-04の先例との整合も確認できた。**判断は妥当。**

## Verdict

**Approve.** blocking findingは無い。Minor 1件はブロッキングではなく、次の機会での反映を推奨する。
