# quory NVMe取得ツール配備 — 要求追補

## 1. 問題定義

Semaphore #1083 の `SEMI-SAFE: Quory health monthly` native `--check` は、`/dev/nvme0n1` の NVMe健康情報を `tool_unavailable` と記録してrc=2で終了した。既存OPRES `req-20260913T103425+0900-66100285a5cf808c` でもOperatorの実行環境に`nvme-cli`が無いと報告された。観測playbookは取得不能を正常へ補完しないため、ツール導入を別入口で扱う必要がある（001要求、002計画、QHM-011/QHM-020）。

## 2. ゴール

quoryのSemaphore実行経路から`nvme`によるread-only健康情報取得が可能になるよう、必要なCLIをquory限定のsetup入口で配備する。観測playbookをパッケージ導入の入口にしない。

## 3. 非ゴール

NVMe self-test・firmware操作・format・sanitize、サービス再起動、reboot、他ホストへの導入、健康値の正常化、Notion親ページや月次scheduleの設定は行わない。`tool_unavailable`を成功扱いする変更もしない。

## 4. ユーザーストーリー

YoshinobuがSemaphoreから対象を明示したsetupジョブを実行し、配備後のreadbackを確認してから、月次ヘルスジョブの`--check`を再実行できる。

## 5. 要件

- P0: setupはquoryだけを対象とし、`nvme-cli`を冪等に導入する。観測playbook・既存Proxmox月次経路は変更しない。
- P0: native `--check`ではパッケージ変更を行わず、導入見込みと対象を確認できる。通常実行だけがインストールを行う。
- P0: Semaphoreから押せる専用テンプレートを追加し、scheduleは作らない。既存のtemplate setupのcheck→apply→readbackを経る。
- P1: setup後に`nvme`コマンドの存在と実行可否をreadbackする。コマンドが使えなければ成功扱いしない。
- P1: `playbooks/README.md`とOperations Contextへ配備順序と未確認事項を反映する。

## 6. 成功指標・受入条件

- AC-S1: Given quory inventory、When setupを`--check`で実行、Then quory以外へ接続せず、パッケージを変更せず、Semaphoreジョブはrc=0で導入見込みを表示する。通知・reportファイルは生成しない。
- AC-S2: Given quoryに`nvme-cli`が無い、When Yoshinobuがsetupを通常実行、Then quory上でパッケージが導入され、`nvme`コマンドの存在・実行可否を同ジョブの出力で確認でき、rc=0となる。導入失敗またはコマンド利用不能ならrc非0となる。他ホスト、NVMeデバイス内容、既存レポートには変更を加えない。
- AC-S3: Given setup後、When Yoshinobuが月次ヘルスジョブを`--check`で再実行、Then `tool_unavailable`が消えたかをジョブ出力で確認できる。消えなくても健康値を推測で正常へ置き換えず、原因を区別して次工程へ残す。Notion・Slack公開や月次schedule有効化はこのACに含めない。
- AC-S4: Given template setupのcheck→apply、When readback、Then専用setupテンプレートが1件存在し、scheduleは増えていないことを確認できる。変更経路の静的検査とsyntax-checkはrc=0。

## 7. オープンクエスチョン

`nvme-cli`導入後、実NVMeで`nvme id-ctrl` / `nvme smart-log`が成功するかは未確認。取得失敗が続けば権限・デバイス・CLI出力形式を別途調べ、健康ジョブの通常実行には進まない。

## 8. タイムライン考慮

コードをcommit/pushしてからquoryのSemaphoreへ反映し、setupのcheck→apply→readback、健康ジョブ`--check`の順で進める。本番適用はYoshinobuがSemaphoreで起動する。

## リスク

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Operational: パッケージ導入が想定外の変更を伴う | Low | Medium | checkの差分確認後に通常実行し、導入対象を`nvme-cli`へ限定する |
| Operational: 導入後もNVMe指標が取得できない | Medium | Medium | setupのコマンドreadbackと健康ジョブ`--check`を別々に評価し、UNKNOWNを維持する |
| Operational: 対象ホスト誤り | Low | High | quory単体のinventory guardと専用テンプレートで停止する |
