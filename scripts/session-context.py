#!/usr/bin/env python3
"""SessionStart hook: /clear・再起動・compactのたびに「現在地」を文脈へ載せる。

規範(どう振る舞うか)は CLAUDE.md → docs/ai/core.md が入口として既に機能している。
ここで補うのは状態(今どこにいて何を待っているか)であり、その正本は docs/ai/status.md。
要約せず現物を渡す — 要約した層は必ず本文より古くなる
(docs/ai/memory/lessons/always-loaded-summaries-are-the-least-current.md)。

**分割して出す理由。** hook の出力は 10,000 文字を超えるとファイルへ退避され、
先頭 2,000 文字のプレビューだけが文脈へ渡る(2.1.234 のバイナリで実測。閾値も
プレビュー長も定数で、環境変数では変えられない)。2026-08-18 時点の出力は
16,821 文字で、実際に status.md の Next 表の2行目で切れていた。要約して縮める
のは上の lesson が禁じている形なので、**現物のまま節境界で分割し、SessionStart
へ複数エントリとして登録する。** 1エントリが1チャンクを出す。

Usage: session-context.py <chunk番号(1始まり)>

セッション起動を妨げないことを最優先とし、何が失敗しても終了コード 0 で抜ける。
中身の無いチャンクは何も出力しない(登録エントリ数が実際のチャンク数より多くてよい)。
"""

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATUS_PATH = REPO_ROOT / "docs" / "ai" / "status.md"

# 1チャンクの上限。実際の閾値 10,000 文字に対し、見出しと注記のぶんを残す。
CHUNK_BUDGET = 9000


def run_git(args):
    """git の出力を返す。失敗しても空文字列にする。"""
    try:
        result = subprocess.run(
            ["git"] + args, cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def status_sections():
    """status.md をトップレベルの `## ` 境界で切る。読めなければ注意書き1つを返す。"""
    try:
        body = STATUS_PATH.read_text(encoding="utf-8")
    except OSError:
        return ["(docs/ai/status.md が読めない。存在しないなら状態の正本が"
                "失われているので確認すること)\n"]
    return [part for part in re.split(r"(?m)^(?=## )", body) if part.strip()]


AGMSG_STATUS = Path.home() / ".agents" / "skills" / "agmsg" / "scripts" / "remote.sh"
AGMSG_TEAMS = ("homelab-ops",)
# 「最後に成功した同期」がこれより古ければ、動いていないものとして出す。
SYNC_STALE_SECONDS = 900


def _humanize(seconds):
    """経過を読める単位にする。分だけで出すと「7834分前」になり読み取れない。"""
    if seconds < 3600:
        return "約%d分" % (seconds // 60)
    if seconds < 86400:
        return "約%d時間" % (seconds // 3600)
    return "約%.1f日" % (seconds / 86400)


def agmsg_sync_block():
    """agmsg remote team の同期状態を1ブロックにする。

    **人が起動時の画面で読むことに頼らない。** 起動直後にCCの画面へ切り替わる
    ため、`remote.sh status` の出力は実際には読まれない。2026-08-29から
    2026-09-02まで sync engine が5日間死んでいたのを誰も気づかなかったのは
    これが理由である(docs/ai/memory/incidents/
    2026-09-02_agmsg-sync-engine-dead-for-five-days.md)。

    **取得できないときは黙って空にせず、確認できなかったと書く。**
    engine が生きていても「最後に成功した同期」が古ければ運べていない
    (`docs/ai/context/operations/agent-messaging.md` §9)。
    """
    lines = []
    for team in AGMSG_TEAMS:
        if not AGMSG_STATUS.exists():
            lines.append("- %s: **確認できず**(%s が無い)" % (team, AGMSG_STATUS))
            continue
        try:
            result = subprocess.run(
                ["bash", str(AGMSG_STATUS), "status", team],
                capture_output=True, text=True, timeout=15,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            lines.append("- %s: **確認できず**(%s)" % (team, type(exc).__name__))
            continue
        out = result.stdout
        running = "engine running" in out
        m = re.search(r"last successful sync ([0-9T:.\-]+)Z", out)
        if not m:
            lines.append("- %s: **同期していない。** engine=%s、"
                         "「最後に成功した同期」の行が無い。"
                         "**通常のシェルから `remote.sh sync start %s` が要る**"
                         % (team, "running" if running else "not running", team))
            continue
        try:
            last = datetime.datetime.strptime(m.group(1)[:19], "%Y-%m-%dT%H:%M:%S")
            last = last.replace(tzinfo=datetime.timezone.utc)
            age = (datetime.datetime.now(datetime.timezone.utc) - last).total_seconds()
        except ValueError:
            lines.append("- %s: 同期時刻を解釈できない: %s" % (team, m.group(1)))
            continue
        if age > SYNC_STALE_SECONDS:
            lines.append("- %s: **同期が古い(%s前)。** engine=%s。"
                         "engineが生きていても運べていないことがある"
                         % (team, _humanize(age), "running" if running else "not running"))
        else:
            lines.append("- %s: 正常(最後の同期は%s前)" % (team, _humanize(age)))
    return "\n## agmsg の同期状態\n\n%s\n" % "\n".join(lines)


def build_blocks():
    """出力の素材を、分割してよい単位のリストとして組む。"""
    blocks = ["## docs/ai/status.md(状態の正本)\n\n"]
    blocks.extend(status_sections())

    blocks.append(agmsg_sync_block())

    git_status = run_git(["status", "--short"])
    blocks.append("\n## git status --short(未commitの現物)\n\n%s\n"
                  % (git_status if git_status else "(なし)"))
    blocks.append("\n## 直近のcommit\n\n%s\n" % run_git(["log", "--oneline", "-5"]))
    return blocks


def pack(blocks):
    """予算に収まるよう、順序を保ったまま貪欲に詰める。

    1つの block だけで予算を超える場合は、その block 単独でチャンクにする。
    そのチャンクは退避されてプレビューだけになるため、先頭へ明示の注記を置く
    (プレビューは先頭 2,000 文字なので、注記は必ず読み手へ届く)。
    """
    chunks = []
    current = []
    size = 0
    for block in blocks:
        if len(block) > CHUNK_BUDGET:
            if current:
                chunks.append(current)
                current, size = [], 0
            note = ("**この節は単独で %d 文字あり、hook の 10,000 文字を超える。"
                    "以降は退避されて届かないので、必要なら docs/ai/status.md を"
                    "直接読むこと。**\n\n" % len(block))
            chunks.append([note, block])
            continue
        if size + len(block) > CHUNK_BUDGET and current:
            chunks.append(current)
            current, size = [], 0
        current.append(block)
        size += len(block)
    if current:
        chunks.append(current)
    return chunks


def main():
    try:
        index = int(sys.argv[1])
    except (IndexError, ValueError):
        index = 1

    chunks = pack(build_blocks())
    if index < 1 or index > len(chunks):
        return

    header = ("# セッション開始時の現在地 %d/%d"
              "(SessionStart hook: scripts/session-context.py)\n\n"
              % (index, len(chunks)))
    body = header + "".join(chunks[index - 1])

    print(json.dumps(
        {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                "additionalContext": body},
         "suppressOutput": True},
        ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # セッション起動を妨げない
        pass
    sys.exit(0)
