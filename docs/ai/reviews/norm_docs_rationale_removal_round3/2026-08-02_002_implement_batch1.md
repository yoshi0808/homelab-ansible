# implement: Batch 1(`proxmox_operations_policy.md` / `log_observability_policy.md`)から経緯・根拠を落とす

正本: `docs/ai/reviews/norm_docs_rationale_removal_round3/2026-08-02_001_requirement.md`

## 変更したファイル

| ファイル | 種別 |
|---|---|
| `docs/ai/policies/proxmox_operations_policy.md` | 変更(未staged) |
| `docs/ai/policies/log_observability_policy.md` | 変更(未staged) |

指定の2本以外は変更していない。着手前から`M`(staged)だった`docs/ai/context-classification.md`・`docs/ai/memory-classification.md`・`docs/ai/role-context-matrix.md`・`docs/ai/status.md`・`norm_docs_rationale_removal_round2/`配下は、Batch 2または別subagentの作業であり、私は触れていない(`git status --short`で自分の2ファイルが` M`=unstaged、他が`M `=staged済みのまま変化していないことを確認済み)。

## 要件充足状況

| ID | 状態 | 備考 |
|---|---|---|
| R1 | 充足 | §5「落とす」列(改訂注記・実測日付注記・改訂の経緯・判断の引用・時点名指し条項・根拠への参照)に該当する記述を21箇所ずつ(各ファイル)除去した。詳細はAC2節の突合 |
| R2 | 該当なし(受け皿確認は実施済み) | 落とした断片はすべて、(a)本文の他の場所に既に現在の規則として存在している、(b)各Policy自身の「変更履歴」節に既に記録されている、(c)ADR-007やgrafana_provisioning案件記録など既存文書に記録されている、のいずれかで受け皿が確認できた。新設を要した箇所はない。詳細は下記「R2の確認結果」 |
| R3 | 充足 | `log_observability_policy.md`本文にあったLOG-073の退番記述(§6、「退番(2026-07-30、v4.0)。再利用しない。」で始まる段落)を本文から除去し、「変更履歴」節(v4.1行)へ「**退番: LOG-073(再利用しない)**」の形で移した。形式は同ファイルv3.0行の「退番: LOG-002(...)」、`proxmox_operations_policy.md`の「退番: SB-023(再利用しない)」に合わせた |
| R4 | 充足 | 見出しの日付・版注記2箇所(`### 観測プレーンの配備方式(2026-07-30新設、v4.0)`)を除去。改訂後、両ファイルとも見出し行に`2026-`・`v[0-9]\.[0-9]`のマッチ0件(grep確認) |
| R6 | 充足 | `scripts/check-doc-consistency.py`のcheck3(markdown内部リンク切れ検査、90件比較)がOK。加えて`grep -rn "LOG-045\|LOG-046\|LOG-073"`をリポジトリ全体で実行し、本節末尾に記載のとおり、ヒットはすべて過去の案件記録・ADR・両Policy自身の変更履歴(=退番後の内容を現行規範として参照していない)であることを確認した |

## R2の確認結果(受け皿確認)

- **proxmox_operations_policy.md**: 除去した21箇所はすべて「(2026-08-01改訂、SB-nnn)」のような改訂注記か、「〜は撤回した」という経緯文だった。これらの改訂内容は、同ファイル「変更履歴」節の既存の2026-08-01行2本(`proxmox_auto_apply_widening`案件、リネーム案件)に詳細が既に記録されており、本文からの除去で情報が失われることはない。新規の受け皿は不要だった。
- **log_observability_policy.md**:
  - LOG-047/LOG-074の改訂経緯・Yoshinobu引用は、同ファイル「変更履歴」節v4.0行に既に詳細記録がある。LOG-074の「判断根拠3つ」の本文(番号付きリスト)自体には日付が無く、§5表の削除対象(日付つき注記・経緯・引用)に該当しないため、そのまま本文に残した(根拠を失っていない)。
  - LOG-083から除去した「2026-07-12 Grafana 13.1事故」の説明は、`docs/ai/adr/007-grafana-provisioning-as-code.md`と`docs/ai/reviews/grafana_provisioning/`に事故の経緯・設計判断が既に記録されており、受け皿を確認したうえで除去した。
  - LOG-044/045/046(時点履歴)の具体的な事実(Phase 1完了、Phase 2状態、Phase 2 extension)は、同ファイル「変更履歴」節のv1.0/v2.0/v2.1行に既に記録されている。

