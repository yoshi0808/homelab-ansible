# cert_renew Policy

本書はhomelabの管理系Web UI用TLS証明書更新に関する正本である。実装詳細はcode / mapを参照し、競合時は本Policyを優先する。

## 1. 目的


<!-- CERT-001 -->
### 1. 目的

homelab内の管理系Web UIのTLS証明書を自動更新する。
ブラウザの証明書警告を解消し、短命証明書（45日）運用を維持する。

## 2. 対象と実行範囲


<!-- CERT-002 -->
### 2. 対象サービス

| ホスト | サービス | Playbook |
|---|---|---|
| `ansy` | Semaphore | `cert_renew.yml`（Semaphoreから実行） |
| `quory` | Semaphore | `cert_renew_quory.yml`（systemd timerから実行） |
| `pve1` | pveproxy | `cert_renew.yml` |
| `pve2` | pveproxy | `cert_renew.yml` |
| `monnie` | Grafana | `cert_renew.yml` |


### 3. Playbook分離の理由

<!-- CERT-003 -->

`cert_renew_quory.yml` を独立したPlaybookとして分離している理由:

- `cert_renew.yml` はSemaphoreから実行する
- quoryのSemaphore証明書を `cert_renew.yml` で更新すると、更新処理の途中でSemaphore自身が再起動される
- これにより実行中のPlaybookが中断される
- quoryのSemaphore証明書はsystemd timerから独立したPlaybookで更新する

cert_renew_quory.yml は quory のみを対象とする。ansy の証明書はこのPlaybookには含まれない。

### 4. CA構成

### 4.1 CA階層

```
Home-RADIUS-CA (ルートCA)
  └── Home-TLS-CA (中間CA) ← v2.0以降の署名CA
        └── リーフ証明書 (各ホスト)
```


<!-- CERT-005 -->
<!-- CERT-016 -->
<!-- CERT-017 -->
### 4.2 方式: ファイルコピー方式（中間CA署名）

CA証明書・CA秘密鍵は quory 上の永続ファイルから取得する。
両 Playbook とも quory 以外での実行を禁止しているため、ansy への CA 配置は不要である。

```
<controller CA directory>/home_tls_ca.crt
<controller CA directory>/home_tls_ca.key
```

これらのファイルを実行時に `/run/semaphore-ca/`（tmpfs）へコピーし、処理後に削除する。

Playbookは実行前にソースファイルの存在確認とCA秘密鍵のmode 0600チェックを行い、
条件を満たさない場合はfailする。


<!-- CERT-006 -->
### 4.3 ルートCA秘密鍵のオフライン保管（v2.0変更点）

ルートCA(Home-RADIUS-CA)の秘密鍵はオフライン保管に移行済みであり、
quory上には存在しない。

- ルートCAは直接TLS証明書を署名しない
- 中間CA(Home-TLS-CA)の証明書・秘密鍵が quory のみに配置される
- 中間CAのみを用いて日常のTLS証明書を署名する


<!-- CERT-007 -->
<!-- CERT-018 -->
### 4.4 CA秘密鍵の保管

| 項目 | 内容 |
|---|---|
| 保管場所 | **quory のみ** `<controller CA directory>/home_tls_ca.key`（ansy への配置は不要） |
| 権限 | `chmod 600`（必須。Playbookが実行前に検証する） |
| 所有者 | controller account（推奨。root で読める限りPlaybookの動作は可能） |
| Git管理 | しない（`.gitignore` で `.cert/` を除外） |
| バックアップ | quory OS再インストール時に手動で再配置が必要 |
| 復旧手順 | 下記 §10 参照 |

### 4.5 CA秘密鍵の所有者チェックについて

Playbookはmode 0600のみを検証し、ownerは検証しない。

理由:
- Playbookは `become: true` で実行するためrootとして動作し、ownerに関係なく読める
- mode 0600であれば世界から読まれるリスクは排除されている
- ownerをhardcodeすると環境変更時に壊れる

## 3. 対応するPlaybook


<!-- CERT-004 -->
### 対応するPlaybook

| 区分 | Playbook | 役割 |
|---|---|---|
| primary | `cert_renew.yml` | ansy（Semaphore）/ pve1・pve2（pveproxy）/ monnie（Grafana）のTLS証明書を更新する。Semaphoreから実行する。 |
| primary | `cert_renew_quory.yml` | quory（Semaphore）のTLS証明書を更新する。Semaphore自身の再起動を伴うため、systemd timerから独立実行する。 |

上記2本がprimary更新入口である。

| 区分 | 関連Playbook | 位置づけ |
|---|---|---|
| supporting | `ca_trust_deploy.yml` | CA trust配備。primary更新入口ではない |
| diagnostic | `test_ca_env.yml` | CA環境診断。primary更新入口ではない |

