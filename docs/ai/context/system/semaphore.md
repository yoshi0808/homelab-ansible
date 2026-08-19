# System Context: Semaphore

## 領域の役割

SemaphoreはAnsible playbookをGUIから手動またはschedule実行し、jobの成否と標準出力を運用者へ提示する入口である。`semaphore_servers` groupには`ansy`と`quory`が含まれるが、`ansy`は開発側、`quory`は確定済みコードを使う本番実行側である。

## ノードの役割

- `ansy` (`ansy.internal`): 開発・レビュー・検証環境であり、開発側Semaphoreの対象でもある。
- `quory` (`quory.internal`): `control_nodes`に属する本番Ansible実行基盤であり、本番Semaphoreとschedule実行の制御点である。
- `pve1` / `pve2`、`authy`、`monnie`: Semaphoreから起動されるhealthcheck、patch dry-run、証明書更新等の管理対象。

`ansy`と`quory`の両方にSemaphoreがあっても、同一jobを同時実行する構成や自動フェイルオーバーを意味しない。開発系と本番系の境界を保つ。

## 依存関係

- Semaphore jobは、Gitから取得したplaybook、inventory、role、実行環境の名前解決、必要なsecret、対象ホストへの到達性に依存する。**UI上の inventory / repository / environment オブジェクトと、登録済みの key・user の現在状態はGitだけでは完結しない。**
- **template と schedule の正本は `roles/semaphore_templates/defaults/main.yml` のカタログにある**(template=2026-08-04、schedule=2026-08-10 の `semaphore_schedules_as_code` 案件)。templateの同定は各templateの `description` に書いたマーカー、scheduleの同定は schedule 自身の name で行う。実物の一覧は `semaphore-query template-list` で読める(下記)。**「いつ押されるか」は `semaphore_schedules_catalog` が持ち、実行パラメータ(`task_params`)も同じエントリが持つ。**
- **カタログが管理しないもの** — inventory / repository / environment のオブジェクト定義そのもの(カタログはこれらを名前で参照するだけ)、users、access key の実体、task の実行履歴。**これらは `semaphore.db` の中にしか無い。**
- **`cron` を決めるとき、このカタログだけで衝突を判定しない。** 定期実行の窓はSemaphoreの外にも広がっている — UniFi(Console / Device / Protect の自動update)、Proxmox(ローカル/NASバックアップ、ZFS TRIM・scrub)、systemd timer、Ubuntuのunattended-upgradesとfstrim。**管理元が別々で、横断して見えるのはYoshinobuが維持する「バッチ処理工程管理表」だけである**(このリポジトリの外にある)。**時刻を提案・変更するときは、その表に照らしてもらうこと。** 照らさずに「カタログ上は空いている」を根拠にしない — 2026-08-18、02時台をUniFiのAP・スイッチ自動update(ネットワークが揺れうる)と重ねかけた。
- `roles/systemd_timers/defaults/main.yml`では、RADIUS・Proxmox・monitoringのhealthcheck、Proxmox patch dry-run等がSemaphore UI scheduleへ移行済みとしてコメント化されている。ただし、UI上で現在有効かどうかと正確な時刻はSemaphore UIで確認する。
- `proxmox_healthcheck`と`proxmox_hw_check`は、複数ホストの結果、次の対応、warnings/criticals、確認項目を1行のSemaphore summaryとして標準出力へ出す。job表示は概要、実行コントローラ上のJSON reportは詳細として使い分ける。
- `cert_renew.yml`は`quory`から実行するSemaphore向けの変更系playbookで、`ansy`のSemaphore、Proxmox UI、`monnie`のGrafanaへ証明書を配布し、必要なserviceをrestartする。CAの秘密情報は一時領域にだけ展開し、cleanupを行う設計である。
- `quory`自身のSemaphore証明書更新は、SemaphoreをrestartするためSemaphore jobから実行せず、`cert_renew_quory.yml`をsystemd timerから実行する。制御平面自身を自分で停止させないための分離である。

## ansy の Semaphore(検証用インスタンス、2026-08-04)

