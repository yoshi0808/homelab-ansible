# Code Review: log_observability debug収集除外(LOG-070/071)

対象:
- `roles/alloy/templates/observability-sources.rsyslog.j2`、`roles/alloy/templates/config.alloy.j2`、`roles/alloy/tasks/main.yml` のgit差分
- `docs/ai/reviews/promtail_to_alloy/2026-07-26_026_implement_debug_exclusion.md`(実装報告)
- `docs/ai/policies/log_observability_policy.md`(LOG-070/071、LOG-027)
- `roles/alloy/defaults/main.yml`(4系統の適用範囲・assert期待値の直接確認)
- ローカルレンダリング(scratch playbook、`hosts: localhost, connection: local`、ダミーIPv4はRFC 5737のドキュメント用予約帯のみ使用・repo外・非追跡)による両テンプレートの独立再現とtasks/main.ymlのassert式の独立再実行

Tier3、production log path影響あり。techlead依頼の8項目を全て独立に確認した。実host適用(APPLY)には触れず、`--check`相当の構文・静的検証の範囲に留めている。

## Summary

4系統(rsyslog受信側、file source側、best-effort側、monnie journal側)全てで「levelを確定させたうえでaction=dropにより明示的にdrop」という設計原則が徹底されていることを確認した。最重要の2点(rsyslogのstop挙動、AlloyRemoteDebug参照の完全消滅)はrainerscript側の構造直読とAlloy側の独立ローカルレンダリングで裏付けた。tasks/main.ymlのassert書き換えは既存の自ノイズdrop検証を一切弱めておらず、新設2 assertを含めて自分で再現したscratch playbook上で全PASSを確認した。warning/error経路・playbooks/への影響はいずれもゼロ。blocking指摘なし。

## Critical Issues

なし。

## techlead依頼8項目の確認結果

### 1. rsyslogのstop挙動(Coordinator必須確認事項)

**結論: 報告どおり。** `observability-sources.rsyslog.j2`の構造を直接確認した:

```
if (アドレス一致) then {
    if (severity <= 3) then { action(...error file...) }
    if (severity == 4) then { action(...warning file...) }
    if (severity == 5 or 6) then { action(...info file...) }
    stop
}
```

severity 7(debug)のメッセージがアドレス一致した場合、3つの`if`いずれにも該当しないため`action()`は一度も呼ばれず、そのままブロック末尾の`stop`(3severity判定と同じ`then{}`内の独立文、いずれかのifの中ではない)へ到達する。rsyslogのrainerscript`stop`は現在処理中のmessageに対する以後の全ルール適用を打ち切る(discardと同義)ため、どのdestination fileへも書き込まれずmessageは破棄される。

`stop`はこのdiffで変更されておらず(削除されたのはseverity==7の`action()`ブロックのみ)、他destinationの`if`ブロックへのfallthrough防止という`stop`本来の役割自体は今回のdiffで新設されたものではない。ローカルレンダリング(ダミーIPv4)で実際に出力を確認し、3 destination(pve_nodes/sophos_fw/ubuntu_nodes)いずれも同じ構造で出力されることを確認した。

### 2. AlloyRemoteDebug参照の安全性(Coordinator必須確認事項)

**結論: 報告どおり、独立再確認でも0件。**

```
$ grep -rn "AlloyRemoteDebug" /home/yoshi/homelab-ansible/
(本reviewファイル作成前の時点で出力なし)
```

実装報告の記述以外に一切ヒットしない。テンプレート定義・`action(... template="AlloyRemoteDebug" ...)`参照ともに完全消滅しており、rsyslog起動失敗(未定義template参照)のリスクは解消されている。

### 3. 4系統で「action=dropによる明示的drop」原則が徹底されているか

**結論: 徹底されている。ラベルを残したままdropしている箇所、unlabeledのまま放置している箇所は見つからなかった。**

`grep -n '"debug"\|action.*=.*"drop"\|drop_counter_reason'`で全出現箇所を確認したところ、`"level" = "debug"`という`stage.static_labels`は1箇所も残っておらず、debugを扱う4箇所は全て`action = "drop"` + `drop_counter_reason`の組で終端している。

- 系統2(file source、pve_nodes/sophos_fw/ubuntu_nodes): `stage.regex`でlevelを`stage.labels`によりラベル化した直後、`selector = "{level=\"debug\"}"`でラベルを条件にaction=drop。ラベルは残さずdropする設計そのままで、確定→drop の順序が明示的。
- 系統3(best-effort、unifi/network_devices): debugトークン正規表現に一致した行を`stage.match`内で直接`action=drop`する(`stage.static_labels`を経由しない)。ラベルこそ付与しないが、判定条件はerror/warning/infoと同じ正規表現ロジックを流用しており、「一致条件で確定 → 明示的にdrop」という原則の実質は満たしている(付与すべきlabelがそもそも到達しないため、後続段でunlabeledとして残る余地がない)。
- 系統4(monnie journal): `loki.relabel`の`priority 7 → level=debug`は変更なしで維持されており、labelが確定した後の`loki.process`内で`{level="debug"}`をaction=dropする。既存の自ノイズdrop(unit限定)とは別のselector・別のreason文字列。