actual renewal role名は`homelab_cert_renew`である。CloudKeyの証明書更新は対象外であり、`cert_renew_cloudkey_policy.md`を参照する。

## 4. 判断軸


<!-- CERT-010 -->
### 7. 中間CA有効期限監視（v2.0追加）

prepare_ca.yml の実行時に home_tls_ca.crt の残存日数を確認する。

| 残存日数 | 動作 |
|---|---|
| 90日以上 | 正常（何もしない） |
| 90日未満 | WARNING ログ出力 + `cert_intermediate_ca_warn: true` ファクト設定 |

WARNING が検出された場合、通知の Slack メッセージに以下が追記される。

```
WARNING: Intermediate CA expires in N days!
```

中間CAは有効期間10年である。失効前の再発行が唯一の能動的更新イベントであり、
定期的な目視確認（年1回以上）を推奨する。


<!-- CERT-012 -->
<!-- CERT-020 -->
### 9. 証明書仕様

| 項目 | 値 |
|---|---|
| 有効期間 | 45日 |
| 更新条件 | 残日数 15日以下（または `force_renew: true`） |
| 鍵アルゴリズム | EC secp384r1 |
| SAN | DNS + IPv4（発行時に CA ホストで `getent ahostsv4` により動的取得） |


<!-- CERT-023 -->
### 到達不能ホストの扱い

`cert_renew.yml` の実行時に対象ホストへSSHで到達できない場合の扱いは、ホストによって異なる。

| 対象 | 到達不能時の扱い |
|---|---|
| `pve1` / `pve2` | 当該nodeをスキップして残りの処理（他nodeの更新、CA cleanup、完了通知）を完走し、**playbookは正常終了する（終了コード0）**。スキップした事実はSlack通知にWARNINGとして出力する |
| `ansy` / `monnie` | 従来どおり失敗として扱う。両ホストは常時稼働が前提であり、到達不能は本物の異常である |

pve1 / pve2 を例外とする理由は、夏季にpve1を平日シャットダウンする運用があり、計画的な停止を毎回ジョブの赤で受け取ると本物の失敗と区別できなくなるためである。同種の判断はProxmoxのread-only点検3本でも採られている（`proxmox_operations_policy.md` SB-095）。

この例外は**通知と終了コードの扱いだけを変える**ものであり、スキップされたnodeの証明書が更新されたことにはしない。到達不能だったnodeは証明書が更新されないまま残る。**復帰後の追いかけは週次実行が行う**（CERT-024）。ただしそれは次の実行までの間、当該nodeが古い証明書のまま稼働することを意味するため、WARNINGを受け取った運用者は残り有効期間を確認する。

技術的背景（`serial: 1` のバッチ内で全hostが到達不能になるとplaybook全体が打ち切られ、CA秘密鍵のtmpfsからの削除まで実行されなくなる）は `docs/ai/reviews/cert_renew_unreachable_node/2026-08-01_001_requirement.md` §1 を正本とする。

<!-- CERT-024 -->
### 更新の起動頻度と、強制再発行の要否

**判断軸は「更新猶予の窓に、実行の機会が2回以上入るか」である。** 証明書は有効45日・残り15日で更新する（§9）ため、窓は15日ある。月次では窓に入る機会が1回しかなく、**その1回を外すと次の機会は期限の後になる**。週次なら2〜3回入る。

| 入口 | 頻度 | 強制再発行 | 機会を外したときの回復 |
|---|---|---|---|
| `cert_renew.yml` | 週次。**週末に実行する** | しない（残り15日を切ったときだけ更新する） | 翌週の実行が拾う |
| `cert_renew_quory.yml` | 月次（実行時刻は `roles/systemd_timers/defaults/main.yml` の `cert-renew-quory` エントリが正本） | する（`force_renew: true`） | timerの `Persistent=true` が、発火時刻に停止していた分をquory起動時に実行する |

`cert_renew.yml` を**週末に実行する**理由は、pve1が夏季に平日シャットダウンされること（CERT-023）にある。平日に実行すると、週次にしてもpve1だけは毎回スキップされ、頻度を上げた効果がそのnodeに出ない。

`cert_renew_quory.yml` が月次かつ強制のままでよい理由は、対象がquory自身であり「**対象ホストが落ちている**」経路を持たないことにある。代わりに「**実行主体そのものが落ちている**」経路があり、頻度を上げても解けない。ここは `Persistent=true` で埋める。**2つの入口は脆さの種類が違うため、同じ対処を適用しない。**