**ansy にも Semaphore が動いており、quory とは別インスタンスである。** 素性は**quory のバックアップからの復元**で、quory が VM でないため Semaphore のバックアップが必要になり、その復元手順を ansy で検証した経緯による(Yoshinobu 談、2026-08-04)。そのため project 名・inventory 名・repository 名は quory と同じだが、**id は異なる**(2026-08-18時点で ansy=3 / quory=1。ansy は 2026-08-04 の実測では 2 で、**その後変わっている**)。**id を固定値として扱わない。この行の値も、読んだ時点で古い可能性がある。**

- 接続は `https://ansy.internal:3000`。**HTTPS である**(httpで叩くと400が返る)。証明書は `homelab_cert_renew` が配っている。
- **2026-08-04 に SSH 鍵を2本(サーバ群向け / github)削除した。** 残るのは `type=none` の1本のみで、inventory と repository はそれを指す。**したがってこのインスタンスは、どのホストへも到達できず、リポジトリを clone することもできない。**
- この「鍵が無いことによる無害さ」は、**API の実挙動を本番へ触れずに確かめられる**という価値を持つ。実際、2026-08-04 に id の固定値・`arguments` の型・API と DB スキーマの差という3つの誤った前提が、本番へ入る前にここで判明した。
- **鍵を再登録しない。** 登録した瞬間にこの性質は失われる。

**quory 側の鍵を、ansy と同じ判断で消してはならない。** Semaphore は inventory の `ssh_key_id` を通じて ansible へSSH鍵を渡すため、quory 側の鍵は本番の認証経路そのものでありうる。ansy で消して無害だったのは、ansy が本番ジョブを走らせないからにすぎない。

## ジョブ結果の読み取り(2026-08-19、SQLite直読みからAPI経由へ移行)

**Semaphoreのジョブ結果はREST API(`GET /project/{id}/tasks` 等)で読む。** AIが読む経路は名前付き操作 `homelab-semaphore-query`(`recovery_exec` が配備)に限る。**project role `guest`(読み取り専用)のトークンを使い、admin権限は持ち込まない。** project idは名前(`homelab-ansible`)で解決し固定値を持たない。トークンファイルは `/etc/homelab-recovery/semaphore-query-token`(root所有、named-user POSIX ACL read — Semaphoreが再作成するファイルではないため通常のACLで足りる)。設計の正本は `docs/ai/reviews/semaphore_query_api/2026-08-19_001_requirement.md`。

