#!/usr/bin/env python3
"""recovery-probe — quory 常駐の pull 検知 daemon (autonomous_recovery E-1)

設計: docs/ai/reviews/autonomous_recovery/2026-07-02_001_requirement.md

- 60 秒間隔 × 5 回連続失敗で発火(閾値は設定ファイル)
- mute 中は判定前に skip + 連続失敗カウンタをリセット(第一防御)
- sophos-fw: ISP 切り分け → pvesh 確証 → 決定論ラダー(reboot → failover)。
  LLM(Codex)はインターネット断で使えないため経由しない
- authy / monnie: E-1 では検知 → 通知のみ(ラダー自動起動は E-2)
- 通知はキューに積み、外部到達性が回復したら flush する
- drill: state_dir/drill/<target> ファイルが存在すると強制的に障害扱いとし、
  ラダーは -e tester_mode=true で実行(実変更ゼロのエンドツーエンド試験)

実行モード:
  recovery-probe.py            # daemon(systemd から起動)
  recovery-probe.py --once     # 1 サイクルだけ probe して結果を表示(アクションなし)
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

CONFIG_PATH = os.environ.get(
    "RECOVERY_PROBE_CONFIG", "/etc/homelab-recovery/recovery-probe.json"
)


def log(msg):
    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"{ts} {msg}", flush=True)


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# mute (roles/recovery_mute と同一ファイル形式)
# ---------------------------------------------------------------------------
def mute_remaining(cfg, target):
    """mute 中なら残り秒数(>0)、そうでなければ 0 を返す。"""
    path = os.path.join(cfg["mute_dir"], f"{target}.json")
    try:
        with open(path) as f:
            data = json.load(f)
        until = datetime.fromisoformat(data.get("until", ""))
        remaining = until.timestamp() - time.time()
        return max(0, int(remaining))
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return 0


# ---------------------------------------------------------------------------
# probes (すべて read-only)
# ---------------------------------------------------------------------------
def probe_icmp(host):
    r = subprocess.run(
        ["ping", "-c", "1", "-W", "2", host],
        capture_output=True,
    )
    return r.returncode == 0


def probe_dns(server, name):
    r = subprocess.run(
        ["dig", "+time=2", "+tries=1", f"@{server}", name],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0 and "status: NOERROR" in r.stdout


def probe_tcp(host, port):
    try:
        with socket.create_connection((host, int(port)), timeout=3):
            return True
    except OSError:
        return False


def probe_target(cfg, target, tconf):
    """全 probe 成功なら True。失敗した probe 名のリストも返す。"""
    host = tconf.get("host", target)
    failed = []
    for p in tconf["probes"]:
        if p == "icmp":
            ok = probe_icmp(host)
        elif p == "dns":
            ok = probe_dns(host, tconf.get("dns_check_name", "quory.internal"))
        elif p.startswith("tcp:"):
            ok = probe_tcp(host, p.split(":", 1)[1])
        else:
            log(f"WARN unknown probe '{p}' for {target}")
            continue
        if not ok:
            failed.append(p)
    return (len(failed) == 0, failed)


def external_reachable(cfg):
    """外部到達性(ISP 切り分け・通知 flush 判定用)。DNS は sophos-fw 依存で
    よい: この関数を評価するのは LAN 側が健全な分岐と flush 時のみ。

    戻り値は `(到達可否, 失敗理由)`。失敗理由は成功時 None。

    例外を握り潰さない理由(2026-07-29): どの層(名前解決 / TCP / TLS /
    timeout)で失敗したかは例外の型と本文にしか現れず、捨てると後から
    切り分けられない。2026-07-29 06:07 JST の失敗は、この情報が無いため
    Loki 全ログを走査しても「未特定」で終わった。
    事後に icmp / dns / tcp の層別チェックを走らせる案は採らない —
    それは失敗の「後」に実行されるため、単発の揺らぎでは復旧後の健全な
    状態しか観測できず、原因を取り違える。失敗の瞬間に捕まえた例外が
    唯一の証拠である。
    """
    try:
        req = urllib.request.Request(cfg["external_check_url"], method="HEAD")
        with urllib.request.urlopen(req, timeout=5):
            return True, None
    except urllib.error.HTTPError:
        # HTTP 応答が返っている(403 等)= ネットワーク到達性はある
        return True, None
    except Exception as exc:
        # 文字列化自体を保護する。`str(exc)` が例外を送出する例外オブジェクト
        # は実在し、その場合ここが未捕捉のまま main() のループを突き破って
        # デーモンが無言で停止する(2026-07-29 Tester が実際に再現、AC5)。
        # urllib / socket / ssl の標準例外はいずれも正常な __str__ を持つため
        # 実運用で踏む確率は低いが、監視が消える方向の失敗なので塞ぐ。
        # 型名はクラス属性の参照だけで得られ、失敗しえない。
        try:
            return False, f"{type(exc).__name__}: {exc}"
        except Exception:
            return False, type(exc).__name__


# ---------------------------------------------------------------------------
# 通知キュー(外部到達性の回復後に flush)
# ---------------------------------------------------------------------------
def queue_notify(cfg, status, title, message):
    qdir = os.path.join(cfg["state_dir"], "notify-queue")
    os.makedirs(qdir, exist_ok=True)
    payload = {
        "nt_status": status,
        "nt_title": title,
        "nt_message": message,
        "nt_queued_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    path = os.path.join(qdir, f"{time.time_ns()}-{os.getpid()}.json")
    with open(path, "w") as f:
        json.dump(payload, f, ensure_ascii=False)
    log(f"NOTIFY queued: [{status}] {title}")


def flush_notify_queue(cfg, ext_ok):
    qdir = os.path.join(cfg["state_dir"], "notify-queue")
    if not os.path.isdir(qdir):
        return
    entries = sorted(os.listdir(qdir))
    if not entries:
        return
    if not ext_ok:
        return
    for name in entries:
        path = os.path.join(qdir, name)
        r = run_playbook(cfg, "recovery_probe_notify.yml", [f"@{path}"])
        if r.returncode == 0:
            os.unlink(path)
            log(f"NOTIFY sent: {name}")
        else:
            log(f"NOTIFY send failed rc={r.returncode}: {name} (retry next cycle)")
            break


# ---------------------------------------------------------------------------
# ラダー実行(決定論。§8.4: allowlist / lock / mute / flapping)
# ---------------------------------------------------------------------------
def run_playbook(cfg, playbook, extra_vars):
    cmd = ["ansible-playbook", f"playbooks/{playbook}"]
    for e in extra_vars:
        cmd += ["-e", e]
    log(f"RUN {' '.join(cmd)}")
    return subprocess.run(
        cmd, cwd=cfg["repo_dir"], capture_output=True, text=True, timeout=1800
    )


def flapping_count(cfg, target):
    """直近 24h のラダー発火回数を返し、今回分を記録する前の値を見る。"""
    path = os.path.join(cfg["state_dir"], f"firings-{target}.json")
    now = time.time()
    try:
        with open(path) as f:
            firings = [t for t in json.load(f) if now - t < 86400]
    except (FileNotFoundError, json.JSONDecodeError):
        firings = []
    return firings, path


def record_firing(path, firings):
    with open(path, "w") as f:
        json.dump(firings + [time.time()], f)


def pvesh_vm_status(cfg, target):
    """pve 経由で VM 状態を確証する(read-only)。
    返り値: (state, node, vmid)。state は
    'running' / 'stopped' / 'not-found' / 'pve-unreachable'"""
    r = subprocess.run(
        [
            "ansible", cfg["pve_host"], "--become", "-m", "ansible.builtin.command",
            "-a", "pvesh get /cluster/resources --output-format json",
        ],
        cwd=cfg["repo_dir"], capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        return ("pve-unreachable", None, None)
    try:
        raw = r.stdout.split(">>", 1)[1].strip()
        resources = json.loads(raw)
    except (IndexError, json.JSONDecodeError):
        return ("pve-unreachable", None, None)
    for res in resources:
        if res.get("type") == "qemu" and res.get("name") == target:
            return (
                res.get("status", "not-found"),
                res.get("node"),
                res.get("vmid"),
            )
    return ("not-found", None, None)


def pvesh_vm_start(cfg, node, vmid):
    """stopped VM の決定論 start(requirement: stopped → reboot ではなく start)。"""
    r = subprocess.run(
        [
            "ansible", cfg["pve_host"], "--become", "-m", "ansible.builtin.command",
            "-a", f"pvesh create /nodes/{node}/qemu/{vmid}/status/start",
        ],
        cwd=cfg["repo_dir"], capture_output=True, text=True, timeout=300,
    )
    return r.returncode == 0


def wait_for_recovery(cfg, target, tconf):
    deadline = time.time() + cfg["recovery_wait_s"]
    while time.time() < deadline:
        ok, _ = probe_target(cfg, target, tconf)
        if ok:
            return True
        time.sleep(30)
    return False


def fire_ladder(cfg, target, tconf, failed_probes, drill):
    """sophos-fw の決定論ラダー。drill 時は tester_mode=true で実行する。"""
    label = "[drill] " if drill else ""
    extra = [f"target={target}"] + (["tester_mode=true"] if drill else [])

    # --- §8.4: 実行中ロック ---
    lock_dir = os.path.join(cfg["state_dir"], "ladder.lock")
    try:
        os.mkdir(lock_dir)
    except FileExistsError:
        log(f"LADDER skip: lock held ({lock_dir})")
        return
    try:
        # --- §8.4: flapping (直近 24h 3 回以上 → エスカレーションのみ) ---
        firings, fpath = flapping_count(cfg, target)
        if len(firings) >= 3:
            queue_notify(
                cfg, "error",
                f"{label}[recovery-probe] flapping エスカレーション - {target}",
                f"直近 24 時間で 3 回以上ラダーが発火したため自動復旧を停止しました。"
                f"手動確認が必要です。failed probes: {failed_probes}",
            )
            return
        record_firing(fpath, firings)

        # --- pvesh 確証 ---
        vm_status, vm_node, vm_id = pvesh_vm_status(cfg, target)
        log(f"LADDER {target}: pvesh status = {vm_status}")
        if vm_status == "pve-unreachable":
            queue_notify(
                cfg, "critical",
                f"{label}[recovery-probe] pve 到達不能 - {target}",
                "probe は失敗していますが pve クラスタにも到達できません。"
                "より大きい障害の可能性があります。手動対応が必要です。",
            )
            return
        if vm_status == "stopped":
            # requirement: stopped → reboot ではなく start(決定論)
            queue_notify(
                cfg, "warning",
                f"{label}[recovery-probe] VM 停止検知 → start 実行 - {target}",
                f"VM が stopped 状態のため start を実行します"
                f"(node={vm_node}, vmid={vm_id})。",
            )
            if drill:
                log(f"LADDER {target}: drill — start はスキップ(実 VM は stopped ではない想定)")
                return
            started = pvesh_vm_start(cfg, vm_node, vm_id)
            log(f"LADDER {target}: vm start ok={started}")
            if started and wait_for_recovery(cfg, target, tconf):
                queue_notify(
                    cfg, "ok",
                    f"[recovery-probe] 復旧確認 (start) - {target}",
                    "VM start 後、probe 応答が回復しました。",
                )
            else:
                queue_notify(
                    cfg, "critical",
                    f"[recovery-probe] エスカレーション - {target}",
                    "VM start を実行しましたが probe 応答が回復しません。手動対応が必要です。",
                )
            return
        if vm_status == "not-found":
            queue_notify(
                cfg, "critical",
                f"{label}[recovery-probe] VM 不明 - {target}",
                "pvesh で対象 VM が見つかりません。手動確認が必要です。",
            )
            return

        # --- Ladder: VM reboot ---
        queue_notify(
            cfg, "warning",
            f"{label}[recovery-probe] ラダー開始 - {target}",
            f"failed probes: {failed_probes} / VM は running のまま無応答(ハング疑い)。"
            f"VM reboot を実行します。",
        )
        r = run_playbook(cfg, "recovery_vm_reboot.yml", extra)
        log(f"LADDER {target}: vm_reboot rc={r.returncode}")
        if drill:
            queue_notify(
                cfg, "ok",
                f"{label}[recovery-probe] drill 完了 - {target}",
                f"vm_reboot (tester_mode) rc={r.returncode}。実変更なし。",
            )
            return
        if r.returncode == 0 and wait_for_recovery(cfg, target, tconf):
            queue_notify(
                cfg, "ok",
                f"[recovery-probe] 復旧確認 - {target}",
                "VM reboot 後、probe 応答が回復しました。",
            )
            return

        # --- Ladder: HA failover ---
        if tconf.get("failover", False):
            queue_notify(
                cfg, "warning",
                f"[recovery-probe] failover 実行 - {target}",
                f"VM reboot で回復しなかったため HA failover を実行します。",
            )
            r2 = run_playbook(cfg, "recovery_ha_failover.yml", extra)
            log(f"LADDER {target}: ha_failover rc={r2.returncode}")
            if r2.returncode == 0 and wait_for_recovery(cfg, target, tconf):
                queue_notify(
                    cfg, "ok",
                    f"[recovery-probe] 復旧確認 (failover) - {target}",
                    "HA failover 後、probe 応答が回復しました。",
                )
                return

        queue_notify(
            cfg, "critical",
            f"[recovery-probe] エスカレーション - {target}",
            "ラダーを実行しましたが probe 応答が回復しません。手動対応が必要です。",
        )
    finally:
        os.rmdir(lock_dir)


# ---------------------------------------------------------------------------
# main loop
# ---------------------------------------------------------------------------
def drill_requested(cfg, target):
    return os.path.exists(os.path.join(cfg["state_dir"], "drill", target))


def clear_drill(cfg, target):
    try:
        os.unlink(os.path.join(cfg["state_dir"], "drill", target))
    except FileNotFoundError:
        pass


def main():
    once = "--once" in sys.argv
    cfg = load_config()
    os.makedirs(cfg["state_dir"], exist_ok=True)
    os.makedirs(os.path.join(cfg["state_dir"], "drill"), exist_ok=True)
    counters = {t: 0 for t in cfg["targets"]}
    isp_down_since = None
    # 外部到達性チェックの連続失敗数と、最初の失敗理由。閾値は設けない
    # (このチェックはアクションを起こさず通知のみで、閾値を入れると
    # 1〜4分の実際の短時間断が見えなくなる。2026-07-29 Yoshinobu 判断)。
    # 回数は通知に載せるためだけに数える — 単発の揺らぎと実際の断を
    # 読み手が区別できるようにする。
    ext_fail_count = 0
    ext_first_reason = None
    log(f"recovery-probe start (interval={cfg['interval_s']}s, "
        f"threshold={cfg['threshold']}, once={once})")

    while True:
        for target, tconf in cfg["targets"].items():
            # --- global monitoring pause ---
            pause_flag = cfg.get("monitoring_pause_flag", "")
            if pause_flag and os.path.isfile(pause_flag):
                if counters[target] != 0:
                    counters[target] = 0
                log(f"PROBE {target}: monitoring paused (global) — skip")
                continue

            # --- mute: 判定前に skip + カウンタリセット(第一防御) ---
            rem = mute_remaining(cfg, target)
            if rem > 0:
                if counters[target] != 0:
                    counters[target] = 0
                log(f"PROBE {target}: muted (残 {rem // 60} 分) — skip")
                continue

            drill = drill_requested(cfg, target)
            ok, failed = probe_target(cfg, target, tconf)
            if drill:
                ok, failed = False, ["drill"]

            if once:
                log(f"PROBE {target}: {'OK' if ok else 'FAIL ' + str(failed)}")

            if ok:
                if counters[target] > 0:
                    log(f"PROBE {target}: recovered (counter reset)")
                counters[target] = 0
                continue

            counters[target] += 1
            log(f"PROBE {target}: FAIL {failed} "
                f"({counters[target]}/{cfg['threshold']})")
            if counters[target] < cfg["threshold"]:
                continue
            counters[target] = 0

            if once:
                log(f"ONCE mode: {target} would fire now (action skipped)")
                continue

            # --- 発火 ---
            action = tconf.get("action", "notify")
            if action == "ladder":
                # ISP 切り分け: LAN 側 probe のうち icmp が生きていて外部だけ
                # 死んでいるケースは probe_target 内で ok になるためここには来ない。
                fire_ladder(cfg, target, tconf, failed, drill)
                if drill:
                    clear_drill(cfg, target)
            else:
                label = "[drill] " if drill else ""
                queue_notify(
                    cfg, "error",
                    f"{label}[recovery-probe] 異常検知 - {target}",
                    f"failed probes: {failed}(閾値 {cfg['threshold']} 回連続)。"
                    f"E-1 では通知のみ。調査には Slack で @Homelab へ依頼するか"
                    f"手動で対応してください。",
                )
                if drill:
                    clear_drill(cfg, target)

        # --- 外部到達性の状態遷移監視(ISP/FW 断。発火はしない。回復後に遅延通知) ---
        ext_ok, ext_reason = external_reachable(cfg)
        if not ext_ok:
            ext_fail_count += 1
            if isp_down_since is None:
                isp_down_since = datetime.now().astimezone().isoformat(timespec="seconds")
                ext_first_reason = ext_reason
            log(f"EXTERNAL check failed ({ext_fail_count} 回連続) — "
                f"監視のみ、発火しない。理由: {ext_reason}")
        elif isp_down_since is not None:
            # 原因を断定しない(2026-07-29)。このチェックが確かめたのは
            # 「HEAD が連続で失敗した」ことだけで、ISP / FW / 名前解決 /
            # 監視ホスト側のどれであるかは決まらない。旧文言は「ISP または
            # FW 断」と断定しており、実際に外部障害ではない事象(systemd
            # daemon-reexec に伴う単発失敗)を外部障害として調査させた。
            queue_notify(
                cfg, "warning",
                "[recovery-probe] 外部到達性チェックの回復",
                f"{isp_down_since} から {ext_fail_count} 回連続"
                f"({cfg['interval_s']}秒間隔)で外部到達性チェックに失敗し、"
                f"現在は回復しています。最初の失敗理由: {ext_first_reason}。"
                f"原因(ISP / FW / 名前解決 / 監視ホスト側)は"
                f"このチェックだけでは確定しません。",
            )
            isp_down_since = None
            ext_fail_count = 0
            ext_first_reason = None

        flush_notify_queue(cfg, ext_ok)
        if once:
            log("once mode: done")
            return
        time.sleep(cfg["interval_s"])


if __name__ == "__main__":
    main()