### 4. best-effort dropがunifi/network_devicesの両方に適用されるか

**結論: 両方に適用される。** `roles/alloy/defaults/main.yml`を直接確認し、`extract_level_best_effort: true`を持つのは`unifi`(L70)と`network_devices`(L80)の2 sourceだけであること、他3 source(pve_nodes/sophos_fw/ubuntu_nodes)は`false`であることを確認した。テンプレートのdrop追加は`{% if source.extract_level_best_effort %}`ブロック内の1箇所のみであり、`alloy_file_sources`ループで自動的に両方へ適用される。ローカルレンダリングでも`loki.process "unifi_pipeline"`・`loki.process "network_devices_pipeline"`の両方に同一のdrop stageが出力されることを確認した(rendered_config.alloy L47-52、L140-145相当)。

### 5. monnie journalのグローバルdebug drop新設が既存の自ノイズdrop(LOG-027)の意図を壊していないか

**結論: 壊していない。selectorに残る"debug"は無害な死んだ条件であり、問題ないと判断する。**

新設のグローバルdebug drop(`{job="ubuntu-nodes", host="monnie", level="debug"}`)は`loki.process "system_pipeline"`内で既存の自ノイズdropループより**前**に配置されている(レンダリング結果でも確認、L371-375がL377以降より先)。Alloyの`loki.process`内のstageは記述順に逐次実行されるため、グローバルdropが先にmonnie journal全体からdebug行を除去し、その後実行される自ノイズdropの5 unit分`stage.match`(selector: `level=~"info|debug"`)に到達する時点では、対象unitのdebug行は既に存在しない。したがって自ノイズdrop側の`"debug"`条件は現在の並び順のもとでは常に不一致となる死んだ分岐であり、二重dropによる実害はない。

LOG-027が担う本来の役割「観測stack自身の5 unitについてはinfoも収集前にdropする」という機能自体は、selectorの`info`側が変更されていないため完全に維持されている。理由文字列(`observability_info_debug`)も従来どおりのカウント式(`(alloy_observability_journal_drop_units | length)`件)で維持されており、可観測性(drop件数の内訳)にも影響しない。

備考(今回のscope外・pre-existing): 自ノイズdrop側selectorの`"debug"`は今回追加されたものではなく、LOG-027の本文(「exact unitかつinfoの場合だけ」)より広い条件を元々含んでいた。この差分自体は今回の変更で作られたものではなく、今回のグローバルdrop新設によって実害が生じない(むしろ冗長化した)ことのみを確認した。selectorを`info`のみへ縮小する整理は今回のdiffの範囲外であり、対応するなら別タスクとして切り出すことを推奨する(Suggestion参照)。

### 6. tasks/main.ymlのassert書き換えが既存の自ノイズdrop検証を弱めていないか

**結論: 弱めていない。既存チェックは無変更で維持されており、新設2 assertはむしろ検証範囲を広げている。**

- 削除された旧assert(`action = "drop"`の総数 == 自ノイズdrop unit数)は、debug drop stageが1種類しか存在しなかった旧テンプレート前提の検証であり、新テンプレートでは前提自体が成立しない(旧: 5件想定 → 実際: 11件)。削除は正当。
- 既存の`drop_counter_reason = "observability_info_debug"`件数チェック(L91、自ノイズdrop unit数と一致)は**一切変更されていない**(diffのhunkに含まれず、変更前の行がそのまま残っている)。自ノイズdropの検証強度は維持されている。
- 新設assert 1: `drop_counter_reason = "observability_debug_excluded"`件数 == (`extract_normalized_level_at_start=true`のfile source数) + (`extract_level_best_effort=true`のfile source数) + (journal source数)。`defaults/main.yml`を直接数えると3+2+1=6であり、期待式の計算根拠は妥当。
- 新設assert 2: `action = "drop"`総数 == 上記2つのreason別件数の合計。これは「reasonの無いdrop stageが紛れ込んでいないこと」を保証する構造的invariantであり、旧assertより広い範囲を保証する一般化。

**独立再現**: 上記2つの新設assertと既存の自ノイズdrop assertを含め、reviewer自身のscratch playbook(`hosts: localhost, connection: local`、defaults/main.ymlを読み込み実際に`config.alloy.j2`をレンダリング)で再実行し、`ALL ASSERTIONS PASSED`を確認した。実測値は `action = "drop"` 総数11、`observability_debug_excluded` 6、`observability_info_debug` 5(6+5=11で一致)。

### 7. warning/error経路への影響がないことの独立確認

**結論: 影響なし。** 3ファイルのdiff全hunkを確認し、`AlloyRemoteError`/`AlloyRemoteWarning`template、rsyslog側の`$syslogseverity <= 3`/`== 4`/`== 5 or 6`の各`action()`、best-effort側のerror/warning/info用`stage.match`(CEF側含む)、`loki.relabel`のerror/warning/info用`replacement`ルールのいずれも変更されていないことを確認した。レンダリング結果でも該当箇所は既存のまま出力されている。

### 8. scope: playbooks/差分ゼロ