**scheduleもrepoにある**(2026-08-10、`semaphore_schedules_as_code`)。`cert_renew.yml` の頻度・曜日と、scheduleが自分で持つ実行パラメータは `roles/semaphore_templates/defaults/main.yml` の `semaphore_schedules_catalog` が正本である。**ただしtemplate側のsurvey既定値は、scheduleの実行には効かない** — 該当scheduleの `environment` が `force_renew` の値を自分で持つため。頻度や強制の要否を変えたときは、**カタログの2箇所(templateのsurvey既定値とscheduleの `environment`)を合わせる。**

## 5. ライフサイクル・処理フロー


<!-- CERT-008 -->
<!-- CERT-019 -->
### 5. CA証明書の一時展開とcleanup

```
処理前:  <controller CA directory>/home_tls_ca.{crt,key}（永続）
         ↓ コピー
実行中:  /run/semaphore-ca/ca.{crt,key}（tmpfs、処理後に削除）
         ↓ cleanup
処理後:  /run/semaphore-ca/ ディレクトリごと削除
```

cleanup失敗は `cert_cleanup_status` ファクトで記録し、最終的にPlaybookがfailする。


### 6. フルチェーン配布（v2.0追加）

<!-- CERT-009 -->

サーバー配布物とクライアント側トラストストアは、別レイヤーの規範として扱う。混同すると
「どこにルートCAが必要か」の判断を誤る。

**サーバー配布物（本節の対象）**: 中間CAで署名したリーフを配布する場合、サーバーは
ハンドshakeでリーフと中間CAの両方を提示しなければならない。リーフ単体を配布すると、
クライアントは中間CAを入手できず鎖を構成できないため検証が失敗する。送出鎖にルートCAは
不要である（クライアントは自身のトラストストアのルートを信頼の起点に使う）。

v2.0 以降、配布するサーバー証明書は以下のフルチェーン形式とする。

```
リーフ証明書（各ホスト固有）
+
中間CA証明書（home_tls_ca.crt）
```

<!-- CERT-021 -->
**クライアント側トラストストア**: 信頼の起点として必要なのはルートCA証明書
（`radius_ca.crt`）だけである。中間CAはサーバーがハンドshakeで提示するため、
トラストストアへ配布しなくてよい。スマートフォン・PC等の管理外デバイスも含め、
ルートCA1枚を信頼させることで全ホストのTLS証明書の正当性を検証できる状態を維持する。

<!-- CERT-022 -->
トラストストアからの中間CA配布を廃止する場合は、廃止前に全TLSエンドポイントが
中間CAを送出していることを実測で確認する。送出していないエンドポイントが1つでもあると、
そのエンドポイントに対する検証だけが失敗する。確認方法と現状はOperations Contextおよび
実測結果を正本とする。

生成タイミング: issue.yml の署名タスク直後に quory（tmpfs）上で cat 連結して作成する。

ファイルパス: `{{ cert_renew_ca_dir }}/certs/{{ inventory_hostname }}.fullchain.crt`


<!-- CERT-013 -->
### 10. CA復旧・移行手順

### 初回 Home-TLS-CA 移行時の実行手順

`cert_renew.yml` は既存証明書の残存日数が 15 日超の場合、発行済みCAの issuer によらず更新をスキップする。
初回移行では全対象を確実に更新するために `force_renew: true` を指定して実行すること。

**cert_renew_quory.yml**（quory の Semaphore 証明書）:
play 内で `force_renew: true` が固定済みのため、通常どおり実行するだけでよい。

```sh
ansible-playbook -i inventories/homelab/hosts.yml playbooks/cert_renew_quory.yml
```

**cert_renew.yml**（ansy / pve1 / pve2 / monnie）:
`force_renew: true` を明示して実行する。

```sh
ansible-playbook -i inventories/homelab/hosts.yml playbooks/cert_renew.yml \
  -e force_renew=true
```

Semaphore から実行する場合は Task Template の Extra Variables に `force_renew: true` を設定する。

`cert_renew_quory.yml` は playbook 内の vars で `force_renew: true` を固定している。

定常運用での起動頻度・強制再発行の要否はCERT-024を正本とする。


### 中間CA秘密鍵の再配置（quory OS再インストール時など）

<!-- CERT-014 -->

1. 中間CA秘密鍵バックアップを安全なメディアから取得する
2. **quory 上にのみ** 配置する（ansy への配置は不要）

   ```sh
   mkdir -p <controller CA directory>
   cp home_tls_ca.key <controller CA directory>/home_tls_ca.key
   cp home_tls_ca.crt <controller CA directory>/home_tls_ca.crt
   chmod 600 <controller CA directory>/home_tls_ca.key
   chmod 644 <controller CA directory>/home_tls_ca.crt
   ```

3. Playbookを実行して証明書を再発行する

### 中間CA自体の再発行（有効期限切れ前）

