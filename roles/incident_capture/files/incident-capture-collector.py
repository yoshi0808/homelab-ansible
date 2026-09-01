#!/usr/bin/env python3
"""incident-capture-collector — quory 常駐の証拠バンドル収集器(Step 1 / R2)

設計の正本: docs/ai/adr/003-incident-capture-collector-runtime.md
入力契約: roles/common_slack/tasks/capture.yml の record_version 1

実行形態(ADR-003 (a) a-1): systemd timer + oneshot service。多重起動抑止は
Python の外側、systemd の ExecStart 上で `flock -n -E 75` が行う(このスクリプト
自身はロックを取らない — flock が起動できなければこのスクリプトは一度も
実行されない)。

終了コード(この役割内で定義。AC5/AC7):
  0 = 正常終了。新規イベントなし(SSHゼロ本)の周期も含む。
  2 = 収集は完了したが、collection_errors に1件以上の記録がある
      (Semaphoreスキーマ不一致・spool不整合・R5b異常等)。
  3 = 想定外の内部例外(バグ)。collection_errors による記録を経由しない、
      本当に予期しない失敗。AC5が期待する「2」とは意図的に区別する。
  75 = (このスクリプトからは返らない。flock -E 75 が多重起動時に返す値。
        参考として記載するのみ。)

**exit 2 の journal可読性**(2026-09-02、
docs/ai/reviews/incident_capture_journal_legibility/2026-09-02_001_requirement.md
AC1〜AC8、実装記録2026-09-02_002。2回の独立レビューで3件blocking差し戻し
(B1〜B3)を受け是正済み — 以下は是正後の最終形): collection_errors を
伴って exit 2 で終わる周期は、journalへ「何件あったか(run/bundle内訳
込み)」と各 collection_errors の"what"の要約を書く
(log_collection_errors_to_journal、AC1/AC2)。多数あるときは件数の上限で
切り詰め、切り詰めた事実自体を明示する(AC3)。EXIT_OK の周期は何も
出力しない(AC4)。既存の EXIT_INTERNAL_ERROR の1行(本ファイル末尾の
`except Exception`節)は変更しない(AC5、severityも含め今回は一切touchしない)。

出力先はstderr — unit template(incident-capture.service.j2)は
StandardOutput/StandardError を指定しておらず、systemd既定(journal)に
従う。この経路は EXIT_INTERNAL_ERROR が既に使っている(ただしそちらが
実際にjournal/Lokiで観測された記録は無い — 本節の結論はunit templateに
明示指定が無いことから独立に成立する)。**各行の先頭へ `<4>`
(syslog priority: warning)を付ける**(_journal_write、B3是正) —
`<4>`無しの既定severity(info)のままだと、monnie側rsyslogの振り分け
(`$syslogseverity==4`だけが"warning"ラベルになる。
roles/alloy/templates/observability-sources.rsyslog.j2)と、既に配備済みの
Grafanaダッシュボード(infra-syslog-all-nodes.json)の既定`level`フィルタ
(`["warning","error"]`)の組み合わせにより、要約はLokiへ入るのに
`Failed with result 'exit-code'`が見えている画面には出ない、という
この案件が防ごうとした状況そのものが再現してしまうため(Claude Reviewer
B3)。EXIT_INTERNAL_ERROR の1行には`<4>`を付けていない(今回のscope外)。

集約対象は周期全体のcollection_errors(このmain()内のローカル変数)と
各バンドルのsummary["collection_errors"]の両方 — 2026-09-01の実
インシデントが示した「no named investigate operations available for
host 'quory'」は後者(バンドル単位)にしか記録されず、write_run_reportが
書くcollection_errorsには載らない。

表示するのは"what"のみで"why"は出さない(AC7)。ただし"what"自体にも
非信頼データ(IC-016: spoolのpath/basename/play_host/play_nameを連結する
5箇所)が混入する経路が実在した(codex Reviewer B2が現物5箇所と
negative testで指摘、初版の「混入経路は無い」という判断は誤りだった)。
是正後は、非信頼値を連結するf-stringを WHAT_PREFIX_* の固定プレフィックス
から組み立て(_runs/・バンドルへ書く内容自体は従来と同一)、journal表示
側だけが _redact_untrusted_what() でこのプレフィックスに一致した"what"を
固定の要約文へ置き換え、連結された非信頼値そのものは出さない。それ以外の
(非信頼な自由記述を連結しない)"what"は、改行相当文字を正規化してから
(B1是正 — 1件の埋め込み改行がJOURNAL_SUMMARY_MAX_ITEMS/_WHAT_MAX_CHARS
という「件数・文字数の上限」を物理journal行数の上限としては無力化していた。
2026-09-01のloki-errors案件とcodexが指摘した欠陥クラスは同一で、是正の
形(" ".join(value.splitlines()))も揃えた)、1件あたりの表示長も
防御的に切り詰める。

dry-run経路は無い(AC8) — このスクリプトはAnsibleではなく`--check`相当の
概念を持たず、今回追加した出力はstderrへの書き込みのみで新たな副作用は無い。

**現況スナップショット中のSSH到達不能は、それ単体では終了コードを2にしない。**
pve1平日日中シャットダウン運用下ではSSHタイムアウトが日常的に起きうる
(docs/ai/adr/003-incident-capture-collector-runtime.md 末尾のd-2解説を参照)。
到達不能の事実は各バンドルの snapshot 配列内に ok:false として正確に記録される
(R5の「隠すべき失敗ではない」はこれで満たす)。終了コード2は「収集器自身が
何を試みて何を取得できなかったかを判断できない/記録できない」状態
(スキーマ不一致・spool破損・R5b)のためだけに予約する。

R5b(捕捉停止の検出): Semaphoreに新規の失敗ジョブ記録があるのに、その周期の
spoolディレクトリが完全に空だった場合、T1(common_slack/capture.yml)が
壊れている可能性を collection_errors へ記録する。厳密な「全ステータス」の
Semaphore活動ではなく「失敗ジョブ」を基準にしている理由: 既存の
homelab-semaphore-query に新規クエリを追加しない制約(ADR-003 (c)。
2026-08-19、実装がSQL直読みからREST API呼び出しへ移ったため文言は「新規クエリ」
へ改めたが、制約の中身(カタログ登録は1本ずつ人が判断する)は変わっていない)
の下では、
`recent-failed`(status IN error/stopped のみ)が唯一のバルク一覧クエリであり、
これを起点にするのが最も安価で正確。

**既知の限界(2026-07-27 独立レビューSuggestion #2で指摘、意図的に直さない)**:
ok状態のみが記録された周期にT1が壊れてもこの経路では検出できない。
直さない理由: 実害が無い期間だからである。T1が壊れていても、その間に
Semaphoreジョブの失敗が一件も起きていなければ実害は発生しない(捕捉すべき
「失敗の証拠」がそもそも存在しない)。実害が出るのは「失敗が起きた時に
ちょうどT1も壊れている」場合であり、そのときは `recent-failed` に新規の
失敗行が現れると同時にspoolが空になるため、このR5bの条件(新規失敗ジョブ
あり かつ spool総数ゼロ)で確実に検出できる。「全ステータスのSemaphore活動」
を捕捉するには新規クエリ(または `task-time` でのID逐次walk)が要り、
ADR-003 (c) の「新規クエリを増やさない」制約およびD1/D2(カタログ登録は1本ずつ
人が判断する)を超えるため、この限定は要件不足ではなく制約から来る意図的な
線引きである。カタログ拡張はしない(2026-07-27 Coordinator判断)。
requirement.mdが言う3層防御の第3層であり、唯一の防御ではない。

spool消費方式(Implementerの設計判断 — 根拠はここに書く):
T1が書くspoolファイルはコントローラ実行ユーザ(quory本番ではyoshi)所有・
0755ディレクトリに作られ、収集器はrecovery-execで動くため、そのままでは
親ディレクトリへの書込権が無く消費済みレコードを削除できない。
ADR-003が新規に許可する権限は「reports/incidents/ へのPOSIX ACL
(default entry付き)」だが、reports/incidents/_spool/ は reports/incidents/ の
**サブディレクトリ**であり、default ACLは「そこから新規作成される」エントリに
しか継承されない。T1がこのroleより先に _spool/ を作っていた場合、
reports/incidents/ への default ACL だけでは既存の _spool/ には遡って効かない。
そのためこのroleは reports/incidents/ 本体に加えて reports/incidents/_spool/
自体にも同じ named-user ACL(rwx、access + default)を明示的に付与する
(roles/incident_capture/tasks/main.yml参照。RSK-06の「reports/直下には
付与しない」制約は reports/incidents/ ツリーの外に出ないため守られている)。
_spool/ 自体に rwx を持てば、sticky bit の無い通常ディレクトリでは
「ディレクトリへの書込権があれば中のファイルは所有者に関係なく rename/unlink
できる」というPOSIXの規則により、各spoolファイルの所有者(yoshi)を変えずに
収集器が消費できる。

補足(2026-07-28、ACL mask障害の教訓。docs/ai/adr/003-incident-capture-collector-runtime.md
補正2、docs/ai/reviews/incident_auto_capture/2026-07-28_018_acl_mask_plan.md):
上記の「ディレクトリへの書込権があれば…」自体はPOSIXの規則として正しいが、
この権限モデルには前提条件がある。named-user ACLエントリの**実効**権限は、
エントリ自体の値ではなく `min(エントリの権限, ACL maskエントリ)` で決まる
(`getfacl` が `#effective:` として警告する値)。上記のrwxは `mask::` がrwxを
維持している間だけ実効し、そのmaskは対象ディレクトリへの `chmod`(および
`chmod` を内部で呼ぶ `ansible.builtin.file` の `mode:` 指定)ひとつで
書き換わってしまう。named entryを含む拡張ACLを持つディレクトリでは、
chmodが要求するグループビットの行き先はgroup entryではなくmaskだからである。
したがって、reports/incidents/ と _spool/ のどちらに対しても、**このroleより
後にこのディレクトリを再chmodする書き手を作ってはならない**
(roles/incident_capture/tasks/main.yml 冒頭の不変条件、C1を参照)。
2026-07-28、roles/common_slack/tasks/capture.yml のディレクトリ作成タスクが
`mode: "0755"` を持っていたためにこのmaskが本番quoryで書き換わり、収集器が
_spool/ 配下の消費済みレコードを削除できなくなる障害が実際に発生した。
    - 正常に取り込めたレコード: 即座に削除する(重複取り込み防止。内容は
      バンドルの summary.json 側に複製済みなので消える情報は無い)。
    - スキーマ不正なレコード(JSON parse失敗・record_version不一致・
      必須フィールド欠如・written_atが不正)は削除せず _spool/_rejected/ へ
      move し、collection_errors に記録する。何が壊れているか人間が調査できる
      余地を残すため、"消せないから読み飛ばして終わり" にはしない。
      _rejected/ は収集器自身(recovery-exec)のUIDで作るため追加のACLは不要。
"""
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import re
from datetime import datetime, timedelta, timezone