## R3の確認結果(退番の記録)

- `log_observability_policy.md`本文からLOG-073ブロックを完全に除去し(既存の`ansible_test_safety_policy.md`のTS-003/TS-004先例と同じく、本文にIDのスタブは残さない)、「変更履歴」節のv4.1行へ「**退番: LOG-073(再利用しない)**」を追記した。同節には既にv4.0行に「LOG-073を退番」という記述があったため、内容は重複させず「上記v4.0行のとおり」と参照する形にした。
- 加えて、OQ1への対応(下記)でLOG-045・LOG-046を本文から除去したため、これも新たな退番として「変更履歴」v4.1行へ「**退番: LOG-045 / LOG-046(再利用しない)**」を追記した。

## OQ1について実際にどう扱ったか

requirement OQ1は「§5の表に従い、一般規則を1つ残して個別条項を落とす方針。ただしLOG-061は保存先の指定を含むため残す」と方針を示したうえで「Batch 1の実施結果を見てCoordinatorが確定する」としていた。この方針どおりに実施した。

- 見出し「時点履歴を現行契約に昇格させない」は残した(一般原則そのもの)。
- LOG-004(Phase 3構想は現行機能でない、という現在の事実)は日付を含まず改訂の必要がないためそのまま残した。
- **LOG-044を一般規則へ書き換えた**: 旧文言「2026-07-16のPhase 1完了はhistorical resultとして保持し、現行notification contractにしない。」を、「特定時点のPhase完了状態や実装状況(「実装済み」「validation待ち」等)は時点履歴として保持し、現行のnotification contractや許可条件として固定しない。」という一般規則に置き換えた。これがrequirementの言う「一般規則を1つ残す」の実装である。
- **LOG-045・LOG-046を本文から除去し退番**: 個別のPhase 2状態・Phase 2 extension状態を名指しする条項で、LOG-044の一般規則へ吸収された。具体的事実は「変更履歴」v2.0/v2.1行に既存。
- **LOG-061はrequirementの指示どおり本文にそのまま残した**(`../reviews/policy_standardization/2026-07-25_021_investigation_remaining_policies_rewrite.md`という保存先指定を含むため)。この行のファイル名に含まれる日付は経緯としての日付ではなく実在ファイル名であり、書き換えていない(下記「非経緯の日付」参照)。

**判断を求めての報告事項は無かった** — OQ1自体がこの実施方針を既に示しており、私の実施はその方針の範囲内に収まったため、新たな規則変更判断は発生しなかった。ただし、LOG-044の文言を「新しい一般規則の文章」として書いたこと自体は、厳密には既存文言のverbatim保持ではなく要約による書き換えである。個別条項3つが述べていた内容(時点履歴は現行契約に昇格させない、という趣旨)を過不足なく一般化したつもりだが、**文言そのものの妥当性はReviewerの独立確認を要する**と考えている(下記「未解決事項」参照)。

## 経緯でない日付(AC1の例外、書き換えず維持)

3箇所とも実在するファイルパス内の日付であり、経緯を語る日付ではないため書き換えていない。

| ファイル | 行 | 内容 | 扱い |
|---|---|---|---|
| `log_observability_policy.md` | L36(LOG-067) | `[Phase 3 alerting requirement](../reviews/promtail_to_alloy/2026-07-19_phase3_alerting_requirement.md)` — 将来のsyslog検知設計の起点となる正本ポインタ | 未編集。ファイル実在を確認済み |
| `log_observability_policy.md` | L280(LOG-083) | `` `docs/ai/reviews/grafana_provisioning/2026-07-30_001_requirement.md` R3の判定表 `` — 判定条件の詳細の行き先 | 未編集。ファイル実在を確認済み |
| `log_observability_policy.md` | L350(LOG-061) | `../reviews/policy_standardization/2026-07-25_021_investigation_remaining_policies_rewrite.md` — OQ1で明示的に残すと指示された保存先 | 未編集。ファイル実在を確認済み |

