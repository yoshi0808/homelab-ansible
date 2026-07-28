# OQ5の現物確認記録 — 何をどう確かめたか

- 実施: 2026-07-28 JST / Tech Lead(subagent)
- 対象requirement: `docs/ai/reviews/incident_auto_capture_step2/2026-07-28_001_oq5_requirement.md`
- 決着本体: `docs/ai/adr/005-auto-incident-filing-destination.md`

## 0. 実施方法と安全境界の遵守

- **実ホストへ触れていない。** ansyの作業ツリー上のファイル読取と、`git status --porcelain` / `git check-ignore -v` / `git branch --show-current` / `ls` のみ。
- **Ansibleを実行していない**(`--check` を含む)。
- **identityを昇格させていない**(`sudo`、`--become-user` とも不使用)。
- **`git add` / `git commit` / `git push` を行っていない。**
- harnessの安全機構によるブロックは**発生しなかった。**
- 変更したファイルは本ファイルと上記ADRの2つのみ。`roles/` / `playbooks/` / 既存の規範文書は一切変更していない。

`git check-ignore -v` は**判定の照会のみで、ファイルを作成しない**。存在しないパスに対しても `.gitignore` のルール照合結果を返すため、ツリーを汚さずに「その拡張子が無視されるか」を確かめられる。今回はこれを使った(実ファイルを置いて `git status` を見る方法は取っていない)。

## 1. requirementの観測O1〜O7の検証

| # | requirementの記述 | 照合先(現物) | 結果 |
|---|---|---|---|
| O1 | Step 1のrequirement §7 がOQ5をStep 2へ持ち越した | `..._002_requirement.md:211` | **一致。**ただし「唯一の未解決事項」という限定は不正確(§3-1) |
| O2 | 中止判定は `git status --porcelain` の非空。`fail` させずSlackで通知 | `roles/knowledge_review/tasks/main.yml:27-42`(判定)、`:35-37`(failさせない理由のコメント)、`:208-216`(`ABORTED_DIRTY`)、`playbooks/knowledge_review.yml:36-37,52-55`(warning通知) | **一致** |
| O3 | `knowledge_review_allow_dirty` は存在するがtimerからは渡らない | `roles/knowledge_review/defaults/main.yml:22-24`(既定 `false`)、`templates/knowledge-review.service.j2:13`(`ExecStart` に `-e` が一切無い) | **一致。**service unitの `ExecStart` は `flock -n ... ansible-playbook playbooks/knowledge_review.yml` のみで、変数を渡す口が無い |
| O4 | 振り返り自身も書込のみでcommitしない | `templates/review-prompt.md.j2:79`(「git commit / git push — **絶対に実行しない**。差分は作業ツリーに残し、commitはYoshinobuが行う」)、`templates/job-settings.json.j2:35-39`(`deny: ["Bash", ...]` により実行手段自体が無い) | **一致。**指示文と技術的封じ込めの二重 |
| O5 | 中止理由の文言が「先月分の昇格結果が未commitの場合もここで止まる」 | `roles/knowledge_review/tasks/main.yml:49` | **一致**(同文言が `playbooks/knowledge_review.yml:54` にも重複して存在) |
| O6 | 本番バンドルの約半数がpve1平日シャットダウン由来 | `docs/ai/reviews/incident_auto_capture/2026-07-28_031_production_status_check.md`(結論部および観測5) | **一致**(実件数は当該一次記録が持つ。本ファイルへは転記しない) |
| O7 | 2026-07-28時点でansyの作業ツリーに未commitの変更が実在する | `git status --porcelain` | **一致。**確認時点で modified 2件 + untracked 2件。**内訳が重要**で、modified 2件は `docs/ai/reviews/` 配下と `docs/ai/status.md` であり、**どちらも月次振り返りの書込allowlist(`docs/ai/memory/` / `docs/ai/context/` / `skills/`)の外**にある(§3-3で使う) |

## 2. 追加で確かめた事実(ADRの論拠に使うもの)

