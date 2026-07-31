# Incident: Semaphoreジョブ失敗時に一次調査のcallbackがenqueueしなかった

日付: 2026-07-31
状態: 原因判明・対応方針決定(暫定)・実装未着手
対象: `roles/incident_investigate/callback_plugins/incident_investigate_trigger.py`、quory上のSemaphore実行経路
種別: 動作不具合
原因分類: (判明後に記入)

## 症状

2026-07-31 21:59、Semaphoreのタスク #495(`SEMI-SAFE:Cert_renew (only on Quory)`、`playbooks/cert_renew.yml`)がERRORで終了した。**「障害の一次調査の自動化」(ADR-009、同日クローズ)が想定する経路のうち、捕捉は動いたが調査要求の投入が動かなかった。**

| 段 | 結果 |
|---|---|
| 捕捉(`homelab-incident-capture`、5分毎にSemaphoreのDBをポーリング) | **動いた。** `reports/incidents/semaphore-495/` に `semaphore-log.log` / `semaphore-errors.log` / `semaphore-hosts.log` / `summary.json` が生成された。`incident-capture/state.json` も `{"last_failed_task_id": 495}` へ更新された |
| callbackによる調査要求の投入 | **動いていない。** `/var/lib/homelab-recovery/incident-investigate/queue/` は空のまま(ディレクトリのmtimeは同日13:03、以後変化なし) |
| 調査の実行(`homelab-incident-investigate.timer`、毎分) | timerは正常稼働し毎分成功終了しているが、**キューが空のため何も起動していない**。`reports/incidents/_investigations/` は空 |

Yoshinobuが「エラーなら追ってCodexから原因が通知されると思ったが来ない」と気づいて発覚した。

これは `docs/ai/status.md` のWatch「一次調査の callback が実Semaphore経路で発火するか(OQ2)」が、**否定側で決着したもの**である。

## 切り分け済みのこと(2026-07-31、read-onlyのみ)

次はいずれも「原因ではない」と確認した。

- **callback pluginの実体と設定は、当該テンプレートのcheckoutに存在する。** Semaphoreはテンプレートごとに `/opt/semaphore/project_1/repository_1_template_<N>/` へcheckoutしており、cert_renewが使うテンプレートには `roles/incident_investigate/callback_plugins/incident_investigate_trigger.py` と、`ansible.cfg` の `callback_plugins` / `callbacks_enabled = incident_investigate_trigger` の両方がある。
- **enqueue判定は到達不能のみの失敗も拾う作りである。** `_maybe_enqueue` は `stats.failures` と `stats.dark` の**両方**を見ており(`failed_hosts` / `dark_hosts`)、今回のような「pve1がUNREACHABLEでrc=4」でも投入される。
- **キューディレクトリは存在し、Semaphoreの実行ユーザーが書ける。** `/var/lib/homelab-recovery/incident-investigate/queue` は `yoshi:yoshi 0750`、Semaphoreは `User=yoshi` で動く。
- **checkoutが古かったわけではない。** 当該テンプレートのcheckoutは同日の変換後のコード(`cert_renew.yml` が `check-mode-native`、`issue_check.yml` が存在)を持っていた。

**Semaphoreは各ジョブの開始時にgitから最新を取り込む。** タスク#495の実行ログに `* branch main -> FETCH_HEAD` / `Updating 859386d..6918cf6` / `Fast-forward` が記録されており(2026-07-31 21:58:43、Yoshinobu提示)、**当該checkoutはジョブ開始時点で当日の最新commit `6918cf6` に追いついていた**。callback設定を含む `ansible.cfg` はその中にある。

> **訂正(2026-07-31)**: Coordinatorは当初、テンプレートごとのcheckoutディレクトリを走査して「分類が `risk-accepted` のまま」「callback設定なし」のものが多数あることから、**「checkoutはそのテンプレートが実行された時にだけ更新される。pushしても全ジョブが新コードで走るとは限らない」と結論した。これは誤りである。** 古かったのは**まだ実行されていないテンプレート**のディレクトリであり、実行時にfetchされる。**ディレクトリの現状だけを見て更新契機を推論し、実行ログという直接の証拠を取らなかったことが原因。** この経路の調査で「checkoutが古かったのでは」という仮説を再び立てないこと。