CONFIG_PATH_DEFAULT = "/etc/homelab-recovery/incident-capture.json"

EXIT_OK = 0
EXIT_COLLECTION_ERRORS = 2
EXIT_INTERNAL_ERROR = 3

JST = timezone(timedelta(hours=9))

# homelab-semaphore-query は Semaphore REST API 経由へ移行済み
# (docs/ai/reviews/semaphore_query_api/2026-08-19_001_requirement.md R3、
# 2026-08-19)。start/end はAPIが返すRFC3339をそのまま出力する — 旧来の
# 'YYYY-MM-DD HH:MM:SS[.nnnnnnnnn] +0000 UTC'(Goの time.Time.String()、
# semaphore.db直読み時代の保存形式。2026-07-27 W0実測、
# docs/ai/reviews/incident_auto_capture/2026-07-27_004_observation.md)は
# もう出力されない。RFC3339は秒未満の桁数と、末尾が'Z'か数値オフセット
# (+HH:MM/-HH:MM)かのどちらも取りうる形として書く — 'Z'限定にすると
# 数値オフセット形の応答を取りこぼす。
RFC3339_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})$"
)

REQUIRED_SPOOL_FIELDS = {
    "record_version",
    "written_at",
    "controller",
    "play_name",
    "play_host",
    "slack_channel",
    "slack_status",
    "slack_title",
    "slack_message",
    "skip_notifications",
    "check_mode",
}

# 通知経路が"問題あり"として記録した(ok/空文字以外の)ステータス集合。
# ok/空文字は「捕捉はしたが単体では証拠バンドルの根拠にならない」通常通知。
NON_NOTABLE_SLACK_STATUS = {"", "ok"}