| # | 事実 | 照合先 |
|---|---|---|
| V1 | OQ5の出典は Step 1 requirement ではなく**設計合意**である。そこには解の方向が2つ明示されている — 「**起票先を分けるか、中止条件を『自分が書く範囲だけ見る』へ精緻化するか**」 | `..._001_design_agreement.md:110` |
| V2 | 設計合意は第一報の書き先を `docs/ai/memory/incidents/`(公開repo・git管理下)と想定している。ただしV1のとおり起票先自体は未確定として残されている | 同 `:111`、`..._002_requirement.md:42` |
| V3 | **自動化が触れるのは `状態: 調査中` まで。`原因分類` タグを埋めるのは人または確定後の対話セッション** | 同 `:37-49`(D3)、`:116`(やらないこと) |
| V4 | 月次振り返りの**タグ集計は `解決済み` のみ**。`調査中` は「滞留」として件数と経過日数だけ報告する | `roles/knowledge_review/templates/review-prompt.md.j2:27-31`、`skills/incident-recording/SKILL.md:56-58`、`docs/ai/memory-classification.md:80` |
| V5 | 月次振り返りの**書込allowlistは `docs/ai/memory/**` / `docs/ai/context/**` / `skills/**`、読取は `docs/**` / `skills/**` と auto-memory のみ**。repo作業ツリー外(`reports/` を含む)は読めない | `roles/knowledge_review/templates/job-settings.json.j2:27-40`、`templates/review-prompt.md.j2:65-72,87-89` |
| V6 | したがって **`docs/ai/memory/incidents/` は月次振り返り自身の書込範囲の内側**にある。V1後段の「自分が書く範囲だけ見る」は、起票先が同ディレクトリである限り**中止を回避しない** | V5 + `templates/review-prompt.md.j2:69` |
| V7 | `.gitignore` の `reports/` 除外は**拡張子3つ(`.json` / `.log` / `.md`)のみ**。`git check-ignore -v reports/incidents/foo.txt` は**一致無し**(= 無視されない)。`docs/ai/memory/incidents/foo.md` も一致無し(= git管理下) | `.gitignore:2-4`、`git check-ignore -v` の実行結果 |
| V8 | Step 1の一次調査はこの拡張子依存を「**この案件で最も安価に壊れる受入条件**」(RSK-13)として明示している | `..._003_investigation.md:184-186` |
| V9 | ADR-004は同じ理由で「生成物の拡張子は `.json` のみ。`.jsonl` は使わない」と実装側を縛っている | `docs/ai/adr/004-notify-capture-insertion.md:92-93` |
| V10 | ADR-003のStep 2引き継ぎ事項は「**バンドル内容は非信頼データである**」。Step 2はこれを読んで公開repoへ叙述する | `docs/ai/adr/003-incident-capture-collector-runtime.md:88`、同 `:75` |
| V11 | 月次振り返りのpromptは無人セッションへ「**作業ツリーが汚れていないことは起動側のAnsibleが確認済み**なので、ここで確認する必要はない」と伝えている。中止条件を外すとこの前提文が偽になる | `templates/review-prompt.md.j2:85-86` |
| V12 | 「作業ツリーが汚れているときは何も書かずに中止する」は**規範文書側にも書かれている**。role実装だけの取り決めではない | `docs/ai/memory-classification.md:101` |
| V13 | 無人 `claude -p` の封じ込めは prompt の指示文ではなく allowlist で成立しており、成立条件3点が実測されている | `docs/ai/memory/lessons/claude-code-unattended-session-confinement.md`、`templates/job-settings.json.j2:8-25` |
| V14 | AIの `git commit` / `git push` 禁止は共通原則の正本にある | `docs/ai/core.md:25` |
| V15 | 現状の `docs/ai/memory/incidents/` の蓄積は README を除き**一桁件数**にとどまる | `ls docs/ai/memory/incidents/` |

## 3. requirementに対する疑義・相違(3件)

### 3-1. O1の「Step 1が明示的に未解決のまま残した唯一の事項」は不正確

Step 1 requirement `:215` は「**OQ1は未解決**」と明記し、OQ1をYoshinobuの判断事項としている。同じ行はOQ5を「解決済み」に分類しており、その実体は `..._003_investigation.md:184` の「**requirementの結論を支持(Step 2へ持ち越し)**」、つまり「持ち越すと決めた」という意味である。

したがって正確には「Step 1が**Step 2へ持ち越した**唯一の設計判断」であり、「Step 1が残した唯一の未解決事項」ではない。**OQ5に取り組むという結論は変わらない**ため、requirementの差戻しは求めない。

### 3-2. OQ5の一次記録は設計合意であり、Step 1 requirementはその引き写しである

requirement §1 O1 は一次記録を `..._002_requirement.md:211` としているが、問題の初出と**解の方向2つの提示**は `..._001_design_agreement.md:110` である(V1)。requirement §8 の参照にこの行は挙がっていない。ADRでは設計合意を一次記録として扱った。