いずれも「経緯」ではなく「行き先・正本の指定」(§5「残す」列)に該当すると判断し、AC1の`grep`ベース測定はこの3件を除いて0件である(`proxmox_operations_policy.md`は例外なしで完全に0件)。

## 判断を求めて報告する事項

**無い。** 規則の意味が変わる編集が必要と判断した箇所、受け皿が存在せず新設が要ると判断した箇所は、実施の過程で発生しなかった(R2節のとおりすべて既存の受け皿で足りた)。OQ1はrequirement側で既に方針決定済みだったため、その範囲内で実施した。

## AC別の自己検証

### AC1(変更履歴を除いた本文の日付が0件、経緯でない日付は書き換えず報告)— 確認済み

```
proxmox_operations_policy.md: 本文(§8手前まで) grep "2026-" → 0件
log_observability_policy.md:  本文(§8手前まで) grep "2026-" → 3件(上表の実在ファイルパス、書き換えず維持)
```

### AC2(改訂前後の逐行突合、許可・禁止・停止条件が1つも変わっていない、Policy IDも失われていない)— 確認済み

`git diff`を両ファイルとも全文読み、削除した全断片を「経緯・根拠・日付・引用」と「規則・Policy ID・行き先」に分類した。

**`proxmox_operations_policy.md`(21箇所)**: すべて「(2026-08-01改訂、SB-nnn)」型の改訂注記、または「〜は撤回した」型の経緯文だった。パターンは3種類。
1. 括弧内がPolicy IDのみ(例: SB-003の`(2026-08-01改訂、SB-027)`→`(SB-027)`): IDを残し日付・「改訂」の語を落とす。
2. 括弧内に経緯だけがあり実質情報がPolicy ID以外に無い(例: SB-142の`(2026-08-01追記、§2.2 B案、Yoshinobu判断)`): 括弧全体を削除。直前の規則文自体(「guestを無人で停止して適用を強行することはしない」等)は本文にそのまま残っているため、削除しても規則は失われない。
3. 経緯文の中に現在も有効な補足規則が同居している(例: SB-094・SB-095・SB-028・SB-046の「除外されたnodeについては到達性・健全性いずれも未確認」「Urgencyによらず自動適用する」等): 経緯の接続詞・改訂注記だけを外し、補足規則は独立した文として残した。
§1目的の2ブロック(L15-25)は「2026-08-01時点で以下2点を変更した」という改訂宣言ごと、現在の規則(重要コンポーネント更新の自動適用条件、pve2先行検証の順序制約)だけの2箇条書きへ書き換えた。SB-003/004/027/028/032/039のID参照は保持。

**`log_observability_policy.md`(21箇所)**: 上記に加えて、判断の引用(LOG-074のYoshinobu逐語引用)・退番記録の移設(LOG-073)・時点履歴の個別条項の統合(LOG-044/045/046)という3種の固有パターンがあった。いずれも上位のOQ1節・R3節で詳細を記載済み。落とした断片はすべて「日付つき注記」「改訂経緯」「実測日付」「判断の引用」「根拠への参照(2026-07-12 Grafana事故の説明)」のいずれかに分類でき、規則本文・LOG番号は1件も失われていない。

**結論**: 両ファイルとも、削除したのは経緯・根拠・日付・引用のみであり、許可・禁止・停止条件(SB-nnn / LOG-nnnそれぞれの規則文)は改訂前と同一である。Policy IDも(退番したSB-023等の既存分・今回のLOG-073/045/046を除き)すべて残存している。

### AC3(退番の記録が「変更履歴」節にすべて含まれている)— 確認済み

`log_observability_policy.md`「変更履歴」v4.1行に「退番: LOG-073(再利用しない)」「退番: LOG-045 / LOG-046(再利用しない)」を明記した。`proxmox_operations_policy.md`は今回新たな退番が無く、既存の退番記録(SB-023、SB-049/SB-083/SB-084/SB-086)は変更履歴内で無改変のまま残っている(v4.1相当の新規行にも「既存の退番記録は本表のとおりで変更なし」と明記)。

