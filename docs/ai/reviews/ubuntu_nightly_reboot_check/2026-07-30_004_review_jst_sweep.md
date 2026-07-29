# Code Review: playbooks/ubuntu_nightly.yml (JST表記統一, Tier 1+R)

対象: `playbooks/ubuntu_nightly.yml`(未commit差分、6箇所)。
方式: 独立Reviewerによる差分レビュー + `+R`(選定妥当性の独立照合)。実ホスト接続・実行なし、Slack実送信なし。`ansible-playbook --syntax-check`とscratch decoy(`hosts: localhost` / `connection: local`)のみ使用。対象ファイルは変更していない。git操作(add/commit/push/stash/checkout/restore/reset)は行っていない。

## 対象の差分

`ansible_facts["date_time"]["iso8601"]`(UTC・`Z`付き)を`lookup('pipe', "TZ='Asia/Tokyo' date '+%Y-%m-%dT%H:%M:%S+09:00'")`へ置換。6箇所すべて`slack_message`内の`Time:`行(check-mode通知×2、reboot開始通知×2、結果通知×2)。

## 実施した確認(選定漏れの独立照合)

Coordinatorの5クラス分類(`date_time.iso8601` / `iso8601_micro` / `date -u`・`utcnow` / リテラルZ付きローカル時刻 / `iso8601_basic_short`)に対し、リポジトリ全体を独自にgrepし、この分類に無い表現形式が残っていないかを確認した。

- `ansible_date_time`(別名)、`.j2`テンプレート内の時刻表現、systemd unit内の時刻表現: **リポジトリ全体で0件**。
- `date -u`/`utcnow`/リテラルZ付き: `roles/recovery_probe/files/recovery-probe.py`が`datetime.now().astimezone().isoformat()`を使用(UTCでもリテラルZでもなく、システムTZに基づくoffset付き)。これは対象playbookと無関係の別ファイルで、今回のdiffのスコープ外。
- **選定漏れを1件検出**: `roles/proxmox_snapshot_check/tasks/main.yml:57`が`'%Y-%m-%dT%H:%M:%S%z' | strftime(item.snaptime | int)`というJinjaの`strftime`フィルタを使っており、Coordinatorの5クラスに含まれない**第6のクラス**である。Ansible core filter(`ansible/plugins/filter/core.py`の`strftime()`)の既定は`utc=False`→`time.localtime`であり、`%z`はコントローラプロセスの**暗黙のシステムTZ**に依存する(他の19箇所超で使われている`TZ='Asia/Tokyo'`明示指定と異なり、明示的なpinが無い)。この値は`snaptime_iso`として`roles/proxmox_snapshot_check/tasks/main.yml:147,151`でSlack通知本文に人間向けに表示されており、`recovery-loki-helper`のUTC変換(Loki API専用、非表示)とは性質が異なる。現状のコントローラTZがAsia/Tokyoであれば実害は無いが、他箇所が明示pinしているのに対しここだけ暗黙依存という**一貫性の欠如**であり、Coordinatorが「掃引した」と主張する分類には入っていない。ただしこのファイルは今回のdiff対象ではないため、本diffをブロックする理由にはしない。

## 除外判断の現物照合

- **`recovery-loki-helper`のUTC変換**: `roles/recovery_exec/files/recovery-loki-helper`を読解。`rfc3339_utc()`(L88-89)はLoki API問い合わせパラメータ(L118, L176-177)専用で、人間向け出力(L205-206)は`astimezone(JST)`＋`+09:00`固定フォーマットで明示的にJST変換している。除外理由は現物と一致し妥当。
- **`iso8601_basic_short`(ファイル名)**: repo横断で7 role(`radius_healthcheck`, `cloudkey_cert_deploy`, `proxmox_snapshot_check`, `monitoring_healthcheck`, `proxmox_healthcheck`, `ubuntu_vm_full_upgrade`, `proxmox_hw_check`)が同一パターンでファイル名に使用しており、今回のみの例外ではない。中身の`executed_at`(JST明示)と一致しているため実害なしという判断は妥当。

## 意味論の変化・dead code懸念の照合

- **"Gather facts after reboot"はdead codeではない**。radius_servers play(L192-195→L223)、monitoring_servers play(L453-456→L473)とも、再取得した`date_time`の`iso8601_basic_short`が直後の`Save result report`のファイル名生成で消費されている(現物確認済み)。
- **意味論変化(fact gather時刻→controller render時刻)は実質的な影響なし**。6箇所とも、直前に発生したイベント(play開始時のgather_facts、または"Gather facts after reboot")から数タスク以内での評価であり、対象ホストとコントローラの時計が大きくずれていない限り誤差は秒オーダー。かつこの方式(`lookup('pipe',...)`によるcontroller render時刻)は`roles/recovery_vm_reboot`、`roles/recovery_ha_failover`、`roles/recovery_service_restart`、`roles/ubuntu_vm_full_upgrade`、`playbooks/cert_renew*.yml`、`playbooks/unifi_backup_fetch.yml`、`playbooks/cloudkey_cert_deploy.yml`、`playbooks/recovery_probe_notify.yml`ですでに採用されている既存パターンであり、今回新規に持ち込んだ設計ではない。

