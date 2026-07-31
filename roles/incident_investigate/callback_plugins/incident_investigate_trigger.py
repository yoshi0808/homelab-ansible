"""incident_investigate_trigger — failure-detection callback plugin.

設計の正本: docs/ai/adr/009-per-incident-investigation-runtime.md (a) a-4。
Policy: docs/ai/policies/incident_capture_policy.md IC-034/IC-037/IC-038。

**現在無効化されている(2026-07-31、方針C、暫定)**: `ansible.cfg` から
`callback_plugins` / `callbacks_enabled` の2行を外したため、このファイルは
配備されていても読み込まれない。原因は、本番のSemaphore実行で
`SEMAPHORE_TASK_DETAILS_*` 環境変数がansible-playbookプロセスへ渡っておらず、
下記 `_maybe_enqueue` が常に早期returnしていたこと(一次記録:
docs/ai/memory/incidents/2026-07-31_incident-investigate-callback-did-not-
enqueue.md)。起動契機は「証拠バンドル(`reports/incidents/semaphore-<id>/
summary.json`)の出現を走査で拾う」方式へ切り替えた
(`roles/incident_investigate/files/incident-investigate.py` を参照)。

**戻し方(この記述がこの機構全体で唯一の場所 — 二重に書かない、T9)**:
`ansible.cfg` の `[defaults]` セクションへ次の2行を追加する。

```
callback_plugins = roles/incident_investigate/callback_plugins
callbacks_enabled = incident_investigate_trigger
```

このファイル自体はその間も変更不要(削除されていないため)。ただし、
`roles/incident_investigate/tasks/main.yml` がキューディレクトリ
(下記 `QUEUE_DIR`)を作らなくなっている(T8)ため、callback経路へ戻す場合は
そちらの作成も合わせて復元する必要がある。戻す判断そのものと、判断に
必要な経緯(なぜCへ切り替えたか)は
`docs/ai/memory/incidents/2026-07-31_incident-investigate-callback-did-not-
enqueue.md`「対応の選択肢と決定」を参照する(ここへは複製しない)。

やること・やらないこと(この1ファイルの不変条件。変更するときは必ず両方を
自己検証すること — 検証手順は
docs/ai/reviews/incident_auto_investigation/2026-07-31_005_u2_implement.md):

  - Semaphoreが実行したplaybookが失敗(タスク失敗/unreachable)で終わった
    ときだけ、キューディレクトリへ1ファイル書く。成功時は何もしない。
  - 判断はローカルファイルの存在確認と環境変数の読み取りのみで完結する。
    LLM呼び出し・ネットワークI/O・ファイル内容の解釈は一切行わない(R2)。
  - キューディレクトリが存在しない環境(ansy等、この機構を配備していない
    ホスト)では、ディレクトリの有無を見た時点で即座に何もせず戻る。
    ディレクトリ自体をこのファイルが作ることは絶対にしない — 存在することが
    「配備済み」の合図であり、その合図をこちら側で作ってしまうと合図の意味が
    なくなる。
  - 例外は最上位(v2_playbook_on_stats自身)で必ず捕捉し、被観測playへ
    一切伝播させない(IC-037: IC-010を起動契機へ適用したもの)。

  - Semaphore以外(systemd timer、recovery-probeが起動するラダーplaybook等)
    からの実行は対象外(requirement.md §3 非ゴール)。判定は環境変数
    `SEMAPHORE_TASK_DETAILS_*` の有無で行う — Semaphore以外の起動経路では
    この接頭辞の環境変数は存在しない(v2.18.4のソースで確認済み、
    2026-07-31_002_u0_test_result.md M3)。

自己検証で確認した事実(ansible-core 2.20.1、2026-07-31):
  callback dispatch自体もansible-core側で例外を捕捉し `[WARNING]:
  Callback dispatch '...' failed for plugin '...'` を出すだけで
  ansible-playbookのexit codeやPLAY RECAPには影響しないことを実測した
  (scratch環境、crashyという名の意図的に例外を送出するcallbackで確認)。
  この自己防御(下記の広いtry/except)は、その挙動に依存せず単独でも
  安全であるための多重防御であり、ansible-core側の挙動を前提にはしない。
"""
import json
import os
import time
import traceback
import uuid
from datetime import datetime, timedelta, timezone

from ansible.plugins.callback import CallbackBase

DOCUMENTATION = r"""
    name: incident_investigate_trigger
    type: notification
    short_description: Enqueue a primary-investigation request when a Semaphore-run play fails
    description:
      - See module docstring. Writes nothing when disabled (queue dir absent),
        when the run was not launched by Semaphore, or when the play succeeded.
    version_added: "1.0"
"""

# 配備済みかどうかの唯一の合図(a-4)。**2026-07-31(T8)以降、
# roles/incident_investigate はこのディレクトリを作らない** — したがって
# 現行の配備状態ではこのパスは存在せず、下の `_maybe_enqueue` は
# `os.path.isdir(QUEUE_DIR)` の時点で常にno-opになる(ansible.cfgでの
# 無効化と合わせた二重の無効化。上のdocstring「戻し方」参照)。
# callback経路へ戻す場合、このパスは roles/incident_investigate/tasks/
# main.yml が作っていたディレクトリ(yoshi:yoshi 0750)と文字どおり
# 一致させる必要がある(incident_sync_outer_lock_path と同型の注意 —
# 片方だけ変更すると無言で機構全体が動かなくなる)。callback pluginは
# Ansible変数を参照できない(ロード時点でplaybook変数のスコープが無い)ため、
# リテラルで持たざるを得ない。
QUEUE_DIR = "/var/lib/homelab-recovery/incident-investigate/queue"