### AC4(§5「残す」列の行き先・保存先・正本の指定がすべて残っている)— 確認済み

```
grep -n "正本" 両ファイル
```
- `proxmox_operations_policy.md`: 冒頭リード文の「実装詳細はコードを正本とする」、SB-013「Proxmox tagを正本」等、既存の正本指定はすべて無改変。
- `log_observability_policy.md`: 冒頭「provisioning YAML自身が正本」(L5)、LOG-089周辺の「正本の場所」表、LOG-078「provisioning YAML / dashboard JSON そのものが定義の正本」、「設計判断の正本は`docs/ai/adr/007-grafana-provisioning-as-code.md`」等、すべて無改変で残存。

### AC5(`check-doc-consistency.py`・`git-pre-commit-check.sh`がOK、宙ぶらりん参照が無い)— 確認済み(隔離コピー経由)

Implementerは`git add`を行えないため、`/tmp/claude-1000/.../scratchpad/repo_check_copy2`へリポジトリ全体を`cp -r`し、そのコピー内でのみ`git add -A`して検証した(実リポジトリのstaging状態には触れていない。検証後にコピーは削除済み)。

```
[check-doc-consistency.py]
[check1] OK (98 compared)
[check2] OK (8 compared)
[check3] OK (90 compared)
exit=0

[git-pre-commit-check.sh]
gitleaks: no leaks found
[tester-gate-lint] OK (49 playbooks)
[check1] OK / [check2] OK / [check3] OK
[pre-commit] OK
exit=0
```

加えて`grep -rn "LOG-045\|LOG-046\|LOG-073"`をリポジトリ全体(reviews/adr含む)で実行し、ヒット箇所がすべて(a)過去の案件記録(`policy_standardization/`、`grafana_provisioning/`)による当時のスナップショット、(b)`docs/ai/adr/007-...`による設計判断の記録、(c)両Policy自身の「変更履歴」節、のいずれかであることを確認した。退番後の内容を現行の規範として参照している箇所は無い。

## 非ゴールの遵守

- 許可・禁止・停止条件は変更していない(AC2の突合で確認)。
- Policy ID(`SB-nnn` / `LOG-nnn`)は落としていない(退番した3件は変更履歴へ移設済み)。
- 「変更履歴」節は書き換えず、追記のみ行った(R3に基づく退番移設1件、および今回の編集内容を要約した新規行1件を各ファイルへ追加)。
- `docs/ai/reviews/`・`docs/ai/memory/`の既存記録は書き換えていない(参照・grepのみ)。
- `skills/`には触れていない。
- Batch 2の7本、対象外2本には触れていない。

## 未解決事項

1. **LOG-044の一般規則化はrequirement OQ1が示した方針の実装であり、文言自体は今回新たに書き起こした要約である。** 個別条項3つ(LOG-044/045/046)が述べていた「時点履歴を現行契約に昇格させない」という趣旨を過不足なく一般化したつもりだが、この要約が元の3条項の意図を正しく汲んでいるかは独立レビューを要する。
2. **`proxmox_operations_policy.md`のSB-012・SB-088・SB-032・§5.1手順に共通して現れていた「§2.2 B案」という内部ラベルを、経緯注記の一部とみなしてすべて削除した。** これは§5表の「規則に埋め込まれた改訂注記」row1の「残す=規則本文とPolicy ID」を文字どおり適用した結果だが、ラベル自体は複数箇所を束ねる用語として機能していたため、削除によって「単一node運用時の退避省略・見送り」という一連の規則群の相互関連性を示す手がかりが薄まった可能性がある。規則そのもの(退避を試みず、running guestが残っていれば適用を見送る)は各所に無改変で残っており実害はないと判断しているが、Reviewerの確認を推奨する。
3. AC5は隔離コピーでの検証。実リポジトリでの最終確認は、Yoshinobuまたは次工程が`git add`した時点で改めて`scripts/git-pre-commit-check.sh`を走らせることを推奨する。
