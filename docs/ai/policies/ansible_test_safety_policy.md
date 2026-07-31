# Ansible Test Safety Policy

本書は全playbookに付与する`# tester-gate:`マーカーの分類、その意味、実行方法、機械チェック、Roleごとの実行義務の正本である。旧`docs/ai/prompts/core.md` §18から移設した(2026-07-26)。環境事実と実装詳細は対応Contextを参照し、競合時は本Policyを優先する。

## 1. 目的

<!-- TS-001 -->
playbookごとに「`--check`の有無で挙動がどう変わるか」「本実行してよいか」を宣言し、実行者が推測せずに安全な実行方法を決められる状態を保つ。

<!-- TS-002 -->
判断はplaybook先頭のマーカーを一次情報とする。マーカーと実装が乖離した場合は乖離自体を欠陥として扱い、マーカーの文言を安全の根拠に使わない。

### 背景: `tester_mode` / `tester_gate` roleとの区別

<!-- TS-003 -->
`tester_mode`変数と`tester_gate` roleは2026-07-06〜07に廃止済みであり、`roles/tester_gate`は実在しない。廃止理由は、`tester_gate`がplay / host単位で`end_play` / `end_host`するため、危険操作の手前にある本来安全な診断ロジック(healthcheck、apt dry-runシミュレーション等)までテスト対象から外れ、テストの実効性が低かったことである。Ansible標準の`--check`(`ansible_check_mode`)をゲート機構とする方式へ移行した。Semaphoreの`--check`オプションがそのまま効くため独自の`-e`変数は不要である。

<!-- TS-004 -->
本Policyが定める`# tester-gate:`**ヘッダマーカーは廃止されていない**。名前が似ているだけの別物であり、廃止済みの`tester_mode`と混同しない。

## 2. 対象と実行範囲

<!-- TS-005 -->
`playbooks/`配下の全playbookを対象とし、5分類のいずれか1つをヘッダに宣言する。

| 種別 | 意味 |
|---|---|
| `safe-readonly` | 完全read-only(収集・観測のみ)。ゲート不要、常に本実行してよい |
| `role-guarded` | 副作用がSlack通知のみで、`roles/common_slack/tasks/notify.yml`の抑止guardで止まる |
| `risk-accepted` | 破壊性はあるが、§4の2条件を満たすため常に本実行してよいと人間が判断したもの。**dry-runを持たず、`--check`を渡された場合は適用せずに停止する**(TS-030) |
| `check-mode-native` | read-onlyな診断・検証部分は`--check`でも常に本実行し、実際の破壊的操作(またはそれに依存する後続処理)だけを`ansible_check_mode`でゲートする |
| `dry-run-aware` | 破壊的コマンド自体を、`ansible_check_mode`下でネイティブのdry-run引数に差し替えて実行する(スキップではなく安全な引数での実行) |

<!-- TS-006 -->
マーカーは`# tester-gate: <種別> — <理由>`の1行形式とする。`risk-accepted`の理由には、許容した最悪ケースを明記する。

## 3. 対応するPlaybook

<!-- TS-007 -->
本Policyは特定のplaybookではなく`playbooks/`全件に適用される横断Policyである。個別playbookの分類実値は各ファイル先頭のマーカーが正本であり、本Policyへ一覧を複製しない(複製すると必ずドリフトする)。

<!-- TS-008 -->
現在の分類分布は`grep -h "^# tester-gate:" playbooks/*.yml | sort | uniq -c`で得る。

## 4. 判断軸

### risk-accepted の許可条件

<!-- TS-009 -->
`risk-accepted`は次の2点をともに満たす場合にだけ選ぶ。

1. 本番サービス・他システムへの実害がない(隔離されている / 影響範囲が自己完結 / 最悪ケースが軽微で復旧が容易)。
2. 破壊的な本体操作を省いた検証には意味がない、または省く価値が乏しい(バックアップのリストア検証など、本体操作自体が検証の目的そのものであるケース)。

<!-- TS-010 -->
いずれか一方でも成立しない場合は`check-mode-native`または`dry-run-aware`を選ぶ。

<!-- TS-011 -->
**実行コスト(所要時間、ストレージI/O量、実行回数)を分類理由にしない。** 重いことはrisk-acceptedを避ける理由にならず、軽いことはrisk-acceptedを選ぶ理由にもならない。

