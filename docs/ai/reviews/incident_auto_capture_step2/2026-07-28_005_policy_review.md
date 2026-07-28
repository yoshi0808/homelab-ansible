**状態: 初回レビュー(findings 4件)→ Coordinatorが反映 → 再照合済み。最終結論は末尾「再照合(2026-07-28、Coordinator反映後)」を参照。**

# Policy Review: docs/ai/policies/incident_capture_policy.md(草案)

Reviewer: Tier `1+R` の R(独立レビュー)。実装者: Coordinator。返却先: Coordinator(`+R`工程、`docs/ai/roles/reviewer.md`「成果物と返却先」の例外)。
併用Skill: `skills/document-norm-review/SKILL.md`(規範文書レビュー)、`skills/code-review/SKILL.md`(出力フォーマット)。

## 確認範囲

現物を全文読了して逐行照合した。

- 対象: `docs/ai/policies/incident_capture_policy.md`(IC-001〜IC-026、§8、§9、変更履歴。全文)
- 集約元: `docs/ai/reviews/incident_auto_capture/2026-07-27_001_design_agreement.md`(D1〜D7、全文)、同 `2026-07-27_002_requirement.md`(§1〜§9、全文)、`docs/ai/adr/003-incident-capture-collector-runtime.md`(全文)、`004-notify-capture-insertion.md`(全文)、`005-auto-incident-filing-destination.md`(全文)
- Lesson: `permission-boundaries-must-be-designed-not-prompted.md`、`claude-code-unattended-session-confinement.md`(全文)
- `docs/ai/core.md`(全文)、`docs/ai/roles/reviewer.md`(全文)、`skills/incident-recording/SKILL.md`(全文)、`docs/ai/memory-classification.md`(見出しのみ、§3節の存在確認)
- 実装現物: `roles/common_slack/tasks/capture.yml`(全文)、`roles/incident_capture/`配下全ファイル(`defaults/main.yml`、`files/incident-capture-collector.py`の該当部、`templates/incident-capture.service.j2`)、`roles/knowledge_review/tasks/main.yml`(冒頭の中止条件部分)

実行したのはgrepとファイル読み取りのみ。Ansible実行・実host接続・`git add`/`commit`/`push`は行っていない。Policy草案および他の正本ファイルへの変更は行っていない(本ファイルのみ新規作成)。

## Summary