1. オフライン保管のルートCA秘密鍵を使用して新しい中間CA証明書を発行する
2. 新しい `home_tls_ca.{crt,key}` を quory のみの `<controller CA directory>/` に配置する
3. `force_renew: true` で cert_renew.yml / cert_renew_quory.yml を実行して全ホストの証明書を更新する

## 6. 通知方針


<!-- CERT-011 -->
### 8. 失敗検知

| Playbook | 失敗検知方法 |
|---|---|
| `cert_renew.yml` | 完了Slack通知を送る。cleanup失敗などPlaybook本体の失敗は fail タスクで検知する。 |
| `cert_renew_quory.yml` | 完了Slack通知を送る。cleanup失敗はSlack通知後に fail する。加えて systemd unitのexitコードでも検知できる（journalctl / OnFailure=）。 |

通知チャンネルの選択:
- `alerts`: FAILED または WARNING を含む場合
- `info`: 正常完了の場合

到達不能なpve1 / pve2をスキップした実行はWARNINGを含むため`alerts`へ送るが、playbook自体は正常終了する（CERT-023）。通知チャンネルと終了コードは独立であり、`alerts`への通知をジョブの失敗と読み替えない。

## 7. 制約・禁止事項


<!-- CERT-015 -->
### 11. 除外対象

以下は本roleの管轄外である。

| 対象 | 理由 |
|---|---|
| CloudKey の証明書 | Home-TLS-CA 配下へ移行。別ポリシー `cert_renew_cloudkey_policy.md`（cloudkey_cert_deploy role）で管理 |
| authy の EAP-TLS クライアント/サーバー証明書 | ルートCA直下30年、別管理 |

CA資材の配置、mode、offline root、runtime staging、owner非固定の制約はP2のCA構成を構成する規範であり、本節からも適用する。

## 8. 変更履歴

作成日: 2026-06-05
改版日: 2026-06-12
版: v2.0
対象: homelab 環境のTLS証明書自動更新（cert_renew role）


### 変更履歴

| 版 | 日付 | 変更内容 |
|---|---|---|
| v1.0 | 2026-06-05 | 初版。ルートCA(Home-RADIUS-CA)直接署名方式。 |
| v2.0 | 2026-06-12 | 中間CA(Home-TLS-CA)署名方式へ移行。フルチェーン配布・中間CA有効期限監視を追加。ルートCA秘密鍵のオフライン保管に伴う変更。 |
| v2.1 | 2026-07-25 | 標準8見出しへ再編し、安全境界の意味を維持。 |
| v2.2 | 2026-07-26 | CERT-009がサーバー配布物とクライアント側トラストストアを1文に混在させていた点を分離。トラストストアに必要なのはルートCAのみである規範をCERT-021として明記し、中間CA配布廃止時の実測確認要件をCERT-022として追加。 |
| v2.3 | 2026-07-26 | CERT-022の実測要件を6/6エンドポイントで充足したうえで、`deploy_ca_trust.yml`からの中間CA配布を廃止しルートCA単独配布へ移行。配布済み`home-tls-ca.crt`は`state: absent`で回収する。実測記録は`docs/ai/reviews/cert_renew/2026-07-25_006_test_result.md`。 |
| v2.4 | 2026-08-01 | CERT-023を新設。夏季のpve1平日シャットダウン運用を受け、`cert_renew.yml`でpve1 / pve2が到達不能な場合は当該nodeをスキップしWARNING通知のうえ正常終了する（`ansy` / `monnie`は従来どおり失敗）。§6の通知チャンネル選択に、`alerts`通知と終了コードが独立である旨を追記。実装と検証は`docs/ai/reviews/cert_renew_unreachable_node/`。 |
| v2.5 | 2026-08-06 | CERT-024を新設し、更新の起動頻度を「更新猶予の窓に機会が2回以上入るか」で決める規範にした。`cert_renew.yml`は月次強制から**週次・期限駆動・週末実行**へ移行し、カタログの`force_renew`既定値を`false`へ変更（surveyは残し、強制が要る場面では打てる）。`cert_renew_quory.yml`は月次強制のまま、timerを`Persistent=true`へ変更して実行主体停止時の取りこぼしを埋める。**2つの入口は脆さの種類が違うため同じ対処を適用しない**ことを明記。あわせてCERT-023の「復帰後の追いかけ更新は自動化していない」という記述を、週次実行が拾う現状へ改めた。 |
| v2.6 | 2026-08-25 | CERT-013末尾の「両経路とも月次強制」という旧文（v2.5で移行済みのはずが改訂漏れしていた）を削除し、定常運用の起動頻度・強制要否はCERT-024を正本とする形へ改めた。CERT-024表の`cert_renew_quory.yml`実行時刻の実値（毎月1日 00:35）を落とし、`roles/systemd_timers/defaults/main.yml`の`cert-renew-quory`エントリへのポインタへ置換。 |