**このtokenを直接読む識別子は4つ**(2026-08-19、R13): `recovery-exec` / `incident-inspect` / `dev-investigate`(R9)に加え、`incident_investigate_run_user`(`yoshi`。旧設計ではsemaphore.dbの所有者として直接読めていたが、token file方式では明示ACLが要る——R13で追加)。**ただしincident-inspect自身のCodexセッションはこのtokenを実際には使わない**(R14)。incident-inspectのsandbox(`--sandbox read-only`)は外向き通信を塞ぐため、`homelab-semaphore-query`をこのセッションの中から呼んでも必ず失敗する(2026-08-19実測)。Semaphoreの情報はyoshi(`roles/incident_investigate`)がsandboxの外で先読みし、incident-inspect専用のcontext directoryへジョブ番号入りのファイル名(`semaphore-context-<job-id>.txt`)で渡す——workspaceとは別のディレクトリで、AGENTS.md(LLMが従う指示書)と同居させない設計にしている(独立レビューround2 High #1/#2/#3を参照、`docs/ai/reviews/semaphore_query_api/2026-08-19_002_implement.md`)。

- **時刻はAPIが返すRFC3339をそのまま出力する。** SQLite直読み時代の保存形式(`YYYY-MM-DD HH:MM:SS.nnnnnnnnn +0000 UTC`、Goの `time.Time.String()`)は、下記の移行後はもう出力されない。
- `status` の語彙は `success` / `error` / `stopped`(終端3値)、それ以外は実行中側とみなす。
- **`task-hosts` / `task-errors` はAPIに構造化エンドポイントが無い**(`GET /project/{id}/tasks/{task_id}/hosts` と `.../errors` はいずれも404、2.19で追加された `/stages` もstage単位でホスト内訳を持たない)。ジョブ出力テキスト(`task-output` と同じ取得元)からの導出になっている — `task-hosts` は `PLAY RECAP` 行以降、`task-errors` は `fatal:` で始まる行。出力にはANSI SGRエスケープが埋め込まれるため、導出前に除去する。`PLAY RECAP` が見つからない場合は0件の正常終了ではなく非ゼロ終了とする(完了したjobの出力には必ずPLAY RECAPがあるはずなので、無い場合は取得・整形側の異常とみなす)。
- **`template-list <n>`は、テンプレート1件ごとに自己記述的なJSON1行を返す**(2026-08-19、旧: `project__template` の CREATE TABLE文+行dumpの2文形式から変更。APIの応答が既にフィールド名付きJSONであるため、列名を推測しない目的はより直接に満たせる)。
- **2.19.8 で `semaphore.db` の直読みが壊れたことが、この移行の理由である**(2026-08-19、quory / ansy とも実測)。2.19.8 は SQLite を **WAL モード**で開き(上げる前は `journal_mode=delete`)、`semaphore.db-shm` / `semaphore.db-wal` が現れる。**この2ファイルに ACL は付かず、WAL では読み手も `-shm` を読み書きできる必要がある**ため、`semaphore.db` に `r--` を持つだけの `recovery-exec` / `incident-inspect` / `dev-investigate` は `unable to open database file (14)` になっていた。**ファイル個別に ACL を足しても直らない** — 停止中に `journal_mode=delete` へ戻しても、起動時に必ず WAL へ戻され `-shm` / `-wal` が ACL なしで作り直される。**そもそも SQLite の直読みは Semaphore がサポートする接し方ではない**(公開された口は API であり、ストレージの内部形式は上流が自由に変えてよい)。当時の実測は `docs/ai/reviews/semaphore_upgrade/2026-08-18_003_result.md`。
- ansy / quory ともSemaphoreのバージョンとサービス実行ユーザーは一致している(**2026-08-18に両方を 2.19.8 へ上げた**。案件: `docs/ai/reviews/semaphore_upgrade/`)。スキーマ調査は開発側(ansy)で先に行い、本番の読み取りを最小化する。**両者の版が揃っていることがこの前提を支えているので、片方だけ上げた状態を作ったら、その間は ansy のスキーマを quory のものとして読まない。**

## UIは新しいテンプレートを即座に表示しない(2026-08-05 Yoshinobu実測)

**APIで作成したテンプレートは、一度ログアウトするまでUIの一覧に現れない。** 作成自体は成功しており、DBにもAPIにも入っている。

**症状の出方が紛らわしい。** reconcileを流した本人が「ボタンが出ない」と見るため、ジョブの失敗・カタログの記述ミス・reconcileが走っていないこと、のいずれかを疑って実行ログ側を探しに行くことになる。実際には表示だけの問題である。

**確かめ方**: `ssh quory-investigate "semaphore-query template-list <n>"` で実物を見る。ここに在ればUIの表示の問題で、無ければ本当に作られていない。**UIの見た目を、作成されたかどうかの判断に使わない。**

## インストールと版上げ(2026-08-10 ansy 実測)

**apt リポジトリは存在しない。`apt upgrade` では上がらない。** 導入は GitHub Releases の `.deb` を `apt install ./semaphore_X.Y.Z_linux_amd64.deb` で入れた形で、apt から見た供給元は `/var/lib/dpkg/status` だけである(`apt-cache policy semaphore`)。`/etc/apt/sources.list.d/` に semaphore の source は無い。上流も apt リポジトリを提供しておらず、公式の Upgrading 手順自体が「Releases から `.deb` を落として `dpkg -i`」である。**新版が出たことを知る経路が無い。**

**この `.deb` が持つファイルは `/usr/bin/semaphore` の1つだけで、maintainer script を持たない**(`/var/lib/dpkg/info/semaphore.list`、postinst / prerm ともに存在しない)。したがって:

- **`apt install` は `needrestart` 経由でサービスを再起動する**(2026-08-18 ansy 実測)。`.deb` 自身は maintainer script を持たないが、Ubuntu の apt hook である `needrestart` が `systemctl restart semaphore.service` を打つため、**install した瞬間にマイグレーションまで走る**。**`NEEDRESTART_MODE=l` を付けると抑止でき**(同日、同じ `.deb` の `--reinstall` で MainPID が変わらないことを確認)、install と restart を分離できる。**版上げの playbook は、この抑止を明示しない限り install と restart を分けられない。**
- `/etc/systemd/system/semaphore.service` と `/etc/semaphore/config.json` は **dpkg の管理外**(`dpkg -S` が一致なし)。パッケージを入れ替えても unit と config は変化しない。
- unit は `KillMode=control-group` なので、restart で死ぬのは `semaphore.service` の cgroup だけである。**別セッションから手で流している `ansible-playbook` は巻き添えにならない。** 巻き添えになるのは Semaphore job として流したときに限る。**そして `setsid` / `nohup` による切り離しでは逃げられない**(2026-08-18 実測) — cgroup の所属は fork で継承されるため、非同期化しても同じ cgroup に留まり一緒に殺される。**逃げる唯一の方法は `systemd-run` で PID1 に別 unit を作らせることである。** 実績は `roles/ubuntu_vm_full_upgrade/tasks/reboot_quory.yml`(quory が自分を reboot する同型の問題)。

**不可逆なのはプロセスではなく DB である。** dialect は `sqlite`、実体は `/var/lib/semaphore/semaphore.db`。`semaphore server` は起動時にマイグレーションを実行するため、restart した時点でスキーマが上がる。バイナリを戻しても旧版が動く保証は無い。**退避すべきはバイナリではなく `semaphore.db`。** なお `semaphore migrate` サブコマンドが独立に存在するので、マイグレーションを `server` の起動任せにせず明示のタスクへ切り出せる。

版の読み取りは `semaphore version` で、出力は `2.19.8-3449a04-1786894505` の形(`X.Y.Z` の後に commit hash とビルド番号が付く)。

**ansy / quory とも非 community 版**(`semaphore_X.Y.Z_linux_amd64.deb`)である。2026-08-18〜19 に**両ホスト・両版**(2.18.4 / 2.19.8)で `/usr/bin/semaphore` の sha256 を upstream の `.deb` から展開したバイナリと照合して確定した。**`.deb` は2種類公開されており(`semaphore_` と `semaphore_community_`)、取り違えると版と一緒にエディションまで入れ替わる。** **版上げのたびに、入れる前(現行バイナリ)と入れた後の両方で照合する。**期待値はここへ書かない — 版ごとに変わるため、upstream の該当リリースの `.deb` を展開して都度求める。

**未確認**: quory の unit と config の中身は測っていない。`quory-investigate` の forced command に apt / dpkg / systemctl-cat 系の操作が無く、この経路では読めない。

## 可用性

- 本番Semaphoreの停止は、新しいGUI・schedule jobの起動と結果閲覧に影響する。すでに稼働中の管理対象serviceの可用性と、制御平面の可用性は分けて判断する。
- `quory`はProxmoxクラスタ外の制御点として、rolling patch中も到達可能であることが重要である。
- Semaphoreはjobをsuccess/failで表現するため、意図的なskipやWARNINGの意味が潰れないよう、playbook側のsummary・通知・終了状態を併せて読む。
- `ansy`と`quory`は役割分離であり、片方の障害時にもう片方が同じscheduleを自動継続することはコードから確認できない。
- UI設定はリポジトリ外で変化し得る。scheduleが存在するという過去記録だけで、現在も実行されていると判断しない。

## 安全上の注意

- Semaphore UIからの起動も本番操作である。job templateに`--check`や安全用extra variablesがあるという推測だけで変更系playbookを実行しない。playbook先頭の`tester-gate`と実際のtemplate設定を確認する。
- `cert_renew.yml`は`risk-accepted`であり、`--check`でも対象へのissue・deployが本実行される。`cert_renew_quory.yml`も一部taskは`--check`で実行され、Semaphore deploy/restartだけがgateされる。通常のdry-runと同一視しない。
- Semaphoreのtemplate、schedule、secret、UI設定を変更する作業はリポジトリ編集とは別の外部状態変更であり、人間の明示依頼なしに行わない。
- private key、password、token、secret変数の値をjob log、Context、レビュー文書へ転載しない。
- IPアドレス、VLAN ID、VM IDを記載せず、inventory名またはFQDNで表す。

想定読者Role: Coordinator=実行経路とGit外状態を詳細確認(2026-07-29、Tech Lead廃止に伴い統合)、Implementer/Reviewer/Tester=Semaphore経由案件時に詳細確認、その他=概要のみ。