規範文書としての体裁(参照の実在性、引用の正確性)は概ね健全で、宙ぶらりん参照は検出されなかった。一方で、集約元にあった**許可・禁止・停止条件のうち2件が本文からもどこからも読み取れない状態(規範の消失)**になっており、うち1件は集約元で「最重要」と明記された安全条件である。さらに§8「決めていないこと」に、実際には確定している決定(ADR-005 Decision (4))が「未決」として書かれている疑いが1件ある。Criticalが2件、Majorが2件。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| C1 | docs/ai/policies/incident_capture_policy.md | 42-45(IC-010) | requirement.md R3「**最重要**」(T1追加によって呼び出し元playbookの終了コード・タスク結果・所要時間の有意な増加のいずれも発生させない。捕捉自体の失敗はplayを失敗させず、失敗した事実をレコードへ残す)が、Policy本文のどこにも現れない。IC-010の見出し「観測が被観測の挙動を変えてはならない」はR3の見出しと文言まで一致するが、続く本文は「caller側の通知ロジックを書き換えない」という別の(R3の一部でしかない)論点に差し替わっている。§7(停止条件)・IC-024/025も収集器側の非ゼロ終了の話であり、T1側の「捕捉の失敗はplayを失敗させてはならない」というR3/AC4の核心には触れていない。**見出しを流用しつつ本体の禁止事項を別の禁止事項へ差し替える**、`skills/document-norm-review/SKILL.md`欠陥クラス2が明示する「明示禁止が暗黙導出へ後退する」の典型形。実装(`roles/common_slack/tasks/capture.yml`のblock/rescue、AC4)はこの規律を正しく実装しているが、**Policy本文に規律として書かれていない**ため、将来capture.ymlを改訂する人がこの制約をPolicyから読み取れない。 | Critical |
| C2 | docs/ai/policies/incident_capture_policy.md | 全体(該当箇所なし) | ADR-003「制約5」「(b)補正(2026-07-27)」「Consequences」が3箇所で繰り返し明記する禁止 ——「**`reports/` 直下へのACL付与を禁止する**(`recovery_exec`のACLは`reports/incidents/`配下にのみ与え、`reports/`直下には与えない)」—— がPolicy本文にも§8にも現れない。理由はADR-003自身が明記している: `roles/proxmox_patch_apply_node/tasks/main.yml:293`が`reports/proxmox-dryrun/*_unified_dryrun.json`をfileglobで読み、**Proxmoxパッチ適用の可否判定に使う**ため、この境界を越えるACL付与は別システム(パッチ適用ゲート)を壊しうる。`grep`で確認した限り、この禁止は`docs/ai/policies/`配下のどのPolicyにも存在せず、ADR-003(案件スコープの正本)にしか残っていない。本Policyは「本案件はrequirement・ADR・案件記録という**すべて案件スコープの正本**しか持たなかった」ことを新設理由に掲げているため、まさにこの種の禁止こそ本Policyへ集約されるべき対象である。 | Critical |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| S1 | docs/ai/policies/incident_capture_policy.md | 101-108(§8) | 「ansy側の置き場所と、`.gitignore`の扱い。作業ツリー内(ディレクトリ単位で除外)か作業ツリー外かは再比較が必要 — 当初の判断(ADR-005)は**事象ごとのLLM叙述が存在する前提**で下されており、IC-007でその前提が消えた」という一文は、ADR-005のDecisionを検討し直すと**過大に広い**。ADR-005のDecision (1)〜(3)(第一報の出力先・`claude -p`のEdit権限ゼロ・昇格は人)は確かに「事象ごとの`claude -p`叙述」を前提にしており、IC-007で前提が崩れる。しかしDecision (4)「**quory→ansyのバンドル転送経路にも同じクラス制約を課す。転送先もgit作業ツリーの外とする**」は、Decision文中で明示的に「経路自体の設計は本件の非ゴールだが、**この制約は先に固定する**」と書かれており、Trade-off Analysisの論拠((a)封じ込めの面の数 (b)叙述の材料を叙述者が書き換えられないこと (c)`.gitignore`依存の強度)も評価対象データ(バンドル)を非信頼として扱う一般原則に基づいていて、評価が「事象ごと」か「まとめて」かに依存しない。**§8は「第一報(叙述結果)の置き場所」と「バンドル(転送された証拠そのもの)の置き場所」という別のDecisionを一つの文へ畳んでおり、後者(Decision (4)、既に固定済み)まで「再比較が必要」と読める形で未決に落としている。** これは`document-norm-review`が挙げる「既に決まっている事項が§8へ落ちていないか」の逆型に当たる可能性がある。Coordinatorが再検討する際、Decision (4)(転送先は作業ツリー外)まで議論の対象に含めるのか、それとも第一報の置き場所だけを再検討するのかを一度切り分けて確認することを推奨する。**確度としてはCONFIRMEDでなくPLAUSIBLE** — Decision (4)がIC-007後も無条件に生き残るかどうか自体はADR-005本文に明記が無く、Coordinatorの判断を要する。 | correctness |
| S2 | docs/ai/policies/incident_capture_policy.md | 48-60(§4) | requirement.md R4/AC6(バンドルは`reports/incidents/<id>/`配下、`.gitignore`は`reports/**/*.{json,log,md}`のみを除外するため**バンドルの全ファイルをこの3拡張子のいずれかにする**、`.gitignore`は変更しない方針)がPolicy本文のどこにも無い。grep結果、Policy中で`.gitignore`に触れているのは§8の1箇所(ansy側の置き場所の議論)だけで、**quory側の成果物**(収集器が書く`reports/incidents/`配下)の拡張子制約・`.gitignore`不変の方針には触れていない。これは`AC6`(バンドル生成後も`git status --short`が空であること)を支える具体的な禁止であり、既存の「quoryはpush後も自動pullされない→明示的`git pull --ff-only`で同期確認する」運用(auto-memory記録)を踏まえると、quory側の作業ツリーが汚れると素の`git pull`が壊れうる。C1・C2ほどの緊急性ではないが、本Policyが「捕捉・転送・評価」の全段を対象とする以上、収集器(R2)の出力形式に関するこの制約も§3または§4に一行残す価値がある。 | completeness |
| S3 | docs/ai/policies/incident_capture_policy.md | 34-45(§3) | requirement.md R1「T1は安価かつローカル完結でなければならない…**SSHもHTTPも行わない**」がPolicy本文に無い(ADR-004参照でのみ回収可能)。IC-010は「caller側の通知ロジックを書き換えない」ことしか述べておらず、「捕捉自体がネットワークI/Oを持たない/軽量である」という制約(38箇所全経路に効くため重要度が高い)には触れていない。C1と異なり、この制約はADR-004本文および`capture.yml`のコメント(`No SSH, no HTTP, no external network I/O`)に現存し「消失」はしていないため、Suggestion止まりとする。将来T1へ機能追加する際に見落とされやすい制約なので、§3への一行追記を推奨する。 | completeness |

