# implement: Phase 3 Step 3 — class G / class P dispatch への追加、Claude Code 鍵エントリ、日次ドリフト検査の期待値追随

日付: 2026-08-03 (JST)
requirement: `2026-08-02_001_requirement.md` R11 / R12 / R13c
plan: `2026-08-03_007_plan_phase3.md` §1.2(G2)/ §1.3 / §2 Step 3
catalog(正本): `2026-08-03_008_phase3_check_catalog.md` §2(class G)/ §3(class P)
先行記録: `2026-08-03_009_implement_phase3_step1.md`(Step 1、`incident-bundle-helper` 等の新設)

`roles/dev_investigate/`、`playbooks/dev_investigate_setup.yml` は触れていない(並行実装中の別subagentの領域、依頼の禁止事項どおり)。

## 1. 成果物

| 契約 | 種別 | パス |
|---|---|---|
| 契約A | 既存ファイル修正 | `roles/recovery_exec/templates/recovery-investigate-dispatch.sh.j2`(class G に `deployed-hash`/`unit-cat` 追加) |
| 契約A | 既存ファイル修正 | `roles/recovery_exec/templates/recovery-investigate-dispatch-pve.sh.j2`(class P に `deployed-hash`/`unit-cat` 追加) |
| 契約B | 既存ファイル修正 | `roles/recovery_exec/templates/authorized_keys.j2`(2→3エントリ) |
| 契約B | 既存ファイル修正 | `roles/recovery_exec/templates/authorized_keys-pve.j2`(1→2エントリ) |
| 契約B(周辺) | 既存ファイル修正 | `roles/recovery_exec/tasks/target_setup.yml`(該当2 task の name/コメントをエントリ数に追随) |
| 契約C | 既存ファイル修正 | `roles/deployment_drift_check/defaults/main.yml`(`deployment_drift_check_forced_command_keys` の `entries` を 2→3 / 1→2) |
| O1対処 | 既存ファイル修正(scope外・判断により実施) | `roles/recovery_exec/files/incident-bundle-helper` |
| O2対処 | 既存ファイル修正(scope外・判断により実施) | `roles/recovery_exec/files/recovery-reports-helper`、`roles/recovery_exec/files/homelab-reports` |

`claude-investigate.pub` / `claude-investigate-pve.pub`(Step 1着手前からuntracked)は自分が作った変更ではない。

## 2. 契約の充足状況

### 契約A — class G(catalog §2)/ class P(catalog §3)

**読める identity の確認(実装前の判断)**: dispatch は SSH forced command 経由で **`recovery-exec` OS ユーザーとして実行される**(`authorized_keys` が `/home/recovery-exec/.ssh/` にあるため、sshd はこのユーザーの権限でforced commandを起動する。既存コード内コメント「Runs as recovery-exec directly (no sudo/user-switch)」と整合)。名前→パス表の全エントリを `target_setup.yml`/`recovery_push` role の配備taskで確認した結果:

| name(class) | owner:mode | 読めるか |
|---|---|---|
| recovery-push(G) | root:root 0755 | ○(world-readable) |
| recovery-trigger-unit(G) | root:root 0644 | ○ |
| investigate-dispatch(G) | root:root 0755 | ○ |
| action-script(G) | root:root 0755 | ○ |
| authorized-keys(G/P) | recovery-exec:recovery-exec 0600 | ○(dispatchの実行identity自身が所有者) |
| loki-helper(G, monnieのみ) | root:root 0755 | ○ |
| investigate-dispatch-pve(P) | root:root 0755 | ○ |

読めないものは無かったため、カタログどおり全件実装した(除外・報告のみに留めたものは無い)。

**実装**: `deployed-hash <name>` は `read -r _ name extra <<<"$cmd"`(class G)/ 既存の `read -r check p1 p2 extra`(class P、既存の全体パース済み変数を再利用)で受け、`case` の enum のみに一致した名前だけを固定パスへ写像して `sha256sum` する。`unit-cat <unit>` も同型で、class G は既存 `target_item.investigate_services` + `recovery-trigger@.service`、class P は既存 `journal-unit` と同一の5 unit enum。**パスはoperandから一切組み立てず、script内蔵の固定表のみを使う(I-3)**。`loki-helper` は `{% if 'loki' in target_item.investigate_services %}` で monnie のみに出し分け、authy では case にすら現れない(受理不可)。

