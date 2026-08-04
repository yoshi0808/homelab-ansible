# 入口・共通原則・Role層 規範レビュー

作成日: 2026-08-04 / 担当: Reviewer(規範文書レビュー)

対象: `CLAUDE.md` / `AGENTS.md` / `docs/ai/core.md` / `docs/ai/roles/{coordinator,implementer,reviewer,tester,auditor}.md` / `docs/ai/role-routing-index.md` / `docs/ai/role-context-matrix.md`。全文読了。

前提資料: `docs/ai/reviews/norm_docs_post_phase4_sweep/2026-08-04_001_change_baseline.md`(事実の列挙、鵜呑みにせず`git show`で裏取り)。

`skills/document-norm-review/SKILL.md` の欠陥クラス(1 宙ぶらりん参照 / 2 規範の消失 / 3 撤回した根拠の残存 / 4 判定ラダーの全域性・一意性 / 5 文書内の自己整合 / 6 追跡表ドリフト / 7 適用範囲の広狭変化)に沿って確認した。

---

## Critical Issues

### C1. `docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」表が自己矛盾している(判定ラダーの一意性欠落、欠陥クラス4)

表の行3と行4が同一のホスト集合を挙げ、正反対の結論を出している。

- 行3: 「**保護対象ホスト**(`pve1` / `pve2` / `authy` / `sophos-fw` / UniFi機器)への非冪等操作でYoshinobu承認済みscope内のもの → Coordinatorが着手前に計画を確認し承認。」
- 行4: 「**到達手段が無いホスト**(`pve1` / `pve2` / `authy` / `quory` / `sophos-fw`) → **承認の対象ではない。届かない。**」

`pve1` / `pve2` / `authy` / `sophos-fw` の4ホストが両方の行に載っている。行4は「承認して実行する」という選択肢自体が存在しないと述べているのに、行3は同じホストに対して承認さえ得ればCoordinatorが実行できるかのように読める。**入力(例: pve1への非冪等操作)が両方の行に一致し、結果が「承認して実行」と「不可能」で正反対になる**(`skills/document-norm-review/SKILL.md`欠陥クラス4の「一意性の欠落」に該当)。

裏取り: `git show 73dd527 -- docs/ai/roles/coordinator.md` を確認した。このcommitで旧行「保護対象ホスト以外(`monnie`/`quory`/`ansy`)…確認不要」を割って「到達手段が無いホスト」行(新設)と「上記以外(`monnie`/`ansy`)」行の2行へ差し替えた。**このとき行3(保護対象ホスト)には一切手を入れていない** — dev_prod_boundary Phase 1〜4(ansyの認証情報全廃、baseline項目1)を反映した新設行を追加しながら、その事実と矛盾する既存行を残した典型的な「部分反映」(欠陥クラス5)。

行3の下に置かれた注記(同commitで追加)「実効的な境界は、承認の規則ではなく能力の不在で作られている。`pve1`/`pve2`/`authy`/`quory`/`sophos-fw`へは、ansyが認証情報を1つも持たない…**この表は、届く相手についてしか意味を持たない。**」は趣旨としては行3を無効化する意図に見えるが、**行3のホスト列挙そのものは書き換えられていない**ため、読み手は「UniFiだけでなくpve1等も、Yoshinobu承認さえあれば実行できる」と読める余地が残る。注記は解決ではなく症状の緩和に留まっている。

