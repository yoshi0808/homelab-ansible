# Autonomous Recovery Policy v0.5 (draft, 試行錯誤前提)

作成日: 2026-06-28
版: v0.5（アカウント構成・LLM実行基盤・ガバナンスの考え方を全面見直し）
対象: authy / monnie / sophos-fw の異常検知 → 自律復旧パイプライン

参照:

- docs/ai/prompts/core.md
- docs/ai/prompts/proxmox_patch_policy.md
- docs/ai/prompts/proxmox_backup_restore_verify_policy.md

本書は「何を許可し、何を許可しないか」を定める。実装方法の詳細はここでは規定しない（v2.0方針: what/howの分離）。

---

## 0. v0.5での変更の経緯

v0.4は「実装完了の正本」として書いたが、実装後の振り返りで以下が判明し、再設計が必要になった。

```text
- アカウント分離が「目的の違い」ではなく「アクターが違うから機械的に分離」
  という基準で進んでしまい、単一運用者のホームラボに対して過剰な複雑さを
  生んでいた（エンタープライズ的発想の誤用）
- annの鍵がforced command保護を持たない唯一の鍵であり、recovery
  pipelineがこれを保持していることへの認識が不足していた
- LLM実行基盤（Claude Code）の選定が、既に実績のある別の選択肢
  （Codex CLI、patch適用のadvisor役として運用実績あり）との比較なしに
  進んでいた
```

本書はこれらを「目的・リスク種別が異なる場合のみ分離する」という基準で再設計したもの。実装は試行錯誤を前提とし、確定事項と検証中の事項を明示的に分ける。

---

## 1. 目的

authy / monnie / Sophos の業務継続を最優先とし、異常検知時に人間の承認を待たず自律的に復旧を試みる。外出時（スマホのみ、SSH鍵なし、VPN経由でも実質操作困難）でも対応できることが前提。

---

## 2. 対象と対象外

| 対象 | タグ | 適用される復旧手段 |
|---|---|---|
| Sophos (`sophos-fw`) | `hacritical`, `preferpve1` | VMリブート、フェイルオーバー（サービスrestartは対象外） |
| authy | `hacritical`, `preferpve1` | サービスrestart、VMリブート、フェイルオーバー |
| monnie | `ops`, `preferpve2` | サービスrestart、VMリブート（フェイルオーバーは対象外） |
| pve1 / pve2 | - | 対象外。既存 `proxmox_patch_policy.md` の枠組みに委ねる |
| ansy | - | 対象外（開発環境） |

### 2.1 VMID / systemdユニット対応表

| 対象 | VMID | サービスrestart対象unit |
|---|---|---|
| authy | 101 | `freeradius.service` |
| monnie | 211 | `grafana-server.service`, `prometheus.service`, `loki.service`, `unpoller.service` |
| sophos-fw | 1000 | 対象外（VMリブート・フェイルオーバーのみ） |

---

## 3. 設計原則（v0.5で明文化）

### 3.1 分離の基準

エンタープライズ的な「役割ごとに分ける」発想をそのまま当てない。分離するのは以下の場合のみとする。

```text
分離する: 目的が違う（例: annの定常自動化 と LLM判断が混じる緊急対応）
分離する: リスクの種別が違う（例: 通信トークンの機密性の保護 と
          実行権限濫用の防止は別種のリスク）

分離しない: 単に「アクターが違う」というだけの理由
分離しない: 既に守られているものへの"念のため"の積み増し
            （具体的に説明できるリスクが無い限り、多層防御を
            目的とした重複分離は採用しない）
```

### 3.2 開発（ansy）と本番（quory）は「場所」の違いであり「目的」の違いではない

ansyとquoryで同一のアイデンティティ・同一の鍵・同一のコードを使う。テストがansyで完結し、quoryへの移行は「動かす場所を変えるだけ」になることを優先する。

ステージング環境を別途常設しない。本番同等の権限配下で検証する必要がある場合は、Proxmoxの使い捨てクローンVM（`proxmox_backup_restore_verify`と同じ発想）を使う。

---

## 4. アカウント構成

### 4.1 アカウント一覧