### オーケストレータの扱い

<!-- TS-012 -->
`import_playbook`で束ねるオーケストレータは、import先が既に`check-mode-native`化されている場合、上位の`when:`条件へ`ansible_check_mode`を追加しない。追加するとimport先で意図的に残した「read-only部分は`--check`でも本実行する」設計を上位で握りつぶし、テスト網羅性が落ちる。オーケストレータ自身のpreflightと完了通知は別途`--check`対応を要する。

## 5. ライフサイクル・処理フロー

<!-- TS-028 -->
本節は分類ごとの実装方式を定める。**module差、handler、`end_play`、`loop:`付きinclude等の実装上の例外は`skills/ansible-implementation-style/SKILL.md`「check_mode の実装上の落とし穴」を必ず併せて読む。** 本節の方式は、そこに記載された例外条件を満たす場合にのみ意図どおり機能する。

### risk-accepted: 常時本実行

<!-- TS-013 -->
呼び出し元(playbookまたはroleのimport箇所)に`check_mode: false`を1つ置けば、配下のtask / block / rescue / always / ネストされた`include_tasks`・`include_role`(`loop:`付きも含む)まで一括でカスケードする(実地検証済み)。

```yaml
tasks:
  - name: Run <role> (always for real)
    ansible.builtin.import_role:
      name: <role>
    check_mode: false
```

<!-- TS-030 -->
`risk-accepted`は`--check`を安全な実行手段として提供しない。**実際に変更を行う各playの`pre_tasks`に、`ansible_check_mode`が真なら停止するassertを置く。** `check_mode: false`は「`--check`を無視して適用する」意味であり、停止条件が無ければdry-runのつもりの実行がそのまま本番適用になる(2026-07-31 Incident: subagentが`--check`付きで実配備した)。**停止の有無はplay単位で確認する** — 複数playを持つplaybookでは、変更を行うplayすべてに要る。

<!-- TS-032 -->
`risk-accepted`のplaybookをcheck-mode-safeにした場合は、**分類そのものを`check-mode-native`へ変え**、TS-030の停止assertと`check_mode: false`を外す。「`risk-accepted`のまま`--check`でも安全」という第3の状態を作らない。`--check`が何を意味するかはヘッダのマーカーが単独で決める。

### check-mode-native: 破壊的操作だけゲート

<!-- TS-014 -->
read-onlyな診断taskには`check_mode: false`、破壊的task(またはそれをまとめたblock)には`when: not ansible_check_mode`と`tags: [destructive]`を付ける。

<!-- TS-015 -->
複数の破壊的taskが相互依存する場合(reboot→post-reboot検証→報告、migrate→maintenance mode→HA待機→強制停止など)は、個別taskへ`when`を付けるより、一連をまとめて1つのnamed blockにしblock単位でゲートする。

### dry-run-aware: ネイティブdry-runへ差し替え

<!-- TS-016 -->
破壊的コマンド自体の引数を`ansible_check_mode`で切り替える(実装例: `roles/sophos_trim/tasks/main.yml`)。

<!-- TS-017 -->
この方式では、コマンドを実行するtask自体(`expect`や`command`などcheck_mode非対応module)に`check_mode: false`を付けないと、`--check`時にtaskごとauto-skipされ、引数の切り替えが無意味になる。**安全な引数を選んだだけではdry-run検証は成立しない。**

## 6. 通知方針

<!-- TS-018 -->
2値分岐(`ok` / `error`等)の通知・レポートには、plan-only / check-modeの分岐を必ず含める。これを忘れると、dry-runの成功が`error`(最悪`critical`)として誤通知される。`--check`実行時は結果分岐にもcheck_modeを考慮する。

<!-- TS-031 -->
`ansible_check_mode`が真のとき、`roles/common_slack/tasks/notify.yml`はSlackへ送信せず通知本文を出力に示す。**この判定はnotify.yml側だけが持ち、呼び出し側が`check_mode: false`で覆さない。** 分類によらず一貫させ、check mode下で送信する例外を作らない — 例外を1つ作れば、それが唯一の抜け道になる(TS-029と同じ理由)。抑止を明示したい場合の`skip_notifications`は従来どおり有効で、`--check`を付けずに本適用しつつ通知だけ止める手段はこちらである。

## 7. 制約・禁止事項

### 機械チェック

