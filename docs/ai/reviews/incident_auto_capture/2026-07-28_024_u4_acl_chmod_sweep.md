# U4 — 同じ欠陥クラスの掃引(AC5): named-user/named-group ACLパスへのchmod相当

- 作成: 2026-07-28 Reviewer(subagent)
- 対象計画: `docs/ai/reviews/incident_auto_capture/2026-07-28_018_acl_mask_plan.md` §1(因果モデル)、§2 C3、§4 U4、§5(Tech Leadの下地)
- Coordinator決定: `2026-07-28_020_coordinator_decisions.md`「Q-U4-1」
- 実装変更: **ゼロ。** 本ファイルの新規追加のみ。`git status` で確認できる(下記§0参照)。実ホストへは一切触れていない(すべてローカルのgit/grep/read)。
- 独立性: 本レビューはU1/U2(Implementer、`roles/common_slack/tasks/capture.yml` と `roles/incident_capture/tasks/main.yml` を変更)とは別体のsubagentが行った。対象実装の変更は自ら行っていない。

---

## 0. 前提として確認した現在の作業ツリー状態

本掃引の着手時点で、U1・U2のImplementerが既に作業を終えていた(`git status --short` で確認):

```
 M roles/common_slack/tasks/capture.yml       (U1: T1側の mode: 削除)
 M roles/incident_capture/tasks/main.yml      (U2: role側 create-only化)
```

**この掃引は、U1/U2適用後の現在のコードベースを対象に行う。** 「まだ直っていない箇所」だけでなく「直った箇所が本当に直っているか」も含めて全体を掃引した(C3の手順はU1/U2の差分そのものにも同じ基準で適用できるため、二重の確認になる)。U2の docstring・ADR-003補正は本掃引の着手時点ではまだ未着手だったが、これはAC6(U2+U3の担当)であり、AC5(本掃引)の対象外。

---

## 1. 方法の妥当性の証明(パス文字列検索が失敗することの再現)

Tech Leadの主張(計画§5)を鵜呑みにせず、自分で再現した。

Tech Leadが最初に使った検索:
```
grep -rn "_spool" roles/ playbooks/ scripts/ | grep -iE "chmod|mode:|mkdir -m"
```

これを**U1適用前のcommit済み版**(`git show HEAD:roles/common_slack/tasks/capture.yml`)に対して実行した:

```
$ git show HEAD:roles/common_slack/tasks/capture.yml > /tmp/.../capture_pre_u1.yml
$ grep -n "_spool" /tmp/.../capture_pre_u1.yml | grep -iE "chmod|mode:|mkdir -m"
(出力なし、rc=1)
```

一方、同じファイルの同じ版で `mode: "0755"` を直接確認すると:

```
$ grep -n 'mode: "0755"' /tmp/.../capture_pre_u1.yml
228:        mode: "0755"
```

**確認できた。** 当時まさに本番事故を起こしていた箇所(228行目、`_capture_ctx.spool_dir` に対する `mode: "0755"`)を、パス文字列 `_spool` からの検索は1件も拾えない。理由はTech Leadの説明どおり: このタスクの `path:` は `{{ _capture_ctx.spool_dir }}` という変数であり、`_capture_ctx` は `set_fact` で `capture_spool_dir | default(reports_base_dir ~ '/incidents/_spool')` から組み立てられる(`capture.yml` 202行目)。`_spool` という文字列自体はこのタスクの周辺のどこにも書かれていない(defaultのjinja式の中に `'/incidents/_spool'` という文字列は登場するが、それは202行目の `set_fact` タスクにあり、228行目のchmodタスクの近傍ではないため、`grep -iE "chmod|mode:|mkdir -m"` の同一行フィルタには引っかからない)。

**これは方法の妥当性の証明として重要**: 本掃引はパス文字列からの検索を採用せず、C3の手順(ACL付与箇所→変数解決→書き手を変数名でも追う)で行った。

---

## 2. ACL付与箇所の完全な一覧

リポジトリ全体で `ansible.posix.acl` タスクと `setfacl` の直接呼び出しを検索した。

```
grep -rn "ansible.posix.acl" roles/ playbooks/ scripts/
grep -rln "setfacl" .  (全ファイル種別、"*.yml/*.py/*.sh/*.j2"含む)
```

`ansible.posix.acl` タスクは2 role・8タスク(重複パスあり)。`setfacl` の直接呼び出しは**リポジトリ全体でゼロ件**(`roles/recovery_exec/tasks/main.yml:271` のコメント内言及のみ。Tech Leadの記載どおり、実行コードではない)。