| Identity | 配置 | 目的 | 保持する鍵・情報 |
|---|---|---|---|
| `ann` | 既存の対象ホスト全般 | 既存の定常自動化（patch/evacuate/restore等）。変更なし | NOPASSWD ALL sudo、forced command無し |
| `recovery-io` | ansy・quory共通 | Slack接続（Socket Mode）・トークン保持・認可チェックのみ | Slack Bot Token / App Token のみ。鍵は一切持たない |
| `recovery-exec` | ansy・quory共通 | Codexの呼び出し、調査・復旧の実行 | §4.2の調査用キー1本、§4.3のrecovery_action用キー1本。Slackトークンは持たない |

`recovery-io`と`recovery-exec`はansy/quoryで同一の実装・同一の鍵を使う（§3.2）。旧`recovery-slack`/`trigger`/`recovery-runner`の3アイデンティティ構成は廃止する。

### 4.2 鍵一覧

| 鍵 | 保持者 | 対象ホスト | 本数 | forced commandの性質 |
|---|---|---|---|---|
| 調査用キー | `recovery-exec` | authy / monnie / sophos-fw / pve1 / pve2（共用、1本） | 1 | パラメータ受領可。ノード側wrapperが許可リスト照合（§4.4） |
| recovery_action用キー | `recovery-exec` | authy / monnie / pve1 / pve2（共用、1本。annとは別系統） | 1 | パラメータ不可。完全固定文字列のみ（§4.3） |
| `ann`の既存鍵 | `ann`自身 | 既存対象ホスト全般 | 既存のまま | forced command無し（既存の定常自動化専用、recovery-execは使わない） |

ノード間で鍵を共用する理由: 秘密鍵は常にansy/quory側（`recovery-exec`）にあり、ターゲット側（authy/monnie/pve）には公開鍵しか置かれない。攻撃が成立するのはansy/quoryへの侵入時のみであり、その時点で`recovery-exec`が持つ鍵は本数に関わらず等しく危険になる。ノード単位で鍵を分けても防御効果が無いため、§3.1の基準により共用する。

### 4.3 recovery_action用キー（変更系）の設計: 完全固定

復旧3 primitive（サービスrestart・VMリブート・HA failover）は、パラメータを一切受け取らない完全固定文字列のforced commandとする。

```text
command="systemctl restart freeradius"（authy向け、固定）
command="systemctl restart grafana-server"（monnie向け、サービスごとに
  個別登録。grafana-server/prometheus/loki/unpollerの4本）
command="qm reboot <固定vmid>"（VMリブート用、対象ごとに固定）
command="ha-manager crm-command relocate vm:<固定vmid> <固定node>"
  （フェイルオーバー用、対象ごとに固定）
```

理由: 操作の種類が数パターンしかなく、パラメータ化する実益が無い。誤りのコストが直接実害になるため、柔軟性より固定の確実性を優先する。

このトレードオフとして、monnieの`homelab-recover-monnie`は対象サービス（grafana-server/prometheus/loki/unpoller）を一括で再起動する。例えばprometheusのみが異常な場合でも、loki/grafana-server/unpollerも巻き込まれる。これは個別指定（パラメータ化）を避けるための意図的な受け入れであり、実装の不備ではない。個別restartが必要になった場合は、本セクションの改訂を経る。

### 4.3.1 wrapper単位のリトライ上限（§9のflapping対策とは別階層）

調査・復旧wrapperの実装は、同一対象への調査・復旧を最大2回までに制限し、それでも復旧しない場合はエスカレーションする仕組みを持つ。これは§9で定めた「24時間以内3回以上で即エスカレーション」とは別の階層で機能する。

```text
wrapperレベル（本セクション）: 1回のSlack依頼・1回のトリガー内での
  調査→復旧→再調査のリトライ上限（最大2回）
§9のflapping対策: 複数回のトリガーに渡る、24時間単位の発生回数制限
```

両者は矛盾せず、内側（1回の対応の中での粘り過ぎ防止）と外側（繰り返し発生する障害への対応）として独立に機能する。

### 4.4 調査用キー（調査系）の設計: パラメータ可、wrapper側で許可リスト照合

調査系（journalctl/systemctl status等）は、パラメータを受け取ってよい。ただし対象ホスト側のwrapperスクリプトが、受け取った値を許可リスト（case文等）と照合し、合致しない場合は即座に拒否する。`$SSH_ORIGINAL_COMMAND`を未検証のままeval・変数展開して実行に使うことは禁止する。

