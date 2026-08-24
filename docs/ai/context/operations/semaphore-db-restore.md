# Operations Context: quory の Semaphore を退避物から戻す

作成日: 2026-08-17

**位置づけ**: `roles/semaphore_db_backup`(`playbooks/semaphore_db_backup.yml`)が Synology NFS へ作る1世代(3ファイル)を使って、quory の Semaphore を戻す手順を記録する。**戻す操作自体は自動化しない**(`docs/ai/reviews/semaphore_db_backup/2026-08-17_001_requirement.md` 非ゴール)。ここは「人が実際に手を動かすときに何を確認すればよいか」の記録であり、実行手順書ではない。

値(保存先パス、世代数)はここに写さない。正本は `roles/semaphore_db_backup/defaults/main.yml`。

## 1. 1世代の中身

保存先(`semaphore_db_backup_dest_dir` 配下)の `<世代名>/` に、3ファイルが揃って置かれている。

| ファイル | 何か | 誰が読むか |
|---|---|---|
| `semaphore.db` | quory の Semaphore の SQLite DB そのもの(`sqlite3 .backup` による一貫スナップショット) | Semaphore 本体(`semaphore server` プロセス) |
| `config.json` | quory の `/etc/semaphore/config.json` の写し(Slack Webhook URL、DBダイアレクト、**access key を復号する鍵**、TLS証明書パス等を含む) | Semaphore 本体 |
| `semaphore_projects_export.json` | `semaphore projects export` の出力(templates / schedules / inventories / repositories / environments / keys(メタデータのみ)/ views / meta) | `semaphore projects import`、または人間による目視確認 |

**`semaphore.db` と `config.json` は同じ世代のペアで使う。** `config.json` はDB内の暗号化された access key を復号する鍵を持つ(requirement §1「access keyの実体…configの鍵とセットでのみ復号できる」)。異なる世代の `semaphore.db` と `config.json` を組み合わせると、鍵が合わず access key が復号できない状態になりうる — これは検証していない未確認の懸念であり、**組み合わせて使わないことで避ける**。

**主経路(§2)で対象ホストへ配置するのは `semaphore.db` と `config.json` の2つだけである。** `semaphore_projects_export.json` は Semaphore 本体が直接読むファイルではなく(`semaphore server` の起動時読み込み対象に含まれない)、確認用(§3)または `semaphore.db` が使えない場合の補助的な取り込み経路(§4)でのみ使う。**3ファイルとも同じ場所へ戻す、という読み方をしない。**

## 2. 主な復元経路 — DBファイルそのものを差し替える

**quory が全体として失われたときに、いちばん多くを取り戻す経路。** `semaphore.db` は quory の Semaphore が持っていたものの生の写しなので、これを別インスタンスへ差し替えると、そのインスタンス上で users・API token・task の実行履歴・project 定義・inventory / repository / environment のオブジェクト定義・template・schedule が、退避した時点の状態のまま現れる。

2026-08-04 に ansy の Semaphore を同じ考え方(quory のバックアップからの復元)で一度手で立てた実績があり(`docs/ai/context/system/semaphore.md`「ansy の Semaphore」)、AC7 の検証はこの手順を、このplaybookが作った退避物で再現するものである。

### 手順(人が行う)

1. 対象ホスト(検証なら ansy、実際の災害復旧なら新しい quory)で `semaphore` サービスを止める。
2. 対象ホストの既存 `/var/lib/semaphore/semaphore.db` と `/etc/semaphore/config.json` を(戻せるように)退避する。
3. 退避物の `semaphore.db` を `/var/lib/semaphore/semaphore.db` へ、`config.json` を `/etc/semaphore/config.json` へ配置する。所有者・パーミッションは対象ホストの既存の値に合わせる(退避物側は `root:root 0600` — R5 参照。実際に読むのは `semaphore` サービスを動かすOSユーザーなので、そのユーザーが読める所有・権限へ調整が要る)。
4. サービスを起動する。`semaphore server` は起動時にマイグレーションを実行する(`docs/ai/context/system/semaphore.md`「インストールと版上げ」)。**退避時の Semaphore の版と、起動する側の版が違うと、マイグレーションが不可逆に進む。** 版を揃えられない場合は、起動前に版を確認すること。

### 起こりうる不整合(未検証、確認が要る)