### 3-3. 「中止条件を『自分が書く範囲だけ見る』へ精緻化」は、OQ5を解かない

V6のとおり `docs/ai/memory/incidents/` は月次振り返り自身の書込範囲の内側にあるため、起票先をそこにしたまま判定範囲を自分の書込先へ絞っても、自動起票された第一報は依然として判定に引っかかる。この案が効くのは**O7が示した現実の汚れ**(`docs/ai/reviews/` と `docs/ai/status.md`、いずれも書込範囲の外)に対してであって、OQ5に対してではない。**両者は別の原因であり、片方の対策がもう片方を兼ねない。**

## 4. 現物確認できなかったこと(ADRの前提から外したもの)

- **月次timerの実際の発火結果**(過去に `ABORTED_DIRTY` で止まった実績があるか)は未確認。`systemctl` / journal の照会は実行環境への接触にあたるため行っていない。したがってADRは「止まりうる」という構造の議論に留め、「実際に何回止まった」は主張していない。
- **Step 2の実行形態**(`claude -p` の起動契機、権限プロファイル、書込先の実パス)は本件の非ゴール。ADRは「git作業ツリーの外」という**クラス**までを決め、実パスは決めていない。
- **quory→ansyのバンドル転送経路**は未設計(requirement §3で非ゴール)。第一報の生成がansy側で行われる前提そのものはStep 1のD4(`..._001_design_agreement.md:53`)に依拠しており、本件では再検証していない。

## 5. 本件と無関係に見つかった不整合(修正していない)

`roles/knowledge_review/templates/job-settings.json.j2:6` が正本として指す `docs/ai/memory/lessons/claude-code-unattended-write-confinement.md` は**存在しない**。実在するのは `claude-code-unattended-session-confinement.md`(内容は同主題)。リポジトリ全体で当該文字列の参照はこの1箇所のみ。

本件の成果物範囲外のため**修正していない**。Coordinatorへ報告する。

なお第2巡(§6)で判明したとおり、この dangling 参照が指す先のLessonは**Step 2の設計を直接拘束する内容**を持つ。参照が切れたままだとStep 2のImplementerが「repo外へは書けない」という実測に到達しない経路が残る。Step 2着手前の修正を推奨する。

---

# 第2巡 — 査読(`..._003_adr_review.md`)を受けた再確認

- 実施: 2026-07-28 JST(同日、同一のTech Lead役subagent)
- 契機: Coordinatorからの差戻し。査読の指摘F-1〜F-3
- 安全境界の遵守は第1巡と同じ。実ホスト未接触、Ansible未実行(`--check`含む)、identity昇格なし、`git add`/`commit`/`push` なし、harnessのブロックなし。**査読ファイル `..._003_adr_review.md` は読取のみで変更していない。**

## 6. 査読が挙げた新事実を、査読の説明ではなく現物で確認した

査読の記述を信用せず、指摘の根拠となる現物を自分で読み直した。**4件すべて査読の記述が正しい。**

| # | 査読の主張 | 現物 | 結果 |
|---|---|---|---|
| W1 | 無人 `claude -p` は**repo外へ書けない**。`--add-dir` は読取を足すだけで書込の柵にならない。repo外の記録を更新するなら起動側(Ansible等)が確定的に行う | `docs/ai/memory/lessons/claude-code-unattended-session-confinement.md:26-30`(節「repo外へは書けない」)、読取側は `:13`、効かない構成の表は `:19-24` | **一致。**初版ADRのDecision (1)+(2)は**両立しない**。初版が自ら正本として指定したLessonが、初版の決定を否定していた |
| W2 | `reports/` の追跡対象は `reports/radius-health/` の2件のみ。`reports/incidents/` 配下に追跡中のファイルは無い | `git ls-files reports/` | **一致。**ディレクトリ単位の除外を足しても既存の追跡ファイルへ影響しない |
| W3 | 設計合意は「捕捉時にIDを確定しSlack本文へ載せ、通知を**終点でなく入口**にする」と定めている。同時に「良質な調査結果がSlackの散文として蒸発している」を解くべき問題として挙げている | `..._001_design_agreement.md:101`(査読の引用は `:100`。1行のズレ)、同 `:99` | **一致**(行番号のみ訂正) |
| W4 | Step 1は「静かな取りこぼしを作らない(R5の趣旨)」を既に採用しており、取り込まれなかったspoolレコードを消さず `orphan` としてバンドル化する | `..._003_investigation.md:180`(査読の引用は `:181`。1行のズレ) | **一致**(行番号のみ訂正) |