| # | パス(変数展開後) | entity | perms | access/default | 付与元 file:line(現在のHEAD+作業ツリー) |
|---|---|---|---|---|---|
| 1 | `/home/yoshi` | recovery-exec | x | access | `roles/recovery_exec/tasks/main.yml:229-236` |
| 2 | `/var/lib/semaphore` | recovery-exec | x | access | 同 238-245 |
| 3 | `/var/lib/semaphore/semaphore.db` | recovery-exec | r | access | 同 247-254 |
| 4 | `/var/lib/homelab-recovery/mute` | recovery-exec | rwx | access | 同 285-291 |
| 5 | `{{ incident_capture_bundle_dir }}` = `{{ reports_base_dir }}/incidents` | recovery-exec | rwx | access | `roles/incident_capture/tasks/main.yml:96-103` |
| 5' | 同上 | recovery-exec | rwx | **default** | 同 105-113 |
| 6 | `{{ incident_capture_spool_dir }}` = `{{ incident_capture_bundle_dir }}/_spool` | recovery-exec | rwx | access | 同 124-131 |
| 6' | 同上 | recovery-exec | rwx | **default** | 同 133-140 |

以下、他人の記録(Tech Leadの下地§5)にあった行番号を鵜呑みにせず、現物を再度読んで確認した。Tech Leadの下地は**U2適用前**の行番号だったため、U2のcreate-only化で行がずれている(例: 旧59/68行 → 現96/105行)。行番号は上表のとおり更新して記録する。

**変数の別名(C3手順2)を確認した**:
- `incident_capture_bundle_dir`(role側の変数名)= `{{ reports_base_dir }}/incidents`(`roles/incident_capture/defaults/main.yml:22`)
- `incident_capture_spool_dir`(role側)= `{{ incident_capture_bundle_dir }}/_spool`(同25行)
- `capture_spool_dir`(T1側の変数名。role側と別名だが同じ値を指す)のデフォルトは `reports_base_dir ~ '/incidents/_spool'`(`roles/common_slack/tasks/capture.yml:202`)。**リテラル文字列としては `incident_capture_spool_dir` の展開結果と一致するが、変数名が違う。** これがまさに§1で再現した検索失敗の原因である。
- `recovery_exec_user` / `incident_capture_user` は共にデフォルト値 `recovery-exec` を指す同一entity(`roles/recovery_exec/defaults/main.yml` および `roles/incident_capture/defaults/main.yml:12`)。

---

## 3. 各パスに対する全書き手の一覧とchmod相当の有無

方法(C3手順3): 各実体を書く `file` / `copy` / `template` / `command` / `shell` タスクとPythonの `os.chmod` を、パス文字列と変数名の両方で検索した。

### #1 `/home/yoshi`

- 検索: `path: /home/yoshi` の完全一致、および `ansible.builtin.user` で `name: yoshi` を管理するタスク。
- **書き手: リポジトリ内にゼロ件。** `yoshi` ユーザー自体を作成・管理する `ansible.builtin.user` タスクがこのリポジトリに存在しない(既存の人間アカウントであり、Ansibleの管理対象外)。
- **判定: 非該当。** chmod相当の書き手が存在しないため、欠陥クラスが発生する余地がない。
- 補足: 仮に将来 `/home/yoshi` に対するchmod相当が追加された場合、grant permissionsが `x`(traverse)のみであっても、named-userエントリの実効権限が切り詰められうる(`x` 単体でも `mask` が `r--` 等へ落ちればtraverse不能になる)ため無視してよい理由にはならない。現状は書き手ゼロで確定。

### #2 `/var/lib/semaphore`、#3 `/var/lib/semaphore/semaphore.db`

- 検索: `/var/lib/semaphore` を含む全行。
- 一致したのは `roles/recovery_exec/tasks/main.yml:238`, `:240`, `:249` の3行のみ、すべてACL付与タスク自身。
- **書き手: リポジトリ内にゼロ件。** `/var/lib/semaphore` はSemaphore本体(このリポジトリ外で管理されるアプリケーション)のデータディレクトリであり、このAnsibleリポジトリはそこへ書き込むタスクを持たない(ACLで読み取り専用のtraverse/read権限を付与しているだけ)。
- **判定: 非該当。** リポジトリのAnsible/scriptの範囲でchmod相当の書き手が存在しない。Semaphore自身のインストーラ/パッケージ管理がこのディレクトリを内部でchmodする可能性はD5の境界(「このリポジトリのAnsible/script」)の外であり、対象外とする(§6の完了条件で明示)。