# collection_errors の "what" のうち、非信頼データ(IC-016: spoolのpath/
# basename/play_host/play_name。書き手は recovery-exec とAnsible controller
# identityのいずれも非信頼)を末尾に連結して組み立てるものの固定プレフィックス
# (B2是正、2026-09-02 Reviewer)。journal表示側(log_collection_errors_to_journal
# の _redact_untrusted_what)はこの定数を使ってprefixだけを残し、連結された
# 非信頼値は出さない。生成側(reject_spool_file/consume_spool_file/
# collect_host_snapshot/spool単独バンドル生成)もこの定数からf-stringを組み立て、
# 文字列リテラルを二重管理しない — _runs/・バンドル本体に書く内容(prefix+値)は
# 従来と完全に同じ文字列になる。
WHAT_PREFIX_REJECT_MOVE_FAILED = "failed to move malformed spool record "
WHAT_PREFIX_REJECT_MALFORMED = "malformed spool record "
WHAT_PREFIX_CONSUME_REMOVE_FAILED = "failed to remove consumed spool record "
WHAT_PREFIX_NO_INVESTIGATE_OPS = "no named investigate operations available for host '"
WHAT_PREFIX_NO_CORRELATED_JOB = "no correlated Semaphore job found for spool record ("


# ---------------------------------------------------------------------------
# 時刻
# ---------------------------------------------------------------------------
def parse_semaphore_time(raw):
    """homelab-semaphore-query生値(RFC3339) -> aware datetime。

    形式が一致しなければ ValueError。握りつぶさない(R5)。呼び出し側で
    except して collection_errors へ積む。Python 3.11未満でも動くよう
    datetime.fromisoformatの'Z'対応には頼らず、'Z'/数値オフセットの両方を
    自前の正規表現(RFC3339_RE)で受ける。
    """
    if not raw:
        raise ValueError("empty timestamp value")
    m = RFC3339_RE.match(raw.strip())
    if not m:
        raise ValueError(f"does not match RFC3339 format: {raw!r}")
    y, mo, d, h, mi, s, frac, tz = m.groups()
    micros = int((frac or "0").ljust(6, "0")[:6])
    if tz == "Z":
        offset = timezone.utc
    else:
        sign = 1 if tz[0] == "+" else -1
        oh, om = tz[1:].split(":")
        offset = timezone(sign * timedelta(hours=int(oh), minutes=int(om)))
    return datetime(int(y), int(mo), int(d), int(h), int(mi), int(s), micros, tzinfo=offset)


def to_rfc3339_jst(dt):
    """aware datetime -> RFC3339(JST、オフセット明示、裸のZ/UTCは付けない)。"""
    return dt.astimezone(JST).isoformat(timespec="seconds")


