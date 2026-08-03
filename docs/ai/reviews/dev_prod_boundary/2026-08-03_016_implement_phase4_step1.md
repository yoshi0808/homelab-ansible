# implement: Phase 4 Step 1 — D6 追加チェック(X1〜X4)

日付: 2026-08-03 (JST)
catalog: `2026-08-03_008_phase3_check_catalog.md` §6(D6)
plan: `2026-08-03_015_plan_phase4.md` §3.1 / §4 Step 1
担当: Implementer

## 対象ファイル(変更したのはこの6つのみ)

- `roles/dev_investigate/files/recovery-investigate-dispatch-quory.sh`(class Q。X1/X2/X3/X4)
- `roles/recovery_exec/templates/recovery-investigate-dispatch.sh.j2`(class G。X2/X3/X4)
- `roles/recovery_exec/templates/recovery-investigate-dispatch-pve.sh.j2`(class P。X2/X3/X4)
- `roles/recovery_exec/templates/homelab-investigate.sh.j2`(Codex wrapper、G向け。X2/X3/X4)
- `roles/recovery_exec/templates/homelab-investigate-pve.sh.j2`(Codex wrapper、P向け。X2/X3/X4)
- `roles/recovery_exec/templates/AGENTS.md.j2`(Codex向け説明。X2/X3/X4を authy/monnie/pve の3セクションに追記)

いずれも `roles/dev_investigate/` と `roles/recovery_exec/` 配下。`git status` は着手前から `docs/ai/reviews/dev_prod_boundary/2026-08-03_008_phase3_check_catalog.md` と `docs/ai/status.md` に未コミット差分があったが(D6承認時点でのCoordinator側の既存変更)、いずれも自分は触っていない。着手前後で自分のdiffがこの6ファイルに閉じていることを `git status` / `git diff` で確認済み。

## 契約の充足状況

| チェック | class | 実装 |
|---|---|---|
| X1 `acl-status <path>` | Q のみ | 実装した。enum: `yoshi-home`→`/home/yoshi`, `semaphore-dir`→`/var/lib/semaphore`, `semaphore-db`→`/var/lib/semaphore/semaphore.db`, `reports-root`→`/home/yoshi/homelab-ansible/reports`。`getfacl -p -- "$target_path"`。パスは固定 case テーブルのみで operand から組み立てない |
| X2 `users` | Q/G/P | 実装した。uid 下限 1000・上限 64999 を script内固定値(`(( u_uid >= 1000 && u_uid <= 64999 ))`)で持ち、operand を取らない(arity 0)。`getent passwd` をパース、`/etc/shadow` は未使用 |
| X3 `unit-files` | Q/G/P | 実装した。`systemctl list-unit-files --no-pager`。パス走査ではなくsystemdへの問い合わせ |
| X4 `forced-command-keys` | Q/G/P | 実装した。**自分自身**の `authorized_keys`(Q=`/home/dev-investigate/.ssh/authorized_keys`、G/P=`/home/recovery-exec/.ssh/authorized_keys` — いずれも各scriptの既存 `deployed-hash` の `authorized-keys` エントリと同一の絶対パス文字列を再利用しており、他identityの鍵ファイルへは到達しない)。鍵種別・base64鍵本体は一切出力せず、エントリ数と各行の `command=` パス・コメント欄のみ出力 |

契約B(Codex wrapper 同時解放): `homelab-investigate.sh.j2` / `homelab-investigate-pve.sh.j2` の許可リストへ X2/X3/X4 を追加済み(X1はQ専用でCodex wrapperがそもそも存在しないため対象外)。`AGENTS.md.j2` の authy/monnie/pve 3セクションへ用途を追記(「repoの差分だけでなくホストへ実際に反映されたか」を確認する目的、と明記)。

新規に増えた語彙は `getfacl` / `getent` / `systemctl list-unit-files` の3種のみ(自分自身のファイルの直接読み取りはbashの `<` リダイレクトのみで新規外部コマンドを追加していない)。`eval` は使っていない。

## X1 の可否判断(カタログ§6.2で指定された判断点)

**実装可能と判断した。** 根拠:

1. **`getfacl` によるACL取得は、対象パス自身の権限ではなく、その親ディレクトリ群のtraverse(実行)権限だけで成立する。** これは通常の `stat()` と同じ権限モデルであり、対象自身のmode/ACLがどれだけ厳しくても、そこへ辿り着けさえすれば読める。ローカルで実測して確認した: `/tmp` 配下に mode 0700(other権限なし)のディレクトリを作り、親ディレクトリを traverse-onlyにした状態で、無関係な `nobody` ユーザーから `getfacl -p` を実行 → 成功(該当ディレクトリの完全なACL情報が返った)。
2. 4つのenumパスそれぞれについて、dev-investigate の実行identityが親チェーンをtraverseできるかを確認した。
   - `yoshi-home`(`/home/yoshi`)の親は `/home` — 標準的なシステムディレクトリで誰でもtraverse可能。
   - `semaphore-dir`(`/var/lib/semaphore`)の親は `/var/lib` — 同様に誰でもtraverse可能。
   - `semaphore-db`(`/var/lib/semaphore/semaphore.db`)の親 `/var/lib/semaphore` は、dev_investigate role が既にACL traverse(`--x`)を明示的に付与している(`roles/dev_investigate/tasks/main.yml` の既存task、Q11向け)。
   - `reports-root`(`/home/yoshi/homelab-ansible/reports`)の親 `/home/yoshi/homelab-ansible` へのtraverseは、既存の Q5〜Q7(`report-*`、`recovery-reports-helper` 経由で `BASE=/home/yoshi/homelab-ansible/reports` 配下を dev-investigate 自身のuidで読む)が既に成立していることから構造的に保証されている——この経路がQ3実装時点(Phase 3)で機能する前提になっているため。