- **`config.json` はホスト固有の値(TLS証明書パス、bind host/port 等)を持つ。** quory の `config.json` をそのまま別ホスト(ansy 等)へ置くと、そのホストに存在しない証明書パスを参照して起動に失敗する可能性がある。この場合、`config.json` のうち DB 接続とaccess key の復号鍵(**§1 のペア制約**)だけを保ち、TLS/bind 関連は対象ホストの値へ書き戻す、といった手当てが要る可能性がある。**このセッションでは実機確認していない。**
- 対象ホストに既に別の Semaphore project(例: ansy 自身の project id=2)が存在する場合、差し替えは**そのインスタンス自体を quory の状態で上書きする**ことを意味する。検証用途で使い捨てるのでない限り、この経路を本番の別ホストへ直接使わない。

## 3. 補助経路 — `semaphore_projects_export.json` を読む・取り込む

`semaphore projects export` の出力は、DBファイルを直接扱わずに template / schedule / inventory / repository / environment の定義**内容**を見られる、人間可読な形式である。

- **確認用途**: 「この世代の時点でどの template・schedule が存在したか」を、`semaphore.db` を SQLite として開かずに読める。
- **取り込み用途**: 新しい project(quory 自体が再構築後で project がまだ無い状態など)へ `semaphore projects import --file <path>` で取り込める(§4 参照)。**このセッションでは import 側のコマンドを実測していない** — requirement の「観測されている事実」が確認できているのは `export` 側のみ。

**`keys` に何が入るかは未確認である。** requirement の観測事実のとおり、ansy 側で確認できた唯一の鍵は `type: none` であり、`type: ssh` の鍵で export した場合に秘密材料(秘密鍵そのもの)が JSON に出力されるかどうかは確認されていない。**確認できるまでは、この JSON ファイルも `config.json` と同格の機密として扱う**(保存先モード・アクセスは playbook 側で既に `root` 限定にしているが、目視確認のために取り出す場合は取り扱いに注意する)。

## 4. `semaphore.db` そのものが使えない場合の経路(未検証)

`semaphore.db` が壊れている、または版の非互換で起動できない場合を想定した経路。**このセッションでは実機で試していない、設計上の見立てである。**

1. 対象ホストへ Semaphore を新規インストールし、新しい project を作る。
2. `semaphore projects import --file semaphore_projects_export.json` で template / schedule / inventory / repository / environment を取り込む。
3. **この経路では requirement §1 の表のとおり戻らないものがある**: users・API token・task の実行履歴・access key の実体(鍵の値そのもの。§3 の未確認点とは別に、そもそも export に暗号化前の値が含まれない設計であるため)。**これらは作り直しになる。**

## 5. 退避物に入っていないもの

- **SSH 鍵の実体。** requirement 非ゴール(2026-08-17、Yoshinobu確認)。Semaphore の backup 対象外であることは quory → ansy の取り込みで確認済み。鍵は Bitwarden と外部媒体にある。復元後、inventory が参照する SSH 鍵は**別途、鍵の保管場所から戻す**必要がある。
- **quory 自身の OS 設定・配備物**(`/usr/local/`, `/etc/systemd/system/` 等)。本案件の対象は Semaphore に限る(非ゴール)。quory 自体の再構築は別の話である。

## 6. 復元後に確かめること

- Semaphore の UI または API で、template 一覧・schedule 一覧が復元前の内容と一致すること(AC7)。
- （実際の災害復旧の場合のみ）既存の schedule が退避時点の `active` 状態のまま動いているか確認する — **カタログの reconcile を流すと、`active` はカタログが宣言した値へそのまま揃う。** **2026-08-24 に有効化ゲートを撤去したため、以前あった「4条件が揃わない限り `false → true` にならない」という抑制は無い**(`docs/ai/reviews/semaphore_activation_gate_removal/`)。**復元直後に reconcile を流すと、カタログが `active: true` としている schedule はその時点から動き出す。** 止めたまま確認したい段階があるなら、reconcile を流す前に行うこと。
  - **ただしこれは、復元先が canonical な API base URL のときに限る。** 別名で建て直した quory や ansy の複製へ向けて流すと、**有効化を伴う適用は接続先の検査で止まる**(`semaphore_schedules_canonical_api_base_url`)。**災害復旧で quory を別のホスト名で再建したときは、この検査が先に当たる** — 止まるのは正しい動作であり、**canonical URL の値をカタログ側で更新するのが筋**である。`-e` でその場だけ変えて通さない。

想定読者Role: Coordinator = 復元判断時に全文確認、Tester = AC7検証時に手順を参照、その他 = 概要のみ。