sudoは使っていない — class Gは既存の `systemctl status`/`journalctl -u` も元々sudoなしで動く設計(recovery-execがsystemd-journalグループに所属、target_setup.ymlで確認済み)であり、`sha256sum`/`systemctl cat` も同じ無権限読み取りで足りる。class Pは既存の `journal-*` 系はsudo必須(pve側recovery-execはsystemd-journalグループ非所属)だが、`systemctl cat` はunit fileの直接読み取りであり特権を要しない操作のため、catalogの実行内容欄どおりsudoなしで実装した(§4未解決事項に実機未確認である旨を記載)。

### 契約B — 鍵エントリ追加

`authorized_keys.j2` / `authorized_keys-pve.j2` に、`lookup('file', 'claude-investigate.pub')` / `lookup('file', 'claude-investigate-pve.pub')` で読んだ公開鍵を追加。forced commandは既存investigate用のものと**文字列として同一**(`/usr/local/sbin/recovery-investigate-dispatch.sh` / `-pve.sh`)。script側に鍵ごとの分岐は一切入れていない(catalog末尾「鍵エントリが1行増えるだけで、呼び出し元による分岐は入れない」、AC10の前提)。

`lookup('file', '<relative>')` がrole内`files/`を直接読む前提は、並行実装中の `roles/dev_investigate/templates/authorized_keys.j2` が既に同一パターン(`lookup('file', 'dev-investigate.pub')`)を採用していることで裏付けている(自分では読んだのみで編集していない)。

`target_setup.yml` の該当2 task の `name:` とコメントを新エントリ数に追随させた(「exactly 2 keys」→「exactly 3 keys」、「investigate key only」→「2 keys - Codex + Claude Code investigate」)。**この過程で自作の凡ミスを検出**: `name:` 値に未クォートのコロン(`2 keys: Codex ...`)を入れてしまい YAML パースエラーになった。自己検証中に発見し `-` へ差し替えて解消(§3 V1参照)。

### 契約C — 日次ドリフト検査の期待値

`deployment_drift_check_forced_command_keys` の `entries` を `authy,monnie: 2→3` / `pve1,pve2: 1→2` に更新。契約Bの実エントリ数と一致(§3 V6)。

## 3. 自己検証(V1〜V7)

実施はすべてansy上のローカル操作。実ホストへのansible実行は行っていない。

| # | 検証 | 手段 | 結果 |
|---|---|---|---|
| V1 | 両dispatchが描画でき構文として妥当 | Python jinja2で `recovery-investigate-dispatch.sh.j2` をauthy相当(loki無し)/monnie相当(loki有り)の2パターン、`recovery-investigate-dispatch-pve.sh.j2` をpve1相当で実描画 → `bash -n` | 3ファイルとも `bash -n` OK。`loki-helper`はmonnie版のみに出現しauthy版には不在(grep確認済み) |
| V2 | `deployed-hash`/`unit-cat`がカタログ列挙のname/unitだけを受理 | 描画済みscriptへ`SSH_ORIGINAL_COMMAND`を与えて実行(§3-Vテスト、全パターンをbashで実測) | class G: 5(authy)/6(monnie)のname全て、5 unit(authy: freeradius/sshd + recovery-trigger@.service)全てenum一致で通過(パス自体はansy上に実在しないため`sha256sum`/`systemctl cat`は「No such file」等で失敗するが、これはenum受理後の話でありscriptの検証ロジックには無関係)。class P: 2 name、5 unit全て通過 |
| V3 | 表に無いname、パス風operand、宣言数超過operandの拒否 | 同上。`nonexistent-name`/`/etc/passwd`/`../../etc/passwd`/`recovery-push extra`/`unit-cat sshd extra`(class G)、`unknown-name`/`/etc/passwd`/`investigate-dispatch-pve extra`/`investigate-dispatch-pve x y`(class P、4トークン目)を実行 | 全パターンで非ゼロ終了・stderr先頭が`denied:`(`deployed-hash`単独=空operand、`unit-cat`単独も同様に`denied: invalid parameter count`) |
| V4 | 既存チェックの出力・語彙が不変 | 既存の`failed`/`disk`(class G)、`cluster-status`(class P)を実行、diffは今回追加したcase armのみ(`git diff`で確認、既存armへの変更ゼロ) | `failed`/`disk`はansy実データで正常出力。`cluster-status`はansyに`pvesh`が無いため実行時エラーになるが、到達したコードパス自体は変更前と同一(既存armは1文字も変更していない) |
| V5 | `authorized_keys`が描画でき、全エントリが`command=`始まり、契約Bどおりのエントリ数 | Python jinja2 + `lookup('file', ...)`をrole files/相対解決するよう模したエミュレーションで実描画 | class G: 3エントリ(Codex investigate/action + Claude Code investigate)、class P: 2エントリ(Codex + Claude Code investigate)、全行`command=`始まり |
| V6 | 契約Cの期待値と契約Bの実エントリ数が一致 | `deployment_drift_check/defaults/main.yml`を読み合わせ | authy/monnie: 3=3、pve1/pve2: 2=2 |
| V7 | 両scriptに`eval`が無く、I-1書込語彙が無い | `grep -n '\beval\b'` + 書込語彙パターン(`pvesh (create|set|delete)`/`systemctl (start|stop|restart|enable)`/`qm (start|stop)`/リダイレクト/`tee`/`rm`/`mv`/`cp`)を全文へ実行 | `eval`ヒットなし。書込語彙ヒットなし(検出された行は全て`>&2`のstderrリダイレクトや`printf '==> %s <=='`内の`>`文字列というfalse positiveで、実際のファイル書込は無い) |