## What Looks Good

`document-norm-review`の指示に従い、「消失・意味変化・条件の緩みが無い」ことを確認できた箇所を明記する。

- **宙ぶらりん参照はゼロ。** Policy本文・§9で参照する8ファイル(design_agreement、requirement、ADR-003/004/005、lesson2本、SKILL、memory-classification.md)はすべて実在し、記載節(D3・D4、`月次振り返りの対象と手順`等)も現存を確認した。
- **IC-007の反映は正確。** 「2026-07-28にYoshinobuが事象ごとのLLM起動を不要と決定した」という背景事実と、Policy IC-007の文言(「事象ごとにLLMを起動しない…評価はまとめて行うため、都度の叙述工程を設けない」)は完全に一致する。
- **IC-008(`ok`含む全通知を記録)・IC-009(抑止フラグは記録するがスキップ理由にしない)・IC-011(収集失敗の握りつぶし禁止)は、いずれも`roles/common_slack/tasks/capture.yml`(`when:`なし、`slack_status`を無条件記録、`tester_mode`/`skip_notifications`をフラグとして記録)および`roles/incident_capture/files/incident-capture-collector.py`(`collection_errors`蓄積、非ゼロ終了)の現物と一致する。**規範の消失も現物との不一致も無い。
- **IC-024(収集エラーで非ゼロ終了・systemdがfailed報告)は、収集器の`EXIT_COLLECTION_ERRORS = 2`と、`incident-capture.service.j2`に`SuccessExitStatus`が設定されていない(＝2はsystemdにより無条件でfailed扱いされる)ことの両方を確認し、一致を確認した。**
- **IC-025(月次評価は作業ツリーが汚れているとき実行しない、緩めるのはYoshinobuの領域)は、`roles/knowledge_review/tasks/main.yml`の`Decide whether to abort`タスク(`knowledge_review_allow_dirty`変数、timerからは渡らない)と、ADR-005 Decision本文末尾「月次振り返りの中止条件…はこの決定では一切変更しない」の両方と整合している。**
- **IC-013(quoryにansyへの書込権を与えない)・IC-016(証拠バンドルは非信頼データ)は、ADR-003 Trade-off Analysis(`recovery-exec`がSlack経由Codexの到達可能identityであること)と文言レベルで一致し、過不足のある言い換えは無かった。**
- **§9の参照範囲は集約元の主要文書を過不足なくカバーしており、Policy本文が他文書の内容を丸写ししている箇所(規範の二重化)は見当たらなかった。** IC-018など、Lessonの結論を1〜2文で要約し出典を明示する形が一貫している。
- **D1(名前付き操作、引数面ゼロ)・D2(カタログ登録は1本ずつ人が判断)は本Policyでは詳述されていないが、これは消失ではない** — `docs/ai/policies/autonomous_recovery_policy.md`(execpolicy default deny、`recovery_exec` role配下のwrapperのみ許可)がこの規範の既存の正本であり、本PolicyのIC-026(能力拡張はYoshinobuの判断)はそれと矛盾せず整合的に接続している。

## Verdict

**Request Changes**