## YAMLクォート・lookup副作用の確認

- `ansible-playbook --syntax-check playbooks/ubuntu_nightly.yml` はPASS。
- 6箇所は`slack_message: |`のリテラルブロック内にあり、ダブルクォートのエスケープは不要(そのままの形で正しい)。同ファイル内の未変更箇所(L66, 89, 211, 351, 374, 462、`executed_at`のダブルクォート flow scalar内)は`\"..\"`のエスケープが必要で、そちらも既存のまま正しくパースされている。両方の書式が同一ファイル内で混在し、それぞれ文法的に正しいことを確認した。
- `lookup('pipe', ...)`が`--check`実行時にスキップ/空文字にならないことをscratch decoy(`ansible_connection: local`)で確認した。`--check`下でも実際の日時文字列が返った(lookupはcheck-mode非対象)。
- 呼び出し回数: 現在`radius_servers`=authy 1台、`monitoring_servers`=monnie 1台のみ(`ansible-inventory --graph`で確認)。1回のplaybook実行で6箇所×1ホスト=最大6プロセス起動であり、現行規模では問題にならない。グループにホストが増えた場合はホスト数倍のプロセス起動になるが、nightly実行1回あたりの規模を考えると許容範囲。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| 1 | `roles/proxmox_snapshot_check/tasks/main.yml` | 57, 147, 151 | Jinja `strftime`フィルタ(`utc=False`既定、コントローラのローカルTZに暗黙依存)という第6のクラスがCoordinatorの5クラス分類に含まれておらず、人間向けSlack通知に表示される`snaptime_iso`がこの経路で生成されている。他箇所は`TZ='Asia/Tokyo'`を明示pinしているのに対しここのみ暗黙依存であり、JST規約の掃引としては選定漏れ。今回のdiff(`playbooks/ubuntu_nightly.yml`)のスコープ外のため本diffの承認はブロックしないが、`+R`の主目的(選定漏れの検出)に対する回答として報告する。follow-up起票を推奨 | High(選定完全性の観点。本diffの正誤には影響しない) |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | 全リポジトリ(19箇所超) | - | `lookup('pipe', "TZ='Asia/Tokyo' date '+%Y-%m-%dT%H:%M:%S+09:00'")`という同一の長い文字列が19箇所超で重複している(今回の6箇所は既存の反復パターンへ正しく追従したものであり、新規に導入した重複ではない)。将来的にカスタムfilter/lookupへ集約する余地はあるが、既存の広範な前例に合わせた選択として妥当であり、本diffをブロックする理由にはしない | duplication-reuse-check(pre-existing) |
| 2 | `roles/recovery_probe/files/recovery-probe.py` | 35, 152, 517 | `datetime.now().astimezone().isoformat()`はUTCでもリテラルZでもなく妥当だが、他箇所の明示`TZ='Asia/Tokyo'` pinとは異なりOSのシステムTZに依存する機構。今回のdiff・5クラス分類とは無関係の既存コードであり対応不要だが、選定漏れ確認の過程で見つかったため記録のみ残す | reference-note |

## What Looks Good

- 6箇所の置換はすべて正しいJST表記(`+09:00`固定)へ統一されており、`ansible-playbook --syntax-check`をPASS。
- `lookup('pipe', ...)`は`--check`実行時にスキップされず正しく評価されることをdecoyで確認。副作用面の懸念なし。
- "Gather facts after reboot"タスクはdead codeではない(`iso8601_basic_short`がファイル名生成で消費されている)。
- 除外した2件(`recovery-loki-helper`のUTC変換、`iso8601_basic_short`)はいずれも現物照合の結果、除外理由が正確だった。
- 意味論変化(fact時刻→controller render時刻)は既存の repo 全体パターンと一致しており、今回新規に持ち込んだ設計ではなく、実害も無い。
- コマンドインジェクション相当の懸念なし。埋め込まれているのは固定文字列のみで外部入力の混入は無い。

## Verdict

**Approve**(本diff・6箇所の置換自体)。

- 選定漏れは**1件あり**: `roles/proxmox_snapshot_check/tasks/main.yml`のJinja `strftime`フィルタ(暗黙ローカルTZ依存)がCoordinatorの5クラス分類から漏れている。本diffのファイルスコープ外のためこのdiffの承認は妨げないが、`+R`の主目的である選定妥当性の照合結果として報告する。follow-upとして`docs/ai/status.md`への起票を推奨(このReviewer自身は追記しない)。
- それ以外の選定(`recovery-loki-helper`除外、`iso8601_basic_short`除外、"Gather facts after reboot"の非dead-code性)はすべて現物照合により妥当性を確認済み。

## 未解決事項

- `roles/proxmox_snapshot_check/tasks/main.yml`のstrftime暗黙TZ依存への対応要否・タイミングはCoordinator/Yoshinobuの判断に委ねる(本Reviewは検出のみ)。
- コントローラ(実運用ではansy)の実際のシステムTZ設定そのものは今回検証していない(ローカル実測`/etc/timezone`= Asia/Tokyoを参考値として引用したのみで、これはこのReviewerが起動された環境のものであり、ansy実機の値ではない)。
