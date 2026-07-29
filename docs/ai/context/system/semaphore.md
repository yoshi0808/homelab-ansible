# System Context: Semaphore

## 領域の役割

SemaphoreはAnsible playbookをGUIから手動またはschedule実行し、jobの成否と標準出力を運用者へ提示する入口である。`semaphore_servers` groupには`ansy`と`quory`が含まれるが、`ansy`は開発側、`quory`は確定済みコードを使う本番実行側である。

## ノードの役割

- `ansy` (`ansy.internal`): 開発・レビュー・検証環境であり、開発側Semaphoreの対象でもある。
- `quory` (`quory.internal`): `control_nodes`に属する本番Ansible実行基盤であり、本番Semaphoreとschedule実行の制御点である。
- `pve1` / `pve2`、`authy`、`monnie`: Semaphoreから起動されるhealthcheck、patch dry-run、証明書更新等の管理対象。

`ansy`と`quory`の両方にSemaphoreがあっても、同一jobを同時実行する構成や自動フェイルオーバーを意味しない。開発系と本番系の境界を保つ。

## 依存関係

- Semaphore jobは、Gitから取得したplaybook、inventory、role、実行環境の名前解決、必要なsecret、対象ホストへの到達性に依存する。UI上のtemplate、inventory、repository、schedule、extra variablesの現在状態はGitだけでは完結しない。
- `roles/systemd_timers/defaults/main.yml`では、RADIUS・Proxmox・monitoringのhealthcheck、Proxmox patch dry-run等がSemaphore UI scheduleへ移行済みとしてコメント化されている。ただし、UI上で現在有効かどうかと正確な時刻はSemaphore UIで確認する。
- `proxmox_healthcheck`と`proxmox_hw_check`は、複数ホストの結果、次の対応、warnings/criticals、確認項目を1行のSemaphore summaryとして標準出力へ出す。job表示は概要、実行コントローラ上のJSON reportは詳細として使い分ける。
- `cert_renew.yml`は`quory`から実行するSemaphore向けの変更系playbookで、`ansy`のSemaphore、Proxmox UI、`monnie`のGrafanaへ証明書を配布し、必要なserviceをrestartする。CAの秘密情報は一時領域にだけ展開し、cleanupを行う設計である。
- `quory`自身のSemaphore証明書更新は、SemaphoreをrestartするためSemaphore jobから実行せず、`cert_renew_quory.yml`をsystemd timerから実行する。制御平面自身を自分で停止させないための分離である。

## ジョブ結果の読み取り(2026-07-27 実測)

Semaphoreのジョブ結果はSQLite(`semaphore.db`)にあり、read-onlyのSELECTで読める。AIが読む経路は名前付き操作 `homelab-semaphore-query`(`recovery_exec` が配備)に限る。

- **時刻の保存形式は `YYYY-MM-DD HH:MM:SS.nnnnnnnnn +0000 UTC`**(Goの `time.Time.String()`)。**RFC3339ではなく、`Z` 表記でもない。** ナノ秒9桁・空白区切りのオフセット・末尾のゾーン名という3点が標準パーサを素通りしないため、扱うときは専用のパースが要る。
- **オフセットは常に `+0000` で、保存は実質UTC。** `/etc/semaphore/config.json` の `Asia/Tokyo`(ansy / quory とも)は**保存形式を支配していない**。リポジトリの時刻表記はJSTが正のため、読み出した値は変換して使う。設定ファイルの記述からタイムゾーンを推定しない。
- `task` テーブルには `start` と `end` の両方が存在する(`end` はSQLの予約語のため、列参照は引用が要る)。`status` の語彙は `success` / `error` / `stopped`。
- 既存の `recent-failed` は `substr(t.start,1,19)` を返すため、**タイムゾーンを決める末尾を切り落とす**。生の保存形式を見るには `task-time <id>` を使う。
- `semaphore.db` は `recovery-exec` の権限でのみ読める(ACL)。ansyの接続ユーザーのままでは `unable to open database` になる。
- ansy / quory ともSemaphoreのバージョンとサービス実行ユーザーは一致している(2026-07-27時点)。スキーマ調査は開発側(ansy)で先に行い、本番の読み取りを最小化する。

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