**追加で自分が確認した事実(査読は挙げていない)**

| # | 事実 | 照合先 |
|---|---|---|
| W5 | 「LLMの標準出力を起動側Ansibleがファイル化してrepo外へ保存する」形の**先例が `knowledge_review` role 自身にある** | `roles/knowledge_review/tasks/main.yml:175-192`(`Save report` が `knowledge_review_run.stdout` を state 配下へ `copy`) |
| W6 | したがって A-2′ の配管は新規機構ではない。W1が示す正規の形を、既存の実装がそのまま先行して満たしている | W1 + W5 |

## 7. 指摘への対応(3件すべて反映)

| 指摘 | 判定 | 反映 |
|---|---|---|
| **F-1** Decision (1)と(2)が両立しない | **認める。**W1で追認 | 決定を **A-2′**(LLMは標準出力のみ、ファイル化は起動側Ansible)へ差し替え。初版のA-2は Options に**「実行不能」として残した** — 一度採った案が消えると、同じ誤りが再発しても記録から追えないため |
| **F-2** A-1を退けた唯一の根拠(制約6)が可変の1行 | **認める。**W2で追認 | **H(A-1 + ディレクトリ単位除外)を Options へ追加**し、A-2′と同じ土俵で比較。識別の根拠を制約6から**(a)封じ込めの面の数 (b)叙述の材料を叙述者が書き換えられないこと (c)`.gitignore` 依存**の3点へ置き換えた。あわせてI(Slackのみ)とJ(A-2′+`--add-dir`読取)も追加 |
| **F-3** 中核論証(i)「構造的に母数へ入らない」が誤り | **認める。** `skills/incident-recording/SKILL.md:14-15` の2段階は同一ファイルの状態遷移であり、入らないのは起票の瞬間だけ。滞留報告も設計された検知機構(`docs/ai/memory-classification.md:80`、`SKILL.md:57-58`) | (i)を**撤回**。結論は維持するが、支える論拠を「①Gを成立させるには安全境界を動かすしかない ②非信頼データを人のレビュー無しで公開repoへ入れない ③ノイズ希釈(**未決の設計に依存する条件付きの根拠**であることを明示)」へ書き直した |

**推奨は変わらなかった(A-2 → A-2′ は同系統の精緻化であり、A-1系への転換ではない)。** 変わらなかった理由は上記(a)(b)であり、**初版が唯一の根拠とした制約6は使っていない。**

査読が挙げた補足2点も反映した。①「Step 2は新たな中止要因を作らない」を**第一報の出力に関して**と限定し、転送経路へ同クラス制約を課すDecision (4)を新設した。②**未昇格の第一報を検知する主体が誰も居ない**状態が確定することをConsequencesに明記し、Step 2の必須要件へ「拾われなかったことを検知できること」を加えた(W4の規律と同型)。

B / C / E の分離は査読が妥当と確認したため維持し、**Jを分離集合へ追加**した(無人セッションの読取範囲の拡大にあたるため)。

## 8. 第2巡で新たに確定した契約要素の扱い

Coordinatorから「`.gitignore` の変更を伴う案を検討してよい(Coordinatorの承認範囲)」が追加された。**検討したうえで、採用しなかった。**

- 採用する場合の影響はW2で現物確認済み(追跡ファイルへの影響なし)。**採らないため、本ADRの決定に `.gitignore` の差分は発生しない。**
- ただし**Step 1側のRSK-13(拡張子依存)は本件と無関係に残り続ける。** A-2′を採ってもStep 1のバンドルは `reports/incidents/` 配下にあり、拡張子を1つ誤れば同じ形で月次を止める。ADRのConsequences末尾に「Coordinatorの承認範囲だが本決定には不要な事項」として記録した。**本件のクローズとは独立に処理する価値がある。**

## 9. 第2巡でも確認できなかったこと

- 第1巡の§4と同じ(月次timerの実発火履歴、Step 2の実行形態、quory→ansy転送経路)。**W1により「LLMが書けない」ことは確定したが、Ansible側がどの経路でstdoutを受けてファイル化するかの具体はStep 2の設計であり、本ADRは決めていない。**
- `--add-dir` で渡した先への**書込**が本当に不可能であることは、Lessonの実測記述に依拠しており、本件では再実測していない(実行環境への接触を伴うため)。**再実測が要るならTesterへの依頼が必要である。**この前提はDecision (1)(2)の土台であり、崩れると決定が変わる。