```bash
case "$1" in
  freeradius|sshd|prometheus|grafana-server|loki|unpoller)
    systemctl status "$1" --no-pager ;;
  *)
    echo "denied: unknown service $1" >&2; exit 1 ;;
esac
```

理由: 読み取り専用であり、誤りのコストは「違うものを読んでしまう」程度に留まる。パラメータを禁止すると調査として機能しなくなるため、変更系と同じ基準（完全固定）を当てない。

### 4.5 annの鍵を直接使わない

`recovery-exec`はannの鍵を保持・使用しない。annの鍵は既存の定常自動化（proxmox_patch_*, evacuate, restore等）専用として残す。これにより、復旧パイプラインが実際に握る力は§4.2の2本の鍵（調査用・recovery_action用）に限定され、annの強い権限とは構造的に切り離される。

---

## 5. LLM実行基盤（Codex CLI採用、確定）

### 5.1 結論: 採用するツールに関わらず、安全性の根幹は同じ2点

```text
- LLMには原則ツール（Bash/Write/Edit/Read/Glob/Grep等）を一切渡さない
- 実行可否はLLMの出力ではなく、決定論的ゲート
  （タグ再検証＋健全性再確認）が判断する
```

### 5.2 Codex CLIを採用する理由

- 既存のProxmox patch運用で、Codexを「情報を取りまとめて返すだけ、権限ゼロ」のadvisor役として使っており実績がある。今回の調査役割（wrapperを呼んで結果を解釈する、権限ゼロ）はこれと同一の役割パターンであり、新しい信頼を必要としない
- 実機検証（§5.4, §5.5）により、OSレベルサンドボックス（bubblewrap backed）が機能することを確認済み

### 5.3 Pythonは使わない。コマンド許可の判断はすべて対象ホスト側のシェルスクリプトが行う

旧設計のPython `ACTIONS` dictは廃止する。「何を実行してよいか」の判断は、Codexを呼ぶ側（recovery-exec）ではなく、SSH接続先（authy/monnie/pve等）のforced commandスクリプトが持つ。recovery-exec側はローカルwrapper（shell、1〜数本）を経由してSSHするだけで、コマンドの組み立てや許可判定のロジックを持たない（§4.3, §4.4）。

### 5.4 Codex呼び出し設定

```text
sandbox: workspace-write
writable_roots: []（書き込みは一切許可しない）
network_access: true（wrapperが実際にSSHで外に出る必要があるため）
approval_policy: never（無人実行のため。ハングしないことは検証済み）
```

`network_access=true`にする分、ネットワーク制限という層を1枚手放す。これを補うのが以下の3層:

```text
- execpolicy rulesで、Codexが呼べるローカルコマンドを調査用・復旧用の
  wrapperのみに絞る（ssh/curl/wgetそのものへの直接アクセスは禁止）
- wrapperスクリプト自身が、接続先ホスト名を内部に固定し、Codexから
  渡された引数で宛先を決定しない
- 接続先のforced command（§4.3, §4.4）が最終防御として残る
```

wrapper（`codex-exec-wrapper`）自身は、受け取る引数を`exec` / `--cd` / 固定workspaceパス / メッセージ本文の4つに限定し、これ以外（個数の不一致、各位置の値の不一致を含む）は実行前に拒否する。sandbox・approval・execpolicyに関わるCLIオプションは、呼び出し元（recovery-io等）から一切受け取らず、wrapper内部で固定する。これは「呼び出し元が何も指定しなければ既定値になる」状態（デフォルト値への依存）と「呼び出し元が何を指定しても無視される」状態（固定）の違いであり、前者は実機検証で実際に`--dangerously-bypass-approvals-and-sandbox`等の追加引数が素通りすることが確認されたため、後者に修正した（§14.15）。

### 5.4.1 sandboxとexecpolicyは別の層であることに注意する

両者は制御対象が異なる。

```text
sandbox: 実行された後の動作を制御する層
  （workspace外への読み書き、ネットワーク到達等）
  read-onlyなローカルコマンド（hostname等）自体を、sandboxは
  原理的に禁止しない

execpolicy: 「どのコマンドをそもそも呼べるか」を制御する層
  recovery-execでは default_policy="deny" とし、
  homelab-investigate-*/homelab-recover-*のみを許可リストに
  入れている。hostname等の未許可コマンドは、sandboxに到達する
  前にexecpolicyの段階で拒否される
```