追加で `ansible-playbook playbooks/recovery_exec_setup.yml --syntax-check` と `playbooks/deployment_drift_check.yml --syntax-check` を実行し両方成功を確認(`target_setup.yml`のYAML破損を検出・修正した後)。

## 4. O1 / O2 の扱い

依頼文に「原因や対処方法は指定しない、判断して対処してほしい」とあったため、以下のとおり判断し対処した。いずれも`roles/recovery_exec/`配下で、依頼の許可範囲内。

### O1(`incident-bundle-helper`の空ディレクトリでrc=1)

原因: `list-bundles`/`list-investigations`が`find | grep -E "$ID_RE" | sort[-u]`という3段パイプで、`set -o pipefail`下では**マッチ0件時のgrepのrc=1がパイプ全体の終了コードに伝播**し、`set -e`でscript自体が異常終了していた(出力は空、rcだけが1)。呼び出し元(class Q dispatch。他subagent実装中)がこれを`denied:`と区別できないというのが依頼文どおりの実害。

対処: 両箇所の`grep -E "$ID_RE"`を`{ grep -E "$ID_RE" || true; }`へ変更し、grep自体の非ゼロ終了だけを無害化した(`find`側の真の失敗はこの`|| true`の外側なので伝播したまま)。空ディレクトリでrc=0・空出力、該当データがあれば従来どおり列挙されることを実測確認済み(§3以前の検証セクション)。

### O2(`usage()`のprefix不揃い)

Step 1 で新設された `incident-bundle-helper`/`homelab-incident-bundle` は catalog I-6(拒否は`denied:`+非ゼロ終了)に合わせて `denied: usage: ...` だったが、既存の `recovery-reports-helper`/`homelab-reports` は `usage: ...`のまま(`denied:`無し)だった。I-6は「§0 全体に効く不変条件」であり個別scriptのスコープに閉じないと判断し、`recovery-reports-helper`/`homelab-reports`の`usage()`も`denied: usage: ...`へ統一した(出力される実データやフィールド検証ロジックは一切変更していない、失敗時の先頭文言のみ)。4ファイルとも`bash`で実行し文言が揃ったことを確認済み。

## 5. 未解決事項

- **`unit-cat`(class P)を実機で未確認**: pve1/pve2の既存dispatch armは`journal-*`系も含め全て`sudo -n`経由だが(recovery-execがsystemd-journalグループ非所属のため)、`systemctl cat`はunit file自体の読み取りであり特権を要しない操作のはずという判断でsudo無しにした。ansyはProxmoxホストではないため、pve1/pve2の実recovery-exec identityが無権限で`systemctl cat`をpolkit/AppArmor等に阻まれず実行できるかは実機でしか確認できない。Tester側のAC8検証で併せて確認してほしい。
- **`authorized-keys`(class G/P共通)の`sha256sum`を無権限で読める実証は未了**: 所有者/mode(0600 recovery-exec:recovery-exec)とdispatchの実行identity(recovery-exec自身)が一致することは配備taskの定義から確認したが、ansy上では対象ユーザー・ファイルが実在しないため`sha256sum`自体は「Permission denied」(yoshiとして実行したため)で止まる。実機での最終確認はTester側に委ねる。
- **`lookup('file', 'claude-investigate*.pub')`のrole files/相対解決は、Pythonでのエミュレーションでのみ確認**。Ansible自体でのcheck-mode/decoy実行はしていない(本Stepでは各成果物ファイルのレンダリング/構文/文字列比較で足ると判断した。契約Aの検証と異なり、既存の`_investigate_pubkey`同型の`slurp`パターンではなく`dev_investigate`role側が先に採用した新パターンを踏襲したため、両roleどちらかが実機/decoyで先に実証されると安心材料が増える)。
- `git add`は行っていない(範囲を決めるのはCoordinatorの責務のため)。