**実害の伝播経路**: `docs/ai/roles/tester.md`(実ホストへの非冪等操作を実際に行いうる唯一のRole)が行35で「保護対象ホストへの非冪等操作は、着手前に計画をCoordinatorへ提示して承認を得る。保護対象の範囲…は`docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」が正本」とこの表を直接参照している。Testerがこの表の行3だけを読めば、「pve1への非冪等操作もCoordinator承認を得れば実行できる」という誤った手順を導ける。

**提案**: 行3のホスト列挙から到達不能な4ホスト(`pve1`/`pve2`/`authy`/`sophos-fw`)を外し、UniFi機器だけを残す(UniFi機器はbaseline項目1のansy認証情報全廃の対象に含まれていない)。あるいは行3自体を「UniFi機器への非冪等操作」に改題し、行4との対象重複を解消する。

---

### C2. `docs/ai/role-routing-index.md`「Testerは実ホストへ到達してよい唯一のRole」の記述が、到達可能範囲の現実(ansy認証情報全廃)を反映しておらず、範囲の広狭が読み手に伝わらない(欠陥クラス7寄り)

`docs/ai/role-routing-index.md` L16: 「**subagentのうち、実ホストへ到達してよい唯一のRoleである**」。この文自体は現在も真(Implementer/Reviewer/Auditorは実ホストへansibleを実行しない、というのは変わっていない)だが、baseline項目1により**Testerが実際に到達できる実ホストの集合は激減した**(`pve1`/`pve2`/`authy`/`quory`/`sophos-fw`はansyから認証情報が無く、read専用のforced command dispatchしか無い。書込語彙は無い)。この文だけを読むと、Testerは以前と同じ範囲の実ホストへ非冪等操作を行えるRoleだと誤解しうる。

C1と合わせて読むと問題が悪化する: `role-routing-index.md`の「唯一到達してよい」という強い主張 → `tester.md`の「保護対象ホストへの非冪等操作は承認を得て行う」という具体的手順 → `coordinator.md`の矛盾した表、という3文書の連鎖で、最終的にTesterが「pve1へ非冪等操作ができる」という誤った結論に到達しうる経路が成立している。

裏取り: `grep -rn "UniFi" docs/ai/core.md docs/ai/roles/*.md docs/ai/role-routing-index.md docs/ai/role-context-matrix.md CLAUDE.md AGENTS.md` — UniFiへの言及はC1で挙げた`coordinator.md`行3の1箇所のみ。UniFi機器がなぜ「保護対象ホスト」の中で唯一到達可能なのか、この層のどの文書にも明示されていない(baseline項目1が挙げた認証情報削除の対象ホストにUniFiは含まれない、という事実はこの案件のbaseline文書にしか無く、この層の文書からは読み取れない)。

**提案**: C1の是正と合わせ、`role-routing-index.md`のTester行に「到達可能な実ホストの範囲は`coordinator.md`の表が定める(現状、非冪等操作で実際に到達できるのはUniFi機器のみ)」等、範囲の狭さを明示する一文を足す。

---

## Suggestions

### S1. `docs/ai/role-context-matrix.md`に「Operations Context」の読み分け行が無い

`core.md`は`docs/ai/context/operations/code-delivery-to-production.md`(baseline項目6、新設)と`docs/ai/context/operations/healthcheck.md`を参照するが、`role-context-matrix.md`のマトリクスは「対象領域System Context(`proxmox.md`/`radius.md`/`monitoring.md`/`semaphore.md`)」の行しか持たず、Operations Context配下のファイルをどのタイミングでどのRoleが読むかを定義する行が無い。`healthcheck.md`は本baseline以前から存在するため今回の変更が原因ではないが、`code-delivery-to-production.md`の新設で「配備が要るか」の判断がImplementer/Coordinatorの実務判断に直結するようになった(baseline項目6)以上、マトリクスの手薄さが顕在化した。blockingではない。

### S2. `AGENTS.md`の未判断メモが2026-07-26のまま放置されている

`AGENTS.md` L7: 「Codexは開発工程から外れ…本ファイルの要否は未判断。」この一文自体はbaseline項目8(開発と運用の分離をエージェント名抜きの原則へ書き直し)と直接矛盾しないが、`core.md`の該当節からエージェント名(Claude Code/Codex)が全廃された今、`AGENTS.md`だけがCodex固有の経緯説明を残しており、層の中で浮いている。是正の緊急性は低い(記述として誤ってはいない)。

### S3. `docs/ai/core.md`「打鍵を伴う承認の入口を増やさない」と「Yoshinobuは判断者であって実行者ではない」の関係はやや読み取りにくい

git commitの承認プロンプトへYoshinobuが応答する行為自体は打鍵であり、一見「実行」に見える。同じ節が「ansyで押させてよいのはgitの確定だけ」と明示的に例外化しているため矛盾ではないが、この2文が離れた位置にあり(L20とL26)、初読で「入力を伴う承認は矛盾では」と立ち止まりうる。blockingではない。

---

## What Looks Good(確認できた「変わっていないこと・正しく反映されていること」)

- **baseline項目1(ansyの本番認証情報全廃)**: `core.md`「開発と本番の境界」に到達経路の記述(forced command dispatch、read専用)が正しく追加されている。`git show f8e69ed`で確認。ただしC1/C2のとおり`coordinator.md`の表と`role-routing-index.md`の一部記述が追随できていない。
- **baseline項目4(commit/push全面禁止→都度承認)**: `core.md` L25・L132、`coordinator.md` L33、`role-routing-index.md` L14、`implementer.md` L34、`auditor.md` L68のいずれも「subagentは承認の有無にかかわらず行わない」という結論で一致し、旧「全面禁止」文言の残存は無い(`grep -rn "全面禁止"`はこの層で0件)。
- **baseline項目6(code-delivery-to-production.md新設)**: `core.md` L51が正しく新設ファイルへリンクし、パスは実在する(`ls`で確認)。
- **baseline項目8(core.mdの3点追加、coordinator.mdの1点追加)**: `git show f8e69ed` / `194ff9f` / `1914459`のいずれも、commitメッセージが述べる変更内容と実際の差分が一致することを確認した。「開発と運用の分離」節からエージェント名(Claude Code/Codex)が全廃されている(`grep -n "Claude Code\|Codex" docs/ai/core.md`は該当なし、別途確認済み)。
- **宙ぶらりん参照は無し**: この層が参照する`docs/ai/core-migration-map.md`・`docs/ai/context/operations/code-delivery-to-production.md`・`docs/ai/memory/decisions/ansy-must-not-trigger-production-changes.md`・`docs/ai/reviews/dev_prod_boundary/2026-08-03_008_phase3_check_catalog.md`・`docs/ai/context/operations/healthcheck.md`・`docs/ai/context-classification.md`・`docs/ai/status.md`「このファイルの規律」は全て実在を`ls`/`grep`で確認した。
- **baseline項目2・3・5・7(incident_sync退役、無人Knowledge振り返り廃止、quory worktree自動追随、Semaphoreテンプレート正本化)**: この層(入口・共通原則・Role文書)には該当する記述自体が元々無く、`grep`で新旧いずれの表現も0件を確認した。この層より下位のContext/Policy層の管轄であり、本層の陳腐化には該当しない。

---

## 未確認事項

- `docs/ai/reviews/norm_docs_post_phase4_sweep/`配下で並行して別のReviewerが書いている`2026-08-04_004_review_context_and_skills.md`は、対象範囲がContext/Skill層であるため内容は読んでいない(自分の担当範囲との重複確認はしていない)。
- `.claude/agents/*.md`のfrontmatter現物とrole-routing-index.mdの記述一致は、今回のscope外(baseline項目8には該当なし)のため確認していない。
- C1/C2の是正が実装された場合、`docs/ai/policies/*_policy.md`側に同種の「保護対象ホスト」列挙が無いかは未確認(Policy層はこのレビューのscope外)。

---

## Verdict

**条件付き — C1/C2を是正してから、この層を「Phase 1〜4を正しく反映した状態」とみなせる。** C1は同一文書内の自己矛盾であり、Testerの実手順に誤った経路を作りうるためCritical。C2はC1と連動する範囲記述の広さの誤りでCritical。Suggestions 3件はいずれもblockingではない。