「sandboxの設定を確認したのに、なぜ特定のコマンドが弾かれるか分からない」という調査の手間を避けるため、どちらの層が何を防いでいるかを区別して扱う。

### 5.5 実機検証で確定した事項

```text
- Codex CLIのsandbox（workspace-write、read-onlyのいずれも）は
  書き込み・ネットワークは制限するが、読み取りは制限しない
  （workspace外のファイルでも普通に読める）。これはCodexの
  サンドボックス仕様であり、バグではない
- したがって、機密ファイル（Slackトークン、SSH鍵、vault pass等）の
  読み取り保護は、サンドボックスではなく**OSファイル権限**
  （0600 + 専用ユーザー所有）が担う
- AppArmorのunprivileged user namespace制限（Ubuntu 24.04+デフォルト）
  により、Codexのsandbox付きshell command実行が失敗する場合がある。
  ホスト全体の制限は変えず、Codexのvendored bwrapバイナリのみを対象に
  した個別AppArmorプロファイル（userns許可）で解決する
- AppArmor修正後の再検証で、workspace外書き込み・ネットワーク到達・
  sandbox無効化・nested bypass・承認なし時の危険操作は、いずれも
  拒否されることを確認済み
- §4.2/§4.3の専用鍵・quory側のid_ann/vault passについては、
  v0.5のアカウント再構成実装後に同じOS権限検証を再実施する（§15参照）
```

---

## 6. コマンド許可の管理方法

### 6.1 ガバナンスの層を分ける

```text
重い層（要レビュー、変更コスト高いままでよい）:
  - 新しいforced commandスクリプトの作成（対象ホスト側）
  - execpolicy rulesへの新規wrapper追加（Codex側、§5.4）
  → 実際にホストに触れる、またはCodexの実行範囲を広げる変更。
    レビューを経る

軽い層:
  - 既存のforced commandスクリプト内の許可リスト（case文、§4.4）に、
    既存と同種の調査対象（読み取り専用、既に確立したパターンに沿う
    もの）を1行追加する
  → 新しいスクリプト・新しい実行範囲を増やすものではないため、
    軽量な変更として扱ってよい
```

「許可されたコマンド一覧」はPythonのデータ構造ではなく、対象ホスト側のforced commandスクリプト自身（§4.3, §4.4）とCodex側のexecpolicy rules（§5.4）が、それぞれの場所で保持する。中央集権的なregistryファイルは持たない。

---

## 7. ローカル実行環境の保護と起動方法

```text
- recovery-execはジョブ単位の使い捨てrunnerとして起動する
  （systemd-run、常駐させない。状態を持ちにくくする）
- systemd hardeningフラグを適用する（新規認証情報・新規コンポーネント
  不要、コストゼロ）:
    NoNewPrivileges, PrivateTmp, ProtectSystem=strict, ProtectHome,
    RestrictSUIDSGID, LockPersonality, MemoryDenyWriteExecute,
    PrivateDevices, ProtectKernelTunables, ProtectKernelModules,
    ProtectControlGroups
- ワークスペースはジョブ専用の一時ディレクトリとし、本物のgit
  リポジトリを直接参照させない
- コマンド単位の禁止リスト列挙はしない（LLMにBashツール自体を渡さない
  設計のため、個別コマンドの列挙は不要。§14.7参照）
```

### 7.1 起動方法（開発・本番で異なる）

```text
開発（ansy）: systemdサービス化はするが、手動起動・手動停止のみ。
             テストの間だけ動かす。常時稼働させない
本番（quory）: systemd自動起動（OS起動時に自動で立ち上がる）

ansy/quoryで同時に両方を稼働させない（Slackの@mentionをどちらが
受けるか競合させないため）。ansyでテストする時は、事前にquory側の
サービスを停止する運用とする。
```

---

## 8. トリガー伝達経路

### 8.1 authy / monnie → quory（systemd OnFailure=）

systemd `OnFailure=` フックから、SSH forced command方式でquoryの`recovery-exec`宛に自動通知する。

この経路は省略できない。理由は「通知」のためではなく、**ゲストVM（authy/monnie）自身には持たせられない実行権限を、ハイパーバイザー側（pve経由）で代行する必要がある**ため。VMリブート・HA failoverはゲストVM自身には原理的に実行できない操作であり、これを行える場所（quory経由でpveに到達できる場所）まで処理を引き継ぐ必要がある。ラダー1段目（サービスrestart）はゲスト自身でも実行可能だが、経路を統一するため同じ仕組みに乗せる。