def now_jst_str():
    return to_rfc3339_jst(datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# homelab-semaphore-query 呼び出し(D1: 名前を呼ぶだけ、新規クエリを増やさない。
# 2026-08-19、実装はREST API呼び出しへ移行済み — 制約の対象は「新規クエリ」
# であって「新規SQL」ではない)
# ---------------------------------------------------------------------------
def run_semaphore_query(bin_path, timeout, *args):
    try:
        r = subprocess.run([bin_path, *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, "", str(e)
    return r.returncode, r.stdout, r.stderr


def parse_recent_failed(stdout):
    """'id|template|playbook|status|start' 行のリストを返す。

    フィールド数不一致(スキーマ変更等)は行単位でエラー文字列として返し、
    その行はスキップする(AC5)。

    **既知の限界(2026-07-27 独立レビューSuggestion #6、意図的に直さない)**:
    `str.split("|", n)` によるパースは、template/playbook列の値自体に
    `|` 文字が偶然含まれていた場合、フィールド境界がずれて誤った値を
    静かに拾う(列数は5/6のままなのでエラーにならない)。直さない理由:
    template名はYoshinobu管理下のSemaphoreプロジェクトテンプレート名であり
    `|` を含む運用は現状無く、`homelab-semaphore-query` の出力形式自体が
    この区切り文字を前提にしている(このスクリプト固有の弱さではなく、
    呼び出し先の出力契約に従っているだけ)。区切り文字をやめて別形式
    (JSON等)で返すには `homelab-semaphore-query` 側の変更が要り、それは
    Codexからも叩かれる共有スクリプトであるため本Stepの範囲外。将来
    template名に `|` を許す運用に変える場合はこの制約を再検討すること。
    """
    rows, errors = [], []
    for i, line in enumerate(stdout.splitlines()):
        if not line.strip():
            continue
        parts = line.split("|", 4)
        if len(parts) != 5:
            errors.append(f"recent-failed line {i}: expected 5 fields, got {len(parts)}: {line!r}")
            continue
        task_id_raw, template, playbook, status, start = parts
        try:
            task_id = int(task_id_raw)
        except ValueError:
            errors.append(f"recent-failed line {i}: non-integer id {task_id_raw!r}")
            continue
        rows.append(
            {"id": task_id, "template": template, "playbook": playbook, "status": status, "start_raw": start}
        )
    return rows, errors


def parse_task_time(stdout):
    """'id|template|playbook|status|start|end' の単一行を期待する。"""
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    if len(lines) != 1:
        raise ValueError(f"expected exactly 1 row from task-time, got {len(lines)}")
    parts = lines[0].split("|", 5)
    if len(parts) != 6:
        raise ValueError(f"expected 6 fields from task-time, got {len(parts)}: {lines[0]!r}")
    task_id, template, playbook, status, start, end = parts
    return {
        "id": int(task_id),
        "template": template,
        "playbook": playbook,
        "status": status,
        "start_raw": start,
        "end_raw": end,
    }


# ---------------------------------------------------------------------------
# spool
# ---------------------------------------------------------------------------
def list_spool_files(spool_dir):
    if not os.path.isdir(spool_dir):
        return []
    return sorted(
        os.path.join(spool_dir, f)
        for f in os.listdir(spool_dir)
        if f.endswith(".json") and os.path.isfile(os.path.join(spool_dir, f))
    )


def load_spool_record(path):
    """JSONとしてparseし、record_version/必須フィールド/written_atの妥当性を
    検証して返す。どれか1つでも欠けたり壊れていれば ValueError(呼び出し側が
    _rejected/ へ退避する)。"""
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("spool record is not a JSON object")
    if obj.get("record_version") != 1:
        raise ValueError(f"unsupported record_version: {obj.get('record_version')!r}")
    missing = REQUIRED_SPOOL_FIELDS - obj.keys()
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    try:
        datetime.fromisoformat(obj["written_at"])
    except (ValueError, TypeError) as e:
        raise ValueError(f"written_at is not a valid ISO timestamp: {obj.get('written_at')!r} ({e})") from e
    return obj


def reject_spool_file(spool_dir, path, reason, collection_errors):
    rejected_dir = os.path.join(spool_dir, "_rejected")
    os.makedirs(rejected_dir, exist_ok=True)
    dest = os.path.join(rejected_dir, os.path.basename(path))
    try:
        shutil.move(path, dest)
    except OSError as e:
        collection_errors.append({"what": f"{WHAT_PREFIX_REJECT_MOVE_FAILED}{path}", "why": str(e)})
        return
    collection_errors.append(
        {"what": f"{WHAT_PREFIX_REJECT_MALFORMED}{os.path.basename(path)}", "why": reason}
    )


def consume_spool_file(path, collection_errors):
    try:
        os.remove(path)
    except OSError as e:
        collection_errors.append(
            {"what": f"{WHAT_PREFIX_CONSUME_REMOVE_FAILED}{path}", "why": str(e)}
        )


# ---------------------------------------------------------------------------
# 現況スナップショット(ADR-003 (d) d-2: 名前で呼ぶだけ、文字列連結でコマンドを作らない)
# ---------------------------------------------------------------------------
def run_investigate(bin_template, host, op, timeout):
    """1回の名前付き操作を呼ぶ。

    2種類の失敗を区別する(2026-07-27 独立レビューSuggestion #5):
      - missing_binary=True: `homelab-investigate-<host>` そのものが存在しない。
        これは配備の欠陥(typo・配備漏れ)であり、pve1が落ちているような
        routineな状況とは意味が違う。呼び出し側がこのフラグを見て
        collection_errors へ積む(exit 2 の対象)。
      - missing_binary無し(ok=False, rcあり or timeout): SSH到達不能・
        タイムアウト・非ゼロ終了。pve1平日日中シャットダウン運用下では
        日常的に起きうるため、単体では collection_errors へ積まない
        (ADR-003末尾の解説どおり。事実は snapshot 配列内の ok:false として
        正確に記録されるので、R5の「隠さない」はこれで満たす)。
    """
    path = bin_template.format(host=host)
    if not os.path.exists(path):
        return {
            "host": host,
            "op": op,
            "ok": False,
            "missing_binary": True,
            "error": f"no such investigate wrapper: {path}",
        }
    try:
        r = subprocess.run([path, op], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"host": host, "op": op, "ok": False, "error": f"timed out after {timeout}s"}
    except OSError as e:
        return {"host": host, "op": op, "ok": False, "error": str(e)}
    return {
        "host": host,
        "op": op,
        "ok": r.returncode == 0,
        "rc": r.returncode,
        "stdout": r.stdout,
        "stderr": r.stderr,
    }


def collect_base_snapshot(cfg):
    results = []
    for target in cfg["base_snapshot_targets"]:
        for op in target["ops"]:
            results.append(
                run_investigate(cfg["investigate_bin_template"], target["host"], op, cfg["ssh_snapshot_timeout_s"])
            )
    return results


def collect_host_snapshot(cfg, host):
    """指定ホストの failure_snapshot_ops を全て呼ぶ。

    戻り値: (results_or_None, no_ops_error_or_None)。host が
    failure_snapshot_ops のキーに無い場合は (None, エラー辞書)。
    呼び出し元(main)がホスト単位でこの結果をキャッシュし、同じホストを
    参照する全バンドルへ個別に error/snapshot を反映する(1回しか呼ばれない
    ことに依存して2件目以降のバンドルへの反映が抜けないようにするため、
    副作用(collection_errorsへの追記)をこの関数の中では行わない —
    2026-07-27 独立レビュー対応で、missing_binaryの反映漏れを避けるために
    この形にした)。
    """
    ops = cfg["failure_snapshot_ops"].get(host)
    if not ops:
        return None, {
            "what": f"{WHAT_PREFIX_NO_INVESTIGATE_OPS}{host}'",
            "why": (
                "host is not a key in incident_capture_failure_snapshot_ops "
                "(ADR-003 constraint 4: named operations only exist for "
                "authy/monnie/pve1/pve2)"
            ),
        }
    results = [
        run_investigate(cfg["investigate_bin_template"], host, op, cfg["ssh_snapshot_timeout_s"]) for op in ops
    ]
    return results, None


def append_missing_binary_errors(snapshot_results, bundle_collection_errors):
    """run_investigateがmissing_binary=Trueを返した項目を、SSH到達不能
    (routine、単体では非fatal)とは区別して collection_errors へ積む
    (配備欠陥。2026-07-27 独立レビューSuggestion #5)。"""
    for r in snapshot_results:
        if r.get("missing_binary"):
            bundle_collection_errors.append(
                {
                    "what": f"investigate wrapper missing for {r['host']} {r['op']}",
                    "why": r["error"],
                }
            )


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------
def load_state(state_dir):
    path = os.path.join(state_dir, "state.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"last_failed_task_id": 0}


def save_state(state_dir, state):
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, "state.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# バンドル書き出し(AC6: 拡張子は .json/.log/.md のみ、一時ファイルは *.tmp)
# ---------------------------------------------------------------------------
def write_bundle(bundle_dir, bundle_id, summary, raw_logs):
    dest_dir = os.path.join(bundle_dir, bundle_id)
    os.makedirs(dest_dir, exist_ok=True)
    summary_path = os.path.join(dest_dir, "summary.json")
    tmp_path = summary_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, summary_path)
    for name, content in raw_logs.items():
        if not content:
            continue
        log_path = os.path.join(dest_dir, name)
        tmp_log = log_path + ".tmp"
        with open(tmp_log, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_log, log_path)
    return dest_dir


def write_run_report(bundle_dir, run_id, report):
    runs_dir = os.path.join(bundle_dir, "_runs")
    os.makedirs(runs_dir, exist_ok=True)
    path = os.path.join(runs_dir, f"{run_id}.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def write_heartbeat(bundle_dir, report):
    """毎周期、正常時も含めて無条件で上書きする単一ファイル
    (2026-07-27 独立レビューSuggestion #3で追加)。

    write_run_report は collection_errors がある周期にしか呼ばれないため、
    「収集器プロセスそのものが止まっている」(unit失敗・flockのlock
    ファイル権限問題・Pythonインタプリタ不在等)ことを検出する手段が
    それだけでは存在しなかった。このファイルは固定パス
    (bundle_dir/_heartbeat.json)へ毎回上書きするため、run report と違って
    周期ごとにファイルが増えることはなく、retention対象に含める必要も無い。
    将来、既存の monitoring_healthcheck 系や新規チェックが
    「generated_at からの経過時間」を読めば、収集器自体の死活監視に使える
    (このStepではその監視側の実装まではしない — 読める形でファイルを
    残すところまでが担当範囲)。
    """
    path = os.path.join(bundle_dir, "_heartbeat.json")
    tmp = path + ".tmp"
    os.makedirs(bundle_dir, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def _remove_if_older_than(path, cutoff, is_dir):
    try:
        mtime = os.stat(path).st_mtime
    except OSError:
        return
    if mtime >= cutoff:
        return
    if is_dir:
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            os.remove(path)
        except OSError:
            pass


def apply_retention(cfg):
    """R7(保持世代の削除)。retention_days より古いものを3箇所から削除する
    (2026-07-27 独立レビューSuggestion #7で _rejected/_runs の漏れを指摘され追加):
      1. bundle_dir 直下の semaphore-*/spool-* ディレクトリ(証拠バンドル本体)
      2. bundle_dir/_runs/ 配下の run report ファイル
      3. spool_dir/_rejected/ 配下のスキーマ不正spool退避ファイル
    安全のため、対象は上記3箇所の命名規則に合致するものだけとし、
    _spool/ 本体・_heartbeat.json(毎周期上書きする単一ファイルで、
    それ自体はサイズが増えないためretention対象に含める必要が無い)には
    一切触れない。
    """
    bundle_dir = cfg["bundle_dir"]
    retention_days = cfg["retention_days"]
    cutoff = time.time() - retention_days * 86400

    if os.path.isdir(bundle_dir):
        for name in os.listdir(bundle_dir):
            if not (name.startswith("semaphore-") or name.startswith("spool-")):
                continue
            path = os.path.join(bundle_dir, name)
            if os.path.isdir(path):
                _remove_if_older_than(path, cutoff, is_dir=True)

    runs_dir = os.path.join(bundle_dir, "_runs")
    if os.path.isdir(runs_dir):
        for name in os.listdir(runs_dir):
            path = os.path.join(runs_dir, name)
            if os.path.isfile(path):
                _remove_if_older_than(path, cutoff, is_dir=False)

    rejected_dir = os.path.join(cfg["spool_dir"], "_rejected")
    if os.path.isdir(rejected_dir):
        for name in os.listdir(rejected_dir):
            path = os.path.join(rejected_dir, name)
            if os.path.isfile(path):
                _remove_if_older_than(path, cutoff, is_dir=False)


# ---------------------------------------------------------------------------
# Semaphore失敗ジョブからのバンドル組み立て(AC2)
# ---------------------------------------------------------------------------
def build_semaphore_bundle(cfg, row):
    """recent-failedの1行から、task-time/task-errors/task-hosts/task-outputで
    肉付けした証拠バンドル要約を作る。個々のクエリが失敗しても取れた分だけで
    バンドルを作る(空のバンドルを黙って作らないの逆 — 部分的にでも作る)。
    戻り値: (summary_dict, raw_logs_dict)。summary_dict["collection_errors"]は
    このバンドル固有のエラーのみを持つ(グローバルなcollection_errorsとは別)。
    """
    bundle_errors = []
    raw_logs = {}

    rc, out, err = run_semaphore_query(
        cfg["semaphore_query_bin"], cfg["semaphore_query_timeout_s"], "task-time", str(row["id"])
    )
    task = None
    if rc != 0:
        bundle_errors.append({"what": f"task-time {row['id']} failed", "why": f"rc={rc} stderr={err.strip()!r}"})
    else:
        try:
            task = parse_task_time(out)
        except ValueError as e:
            bundle_errors.append({"what": f"task-time {row['id']} parse failed", "why": str(e)})

    semaphore_meta = {
        "task_id": row["id"],
        "template": row.get("template"),
        "playbook": row.get("playbook"),
        "status": row.get("status"),
        "start": None,
        "end": None,
        "start_raw": row.get("start_raw"),
        "end_raw": None,
    }
    if task is not None:
        semaphore_meta.update(
            template=task["template"],
            playbook=task["playbook"],
            status=task["status"],
            start_raw=task["start_raw"],
            end_raw=task["end_raw"],
        )
        try:
            semaphore_meta["start"] = to_rfc3339_jst(parse_semaphore_time(task["start_raw"]))
        except ValueError as e:
            bundle_errors.append({"what": f"task {row['id']} start timestamp unparseable", "why": str(e)})
        try:
            if task["end_raw"]:
                semaphore_meta["end"] = to_rfc3339_jst(parse_semaphore_time(task["end_raw"]))
        except ValueError as e:
            bundle_errors.append({"what": f"task {row['id']} end timestamp unparseable", "why": str(e)})

    # task-errors / task-hosts: スキーマ(列数・列名)は入力契約に含まれないため
    # 構造化パースをせず、生テキストのままログとして残す(R2の「生ログ全文」の
    # 精神を安全側で満たす)。
    for query_name, log_name in (("task-errors", "semaphore-errors.log"), ("task-hosts", "semaphore-hosts.log")):
        rc, out, err = run_semaphore_query(
            cfg["semaphore_query_bin"], cfg["semaphore_query_timeout_s"], query_name, str(row["id"])
        )
        if rc != 0:
            bundle_errors.append({"what": f"{query_name} {row['id']} failed", "why": f"rc={rc} stderr={err.strip()!r}"})
        elif out.strip():
            raw_logs[log_name] = out

    rc, out, err = run_semaphore_query(
        cfg["semaphore_query_bin"], cfg["semaphore_query_timeout_s"], "task-output", str(row["id"])
    )
    if rc != 0:
        bundle_errors.append({"what": f"task-output {row['id']} failed", "why": f"rc={rc} stderr={err.strip()!r}"})
    elif out.strip():
        raw_logs["semaphore-log.log"] = out
    else:
        bundle_errors.append(
            {"what": f"task-output {row['id']} returned no rows", "why": "task__output has zero rows for this task id"}
        )

    summary = {
        "bundle_id": f"semaphore-{row['id']}",
        "source": "semaphore",
        "semaphore": semaphore_meta,
        "spool_records": [],
        "snapshot": {"base": None, "host": None},
        "collection_errors": bundle_errors,
    }
    return summary, raw_logs


def correlate_time_window(entries, start_dt, end_dt, tolerance_s):
    """valid_spoolのうち未使用(entry['used'] is False)で、written_atが
    [start_dt-tolerance, end_dt(またはstart_dt)+tolerance] に収まるものを返す。
    マッチしたentryは呼び出し側でentry['used']=Trueにすること。"""
    if start_dt is None:
        return []
    lo = start_dt - timedelta(seconds=tolerance_s)
    hi = (end_dt or start_dt) + timedelta(seconds=tolerance_s)
    matched = []
    for entry in entries:
        if entry["used"]:
            continue
        wa = datetime.fromisoformat(entry["record"]["written_at"])
        if lo <= wa <= hi:
            matched.append(entry)
    return matched


def spool_bundle_id(rec):
    try:
        epoch = int(datetime.fromisoformat(rec["written_at"]).timestamp())
    except ValueError:
        epoch = int(time.time())
    return f"spool-{epoch}-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# journal可読性(AC1〜AC4, AC7。設計の全文はモジュールdocstring
# 「exit 2 の journal可読性」節を参照。ここでは実装のみ)
# ---------------------------------------------------------------------------
JOURNAL_SUMMARY_MAX_ITEMS = 10  # AC3: 全件出さず切り詰める
JOURNAL_SUMMARY_WHAT_MAX_CHARS = 200  # AC7: 1件あたりの表示長を防御的に制限する

# B2是正: WHAT_PREFIX_* のいずれかで始まる "what" は、非信頼データ(IC-016)を
# 末尾に連結して組み立てられている。journalへ出すのはこの固定prefix(この
# ファイル自身が書いた文言であり非信頼値を含まない)だけとし、連結された
# 非信頼な値そのものは出さない。表示専用の変換であり、_runs/・バンドル本体に
# 書かれる "what"(prefix+非信頼値の元の文字列)には一切手を触れない。
_UNTRUSTED_WHAT_REDACTIONS = (
    (WHAT_PREFIX_REJECT_MOVE_FAILED, "failed to move a malformed spool record (filename omitted — untrusted, IC-016)"),
    (WHAT_PREFIX_REJECT_MALFORMED, "malformed spool record (filename omitted — untrusted, IC-016)"),
    (WHAT_PREFIX_CONSUME_REMOVE_FAILED, "failed to remove a consumed spool record (filename omitted — untrusted, IC-016)"),
    (WHAT_PREFIX_NO_INVESTIGATE_OPS, "no named investigate operations available for a spool-correlated host (host name omitted — untrusted, IC-016)"),
    (WHAT_PREFIX_NO_CORRELATED_JOB, "no correlated Semaphore job found for a spool record (play name omitted — untrusted, IC-016)"),
)


def _redact_untrusted_what(what):
    """what が既知の非信頼値連結パターン(_UNTRUSTED_WHAT_REDACTIONS)のいずれかに
    一致すれば、固定の要約文へ置き換える(B2是正)。一致しなければ(=このファイル
    自身が生成した固定文言、またはSemaphore由来の数値/既知の内部語彙のみで
    非信頼な自由記述を連結しないもの)そのまま返す。"""
    for prefix, redacted in _UNTRUSTED_WHAT_REDACTIONS:
        if what.startswith(prefix):
            return redacted
    return what


def _truncate_for_journal(value, max_chars):
    """journalの1エントリを1物理行に収めるため、まず改行相当文字(LF/CR/CRLF等、
    str.splitlines()が認識するもの全て)を空白へ正規化してから文字数で切り詰める
    (B1是正、2026-09-02)。正規化を先に行わないと JOURNAL_SUMMARY_WHAT_MAX_CHARS
    は文字数の上限にしかならず、埋め込み改行がそのまま物理journal行数を
    増やしてしまう(2026-09-01 loki-errors案件と同じ欠陥クラス。是正も同じ
    " ".join(value.splitlines()) を使う)。"""
    s = " ".join(str(value).splitlines())
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1] + "…"


def _journal_write(line):
    """stderrへ1行書く。先頭に syslog priority prefix `<4>`(warning)を付ける
    (B3是正、2026-09-02)。

    unitは StandardOutput=/StandardError= を指定していないため既定
    (journal、SyslogLevelPrefix=yes 既定)に従う。prefix無しの行は既定の
    SyslogLevel(info)で journal入りし、monnie側のrsyslogルール
    (roles/alloy/templates/observability-sources.rsyslog.j2、
    `$syslogseverity == 4` だけが "warning" ラベルになる)を通ると
    severity 6(info)のまま扱われる。grafana_provisioningの
    `infra-syslog-all-nodes.json` はデフォルトで `level` 変数が
    `["warning","error"]` のため、prefix無しの要約は既定フィルタで隠れ、
    この案件が防ごうとした「失敗行しか見えない」状況がそのまま残ってしまう
    (Claude Reviewer B3)。`<4>` は個々の行のpriorityを明示的に
    warning(4)へ固定し、rsyslogの `$syslogseverity == 4` 条件と正確に一致する。

    既存の EXIT_INTERNAL_ERROR の1行(`__main__` の except節)は今回
    `<4>` を付けない —意図的にscope外とする(Coordinator指示、2026-09-02)。
    unit全体へ `SyslogLevel=warning` を設定する案は採らなかった —
    prefix無しの全行(EXIT_INTERNAL_ERRORを含む)の既定severityを変えてしまい、
    今回touchしないと決めた経路の挙動まで変えるため。
    """
    sys.stderr.write(f"<4>{line}\n")


def log_collection_errors_to_journal(run_level_errors, pending_bundles):
    """collection_errors を伴って終了する周期に、journal(stderr)へ人が読める
    要約を書く。AC1(要約を出す)/AC2(each "what" + 件数)/AC3(上限+明示切り詰め、
    かつ物理行数ベースで上限を守る)/AC4(空なら何も書かない)/AC7("why"は出さず、
    非信頼値を含む"what"は固定カテゴリへ置換し、残りも防御的に切り詰める)。

    表示のみを行い、run_level_errors・pending_bundles の中身は変更しない
    (_runs/ とバンドル本体への記録は現状のまま — requirement §5の制約)。

    ヘッダの内訳(run N / bundles M)は、`_runs/<run_id>.json` の
    `collection_errors` が run-levelの分(N件)しか持たないことを、
    突合する人が誤読しないよう明示する(2026-09-02 Claude Reviewer Suggestion#6)。
    """
    run_items = [("run", e.get("what", "")) for e in run_level_errors]
    bundle_items = [
        (summary["bundle_id"], e.get("what", ""))
        for summary, _raw_logs, _host in pending_bundles
        for e in (summary.get("collection_errors") or [])
    ]
    items = run_items + bundle_items

    if not items:
        return  # AC4: has_errorsがFalseの周期はここへ来ない設計だが、念のため

    _journal_write(
        f"incident-capture-collector: exiting with {len(items)} collection_errors this cycle "
        f"(run: {len(run_items)}, bundles: {len(bundle_items)}; "
        f"_runs/<run_id>.json only records the 'run' ones):"
    )
    shown = items[:JOURNAL_SUMMARY_MAX_ITEMS]
    for i, (source, what) in enumerate(shown, start=1):
        safe_what = _truncate_for_journal(_redact_untrusted_what(what), JOURNAL_SUMMARY_WHAT_MAX_CHARS)
        _journal_write(f"  [{i}] ({source}) {safe_what}")
    omitted = len(items) - len(shown)
    if omitted > 0:
        _journal_write(
            f"  ... {omitted} more collection_errors omitted "
            "(see _runs/ or the bundle summary.json on quory for full detail)"
        )


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("INCIDENT_CAPTURE_CONFIG", CONFIG_PATH_DEFAULT)
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    collection_errors = []  # この周期全体に属する(特定バンドルに紐付かない)エラー
    pending_bundles = []  # [(summary_dict, raw_logs_dict, host_for_snapshot_or_None)]

    state = load_state(cfg["state_dir"])
    last_failed_task_id = int(state.get("last_failed_task_id", 0))

    # --- 1. spoolを読む(消費前に総数を確定させる。R5bはこの"読んだ時点の総数"で判定する) ---
    spool_paths = list_spool_files(cfg["spool_dir"])
    spool_total_this_cycle = len(spool_paths)
    valid_spool = []  # [{"path":..., "record":..., "used": False}]
    for path in spool_paths:
        try:
            rec = load_spool_record(path)
        except ValueError as e:
            reject_spool_file(cfg["spool_dir"], path, str(e), collection_errors)
            continue
        valid_spool.append({"path": path, "record": rec, "used": False})

    # --- 2. Semaphoreの新規失敗ジョブ ---
    semaphore_query_ok = True
    rc, out, err = run_semaphore_query(
        cfg["semaphore_query_bin"], cfg["semaphore_query_timeout_s"], "recent-failed", str(cfg["recent_failed_batch"])
    )
    new_failed_rows = []
    if rc != 0:
        semaphore_query_ok = False
        collection_errors.append({"what": "recent-failed query failed", "why": f"rc={rc} stderr={err.strip()!r}"})
    else:
        rows, parse_errors = parse_recent_failed(out)
        for pe in parse_errors:
            collection_errors.append({"what": "recent-failed row unparseable", "why": pe})
        new_failed_rows = [r for r in rows if r["id"] > last_failed_task_id]
        if len(rows) >= cfg["recent_failed_batch"] and new_failed_rows:
            collection_errors.append(
                {
                    "what": "recent-failed batch limit reached",
                    "why": (
                        f"recent-failed returned the full batch of {cfg['recent_failed_batch']} rows; "
                        "some failed jobs older than the returned window may have been skipped "
                        "(recent-failed has no id-based pagination, and this collector does not add "
                        "new queries to homelab-semaphore-query — ADR-003 (c); 2026-08-19: "
                        "the tool moved from direct SQL to a REST API call, but the "
                        "\"don't add new named operations\" constraint is unchanged)"
                    ),
                }
            )

    # --- R5b: Semaphoreは失敗ジョブを記録しているのにspoolが完全に空 ---
    if new_failed_rows and spool_total_this_cycle == 0:
        collection_errors.append(
            {
                "what": "capture pipeline appears silent (R5b)",
                "why": (
                    f"Semaphore recorded {len(new_failed_rows)} new failed job(s) since "
                    f"task id {last_failed_task_id}, but {cfg['spool_dir']} contained zero "
                    "spool records this cycle. roles/common_slack/tasks/capture.yml (T1) may "
                    "be broken (e.g. a YAML syntax error, which the include-wrapping "
                    "block/rescue in notify.yml cannot catch)."
                ),
            }
        )

    # --- 3. Semaphore失敗ジョブごとにバンドルを作り、時間窓で相関するspoolを添付する ---
    for row in new_failed_rows:
        summary, raw_logs = build_semaphore_bundle(cfg, row)
        start_dt = end_dt = None
        if summary["semaphore"]["start"]:
            start_dt = datetime.fromisoformat(summary["semaphore"]["start"])
        if summary["semaphore"]["end"]:
            end_dt = datetime.fromisoformat(summary["semaphore"]["end"])

        matched = correlate_time_window(valid_spool, start_dt, end_dt, cfg["spool_correlation_tolerance_s"])
        for entry in matched:
            entry["used"] = True
        matched_recs = [e["record"] for e in matched]
        summary["spool_records"] = matched_recs
        # 既知の限界(2026-07-27 独立レビューSuggestion #8、意図的に直さない):
        # 同一ジョブに複数ホストからのspoolレコードが相関した場合、追加の
        # ホスト別スナップショットは最初にマッチしたレコードのホストにしか
        # 取らない。matched_recs には全レコードが残るため情報自体は失われない
        # (summary["spool_records"]で全件参照できる)。低頻度・低影響と判断し、
        # 全ホスト分のスナップショットを取る変更は見送る(1ジョブあたりの
        # SSH呼び出し数が相関ホスト数に比例して増える設計変更になるため)。
        host_for_ops = matched_recs[0]["play_host"] if matched_recs else None
        if matched_recs:
            summary["source"] = "semaphore+spool"
        else:
            summary["collection_errors"].append(
                {
                    "what": "no per-host investigate snapshot taken for this Semaphore-only bundle",
                    "why": (
                        "no spool record correlated to this job within the configured time "
                        f"tolerance ({cfg['spool_correlation_tolerance_s']}s), so no play_host is "
                        "known. task-hosts is intentionally not structurally parsed (its column "
                        "layout is not part of the input contract — see module docstring), so only "
                        "the base pve1/pve2 snapshot was taken for this bundle."
                    ),
                }
            )
        pending_bundles.append((summary, raw_logs, host_for_ops))

    # --- 4. 相関しなかったspoolのうち"notable"なものは単独バンドルにする ---
    for entry in valid_spool:
        if entry["used"]:
            continue
        rec = entry["record"]
        if rec.get("slack_status") in NON_NOTABLE_SLACK_STATUS:
            continue
        entry["used"] = True
        bundle_id = spool_bundle_id(rec)
        summary = {
            "bundle_id": bundle_id,
            "source": "spool",
            "semaphore": None,
            "spool_records": [rec],
            "snapshot": {"base": None, "host": None},
            "collection_errors": [
                {
                    "what": f"{WHAT_PREFIX_NO_CORRELATED_JOB}{rec.get('play_name')!r})",
                    "why": (
                        "this spool record's slack_status is notable but no Semaphore "
                        "failed-job row correlated within the configured time tolerance "
                        f"({cfg['spool_correlation_tolerance_s']}s); the collector does not walk "
                        "Semaphore task ids beyond recent-failed to avoid adding new query "
                        "capability (ADR-003 (c))"
                    ),
                }
            ],
        }
        pending_bundles.append((summary, {}, rec["play_host"]))

    bundles_created = [s["bundle_id"] for s, _r, _h in pending_bundles]

    # --- 5. スナップショットは新規イベントがある周期だけ取る(ADR-003 補)。
    #        SSHは0本 or pending_bundlesがある周期だけ。 ---
    if pending_bundles:
        base_snapshot = collect_base_snapshot(cfg)
        host_cache = {}  # host -> (results_or_None, no_ops_error_or_None)
        for summary, _raw_logs, host_for_ops in pending_bundles:
            summary["snapshot"]["base"] = base_snapshot
            # 配備欠陥(wrapperバイナリ不在)とSSH到達不能を区別して記録する
            # (2026-07-27 独立レビューSuggestion #5)。base_snapshot は複数
            # バンドルで共有するため、参照する全バンドルへ個別に積む
            # (キャッシュ経由でも、ホストを共有する全バンドルへ毎回反映する)。
            append_missing_binary_errors(base_snapshot, summary["collection_errors"])
            if host_for_ops:
                if host_for_ops not in host_cache:
                    host_cache[host_for_ops] = collect_host_snapshot(cfg, host_for_ops)
                results, no_ops_error = host_cache[host_for_ops]
                if no_ops_error is not None:
                    summary["collection_errors"].append(no_ops_error)
                else:
                    summary["snapshot"]["host"] = {"name": host_for_ops, "results": results}
                    append_missing_binary_errors(results, summary["collection_errors"])

    # --- 6. 書き出し ---
    for summary, raw_logs, _host in pending_bundles:
        summary["generated_at"] = now_jst_str()
        summary["bundle_version"] = 1
        write_bundle(cfg["bundle_dir"], summary["bundle_id"], summary, raw_logs)

    # --- 7. spoolを消費する(バンドル化された/されなかったに関わらず、
    #        validと判定されたものは全て内容をどこかに複製済みか、単なる'ok'
    #        通過なので削除してよい)。 ---
    for entry in valid_spool:
        consume_spool_file(entry["path"], collection_errors)

    # --- 8. 保持世代の削除(R7。バンドル本体・_runs/・_spool/_rejected/ の3箇所) ---
    apply_retention(cfg)

    # --- 9. state更新 ---
    if new_failed_rows:
        state["last_failed_task_id"] = max(last_failed_task_id, max(r["id"] for r in new_failed_rows))
        save_state(cfg["state_dir"], state)

    # --- 10. 終了コード確定 ---
    any_bundle_errors = any(s.get("collection_errors") for s, _r, _h in pending_bundles)
    has_errors = bool(collection_errors) or any_bundle_errors or not semaphore_query_ok
    exit_code = EXIT_COLLECTION_ERRORS if has_errors else EXIT_OK

    # --- 11. run report(エラーがある周期のみ。詳細な collection_errors 一覧) ---
    if has_errors:
        write_run_report(
            cfg["bundle_dir"],
            f"run-{int(time.time())}",
            {
                "generated_at": now_jst_str(),
                "bundles_created": bundles_created,
                "collection_errors": collection_errors,
                "exit_code": exit_code,
            },
        )

    # --- 12. ハートビート(正常時も含め毎周期、固定ファイルへ無条件で上書き)。
    #         2026-07-27 独立レビューSuggestion #3: run reportだけでは
    #         「収集器プロセス自体が動いているか」を正常時に確認する手段が
    #         無かったための追加。詳細は write_heartbeat のdocstring。 ---
    write_heartbeat(
        cfg["bundle_dir"],
        {
            "generated_at": now_jst_str(),
            "spool_total_this_cycle": spool_total_this_cycle,
            "new_failed_job_count": len(new_failed_rows),
            "bundles_created": len(bundles_created),
            "has_errors": has_errors,
            "exit_code": exit_code,
        },
    )

    # --- 13. journal要約(AC1〜AC4, AC7)。_runs/ と同じ has_errors 条件を使う
    #         — 判定を二重に持たない。_runs/・バンドル本体は変更しない。
    #         heartbeat(12)より後に置く(2026-09-02 Claude Reviewer Minor#3) —
    #         この関数が例外を送出した場合でも heartbeat は既に書き終えている
    #         ようにするため(先に置くと、万一の例外で `except Exception` に
    #         捕まりheartbeatが書かれず、exit 2 が exit 3 に化けてしまう)。 ---
    if has_errors:
        log_collection_errors_to_journal(collection_errors, pending_bundles)

    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 - deliberate broad catch, see module docstring
        sys.stderr.write(f"incident-capture-collector: unexpected internal error: {e}\n")
        sys.exit(EXIT_INTERNAL_ERROR)