## 原因(2026-07-31、実測により確定)

**Semaphoreが起動する `ansible-playbook` プロセスに `SEMAPHORE_TASK_DETAILS_*` 環境変数が1つも渡っていない。** callbackはこれを「Semaphore経由の実行か」の判定に使っており、無ければ「Semaphore以外の起動経路(非ゴール)」とみなして黙って `return` する。

実測(2026-07-31 22:28、Yoshinobuがquory上でyoshiとして実施):

```
PID=89186
cwd -> /opt/semaphore/project_1/repository_1_template_11
HOME=/home/yoshi
PWD=/opt/semaphore/project_1/repository_1_template_11
```

`SEMAPHORE` を含む環境変数、および `ANSIBLE_CONFIG` は**1つも出力されなかった**。

これにより次が確定した。

- **cwdはcheckout直下である。** したがって `ansible.cfg` は自動検出される位置にあり、`callback_plugins` / `callbacks_enabled` の指定は効く。**候補2(ansible.cfgが読まれていない)は否定された。**
- **判定に使っている環境変数が存在しない。** callbackはロードされたうえで早期returnしていた。

`docs/ai/reviews/incident_auto_investigation/2026-07-31_002_u0_test_result.md` M3 は、semaphore v2.18.4 のソースに `fmt.Sprintf("SEMAPHORE_TASK_DETAILS_%s", ...)` が存在することを確認していた。**ソースに存在することと、この環境の実行時に注入されることは別であり、そこを実測せずに設計の前提にしたのが本件の構造である。**

### 参考: 確定前に検討した候補

1. **`SEMAPHORE_TASK_DETAILS_*` 環境変数がansibleプロセスへ渡っていない。** callbackはこれが1つも無ければ「Semaphore以外の起動経路(非ゴール)」とみなして黙って `return` する。この分岐に入った場合、ログにも痕跡が残らない(R2により例外を外へ出さず、I/Oも行わない設計であるため)。
2. **`ansible.cfg` がそもそも読まれていない。** Ansibleはカレントディレクトリの `ansible.cfg` を自動検出するが、**Semaphoreが `ansible-playbook` をどのcwdで起動しているかを確認していない。** checkout直下でなければ、`callback_plugins` / `callbacks_enabled` の指定ごと効かない。`docs/ai/reviews/incident_auto_investigation/2026-07-31_002_u0_test_result.md` M2 は、この点を「状況証拠から効いていると推定」と記録したまま**確定できずに終わっている**。今回の事象は、その未確定事項が実害として現れたものである可能性がある。

**候補1と2は、どちらも「callbackが痕跡を残さない」点で症状が同じ**であり、ログからは区別できない。

## 対応の選択肢と決定

| 案 | 内容 | 評価 |
|---|---|---|
| A | Semaphore側で `SEMAPHORE_TASK_DETAILS_*` が注入されるようにする(UIのEnvironment等) | **注入手段があるかが未確認。** ソースに存在しても、この版・この構成で有効化できるとは限らない。確認できるまで採用可否が決まらない |
| B | callbackの判定を別の信号へ変える(cwdが `/opt/semaphore/...` 配下である等) | 判定は代替できるが、**投入レコードに必要な task_id が得られない。** 捕捉側が作るバンドル `semaphore-<id>` と突き合わせられなくなる |
| C | **callbackをやめ、捕捉側の成果物を起点に調査を起動する** | 捕捉は既にSemaphoreのDBを5分毎にポーリングして task_id を持ち、バンドルを作っている。**「新しいバンドルが現れたら調査する」形にすれば、今回壊れた経路そのものが不要になる。** 代償は即時性(最大5分の遅延)と、Semaphore以外の実行経路を拾えないこと |

### 決定: **C を採る(暫定)**(2026-07-31 Yoshinobu)

**「暫定」と明示されている。** 恒久の設計判断としてADRを書き切るのではなく、**戻せる形で先に動かす**。具体的には callback plugin のファイルは削除せず残し、`ansible.cfg` の2行(`callback_plugins` / `callbacks_enabled`)を外すことで無効化する — 戻し方は同ファイルのコメントが既に持っている。