monnieが完全停止し、この経路自体が機能しなくなる場合は許容する（§1の通り、最優先はhacritical=Sophos/authyの業務継続であり、monnieはその次点の優先度）。

開発中（ansy）はこの自動経路を稼働させず、Slackメンションによる手動トリガーのみで検証する。

### 8.2 外部到達性低下時（probe失敗）

quory上でping probeを実行し、失敗時に検知パイプラインを直接呼ぶ。

### 8.3 Slackメンション経由（手動・エージェント的ループ）

ユーザー本人がSlackで `@Homelab` にメンションして調査・復旧を依頼する経路。`recovery-io`がメンションを受け、`recovery-exec`にジョブとして渡す（§4.2, §7）。

自動経路との差分:

```text
- 24時間フラッピングカウントはスキップする（人間の明示依頼のため）
- 実行中ロックは適用する
- 復旧の実行可否は自動経路と同じくProxmoxタグ判定に従う
```

### 8.4 前提チェック（実行順序）

```text
1. target検証（allowlist: authy / monnie / sophos-fw のみ）
2. 実行中ロック確認
3. muteファイル確認（§9）
4. flapping count（手動依頼以外、直近24時間3回以上 → 即エスカレーション）
5. すべて通過 → 調査・復旧パイプライン起動
```

---

## 9. ミュート/TTL機構

メンテナンス系playbookが「今このtargetに触っている」ことを自己宣言する仕組み。明示的なclearは行わず、TTL自然失効に任せる。

```text
ファイル: /var/lib/homelab-recovery/mute/<target>.json
形式:     { "until": "<ISO8601+09:00>", "reason": "..." }
更新規則: 既存のuntilと(今+想定時間+バッファ)を比較し、長い方を採用する
```

mute設定タスクを追加する対象playbook:

| Playbook | ミュート対象 |
|---|---|
| `proxmox_evacuate_node.yml` | target_node + destination_node |
| `proxmox_patch_apply_node.yml` | 対象ノード単体 |
| `proxmox_restore_vm_placement.yml` | target_node |
| `ubuntu_nightly.yml` | その回でrebootするVM |
| `proxmox_patch_weekly_full.yml` の評価対象 | sophos-fw を含む |

---

## 10. 復旧エスカレーションラダー

承認なし、各段1回のみ試行。各段の実行は§4.3の専用鍵経由。

```text
調査 → 復旧見込みありか
  なし → 人間へエスカレーション（Slack通知、自動対応終了）
  あり →
     1. サービスrestart（authy: freeradius / monnie: grafana・
        prometheus・loki・unpoller / Sophos: 対象外）
        NG → 2. VMリブート（authy / monnie / Sophos対象、ソフト→
             強制電源断の内部フォールバック込みで1回）
             NG → hacriticalタグあり？
                  No  → 人間へエスカレーション（終了）
                  Yes → 3. フェイルオーバー（Sophos / authyのみ）
                        NG → 人間へエスカレーション（終了）
```

各段の試行・結果は§11に従い都度Slackへ通知する。

---

## 11. flapping対策

| 仕組み | 目的 | 性質 |
|---|---|---|
| 実行中ロック | 並行実行防止 | アトミック（mkdir方式） |
| 直近24時間のトリガー回数 | 繰り返し失敗時の暴走防止 | 回数ベース、3回以上で即エスカレーション |

---

## 12. Slack通知仕様

新規Slack App / Incoming Webhookスコープは不要。既存の`slack_webhook_alerts`（Vault管理済み）をそのまま流用する。Slack Appに必要なスコープは`app_mentions:read`/`chat:write`（Socket Mode）のみ。

```text
通知タイミング: トリガー受理時、各ラダー段の試行結果、最終エスカレーション時
通知方法: 既存notify.ymlと同一方式
失敗時の扱い: best-effort。通知失敗で本処理を止めない
タイムゾーン: JST（TZ=Asia/Tokyo）で統一
```

---

## 13. 禁止事項