JST = timezone(timedelta(hours=9))


def _now_rfc3339_jst():
    return datetime.now(JST).isoformat(timespec="seconds")


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "notification"
    CALLBACK_NAME = "incident_investigate_trigger"
    # 2026-07-31差し戻し(独立レビュー Critical #1)で訂正: 当初「明示しない
    # = True相当」と書いていたが誤りだった。ansible-core
    # (executor/task_queue_manager.py)は
    # `getattr(plugin, 'CALLBACK_NEEDS_ENABLED', getattr(plugin,
    # 'CALLBACK_NEEDS_WHITELIST', False))` でこの属性を見ており、
    # `CallbackBase` 自体はこの属性を持たない。つまり**明示しなければ
    # `False`(=有効化不要=常に動く)** であり、`callbacks_enabled` から
    # 名前を外しても発火し続ける — 実測で確認済み(このリポジトリの
    # ansible.cfgから callbacks_enabled 行そのものを削除した状態でも
    # キューファイルが生成されることを確認した)。
    # `ansible.cfg` の `callbacks_enabled` を唯一のon/offスイッチにするには
    # 明示的に `True` を書く必要がある。
    CALLBACK_NEEDS_ENABLED = True

    def __init__(self):
        super().__init__()
        self._playbook_file = None

    def v2_playbook_on_start(self, playbook):
        # 例外を出しても実害は無い箇所だが(このメソッドもdispatch経由で保護
        # されるが)、ここでも自前で守る。playbookファイル名が取れなくても
        # 致命的ではない(後段でNoneのまま扱う)。
        try:
            self._playbook_file = getattr(playbook, "_file_name", None)
        except Exception:
            self._playbook_file = None

    def v2_playbook_on_stats(self, stats):
        # 不変条件: このメソッドが例外を外へ投げることは絶対にない。
        # 何を試みたかは分からなくてよい(検出は失われても被観測playより
        # 重要ではない — IC-037)が、被観測playを道連れにしてはならない。
        try:
            self._maybe_enqueue(stats)
        except Exception:
            try:
                self._display.warning(
                    "incident_investigate_trigger: internal error (ignored): "
                    + traceback.format_exc()
                )
            except Exception:
                pass  # 通知すら失敗しても、ここで止めない

    def _maybe_enqueue(self, stats):
        # R2: ネットワークI/Oなし。ここまでの処理はすべてローカルの
        # os.path/os.environ 参照のみ。
        if not os.path.isdir(QUEUE_DIR):
            return  # 未配備環境(ansy等)。ディレクトリはこちらで作らない。

        semaphore_env = {
            k: v for k, v in os.environ.items() if k.startswith("SEMAPHORE_TASK_DETAILS_")
        }
        if not semaphore_env:
            return  # Semaphore以外の起動経路(非ゴール)。

        # 失敗判定: ansible-playbook自身の終了コード算出と同じ定義を使う
        # (failures または dark が1件でもあれば失敗。rescued/ignoredは含めない
        # — 含めるとrescueで回復した/意図的に無視した項目まで誤って調査対象に
        # してしまう)。
        failed_hosts = sorted(h for h, n in stats.failures.items() if n)
        dark_hosts = sorted(h for h, n in stats.dark.items() if n)
        if not failed_hosts and not dark_hosts:
            return  # 成功時は何もしない。

        task_id_raw = semaphore_env.get("SEMAPHORE_TASK_DETAILS_ID")
        task_id = None
        if task_id_raw is not None:
            try:
                task_id = int(task_id_raw)
            except (TypeError, ValueError):
                task_id = None

        record = {
            "schema_version": 1,
            "semaphore_task_id": task_id,
            "semaphore_task_id_raw": task_id_raw,
            "playbook": self._playbook_file,
            "detected_at": _now_rfc3339_jst(),
            "failed_hosts": failed_hosts,
            "dark_hosts": dark_hosts,
        }

        if task_id is not None:
            name = f"semaphore-{task_id}"
        else:
            # SEMAPHORE_TASK_DETAILS_* はあるがIDだけ欠けている異常系
            # (f-2フォールバック対象、ADR-009 (f) f-3)。衝突しないよう
            # pid+uuidを付ける。
            name = f"unresolved-{int(time.time())}-{os.getpid()}-{uuid.uuid4().hex[:8]}"

        path = os.path.join(QUEUE_DIR, f"{name}.json")
        tmp = f"{path}.tmp-{os.getpid()}"
        # 同一ジョブの多重書きは同じファイル名への上書きになり増殖しない
        # (IC-039のキュー側での担保。最終的な二重排除は投資調査側が既存成果物
        # の有無で行う — incident-investigate.py 参照)。
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(record, f)
        os.replace(tmp, path)