### #4 `/var/lib/homelab-recovery/mute`

全書き手を洗い出した(変数名 `recovery_push_mute_dir` / `MUTE_DIR` / リテラルパスの3系統で検索):

| 書き手 | 種別 | chmod相当 | 判定 |
|---|---|---|---|
| `roles/recovery_exec/tasks/main.yml:278-282`(このACLの直前) | `ansible.builtin.command: mkdir -m 0755 -p ...` + `creates:` | **無**(create-only。`creates:` があるため既存ディレクトリに対しては実行されない) | 非該当 |
| `roles/recovery_mute/tasks/deploy_cli.yml:10-13` | 同上パターン | 無 | 非該当 |
| `roles/recovery_mute/tasks/set.yml:26-30` | 同上パターン | 無 | 非該当 |
| `roles/recovery_mute/files/homelab-mute`(人間用CLI、90-93行) | シェルの `mkdir -m 0755 -p "$MUTE_DIR"` | 無(`mkdir -m` は新規作成時のみモードを与え、既存ディレクトリには効果を持たない。POSIXの `mkdir` は既存パスに対して何もしない=エラーになるが、ここでは `-p` があるため黙って成功し、既存ディレクトリのモードには触れない) | 非該当 |
| `roles/recovery_exec/files/homelab-mute-set`(Codex向けラッパー) | `chmod 0644 "$tmp"`(111行) | **対象はディレクトリでなく一時ファイル**(mute JSON書き込みのatomic replace用)。ディレクトリ自体へのchmodではない | 非該当(別オブジェクト) |
| `roles/recovery_mute/files/homelab-mute` | `chmod 0644 "$tmp"`(113行) | 同上、ファイル(`.target.XXXXXX` の一時ファイル)へのchmod。**ディレクトリのACLは`access`のみでdefault ACLが付与されていない**(main.yml:283-290に`default: true`は無い)ため、この一時ファイルはそもそもnamed-userエントリを継承しない。単純なファイルパーミッション操作であり本欠陥クラスの対象外 | 非該当 |
| `roles/recovery_mute/tasks/set.yml:47`(shell内 `MUTE_DIR=...` 変数代入行) | 変数代入のみ、chmod呼び出しではない | 無 | 非該当(誤検出防止のため記載) |

**判定: 非該当(全書き手についてchmod相当なし)。** Tech Leadの下地の記述と一致した。**この#4こそが「正解パターン」の実例であり(D3が模範にした先例)、独立に確認できたことに意味がある**: recovery_exec自身のmute dir作成タスク(main.yml:278-282)ですら、`ansible.posix.acl` タスクの直前にありながらcreate-only化されており、自己が付与したACLを自己が壊す経路を持たない。

### #5 / #5' `reports/incidents/` 本体(access + default ACL)

全書き手を洗い出した(`incident_capture_bundle_dir` 変数名、および `reports/incidents` 文字列、`reports_base_dir ~ '/incidents'` のjinja式の3系統で検索):