```text
- §4で廃止した旧アカウント構成（recovery-slack/trigger/recovery-runner
  の3分割）に戻す
- recovery-execにannの鍵を直接持たせる
  （§4.3の専用鍵を経由しない復旧実行）
- recovery-execにSlackトークンを持たせる
- Codexにツール（Bash/Write/Edit/Read/Glob/Grep等）を許可する
  （execpolicy rulesで許可するのはwrapperのみ。§5.4参照）
- recovery_action用キー（変更系）のforced commandにパラメータを許す
  （§4.3、完全固定文字列を維持する）
- 調査用キー（調査系）のforced commandが、受け取った値を許可リスト
  照合せずにeval・変数展開して実行する（§4.4）
- recovery_*の実行を、対応するhealthcheckの実行・異常確認なしに行う
- 3 primitive以外の変更操作を自動実行する
- ラダーの各段を2回以上自動で繰り返す
- Sophos上でOSレベルの調査を自動的に行う
- §2の対象外ホスト（pve1/pve2/ansy）を復旧アクションの対象にする
- ansyとquoryで異なるLLM実行基盤・異なるアカウント構成を使う
  （§3.2違反）
- ansy・quoryのrecovery-execサービスを同時に稼働させる（§7.1違反）
```

---

## 14. 実装教訓

### 14.1 monitoring_healthcheck.sh への unpoller 追加漏れ

新規healthcheck作成時、対象ユニット一覧（§2.1）との照合をレビュー時に必ず行う。収集漏れはエラーにならず正常扱いになるため、発見が遅れる。

### 14.2 SSH forced command と nologin シェルの非互換

forced commandを使うユーザーのシェルは`/bin/sh`にする（`/usr/sbin/nologin`だと`shell -c`起動が拒否される）。

### 14.3 Claude -p モードでは allow が機能しない

非対話モードでは`permissions.deny`のみが有効。allowlist的な制御をしたい場合は、ツール自体を全deny（カテゴリ単位）にし、実行可否はLLMの外側（決定論的ゲート）で行う。

### 14.4 ANTHROPIC_API_KEY と CLAUDE_CODE_OAUTH_TOKEN

非対話モードの認証はサブスクリプション経由のトークン（`claude setup-token`）を使い、従量課金を避ける。両方が環境に存在する場合、ANTHROPIC_API_KEYが優先される点に注意（逆ではない）。

### 14.5 ansible-playbook の become_user に ACL 問題

`become_user`は使わず、`sudo -u <user> <command>`の形にする。

### 14.6 annの鍵がforced command保護を持たない唯一の鍵だった

復旧パイプラインの権限境界を議論する中で、annの鍵自体にはサーバー側の制約（forced command）が一切無いことが判明した。Pythonコード側での絞り込みは「行儀の良さ」に過ぎず、技術的な壁にはなっていなかった。対応は§4.3。

### 14.7 ユーザー分離は「アクターが違うから」ではなく「目的・リスクが違うから」を基準にすべき

エンタープライズ的発想（部門・サーバー群・攻撃面の種類で分ける）を、目的の違いが無いところに当てはめてしまい、過剰な複雑さ（3アイデンティティ、ホストごとに別鍵等）を生んだ。基準は§3.1。

### 14.8 コードのバグは仮説ではなく実証済みのリスク

1日の実装の中で複数の実バグが見つかった事実から、「recoveryのコード自体に欠陥がある可能性」を前提に設計する（§4.2のSlackトークン分離はこの教訓に基づく）。

### 14.9 LLM実行のサンドボックスは読み取りを制限しない。読み取り保護はOSファイル権限の責務

Codex CLIのsandbox（workspace-write/read-onlyいずれも）は書き込み・ネットワークアクセスを制限するが、ファイルの読み取りは制限しないことが実機検証で確定した（§5.5）。「サンドボックスを有効にしたから機密ファイルは読まれない」という思い込みは誤り。機密ファイルの読み取り保護は、常にOSのファイル権限（0600 + 専用ユーザー所有）で担保する。

### 14.10 鍵をノードごとに分ける防御効果は無い。秘密鍵の保管場所が信頼境界

秘密鍵は常にrecovery-exec側（ansy/quory）にあり、対象ホスト側には公開鍵しか置かれない。攻撃が成立するのはrecovery-exec側への侵入時のみであり、その時点で保持する鍵は本数に関わらず等しく危険になる。ノード単位で鍵を分けても防御効果が無いため、§4.2の通り共用してよい。「分ければ安全」という直感に反するため明記しておく。