<!-- TS-019 -->
「全playbookが5分類のいずれかに分類されている」ことと、「`risk-accepted`が停止assertを持つ」(TS-030)ことは規約ではなくlintで保証する。`scripts/check-tester-gate.sh`が`playbooks/`配下の全playbookを検査し、`scripts/git-pre-commit-check.sh`から自動実行される。**後者はassertの存在を見る床であり、TS-030が求めるplay単位の充足までは機械判定できない**(どのplayが変更を行うかをスクリプトから判定できないため)。play単位の充足はレビュー工程が見る。

<!-- TS-020 -->
マーカーを持たない新規playbookはcommitできない。この機械的停止条件を無効化・迂回しない。

### 実行義務

<!-- TS-021 -->
実行者は渡されたコマンドをそのまま実行せず、対象playbookのヘッダマーカーを必ず確認する。

<!-- TS-022 -->
マーカーが`safe-readonly` / `role-guarded` / `risk-accepted`の場合は通常実行でよい(`--check`は不要)。**`risk-accepted`に`--check`を付けてはならない** — dry-runにはならず、playbook自身が停止する(TS-030)。

<!-- TS-023 -->
マーカーが`check-mode-native` / `dry-run-aware`の場合は**必ず`--check`を付ける**(`--check --diff`を重ねてもよい)。`--check`なしの実行はAPPLY(本番適用)であり、Tester役は行わない。

<!-- TS-024 -->
`check-mode-native` / `dry-run-aware`の検証実行には`scripts/safe-ansible-check.sh <playbook> ... --check`を使う。このwrapperはargvに`--check`が含まれない場合は即終了し、含まれる場合のみ`ansible-playbook "$@"`へ委譲するため、`--check`の付け忘れを機械的に防ぐ。`risk-accepted`はdry-runを持たないためwrapperの対象外である(`--check`を渡すとplaybook自身が停止する。TS-030)。

<!-- TS-025 -->
wrapperは付け忘れ防止の補助であり、安全性の最終判断はplaybook headerのマーカーと承認済みtest_planに基づいて行う。wrapperを通したことを安全の根拠にしない。

<!-- TS-029 -->
検証者が`check-mode-native` / `dry-run-aware`のゲートを明示的に迂回するためのescape hatch(旧設計で検討された`allow_unsafe=true`等)は実装しない。この決定は2026-07-06の分類設計時に確認され、現在もリポジトリ内に該当実装は存在しない。ゲートを迂回する必要が生じた場合は、迂回機構を作るのではなくYoshinobuの本番適用判断を経る。

### マーカーの扱い

<!-- TS-026 -->
マーカーの分類名だけを安全の根拠に使わない。分類名、理由文、実際の抑止guard名、実行経路が一致しているかを照合する。過去に理由文が廃止済みの`tester_mode` guardを指しながら実guardは`skip_notifications`だった「marker drift」が複数playbookで実在した。

<!-- TS-027 -->
`safe-readonly`であっても、冪等なscript配置、localhostへのreport保存、条件付きSlack通知などの副作用を持つ場合がある。分類名から副作用ゼロを推定しない。

## 8. 変更履歴

| 日付 | 変更 |
|---|---|
| 2026-07-06〜07 | `tester_mode` / `tester_gate` roleを廃止し、`--check`(`ansible_check_mode`)ベースの5分類へ移行。旧`docs/ai/prompts/core.md` §18として記述 |
| 2026-07-26 | 旧core §18からPolicyへ移設し正本化(移行表C18-01/02/05/09/11/12/14)。実装上の落とし穴(C18-03/04/06/07/08/10)は`skills/ansible-implementation-style/SKILL.md`へ分離。C18-13(Codex承認prefix由来のwrapper運用)は、Codexが開発工程から外れたためprefix依存の記述を落とし、`--check`付け忘れ防止という本来の効能のみTS-024として保持 |
| 2026-07-31 | `--check`の意味を一本化。`risk-accepted`は`--check`で**停止**する(TS-030新設)、check mode下でSlackへ送らない判定を`notify.yml`に集約(TS-031新設)、check-mode-safe化したら分類を`check-mode-native`へ変える昇格経路を明文化(TS-032新設)。TS-005 / TS-022 / TS-024の「`--check`を付けても挙動が変わらない」という記述を実態へ改訂。案件記録: `docs/ai/reviews/check_mode_semantics/` |