Critical 2件(R3「最重要」の消失、ADR-003制約5/RSK-06の消失)は、いずれも「本Policyが存在する理由」そのもの(案件スコープの正本しか無かったために規範が散逸する)に該当する事例であり、Yoshinobuの承認前に本文へ差し戻す価値がある。Major(Suggestion S1)はCoordinatorが再検討時に切り分けを確認すべき論点として提示した。findingsの修正は行わず、Coordinatorへ返す。

---

## 再照合(2026-07-28、Coordinator反映後)

Coordinatorが「findings 4件すべてを反映した」として`docs/ai/policies/incident_capture_policy.md`のみを再修正。初回依頼の境界(書いてよいのは本ファイルのみ、Ansible実行・実host接続・commit/push禁止)は変わらないとの申告どおり、今回も現物ファイルの読み取りとgrepのみで再照合し、他ファイルへは触れていない。

### 確認範囲(差分)

`docs/ai/policies/incident_capture_policy.md`の全文を再読了し、IC-010・IC-027(新設)・IC-028(新設)・IC-029(新設)・IC-030(新設)・§8追記の6箇所を、対応する集約元(requirement.md R1/R3/R4/AC6、ADR-003制約5・(b)補正・Consequences、ADR-005 Decision(4)とTrade-off)および実装現物(`roles/knowledge_review/tasks/main.yml`、`roles/knowledge_review/defaults/main.yml`、`playbooks/knowledge_review.yml`冒頭コメント)と逐行照合した。

### C1(IC-010/IC-027への分割)— 解消を確認

新IC-010「観測が被観測の挙動を変えてはならない(最重要)。捕捉は、被観測playの終了コード・タスク結果の件数・所要時間のいずれも変えない。捕捉自体の失敗がplayを失敗させてはならない。」は、requirement.md R3の核心(終了コード・タスク結果・所要時間の不変、捕捉失敗によるplay失敗の禁止)と文言レベルで一致する。旧IC-010にあった「caller側の通知ロジックを書き換えない」はIC-027として独立し、内容の欠落は無い。IC-010を§3(捕捉の規律)に置いたままにした点も、R3がT1(捕捉)の要件であることと整合する。**解消。**

### C2(IC-030新設)— 解消を確認

IC-030「証拠の書込に必要な権限は`reports/incidents/`配下にのみ与える。`reports/`直下へ与えてはならない…(ADR-003 制約5・b-1)。この禁止は捕捉・収集・転送のすべての段に適用する。」は、ADR-003の制約5・(b)決定・Consequencesが3箇所で述べる禁止と根拠(`proxmox_patch_apply_node`のパッチ適用ゲート入力の書き換え防止)を過不足なく反映している。**解消。**

軽微な構造上の指摘(blockingではない): IC-030は§4「転送の規律(quory → ansy)」の下に置かれているが、条文自体が「捕捉・収集・転送のすべての段に適用する」と明記しているため、section見出しの範囲(転送のみ)より条文の実際の適用範囲が広い状態になっている。条文内に明記済みのため読者を誤誘導する実害は薄いが、次回改訂の機会があれば§2(実行主体と配置)などセクション非依存の場所へ移す方が座りが良い。

### S1(§8追記)— 妥当な解決と判断

追記された「ADR-005のDecision (4)…同Decisionは自ら『同じクラス制約を課す』と述べており、Decision (1)から導出されているため、(1)が再検討されるなら独立には立たない。ただし『未決である』と明示するのであって、制約が無効になったのではない — 再決定までは(4)を守る側に倒す」は、ADR-005 Decision(4)本文の文言(「同じクラス制約を課す」)を根拠に、初回レビューが「独立に固定された決定では」と留保付きで示した論点を検討した上で、**(4)は(1)-(3)の前提に従属すると判断し、その上で安全側(現状維持)に倒す**という筋の通った処理をしている。「決めていないことを決定として書く」ことも「既に決まっていることを未決へ落とす」ことも避けており、document-norm-review観点5を満たす。あわせて追記された「IC-030はADR-005とは独立の、パッチ適用ゲートに由来する制約であり動かさない」も正確(ADR-003由来でADR-005とは無関係)。**妥当。**

### S3(IC-028新設)— 解消を確認