### 14.11 固定文字列にすべきかパラメータ化してよいかは、操作の可逆性で判断する

変更系（restart/reboot/failover）はパラメータ不可・完全固定文字列、調査系（読み取り専用）はパラメータ可・wrapper側allowlist照合、という基準に分けた（§4.3, §4.4）。「1つの厳しい実例があるからすべて固定にする」という判断は過剰防御であり、誤りのコスト（実害が出るか、単に違う情報を読むだけか）で基準を分けるべき。

### 14.12 複数の防御層は、互いの前提を考慮せずに別々に決めると衝突する

systemdの`ProtectSystem=strict`（§7、workspace全体を読み取り専用化）と、Codexのsandbox（workspace-write、workspace自身への書き込みを要求）が、互いの存在を考慮せずに別々に設定されたため、workspaceへの書き込みすら失敗する事態が発生した。修正は`danger-full-access`（sandbox無効化）ではなく、`ReadWritePaths`でworkspace1か所だけを明示的に書き込み可能にすること。複数の防御層を追加する際は、各層が要求する正当な動作（ここでは「workspace自身への書き込み」）を妨げていないかを必ず確認する。

### 14.13 LLMが正しく理解していることと、それが機械的に強制されていることは別

CodexはAGENTS.mdの制約（許可された引数のみ使う、wrapper以外を呼ばない等）を正確に理解し、その通りに振る舞う意図を示した。ただしこれはCodexの「意図」であり、技術的な強制ではない。実際に許可リスト外の引数が渡された場合に拒否するのは、ターゲット側のdispatchスクリプト（§4.4）であり、LLMの理解の正確さに安全性を依存しない。LLMへの質問で意図を確認することは有用だが、それ自体を安全性の根拠にしてはならない。

### 14.14 sandboxとexecpolicyは別の防御層であり、混同すると原因調査を誤る

Codexがhostname等の未許可コマンドを実行しなかったのは、sandboxによる禁止ではなくexecpolicy（`default_policy="deny"`、許可リスト方式）による拒否だった。sandboxは実行後の動作（ファイルアクセス・ネットワーク到達）を制御する層、execpolicyは「そもそも呼べるコマンドの範囲」を制御する層であり、両者は別物（§5.4.1）。

### 14.15 「呼び出し元が指定しなければ安全な既定値になる」は、固定とは違う

`codex-exec-wrapper`が呼び出し元の引数（`"$@"`）をそのままCodex CLIへ渡していたため、sandbox/approval/execpolicyに関するCLIオプション自体は安全な既定値で運用されていたものの、呼び出し元が追加の引数（`--dangerously-bypass-approvals-and-sandbox`等）を渡せば、それがそのまま反映されてしまう状態だった。実機検証でこれが実際に素通りすることを確認し、wrapperが受け取る引数を4つに限定し、個数・各位置の値を厳密に検証して一致しなければ拒否する実装に修正した。「デフォルトが安全」と「呼び出し元の入力を信用しない」は別であり、後者でなければ安全性の根拠にならない。

### 14.16 追加専用のキー管理（authorized_key state: present）はdriftを生む

`authorized_key`モジュールの`state: present`は鍵を追加するだけで、古いエントリを自動削除しない。アカウント構成の変更（recovery-slack/trigger/recovery-runnerの旧アカウント廃止等）のたびに、対象ホスト側のauthorized_keysにorphanエントリが残留した。対応として、authorized_keysファイル全体をAnsibleのtemplateで生成し、許可する鍵（investigate鍵・action鍵）の2エントリのみを明示的に記述する方式に変更した。これにより、playbook実行が常に「正確な状態への上書き」になり、追加実行のたびにdrift checkを兼ねる。

---

## 15. 未決事項

- recovery_action用キー・調査用キー（§4.2, §4.3, §4.4）の実装
- `recovery-io` / `recovery-exec` の実装（旧recovery-slack/trigger/recovery-runnerからの作り直し）
- 上記実装後、quory側のid_ann・vault pass・専用鍵について、ansyで
  実施したのと同じOS権限検証（低権限ユーザーからPermission deniedに
  なることの確認）を再実施する
- systemd `OnFailure=` の `Restart=`/`StartLimitBurst=` 設定確認
- 調査フェーズのアドホック呼び出しが既存healthcheck系playbookの通知経路と二重発火しないことの確認