| 書き手 | 種別 | chmod相当 | 判定 |
|---|---|---|---|
| `roles/incident_capture/tasks/main.yml:32-36`(U2で新設) | `command: mkdir -m 0755 -p ...` + `creates:` | 無(create-only) | 非該当 |
| `roles/incident_capture/tasks/main.yml:38-49`(U2で `mode:` 削除済み) | `ansible.builtin.file`、`owner: yoshi` のみ、`mode:` なし | **無**(U1/U2適用後の現状。`file` モジュールは `mode is None` のとき `set_mode_if_different()` が即returnするため既存ディレクトリのパーミッションに触れない — D2根拠と同一機構) | 非該当(**修正済み**。U2適用前は該当だった=Tech Leadの表の「#5 該当」はU2適用前の状態を指しており、現状は解消されている) |
| collectorスクリプト(`incident-capture-collector.py`)の `os.makedirs(bundle_dir, ...)` 等 | `bundle_dir` 自体を作る呼び出しは無い(`bundle_dir` は既に存在する前提で使われるのみ。`os.makedirs` が呼ばれるのは `dest_dir`(=bundle_dir配下の新規バンドルdir)、`_runs/`、`_rejected/`、`state_dir`) | — | 対象外(bundle_dir自体を書く操作がそもそも無い) |

**判定: 非該当(現状)。** U2適用前は該当していたが、U2の差分でcreate-only化済み(§0参照。U3が別途、この差分の正しさを検証する)。

### #6 / #6' `reports/incidents/_spool/`(access + default ACL)

| 書き手 | 種別 | chmod相当 | 判定 |
|---|---|---|---|
| `roles/incident_capture/tasks/main.yml:78-82`(U2で新設) | `command: mkdir -m 0755 -p ...` + `creates:` | 無 | 非該当 |
| `roles/incident_capture/tasks/main.yml:84-95`(U2で `mode:` 削除済み) | `ansible.builtin.file`、`owner: yoshi`、`group: homelab-ansible` のみ | 無(#5と同じ機構) | 非該当(修正済み) |
| `roles/common_slack/tasks/capture.yml:249-253`(T1、U1で `mode:` 削除済み) | `ansible.builtin.file`、`path: "{{ _capture_ctx.spool_dir }}"`、`state: directory`。`mode:` なし | **無**(U1適用後の現状) | 非該当(**本番事故の直接原因だった箇所。U1で修正済み**) |
| collectorスクリプトの `os.makedirs` | `_spool/` 自体を作る呼び出しは無い(`list_spool_files`/`load_spool_record`/`os.remove` で消費するのみ。`_rejected/` は `os.path.join(spool_dir, "_rejected")` で作るがmode指定なし) | 無 | 非該当 |
| `_spool/_rejected/`(`_spool/` の子、default ACLを継承) | `reject_spool_file()` 内 `os.makedirs(rejected_dir, exist_ok=True)`(251行) | **無**(mode引数なし。`os.makedirs` はmode省略時umask依存の新規作成のみで、既存ディレクトリを再chmodしない) | 非該当。**D5境界の「配下に作られるファイル/ディレクトリへの明示mode」を確認する項目としてTech Leadが名指ししていたため、個別に検証した** |

**判定: 非該当(現状)。** U1で修正済み。これが本番事故を起こした当該箇所そのものであり、`_spool` 文字列検索が拾えなかった箇所と一致する(§1で再現済み)。

### `default` ACLで継承される配下オブジェクト(D5境界の継続確認)

Tech Leadが「U4が追加で確認すべき」と挙げていた項目: default ACLを持つ#5/#6の配下に作られるファイル/ディレクトリへの明示mode指定。

`reports/incidents/` 配下に新規作成されるのは、collectorスクリプトの以下の呼び出しのみ(§前節で洗い出し済み):
- `write_bundle()` → `os.makedirs(dest_dir, exist_ok=True)`(`dest_dir = bundle_dir/<bundle_id>`) — mode指定なし
- `write_run_report()` → `os.makedirs(runs_dir, exist_ok=True)`(`_runs/`) — mode指定なし
- `write_heartbeat()` → `os.makedirs(bundle_dir, exist_ok=True)` — mode指定なし(bundle_dir自体は既存前提だが念のため確認、mode指定なし)
- `reject_spool_file()` → `os.makedirs(rejected_dir, exist_ok=True)`(`_spool/_rejected/`) — mode指定なし

**`os.chmod` はこのファイル全体でゼロ件**(`grep -n "os\.chmod" roles/incident_capture/files/incident-capture-collector.py` で確認、§4参照)。

**判定: 非該当。** default ACLで継承されるオブジェクトのいずれにも、作成時にmodeを明示する書き手が存在しない(すべてumask既定に委ねている)。作成後にこれらを再chmodする操作(retention削除は `shutil.rmtree`/`os.remove` のみで、chmodを一切含まない)も存在しない。

---

## 4. 網羅的な `chmod` / `os.chmod` / `setfacl` の掃引結果(全件、非該当も含む)

C3の手順1〜3をACL起点で行った上で、取りこぼしがないことを裏付けるため、`chmod`・`os.chmod` の全出現をリポジトリ全体で再確認した(パス文字列検索に頼らない、というC3の原則に反しないよう、これは**補完的な網羅性チェック**であり、判定の根拠には使っていない — 判定は上記§3のACL起点の追跡で確定済み)。

| # | 場所 | 対象 | ACLパス(#1〜6)との関係 | 判定 |
|---|---|---|---|---|
| a | `roles/proxmox_patch_apply_node/files/proxmox-patch-apt-phase.sh:31` | `/bin/chmod 0640 "$log_path"` | `$log_path` は `proxmox_patch_apply_report_dir`(`{{ reports_base_dir }}/proxmox-patch`)配下のログファイル。**ACLが付与されていないパス系統**(上表#1〜6のいずれにも属さない) | 非該当。maskエントリ自体が存在しないため、この欠陥クラスは原理的に発生しない(D5の境界) |
| b | `roles/recovery_mute/tasks/set.yml:67` | `chmod 0644 "$tmp"` | mute dirの中の一時ファイル(#4の子)。#4のACLは `access` のみでdefault ACL無し(§3 #4で確認済み)、対象はファイルでありディレクトリでもない | 非該当(既出、§3 #4と同じ) |
| c | `scripts/tmux-ask-watch.sh:301` | `chmod 600 "$temp_state"` | tmux監視スクリプトの一時状態ファイル。`incident_capture`/`reports/incidents`/mute dirいずれとも無関係 | 非該当 |
| d | `scripts/tests/test-tmux-ask-watch.sh:118` | `chmod +x "$mock_tmux" "$mock_send"` | テストフィクスチャの実行権限付与、ACLと無関係 | 非該当 |
| e | `roles/recovery_exec/files/homelab-mute-set:111` | `chmod 0644 "$tmp"` | 既出(§3 #4)、ファイル対象 | 非該当 |
| f | `os.chmod`(Python全体) | — | **リポジトリ全体でゼロ件**(`grep -rn "os\.chmod" . --include="*.py"` が空) | 該当なし(検索対象そのものが無い) |
| g | `setfacl`(直接呼び出し) | — | **リポジトリ全体でゼロ件**。唯一の言及は `roles/recovery_exec/tasks/main.yml:271` のコメント内(実行コードではない、D3の設計判断を説明する文章) | 該当なし |

**a〜gのすべてが非該当。** 該当したのは§3で列挙した#5・#6の(U1/U2適用**前**に存在していた、現在は解消済みの)2箇所のみであり、それ以外に新規の該当箇所は見つからなかった。

---

## 5. 該当/非該当の総括表

| # | パス | chmod相当の書き手 | 現状の判定 | 備考 |
|---|---|---|---|---|
| 1 | `/home/yoshi` | なし | 非該当 | 書き手ゼロ |
| 2 | `/var/lib/semaphore` | なし(リポジトリ範囲内) | 非該当 | リポジトリ外(Semaphore本体)の管理範囲はD5境界外 |
| 3 | `/var/lib/semaphore/semaphore.db` | なし(リポジトリ範囲内) | 非該当 | 同上 |
| 4 | `/var/lib/homelab-recovery/mute` | 3箇所すべてcreate-only、ファイルへのchmodは対象ディレクトリと別オブジェクト | 非該当 | 本件の模範パターン(D3の先例) |
| 5 | `reports/incidents/` | U2適用前: `incident_capture/tasks/main.yml`(旧11-21行)/ U2適用後: なし | **修正済み(非該当)** | U2で解消。U3が差分の正しさを検証する対象 |
| 6 | `reports/incidents/_spool/` | U1/U2適用前: `incident_capture/tasks/main.yml`(旧46-53行)+ `common_slack/tasks/capture.yml`(旧228行、T1) | **修正済み(非該当)** | **本番事故の直接原因**。U1+U2で解消 |
| — | `_spool/_rejected/`(default ACL継承先) | なし | 非該当 | os.makedirsにmode指定なし |
| — | bundle配下の `spool-*`/`semaphore-*`/`_runs/`(default ACL継承先) | なし | 非該当 | 同上 |

**新規に見つかった、`incident_capture` 以外の該当箇所: ゼロ件。**

Q-U4-1(Coordinator決定)への回答: 掃引の結果、`incident_capture` 以外(#1〜4)に該当箇所は見つからなかったため、「別案件として起票する/本案件で直す」のどちらの分岐も発動しない。**起票対象なし。**

---

## 6. 掃引の完了条件が満たされたことの明示

計画D5が確定した境界: **「named-user または named-group のPOSIX ACLを持つ(または将来持ちうる)パスに対する、chmod相当の操作」だけを見る。** 根拠は「maskエントリはnamed entryまたはgroup entryを持つ拡張ACLにのみ作られ、ACLが無ければchmodは通常のPOSIX意味論しか持たない」という機構上の閉じた境界(§5決めた範囲、原文参照)。

本掃引はこの境界の**内側**を次の手順で網羅した:

1. **境界の内側(ACL付与箇所)を先に確定した**: `ansible.posix.acl` タスクと `setfacl` 直接呼び出しをリポジトリ全体から検索し、8タスク・6パス(うち2パスはaccess+defaultの組で計8エントリ)を得た(§2)。この列挙自体が全体(境界の内側)であり、これ以上の「ACL付与箇所」はリポジトリに存在しない(`ansible.posix.acl` と `setfacl` の検索が全体を尽くしている — POSIX ACLを操作する経路はこの2つ以外にこのリポジトリには無い)。
2. **各パスについて、変数の別名を解決してから全書き手を検索した**(§3)。C3手順2・3のとおり、パス文字列だけでなく変数名(`incident_capture_bundle_dir`/`incident_capture_spool_dir`/`capture_spool_dir`/`_capture_ctx.spool_dir`/`recovery_push_mute_dir`/`MUTE_DIR`)を横断して検索した。
3. **default ACLで継承される配下オブジェクトも追跡した**(§3末尾)。#5・#6はdefault ACLを持つため、その配下に新規作成されるファイル/ディレクトリ(spool-*/semaphore-*バンドル、_runs/、_rejected/)も同じmaskを継承しうる。これらの作成コードすべてを確認し、mode明示の書き手が無いことを確認した。
4. **境界の外側(ACLを持たないパス)は原理的に対象外であることを、実際に見つかった全chmod呼び出し(a〜g)について個別に確認した**(§4)。「たぶん関係ない」で済ませず、リポジトリ内の `chmod`/`os.chmod`/`setfacl` の全出現(7箇所)を1つずつ、対象パスがACL付与済みパス(#1〜6)のいずれとも一致しないことを確認した。

**この4段階を終えた時点で、C3が定義する掃引範囲(D5の境界の内側)を尽くしたと判断する。** 境界の外側(ACLを持たない一般のディレクトリ・ファイルへのchmod)は、D5の機構的根拠(maskエントリが存在しなければ切り詰めが起きえない)により、意図的に見ていない。これは見落としではなく、Tech Leadが計画で示した論拠を独立に検証した上で採用した線引きである。

**確認できなかった項目**: なし。C3の手順1〜4のすべてを実行し、すべての書き手について該当/非該当を判定できた。

---

## 7. Verdict

```
## Code Review: U4 — 同じ欠陥クラスの掃引(AC5)

### Summary
ACL付与箇所(8タスク・6パス)を起点に、パス文字列でなく変数を解決して
全書き手を追跡した。パス文字列検索(_spool grep)が本番事故の当該箇所を
1件も拾えないことを再現し、C3の方法の妥当性を裏付けた。U1/U2適用後の
現状では、named-user/named-group ACLを持つパスへのchmod相当の書き手は
リポジトリ全体でゼロ件。U1/U2適用前に該当していた2箇所(reports/incidents/、
_spool/)はいずれも解消済み。incident_capture以外の該当箇所は見つからず、
Q-U4-1の「別案件起票」分岐は発動しない。

### Critical Issues
(なし)

### Suggestions
| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | roles/incident_capture/files/incident-capture-collector.py | 251 | `_spool/_rejected/` はdefault ACLを継承するため、将来ここへ明示mode付きの
書き手が追加された場合は同じ欠陥クラスに落ちる。現状は非該当だが、
docstring(D10の補完対象)に「配下オブジェクトも再chmod禁止」の一文を
含めるとU2のAC6作業と整合が取れる(判断はU2/U3の担当、ここでは指摘のみ) | 保守性 |

### What Looks Good
- U1(T1側 mode: 削除)・U2(role側 create-only化)とも、C3で洗い出した
  全書き手のうち該当していた箇所を過不足なく修正している(取りこぼしなし)。
- mute dir(#4)は本欠陥クラスに対する模範パターンとして機能しており、
  同じ設計が独立に3箇所(recovery_exec/recovery_mute deploy_cli/set)で
  一貫している。

### Verdict
Approve(掃引結果として、追加の修正対象なし)
```

---

## 8. Coordinatorへの申し送り

- Q-U4-1(掃引で他箇所が見つかった場合の扱い)は**発動しなかった**。`incident_capture` 以外(#1〜4)に該当箇所はゼロ件だったため、別案件の起票も本案件への追加も不要。
- U4自身は計画どおり修正を行っていない(発見と記録のみ)。
- 本記録はU1/U2適用後の状態を対象にしており、U3(独立レビュー)のR1(chmod経路ゼロの横断確認)と観点が重なる。**ただし別体・別関心(横断掃引 vs 差分レビュー)として行ったため、独立性は保たれている**(計画§8の推奨どおり)。U3が本記録と異なる結論に達した場合は、両者を突き合わせてCoordinatorへ報告することを推奨する。