IC-028「捕捉は安価かつローカル完結でなければならない。捕捉の実行経路でSSH・HTTPを行わない。多数の箇所から呼ばれるため…全通知が遅くなり、ハングの経路にもなる。」は requirement.md R1(「T1は安価かつローカル完結でなければならない…SSHもHTTPも行わない…38箇所(25ファイル)から呼ばれるため」)と一致する。具体的な箇所数(38)を「多数の箇所」と一般化しているのは、Policy内で他の具体的カウント(33/38など)を持たない既存の書き方と一貫しており問題ない。**解消。**

### S2(IC-029新設)— 新しい不一致を検出(Major)

IC-029「捕捉と収集が生成するファイルは、`reports/`の`.gitignore`除外が現に効く形式に限る。**quoryの作業ツリーを汚さないこと自体が受入条件である(汚れると月次評価が止まる — IC-025)。**形式を増やす変更は、除外設定の側と必ず同時に確認する。」

前段(拡張子を`.gitignore`が効く形式に限る、形式追加時は除外設定を同時確認する)はrequirement.md R4/AC6と一致し問題ない。しかし**括弧内の因果関係(「汚れると月次評価が止まる — IC-025」)が誤りである。**

- IC-029が対象とする「捕捉と収集が生成するファイル」は**quory上**のもの(`roles/common_slack/tasks/capture.yml`のspoolレコード、`roles/incident_capture`の収集器バンドル)。
- 一方IC-025(月次評価は作業ツリーが汚れているとき実行しない)が参照する作業ツリーは、`playbooks/knowledge_review.yml`冒頭のコメントで明記されている通り「対象: localhost(ansy)」であり、`roles/knowledge_review/defaults/main.yml`の`knowledge_review_repo_dir: /home/yoshi/homelab-ansible`も**ansy上のパス**である。月次振り返りは**ansyの**リポジトリクローンの`git status --porcelain`を見ており、quoryのクローンは別ホストの別クローンで、参照すらしていない。
- auto-memory記録のとおり「quoryはpush後も自動pullされない」ため、quory上のuntrackedファイルはpush/pullの経路を経由してansyへ伝播することも無い。したがって**quory側の作業ツリーが汚れても、IC-025が定義する中止条件は物理的に発火しようがない。**

quory側の成果物を`.gitignore`が効く形式に限定すること自体はrequirement.md R4/AC6が求める正しい要件であり、削除すべきではない。誤っているのは根拠づけ(IC-025への参照)だけである。**正しい根拠は、(a) quoryの`git pull --ff-only`運用を壊さないこと(auto-memory「quoryはpush後も自動pullされない」)、および (b) 将来§8で転送先がansyの追跡下ツリー内に決まった場合に備え、量産元での拡張子逸脱を今のうちに防いでおくこと、の2点であり、IC-025(ansy側・月次評価)ではない。** 現在の書き方は、読者に「quoryを汚すと月次評価が壊れる」という存在しない因果を教える。

`skills/document-norm-review/SKILL.md`「参照先を誤らないための作法」が警告する型そのもの — 検証(拡張子要件が集約元と一致するか)は正しく通ったが、**当てた根拠(IC-025)が対象(quory)を誤っている**。「検証した」感覚を伴うため見落としやすい。

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| C3(新規) | docs/ai/policies/incident_capture_policy.md | IC-029 | quory側成果物の拡張子制約の根拠として、ansy側の月次評価中止条件(IC-025)を誤って引用している。両者は別ホストの別git作業ツリーであり、quoryの汚れはIC-025を発火させない。要件自体(拡張子限定)は正しいが、括弧内の因果("汚れると月次評価が止まる — IC-025")を削除するか、正しい根拠(quoryの`git pull --ff-only`運用、および将来ansy側追跡ツリーに転送先が決まった場合への予防)へ差し替える必要がある。 | Major |

### 再照合のVerdict

**Request Changes(1件)**

初回のCritical 2件(R3の消失、ADR-003制約5の消失)とMajor(S1の§8切り分け)はいずれも解消・妥当と確認した。S3(IC-028)も解消。**S2の修正(IC-029)が新しい不一致(誤った因果引用)を持ち込んでいる**ため、この1点のみ再修正を要する。修正はfindingとして返し、本ファイルでは行わない。他の3セクション(§3のIC-010/027/028、§4のIC-030、§8のDecision(4)整理)は追加の変更不要。
