# 実ホスト操作の承認権限をYoshinobuからCoordinatorへ移す

決定日: 2026-07-26 / 決定者: Yoshinobu / 起案: Coordinator

> **一部が更新された(2026-08-03)。** 本ファイルが前提とする「`git commit` / `git push` の deny を維持するため、リポジトリへの確定操作は必ずYoshinobuの手を通る」は、denyから都度承認(ask)へ変わっている。後継は `docs/ai/reviews/git_gate_deny_to_ask/2026-08-03_001_requirement.md`、現行の規範は `docs/ai/core.md`「人間の権限と安全境界」。**以下は2026-07-26時点の決定の記録として読むこと。**

## 決定

実ホストへの操作に対する個々の承認判断を、Yoshinobuから**Coordinatorへ移す**。Yoshinobuは要件と「こうなったら困る」という前提を示す立場に専念し、承認済みscope内で個々の操作がその範囲に収まっているかの判断はCoordinatorが負う。

Yoshinobuの承認が引き続き必須なのは`git commit` / `git push`のみ。ほかに、要件段階で許可されていない破壊的操作、復旧不能なデータ削除、安全境界そのものの変更は、Coordinatorが判断せずYoshinobuへ上げる。

**運用上の境界(3分類)の正本は`docs/ai/policies/execution_boundary_policy.md`**。本ファイルへ複製せず、判断のたびにそちらを参照する。

## なぜこうしたか

**判断材料が承認者の側に無かった**。従来は`permissions.ask`にコマンドパターン(`Bash(ansible-playbook*)`、`Bash(sudo *)`、`Bash(python3 *)`等)を並べ、一致したらYoshinobuへ確認プロンプトを出していた。この方式は中身を区別しないため、`--syntax-check`のような無害な構文検査も、decoy inventoryでの検証も、実ホストへの本番実行も、すべて同じ「確認してください」として表示される。

2026-07-26、1日の作業でYoshinobuは約100回の確認応答を行い、延べ4時間を要した。そのうち実質的な判断を要したものは1件もない。一方、その日唯一の危険予兆(subagentが提示した`ansible-playbook -i inventory.ini test_play.yml`で、`test_play.yml`の中身が承認者から見えなかった)は、プロンプトの表示内容からは安全性を判定できず、Coordinatorがファイルを読んで初めてdecoy(実ホスト非接触)だと確認できた。

つまり、**承認を求められる側は判断材料を持たず、判断材料を持つ側は承認権限を持たない**という逆転が起きていた。加えて無害な承認が大多数を占めると、本当に危険な1件が埋もれる。

Yoshinobuの整理: 「私は要件を伝え、こうなったら困るという前提はお渡しする。ただし実装に入るとその中身は私は理解していないので、Coordinator以下に慎重に判断してもらいたい」。

## 実施内容

3層で構成する。

1. **`permissions.ask`を全廃**(プロジェクト・ユーザー両スコープ)。`ask`は`allow`にもauto modeにも常に優先するため、これを残すと他の層が効かない。
2. **`.claude/settings.json`の`autoMode`で境界を宣言**。`soft_deny`にProxmox / Sophos / UniFiへの非冪等操作とバックアップなしの不可逆データ削除、`hard_deny`に`git commit` / `push`、`environment`にホスト構成とCoordinatorが承認主体である旨を記す。あわせて`allow`から`Bash(*)`を除き、`autoMode.classifyAllShell: true`を設定する(`Bash(*)`が残っていると全bashが分類器を迂回し、`soft_deny`が死ぬ)。
3. **Role文書に承認プロセスを明文化**。`docs/ai/roles/coordinator.md`に3分類、`implementer.md` / `tester.md`の禁止・エスカレーション節に「実ホストへの非冪等操作は着手前にCoordinatorへ計画を提示する」を記載。`docs/ai/core.md`の「人間の権限と安全境界」もこの決定に合わせて改訂済み。

## 引き受けたリスク

Coordinatorが実質的な最後のゲートになる。Coordinatorの思い込みによる誤り(例: 同日、曜日を確認せず「pve1は夏季シャットダウン中のはず」と誤った前提でTesterへ指示した)は起こりうる。

これを承知のうえで移行する判断根拠は、同日の実測でその種の誤りが1件だったのに対し、100回の確認応答が検出した問題は0件だったこと。期待値として移行が優ると判断した。`git commit` / `git push`のdenyを維持するため、リポジトリへの確定操作は必ずYoshinobuの手を通る。

## 見直し条件

- Coordinatorの誤判断に起因する本番障害が発生した場合。
- 単一のCoordinatorセッションでなく複数の主体が並行して実ホストを操作する体制になった場合(承認の所有権が曖昧になるため)。
- auto modeの分類器を使わない実行形態(manual modeでの常用等)へ戻す場合。`permissions.ask`を外し`Bash(*)`も除いた状態でmanual modeへ戻すと、逆に全bashコマンドが確認対象になる。
