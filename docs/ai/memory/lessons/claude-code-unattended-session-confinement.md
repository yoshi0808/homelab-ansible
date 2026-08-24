# 無人 claude -p の読み書きを封じ込める条件

> **前提が変わっている(2026-08-03)。** 月次Knowledge振り返りの無人実行は廃止され、**この環境に無人の Claude Code セッションは1つも残っていない。** 実装だった `roles/knowledge_review/templates/job-settings.json.j2` も同日に削除された(commit `6a592a9`)。
>
> **それでもこのLessonを残すのは、下の実測が「無人実行」ではなく Claude Code の権限モデルそのものの性質だからである。** `Read` と `Edit` で既定挙動が違うこと、`Write()` が no-op であること、`acceptEdits` が path 指定を無効化すること — いずれも `.claude/settings.json` を触るときに今も効く。**無人実行を再開する話ではない。**

## 教訓

`claude -p`を無人で走らせるとき、**読み書きの範囲を限定するには次の3条件が同時に必要**である。1つでも欠けると封じ込めは成立しない。

1. **権限ルールのpathは相対表記にする。** 絶対表記(`Write(/home/.../docs/**)`)はルールが照合されず、許可したはずのパスまで拒否される。
2. **`--permission-mode acceptEdits` を付けない。** 付けると作業ディレクトリ内の編集が無条件承認され、path指定が丸ごと無効化される。
3. **`--setting-sources` を空にする。** repoの`.claude/settings.json`が`Write(./**)`を許可していると、それが載って素通りする。

そのうえで`--settings`にジョブ専用のプロファイルを渡し、**allowlist方式**(許可した場所以外は全部拒否)にする。

**書込と読取は別の軸として両方絞る。** bareな`Read`を許すとansyユーザーが読める全ファイル(`~/.ansible/vault/`のパスワード、SSHキー等)へ到達できる。このrepoは公開GitHubにあり、書込先はgit管理下でYoshinobuがcommitする対象なので、読取が無制限だと機密混入の経路が残る。**書込側だけを塞いでも封じ込めは片側にしかならない。** `Read(docs/**)`のようにpathを絞ると、作業ディレクトリ外は拒否される(実測)。`--add-dir`で渡した範囲は読める。

**denylist(`--disallowedTools`で禁止パスを列挙)は使わない。** 列挙から漏れた経路には柵が無く、モデルの自制以外に歯止めが無い。列挙漏れは書いた本人には見えない([[verify-the-outside-of-a-claimed-boundary]])。

### 追記(2026-07-29) — `Read`はcwd内で「allowlist方式」になっていなかった

上記「書込と読取は別の軸として両方絞る」は、**cwd外の拒否だけを実測しており、cwd内の挙動までは確認していなかった。** `roles/knowledge_review`の権限プロファイルへ`Read(roles/**)`等を追加する案件で、Testerがdecoy実測により次を発見した。

**Claude Code(v2.1.220時点)のReadは、cwd内かつallow/denyのどちらにも一致しないpathを、既定で許可する。** cwd外は正しく拒否される(`/etc/hostname`等で確認済み)。つまり`Read(docs/**)`・`Read(skills/**)`だけを`allow`に書いていた元の構成でも、**cwd内にある`roles/`・`playbooks/`・`inventories/vars/`(秘密を含み得る)は、そもそも`allow`に載せていなくても読めていた可能性が高い。** 「path を絞ると読取が絞られる」という理解は誤りで、実際には「allowは追加の許可、denyだけが拒否として効く。cwd内でallowに載らないpathは黙って通る」という挙動だった。

**是正**: cwd内の機密パス(このrepoでは`inventories/vars/`)は、**`allow`から外すだけでなく`deny`へ明示的に書く**(`roles/knowledge_review/templates/job-settings.json.j2`の`deny`配列、2026-07-29時点で`Bash`/`WebFetch`/`WebSearch`と並べて追加)。denylistを主たる防御にしない、という上段の方針とは矛盾しない——ここは「allowlistで防げると誤解していた1箇所」に対する、狙いを定めた例外的な追加であり、防御の主体は引き続きcwd境界とEdit側のallowlistである。

**教訓**: `Edit`(書込)は今回もallowlist通りに機能した(`docs/ai/memory/**`等の3パス以外は拒否)。**`Read`と`Edit`で同じ「allowlist」という言葉を使っていても、既定挙動(cwd内の扱い)が異なる場合がある。** 新しい権限プロファイルを作る・広げるときは、追加するツール(`Read`/`Edit`/`Bash`等)ごとに「未指定pathがどちらに転ぶか」を実測で確認し、思い込みで転用しない。

### 効かない構成(実測)

| 構成 | 許可パス | 列挙外(`CLAUDE.md`) | repo外 |
|---|---|---|---|
| denylist + acceptEdits | 書ける | **書けた** | 書けた |
| allowlist(絶対path) + acceptEdits | 書ける | **書けた** | 書けた |
| allowlist(絶対path) + acceptEditsなし | **書けない** | 拒否 | 拒否 |
| **allowlist(相対path) + acceptEditsなし + setting-sources空** | 書ける | 拒否 | 拒否 |

### repo外へは書けない

`--add-dir`は**読み取りを追加で許可するだけで、書込の柵にはならない**。上記の成立構成ではrepo外への書込をどう指定しても許可できなかった(絶対path・`//`前置きとも不可)。

これは制約だが、設計上はむしろ利点である。git管理外の記録(Coordinatorのauto-memory)を無人実行が壊すことが構造的に起きない。**書けないものは壊せない。** repo外の記録を更新する必要があるなら、LLMではなく起動側(Ansible等)が確定的に行う。

### Write() はno-op、Edit() が実効

現行harnessでは`Write(path)`エントリはファイル権限チェックに一致せず**no-op**で、実行のたびにstderrへ警告を出す。実際に許可を成立させているのは`Edit(path)`側である。両方併記しておくのは将来のharness変更に備えるためで、**重複に見えて`Edit()`を消すと許可が全部落ちる**(denyへfail-safeするので安全側だが、機能停止に気づきにくい)。

### Bashは禁止する

Writeのpath制限はBash経由で迂回できる。無人実行では`Bash`を全面denyし、必要な状態収集は起動側で済ませてpromptには渡さない。副次的に、commit/pushの実行手段そのものが無くなる。

## 根拠(2026-07-27、月次Knowledge振り返りの無人実行)

`roles/knowledge_review`で、月次のKnowledge仕分けを`claude -p`に無人実行させる際に確定した。当初promptの文章だけで境界を示し、次に`--disallowedTools`のdenylistへ移したが、独立レビューが実機検証で列挙外9ファイル(`CLAUDE.md`・`AGENTS.md`・`docs/ai/`直下の正本群・`docs/ai/reviews/**`)への書込成功を実証したため、allowlist方式へ反転した。

decoy環境で4構成を実測して上表を得た。3条件のうち`acceptEdits`が最も見落としやすい(「編集を自動承認する」だけの設定に見えて、実際にはpath指定を無効化する)。

**当時の実装(`roles/knowledge_review/templates/job-settings.json.j2`)と、Role観点の要約を置いていた `docs/ai/role-routing-index.md` は、どちらも既に存在しない**(前者は2026-08-03の無人実行廃止で、後者は2026-08-04の解体で削除)。**上の3条件と実測表の正本は本ファイルである。**

関連: [[verify-the-outside-of-a-claimed-boundary]]、[[destructive-operation-classification-criteria]]