```
$ git diff --stat -- playbooks/
(出力なし)
```

独立再実行で確認した。変更ファイルは`roles/alloy/tasks/main.yml`・`roles/alloy/templates/config.alloy.j2`・`roles/alloy/templates/observability-sources.rsyslog.j2`の3件のみ(`git status --porcelain roles/alloy/ playbooks/`で確認)。

## Suggestions

| # | File | Line | Suggestion | Category |
|---:|---|---|---|---|
| 1 | `roles/alloy/templates/config.alloy.j2` | 214(自ノイズdrop selector) | `level=~"info|debug"`の`debug`側は、新設グローバルdrop(L206-211)がより先に実行されるため常に不一致になる死んだ条件になった。動作に影響しないため今回のscopeでの修正は不要だが、将来2つのdrop stageの順序を入れ替える変更が入った場合に振る舞いが変わりうる(実害はどちらの順序でも「dropされる」という結論自体は変わらないが、`drop_counter_reason`の内訳が変わる)。「グローバルdropが必ず先に実行される」という順序依存を短いコメントで明記するか、selectorを`info`のみへ縮小してLOG-027本文とテンプレートの記述粒度を合わせることを次の整理タスクの候補として記録する。 | maintainability |

## Security Review

| 観点 | 結果 |
|---|---|
| 変数注入(shell/command) | 今回の差分にshell/commandモジュールの追加なし。rsyslog/Alloyテンプレートへの変数はいずれも`alloy_file_sources`/`alloy_journal_sources`/`alloy_observability_journal_drop_units`という既存の定義済みAnsible変数で、外部入力や実行時ユーザー入力を経由しない |
| no_log | debug drop追加はセキュリティ上機微な値を扱わない(level/unit/jobラベルのみ) |
| IP/VLAN/VM ID等の実値記載 | 本review文書にIPv4実値は記載していない。reviewer自身のローカル検証で使用したIPv4値はRFC 5737文書用予約帯のダミー値で、scratch fileは`/tmp`配下のみに存在しgit追跡対象外 |

## Scope・静的検査

| 検査 | 結果 |
|---|---|
| `--syntax-check`(独立再実行) | PASS(`playbooks/alloy_setup.yml`) |
| `git diff --stat -- playbooks/`(独立再実行) | 出力なし(playbooks/差分ゼロ) |
| `grep -rn "AlloyRemoteDebug" .`(独立再実行) | 出力は本review作成前時点で0件(実装報告の記述と一致) |
| `extract_normalized_level_at_start=true`の実件数 | `defaults/main.yml`直読で3件(pve_nodes/sophos_fw/ubuntu_nodes)、実装報告と一致 |
| `extract_level_best_effort=true`の実件数 | `defaults/main.yml`直読で2件(unifi/network_devices)、実装報告と一致 |
| ローカルレンダリング(reviewer独自のscratch playbook) | `config.alloy.j2`・`observability-sources.rsyslog.j2`双方をlocalhostでレンダリングし目視確認。tasks/main.ymlの新旧assert相当をこのscratch playbook内で再実行し全PASS |
| `alloy validate`(River構文の公式パーサ検証) | このマシンに`alloy`バイナリが存在せず未実施。実装報告と同じくtester/APPLY時委譲として扱う(reviewer側でも代替できないことを確認した) |
| `rsyslogd -N1`(rsyslog構文のバイナリ検証) | 実装報告と同じ理由(ansy実rsyslogサービスへの影響回避)により未実施。tester委譲 |

## What Looks Good

- 4系統とも「labelやmatchを消して静かに通す」のではなく、既存の判定条件(regexまたはlabel)をそのまま使い、末端だけを`action=drop`へ変えるという設計原則が一貫している。
- 新設のdrop stageが使う`action = "drop"` + `drop_counter_reason = "..."`という書き方は、この同じファイル内で既に本番稼働しているLOG-027自ノイズdropと全く同じ構文パターンの再利用であり、新規構文リスクが低い。
- `drop_counter_reason`をreason文字列で分けたことで、`observability_debug_excluded`と`observability_info_debug`が別カウントとして可観測になり、将来Alloyのdrop metricsから内訳を追跡できる。
- config.alloy.j2冒頭のコメントをLOG-070/071の実際の挙動(debugは正規化はするが常にdropする)に合わせて更新しており、実装とコメントが乖離していない。
- rsyslog側もLOG-071を明示引用するコメントを削除箇所に残しており、「なぜactionが無いのか」が読み手に伝わる。
- tasks/main.ymlのassert書き換えは、旧チェックを弱めるのではなく「reasonの無いdrop stageの混入」という新しい一般的な不変条件を追加しており、今後系統が増えても壊れにくい検証になっている。

## Verdict

**Approve**

blockingな指摘なし。Suggestion 1件(非blocking、自ノイズdrop selectorの`debug`条件整理)は今回のscopeに含める必要はなく、将来の整理タスク候補として記録するに留める。実host適用(APPLY)・`alloy validate`・`rsyslogd -N1`の実バイナリ検証は本レビューの対象外(tester/APPLY段階)として扱う。