3. 以上より sudo を足す必要はなく、`dev-investigate` が sudo を1つも持たないという契約(`roles/dev_investigate/tasks/main.yml` 冒頭のコメント)は崩していない。

## 自己検証で確認したこと

実ホストへは一切触れていない(Implementerの権限どおり)。ローカルの `/tmp` とこのリポジトリの作業ツリー内で、Jinja テンプレートを Python(`jinja2.Environment`)で実際にレンダリングした上で確認した。

- **V1(classごとの存在)**: レンダリング後の各スクリプトへ `SSH_ORIGINAL_COMMAND` を設定してローカル実行。`acl-status` は class Q では動作し、class G(authy/monnie両方でレンダリング確認)・class P(pve1でレンダリング確認)では `denied: unknown command` で拒否されることを確認。`users`/`unit-files`/`forced-command-keys` はQ/G/Pすべてで動作することを確認。
- **V2(拒否系統)**: enum外(`acl-status bogus-name`)、パス風operand(`acl-status /etc/shadow`)、operand過多(`acl-status yoshi-home extra`、`users extra` 等)、空(`acl-status` のみ)、改行混入(`SSH_ORIGINAL_COMMAND=$'users\nrm -rf /'`)のすべてで `denied:` プレフィックス付きメッセージが stderr へ出て、**パイプを使わず直接 `$?` を見て**非ゼロ終了することを確認(Q/G/P全class)。
- **V3(X4が鍵本体を出さない)**: ダミーの `authorized_keys`(ダミー鍵material入り)を用意し `forced-command-keys` を実行、出力にkey type・base64鍵本体が含まれず、`command=` パスとコメント欄のみが出ることを確認。
- **V4(X2のuid範囲)**: このローカル環境自体の `getent passwd`(root=0、daemon等システムuid、`nobody`=65534を含む)に対して `users` を実行し、出力が uid 1000〜64999 の5アカウントのみに絞られている(root・システムアカウント・nobodyが出ない)ことを確認。
- **V5(既存チェック無変更)**: `git diff` で追加ブロック以外に変更が無いこと(削除された行は、新checkを列挙リストへ足すために書き換えた3行の宣言行のみで、既存の選択肢は1つも失われていない)を確認。加えて `disk`/`status`/`unit-cat sshd`/`deployed-hash authorized-keys`/`cluster-status` 等の既存checkをローカル実行し、従来どおり動作(またはこのローカル環境に実バイナリ/実ファイルが無いことによる想定内のエラー)することを確認。
- **V6(eval無し・書込語彙無し)**: `grep` で対象5scriptに実際の `eval` 呼び出しが無い(コメント中の言及のみ)こと、I-1の禁止語彙(`pvesh create/set/delete`、`systemctl start/stop/restart/enable`、`qm start/stop`、リダイレクト、`tee`/`rm`/`mv`/`cp`)が無いことを確認。
- **V7(Codex wrapper側)**: `homelab-investigate.sh.j2`(authy/monnieでレンダリング)と `homelab-investigate-pve.sh.j2`(pve1でレンダリング)に対し、`ssh` をスタブ(引数をechoして即終了)に差し替えた `PATH` でローカル実行。`users`/`unit-files`/`forced-command-keys` が実SSHへ到達せず正しい remote command 文字列(例: `... recovery-exec@authy.internal users`)を組み立てて `run_remote` まで進むこと、`acl-status`(wrapperのallowlistに無い)とoperand過多が `denied:` で拒否されることを確認。
- **V8(構文・lint)**: `ansible-playbook --syntax-check` を `playbooks/dev_investigate_setup.yml` / `playbooks/recovery_io_setup.yml`(このrole 2つを使う唯一のplaybook)へ実行、両方成功。`ansible-lint roles/dev_investigate roles/recovery_exec` を実行、検出された3件の `var-naming[no-role-prefix]` は `roles/recovery_exec/tasks/target_setup.yml` の既存 `register` 変数名に対するもので、自分は当該ファイルを変更していない(着手前から存在する指摘、対象外)。`.sh` / `.sh.j2` は `bash -n`(Jinjaレンダリング後)で全て構文OK。

## 未解決事項

- `getfacl -p -- <path>` が「パスが実在しない」場合(例えば `reports-root` がまだ作られていないタイミング)にどう振る舞うかは、GNU acl の標準的なエラー出力(`getfacl: <path>: No such file or directory` を stderr、非ゼロ終了)に委ねている。カタログはこのケースを明示的に扱っていないため、独自の追加ハンドリングはしていない——`set -euo pipefail` により script 自体は非ゼロ終了で止まる。
- 配備・実機での動作確認(quory / authy / monnie / pve1 / pve2 それぞれでの実際の `getfacl` 権限・`getent`・`systemctl list-unit-files` の出力)は行っていない。plan §4 のとおり配備はCoordinatorが行い、実機検証はTesterの役。
- `AGENTS.md.j2` の追記は「用途の説明」のみで、Codex側の運用手順(いつこれらを使うべきか、というLadder上の位置づけ)への統合は行っていない——既存の `## Recovery Procedure (Ladder)` 節は変更していない。必要であれば別途判断を要する。