**Cを推した理由**: 今回の事象は「捕捉は動き、調査だけが動かなかった」である。捕捉はDBポーリングという独立経路を持ち、調査はcallback 1本に依存していた。**冗長性の非対称がそのまま出た。** ADR-009 が callback を選んだ理由は「載せない限り『どこで落ちても拾う』が成立しない」だったが、**Semaphoreジョブの失敗に限れば捕捉側が既に拾えている**。ADR-009の前提の見直しを含むため、ADRの改訂または新規ADRを伴う。

## 未確認のこと(この記録の限界)

- **Semaphoreが何を注入しているかの全体像を見ていない。** 観測したのは `SEMAPHORE` / `ANSIBLE_CONFIG` / `PWD` / `HOME` に絞ったgrepの結果であり、**環境変数名の一覧は取っていない。** 案Bの「別の判定信号」を検討するなら、まず名前だけを列挙する必要がある(値には秘密が含まれうるため名前のみ)。
- callbackが**ロードされたことを直接観測してはいない**(早期returnの経路を通ったという推論である)。ただしcwdがcheckout直下であることから設定は効く位置にあり、ロードされなかったと考える根拠は無い。
- **この観測にはyoshiまたはrootの権限が要る。** Coordinatorの接続identity(`ann`)では `Permission denied`、Codex(`recovery-exec`)でも同じ理由で読めない。**同種の確認は今後も人の手が要る。**
- 過去の失敗ジョブで同じことが起きていたかは調べていない(この経路が本番稼働に入ったのが同日であるため、母数がほぼ無い)。

## 設計上の含意(暫定)

**捕捉は動き、調査は動かなかった。** 捕捉はSemaphoreのDBを5分毎にポーリングする独立した経路を持つのに対し、**調査はcallbackというplaybook実行内の経路1つだけに依存している。** 冗長性の非対称がそのまま出た形である。

`docs/ai/reviews/incident_auto_investigation/2026-07-31_001_requirement.md` の R8(Semaphore外ジョブの保険)が未実装であることとは別の問題で、こちらは**Semaphore内ジョブでも投入されない**ケースである。

## 修正内容

**未実施。方針(C)は決まっており、実装はこれから。** 着手時の計画は次のとおり(2026-07-31にCoordinatorが提示、Yoshinobu合意済み)。

1. requirement を `docs/ai/reviews/incident_investigate_trigger/` に書く。
2. `incident-investigate.py` のトリガを**キュー読みから「未調査バンドルの走査」へ**変える。`ansible.cfg` の2行を外して callback を無効化(pluginファイルは残す)。
3. 独立レビュー。
4. Tester — **`semaphore-495` が実際に拾われて `_investigations/` に成果物が出ること**(通過側)と、**調査済みバンドルが再投入されないこと**(非通過側)の両方を観測する。片方だけでは機構が効いた証明にならない。
5. **ADR-009 にトリガ機構の暫定supersessionを注記**し、`docs/ai/policies/incident_capture_policy.md` IC-034〜042 の該当箇所を確認する。

**Coordinatorが決めた設計点**(実装時に覆すなら理由を記録すること):

- **未調査の判定は `_investigations/semaphore-<id>.json` の不在**とする。状態を別ファイルへ二重に持たない(捕捉側で「消費済みidの記憶」を二重化しない判断をしたのと同じ理由。`docs/ai/status.md` Next 参照)。
- **1回の実行で処理するのは最大1件**、かつ**一定期間より古いバンドルは対象外**とする。timerは毎分なので実質毎分1件で、初回に積み残しを一気にCodexへ投げない。
- **可逆性を優先する。** 暫定判断であるため、callback plugin のファイルは残す。

## 確認方法

未確定。修正後は「Semaphoreジョブが失敗したとき、`queue/` に要求ファイルが現れること」と「成功したときは現れないこと」の**両方**を観測して確認する。片方だけでは機構が効いた証明にならない。

## 参照

- `docs/ai/adr/009-per-incident-investigation-runtime.md`(Accepted)
- `docs/ai/policies/incident_capture_policy.md` §3.5(IC-034〜IC-042)
- `docs/ai/reviews/incident_auto_investigation/2026-07-31_002_u0_test_result.md` M2(`ansible.cfg` がSemaphore実行に効くかを当時確定できなかった記録)
- `reports/incidents/semaphore-495/`(quory。捕捉側は正常に生成された証拠)
