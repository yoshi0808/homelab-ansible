#!/usr/bin/env python3
"""syslog-weekly-digest-collect: read-only Loki週次集計 collector (monnie専用)。

requirement: docs/ai/reviews/syslog_weekly_digest/2026-09-01_001_requirement.md
設計判断は同ファイル §6(Coordinator確定、2026-09-03/09-04訂正)。
是正内容: docs/ai/reviews/syslog_weekly_digest/2026-09-01_003_review_codex.md
(Major finding 1・3への対応)。

責務分離(skills/ansible-implementation-style「check系shellの責務分離」):
本scriptは**観測だけを行いJSONを標準出力へ返す**。正常/異常の判定、
error全文の予算内切り詰め、level非保有系列の抜き出し、Slack本文の整形、
マスク処理、通知はすべて呼び出し元 roles/syslog_weekly_digest/tasks/main.yml
(と filter_plugins/syslog_weekly_digest.py)が行う。本scriptはLokiへの
問い合わせが失敗しても非ゼロ終了しない — 常に有効なJSONを返し、`ok`/
個別の`*_ok`フィールドで成否を表現する(AC4: 判定はAnsible task側が行う)。

fail-closed(finding 3。2026-09-04是正2回目 — 再レビューが
`result: [null]`で`AttributeError`になることを再現し、追加で巨大指数・
少数・負数のcount、timestampの範囲外・label型も未確認と指摘した):
各endpointの応答は`status: "success"`・期待する`resultType`・`result`の
shape・count/timestampの数値性まで厳密に検証する。HTTP 200であっても
envelopeが壊れている、キーが欠けている、型が違う場合は0件/skipへ
フォールバックせず、そのqueryをerror扱いにする(本物の0件は`result`が
空リストとして正しく返ってくるケースであり、これは区別してokのまま
許容する)。

再レビュー指摘の個別確認結果(実装記録に詳細):
  - `result: [null]`(vector内の要素がnon-object) → `series.get(...)`等が
    `AttributeError`で未処理落ちすることを実際に確認した。**修正した**
    (各要素へ`isinstance(..., dict)`チェックを追加)。
  - `_parse_count`の巨大指数(例: "1e400") → `float()`はinfを返し例外に
    ならないが、続く`int(inf)`が`OverflowError`になることを確認した。
    **修正した**(inf/nan判定を`int()`呼び出しより先に行う)。
  - 少数のcount(例: "3.7")・負数のcount(例: "-5") → 例外にはならないが
    サイレントに切り捨て/受理されることを確認した。ログ件数として意味を
    なさない値であり、**malformedとして拒否するよう修正した**。
  - timestampの実在範囲 → 極端に大きい/小さいtimestampで
    `datetime.fromtimestamp()`が`OverflowError`になることを確認した。
    **修正した**(problemのある値がそこへ到達する前に、要求した
    query窓〔`start`/`end`、余裕60秒×5〕の範囲内かを検証する)。
  - labelのstring型(non-string job/host/level) → **2回目是正時点では
    「Slack本文への整形はstr.format()が暗黙にstr()変換するため例外は
    発生しない」ことだけを確認し、追加のvalidationを行っていなかった。
    この判断は3回目是正で誤りと判明し撤回済みである**(下記
    `collect_series`のコメント、および実装記録参照)。実際には
    `str.format()`より手前の`rows.sort(key=lambda r: (r["job"], r["host"],
    r["level"]))`がint/str混在比較で`TypeError`になり、collectorが例外
    終了することをCoordinatorが再現した。**現在は`collect_series`内で
    job/host/levelそれぞれに`isinstance(..., str)`検証を行い、sort()へ
    到達する前に非stringをmalformedとして拒否している**(2026-09-04
    是正3回目)。

roles/recovery_exec/files/recovery-loki-helper を再利用しない理由:
requirement §6.1。helperのALLOWED_COUNT_WINDOWS/ALLOWED_ERRORS_WINDOWSは
最大24hで7日窓を表現できず、allowlistを広げることはSSH forced command
経由の調査経路の認可境界そのものを変えることになるため、別実装とする。
helperファイル自体は変更しない。ただし出力量の上限(ERROR_QUERY_LIMIT/
MAX_SERIES/MAX_LINE_LENGTH)はhelperの値をそのまま踏襲する(requirement
§5、独立レビューが2000件を契約違反と判定しCoordinatorが受け入れた)。

window: 引数を取らない。実行時のJST "now" から遡って7日固定
(WINDOW_HOURSのリテラル)。cronの実行タイミングが多少ずれても、常に
「実行時刻を基準とした直近168h」を問い合わせるだけであり、前回実行との
連続性(gapを埋める)は保証しない — 週境界をまたぐ遅延・重複時は
理論上gap/overlapが生じうる(non-blocking、2026-09-01レビュー)。AC群は
固定7日窓を求めているだけで週境界の厳密な連続性までは要求していないため
挙動は変えない。
"""
import decimal
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

LOKI_BASE = "http://localhost:3100"

# JST is a fixed UTC+9 offset with no DST (see recovery-loki-helper for the
# same rationale: no dependency on IANA tzdata being installed/current).
JST = timezone(timedelta(hours=9))

WINDOW_DAYS = 7
WINDOW_HOURS = WINDOW_DAYS * 24  # expressed in hours for the LogQL duration
# literal — avoids relying on Loki's parser accepting a "d" unit, which
# recovery-loki-helper also never exercises (its ALLOWED_*_WINDOWS top out
# at "24h").

# 収集段の安全策として1行あたりの長さを軽く制限する(recovery-loki-helperの
# MAX_LINE_LENGTHと同じ値)。これは生データがパイプラインを流れる量を早期に
# 減らすための予防策であり、AC3/§6.3が求める「最終的に整形・マスクした
# 1行を300文字以下にする」契約そのものはここでは満たさない — ts/job/host
# の前置とマスクはこの後段(filter_plugins側)で行われるため、その契約の
# 判定点はfilter側にある(2026-09-04是正、finding 1)。
MAX_LINE_LENGTH = 300

# Lokiへ要求するerror行の上限。recovery-loki-helperのQUERY_LIMITと同値
# (2026-09-04是正、finding 1: 独自に2000へ広げていたのは既存helperの
# 出力量制限を回避しているとレビューが判定し、Coordinatorが受け入れた)。
ERROR_QUERY_LIMIT = 300

# series集計行の上限。recovery-loki-helperのMAX_SERIESと同値・同じ理由
# (job・host増加への保険。実測は11系列)。超過分は切り捨て、件数を
# series.truncated / series.total_countで明示する(2026-09-04是正、
# finding 1)。
MAX_SERIES = 500

# error entriesのtimestampが、要求したquery window(start/end)からどれだけ
# 外れていたら「明らかにおかしい値」と判定するかの許容幅(ナノ秒)。
# monnieとLoki間の時計のずれ・処理遅延を吸収する目的の保守的な値であり、
# 業務判断ではない(2026-09-04是正2回目、finding 3)。
_TS_WINDOW_MARGIN_NS = 300 * 10**9  # 300秒 = 5分

_URLLIB_ERRORS = (urllib.error.URLError, OSError)


def now_jst():
    return datetime.now(JST)


def rfc3339_utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def loki_get(path, params, timeout):
    url = "{}{}?{}".format(LOKI_BASE, path, urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read()
    except _URLLIB_ERRORS as exc:
        # str(exc) for a connection to a bare "localhost" URL never contains
        # an IP literal (constraint: no IP addresses in output).
        return None, "Loki request failed: {}".format(exc)
    try:
        return json.loads(body), None
    except json.JSONDecodeError:
        return None, "Loki returned non-JSON response"


def _validate_envelope(data, expected_result_type):
    """Strictly validate a Loki success envelope (finding 3).

    Returns (result_list, None) on a well-formed envelope (including a
    legitimately empty `result: []`, which is a real zero, not an error),
    or (None, error_message) if the envelope cannot be classified as either
    — an HTTP 200 with a missing/wrong `status`, a missing/wrong
    `resultType`, or a `result` that is not a list is treated as a query
    failure, never silently coerced to an empty/zero result.
    """
    if not isinstance(data, dict):
        return None, "malformed Loki response: top-level JSON is not an object"
    if data.get("status") != "success":
        return None, "Loki response status != 'success' (got {!r})".format(data.get("status"))
    payload = data.get("data")
    if not isinstance(payload, dict):
        return None, "malformed Loki response: 'data' is missing or not an object"
    result_type = payload.get("resultType")
    if result_type != expected_result_type:
        return None, "unexpected resultType {!r} (expected {!r})".format(
            result_type, expected_result_type
        )
    result = payload.get("result")
    if not isinstance(result, list):
        return None, "malformed Loki response: 'data.result' is missing or not a list"
    return result, None


def _parse_count(value):
    """Parse a Loki instant-query `value` pair's count strictly.

    Returns (count, None) or (None, error). Loki always encodes the sample
    value as a string (even for integer counts), so a value that is not a
    2-element [timestamp, string] pair, or whose string does not parse as a
    non-negative integer, is a shape violation — not a 0.

    2026-09-04是正2回目(finding 3の再レビュー指摘): 旧実装は
    `int(value[1])`失敗時に`int(float(value[1]))`へ落ちていたため、
    (a) 巨大な指数表記(例: "1e400")で`float()`がinfを返し、続く`int(inf)`
    が`OverflowError`になり未処理で落ちる、(b) 少数(例: "3.7")を
    サイレントに整数へ切り捨てる、(c) 負数(例: "-5")をそのまま受理する、
    という3つの問題があった。件数(count_over_time)は本来非負整数であり、
    これらはいずれも「表示している数字が実際の値と異なる」または
    「クラッシュする」ため、malformedとして拒否する。

    2026-09-04是正3回目(Coordinator再現): `int(float(raw))`は`float`の
    53bit仮数部を経由するため、`"9007199254740993"`(2**53+1)のような
    巨大な整数値が`9007199254740992`へ丸まって返っていた ——
    クラッシュはしないが「表示している数字が実際の値と違う」という
    finding 1のMAX_SERIES二重化と同種の欠陥だった。プレーンな整数
    リテラル文字列は`int(raw)`で直接(Pythonの多倍長整数、丸め無し)
    parseする。

    2026-09-04是正4回目(Coordinator再現、Minor): 3回目是正は「プレーン
    整数リテラルでない場合」を`float()`経由で分類し`int(as_float)`を返して
    いたが、これは"9007199254740993.0"や"9.007199254740993e15"のように
    小数点・指数表記を伴う巨大な整数値では、`float(raw)`自体の変換時点で
    既に53bit仮数部の丸めが発生しており、3回目是正が解消したはずの丸め
    問題が形を変えて残っていた。**丸めた値を正しい値として通す設計その
    ものを残さない**という方針(小数countも負のcountも既にmalformedとして
    拒否している)に揃え、非プレーン整数リテラルは`decimal.Decimal`で
    元の文字列を直接(10進・任意精度、floatの2進53bit精度を経由しない)
    parseし、その値が整数と厳密に一致する場合のみ`int()`化して返す。
    `float(raw)`によるinf/nan判定("1e400"のような桁あふれの拒否)は
    そのまま維持する — `Decimal`は"1e400"のような値も丸めずに厳密な
    整数として表現できてしまう(桁あふれしない)ため、`Decimal`だけに
    切り替えると「巨大な指数表記を拒否する」という3回目是正の挙動が
    失われてしまう。したがって finite 判定は `float()` のオーバーフロー
    特性(絶対値が大きすぎる値はinfになる)に**意図して依存し続け**、
    整数としての厳密な値の取得だけを`Decimal`へ切り替える、という
    2段構成にした。
    """
    if not (isinstance(value, list) and len(value) == 2):
        return None, "'value' is not a 2-element array"
    raw = value[1]
    # Loki always encodes the sample value as a JSON string, never a bare
    # number/bool/null -- require that shape explicitly rather than
    # accepting anything float()/int() happens to coerce.
    if not isinstance(raw, str):
        return None, "count value {!r} is not a string".format(raw)

    try:
        # Exact, arbitrary-precision parse for the common case (a plain
        # integer literal) -- never loses precision the way float() would
        # for values beyond 2**53.
        count = int(raw)
    except ValueError:
        # Not a plain integer literal (e.g. "3.7", "1e400",
        # "9007199254740993.0", "abc"). First reject non-finite magnitudes
        # via float() -- its overflow-to-inf behavior is exactly the check
        # we want for absurdly large exponents, and is simpler than picking
        # an arbitrary manual bound.
        try:
            as_float = float(raw)
        except (TypeError, ValueError):
            return None, "count value {!r} is not numeric".format(raw)
        if as_float != as_float or as_float in (float("inf"), float("-inf")):
            return None, "count value {!r} is not a finite number".format(raw)
        # Now extract the EXACT value from the original string via Decimal
        # (base-10, arbitrary precision) rather than int(as_float) -- the
        # float conversion above is only used for the finite/nan check, its
        # (possibly already-rounded) value is never used as the count.
        try:
            as_decimal = decimal.Decimal(raw)
        except decimal.InvalidOperation:
            return None, "count value {!r} is not numeric".format(raw)
        as_integral = as_decimal.to_integral_value()
        if as_integral != as_decimal:
            return None, "count value {!r} is not an integer".format(raw)
        count = int(as_integral)

    if count < 0:
        return None, "count value {!r} is negative".format(raw)
    return count, None


def collect_series(end):
    # Same shape as recovery-loki-helper's `count`:
    # sum by (job, host, level) (count_over_time(...)), just over a 7-day
    # window instead of helper's max 24h. Instant queries return
    # resultType "vector".
    query = 'sum by (job, host, level) (count_over_time({{job=~".+"}}[{}h]))'.format(
        WINDOW_HOURS
    )
    data, err = loki_get("/loki/api/v1/query", {"query": query, "time": rfc3339_utc(end)}, timeout=30)
    if err:
        return None, err
    result, err = _validate_envelope(data, "vector")
    if err:
        return None, err

    total_count = len(result)
    truncated = total_count > MAX_SERIES
    limited = result[:MAX_SERIES] if truncated else result

    rows = []
    for series in limited:
        # 2026-09-04是正2回目: `result: [null]`のような non-object 要素に
        # 対して`series.get(...)`をいきなり呼ぶと`AttributeError`で未処理
        # 落ちすることを再レビューが再現した。要素自体の型を先に確認する。
        if not isinstance(series, dict):
            return None, "malformed series entry: item is not an object"
        metric = series.get("metric")
        if not isinstance(metric, dict):
            return None, "malformed series entry: 'metric' is missing or not an object"
        job = metric.get("job", "")
        host = metric.get("host", "")
        # 2026-09-04是正3回目(Coordinator再現): job/hostがLokiの本来の
        # label値(常に文字列)でなく数値等が混在すると、str.format()自体は
        # 例外にならない(暗黙にstr()変換されるため確認済み)が、その手前の
        # `rows.sort(key=lambda r: (r["job"], r["host"], r["level"]))`が
        # int/str混在比較で`TypeError`になり、collectorが例外終了する
        # ("labelのstring型は該当しない"という2回目是正時の判断は、
        # 検査対象を`str.format()`だけに絞っていたため誤りだった —
        # 値が通る経路全体〔sortを含む〕を見ていなかった)。Lokiのラベル値は
        # 仕様上常に文字列であり、非文字列はそれ自体が壊れたshapeの証拠
        # なのでmalformedとして拒否する。
        if not isinstance(job, str):
            return None, "malformed series entry: 'job' label is not a string"
        if not isinstance(host, str):
            return None, "malformed series entry: 'host' label is not a string"
        # Distinguish "label absent" from "label present but empty", same as
        # recovery-loki-helper cmd_count.
        if "level" in metric:
            level_raw = metric["level"]
            if not isinstance(level_raw, str):
                return None, "malformed series entry: 'level' label is not a string"
            level = level_raw if level_raw != "" else "(empty)"
        else:
            level = "(no level label)"
        count, count_err = _parse_count(series.get("value"))
        if count_err:
            return None, "malformed series entry: {}".format(count_err)
        rows.append({"job": job, "host": host, "level": level, "count": count})
    rows.sort(key=lambda r: (r["job"], r["host"], r["level"]))
    return {"rows": rows, "total_count": total_count, "truncated": truncated}, None


def collect_error_total(end):
    # Accurate total independent of ERROR_QUERY_LIMIT, used by the playbook
    # to report "N件中M件を表示" even when the full-text list below is
    # capped. sum(...) collapses to at most one series (resultType
    # "vector"); more than one is itself a shape violation.
    query = 'sum(count_over_time({{job=~".+", level="error"}}[{}h]))'.format(WINDOW_HOURS)
    data, err = loki_get("/loki/api/v1/query", {"query": query, "time": rfc3339_utc(end)}, timeout=30)
    if err:
        return None, err
    result, err = _validate_envelope(data, "vector")
    if err:
        return None, err
    if len(result) == 0:
        # A real zero: no error-level series matched at all.
        return 0, None
    if len(result) != 1:
        return None, "unexpected result shape: sum() query returned {} series".format(len(result))
    item = result[0]
    # 2026-09-04是正2回目: 同上、`result: [null]`に対する
    # `AttributeError`の再現箇所。
    if not isinstance(item, dict):
        return None, "malformed error_total: result item is not an object"
    count, count_err = _parse_count(item.get("value"))
    if count_err:
        return None, "malformed error_total: {}".format(count_err)
    return count, None


def collect_error_entries(start, end):
    # level が付かなかった行はselectorの時点で除外される(level="error"を
    # selectorへ含めているため) — recovery-loki-helper cmd_errorsと同じ
    # 性質。level無しの行数は collect_series の "(no level label)" 側で
    # 読める(到達経路は別に残っている)。query_range against raw log lines
    # returns resultType "streams".
    selector = '{job=~".+", level="error"}'
    params = {
        "query": selector,
        "start": rfc3339_utc(start),
        "end": rfc3339_utc(end),
        "limit": str(ERROR_QUERY_LIMIT),
        "direction": "forward",
    }
    data, err = loki_get("/loki/api/v1/query_range", params, timeout=30)
    if err:
        return None, err
    result, err = _validate_envelope(data, "streams")
    if err:
        return None, err

    # 2026-09-04是正2回目(finding 3の再レビュー指摘): 極端に大きい/小さい
    # timestamp(例: 10**30)は`int()`自体は例外にならず通過するが、後段の
    # `datetime.fromtimestamp()`が`OverflowError`で未処理落ちすることを
    # 確認した。ここで要求した query window(start/end)を基準にした妥当な
    # 範囲へ収まっているかを検証し、収まらなければ`datetime.fromtimestamp`
    # へ到達する前にmalformedとして拒否する。余裕(_TS_WINDOW_MARGIN_NS)は
    # monnieとLoki間の時計のずれ・処理遅延を吸収するための保守的な値。
    start_ns = int(start.timestamp() * 1e9) - _TS_WINDOW_MARGIN_NS
    end_ns = int(end.timestamp() * 1e9) + _TS_WINDOW_MARGIN_NS

    raw_entries = []
    for stream in result:
        if not isinstance(stream, dict):
            return None, "malformed error_entries: stream item is not an object"
        labels = stream.get("stream")
        if not isinstance(labels, dict):
            return None, "malformed error_entries: 'stream' labels missing or not an object"
        job = labels.get("job", "")
        host = labels.get("host") or labels.get("unit") or job
        values = stream.get("values")
        if not isinstance(values, list):
            return None, "malformed error_entries: 'values' is missing or not a list"
        for pair in values:
            if not (isinstance(pair, list) and len(pair) == 2):
                return None, "malformed error_entries: a value pair is not a 2-element array"
            ts_ns_raw, line = pair
            if not isinstance(line, str):
                return None, "malformed error_entries: log line is not a string"
            try:
                ts_ns = int(ts_ns_raw)
            except (TypeError, ValueError):
                return None, "malformed error_entries: timestamp {!r} is not numeric".format(ts_ns_raw)
            if not (start_ns <= ts_ns <= end_ns):
                return None, "malformed error_entries: timestamp {!r} is outside the requested query window".format(
                    ts_ns_raw
                )
            raw_entries.append((ts_ns, job, host, line))
    raw_entries.sort(key=lambda e: e[0])
    hit_query_limit = len(raw_entries) >= ERROR_QUERY_LIMIT

    entries = []
    for ts_ns, job, host, line in raw_entries:
        # The start_ns/end_ns bound check above already guarantees ts_ns is
        # well within datetime's representable range, but the conversion is
        # still wrapped defensively -- if it ever raised despite that bound
        # (e.g. a future change narrows the bound incorrectly), this must
        # become a query error, not an unhandled crash (AC4).
        try:
            ts = datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc).astimezone(JST)
        except (OverflowError, OSError, ValueError):
            return None, "malformed error_entries: timestamp {!r} could not be converted".format(ts_ns)
        # C1 note from recovery-loki-helper cmd_errors: normalize embedded
        # CR/LF in the line body to a single logical line before capping its
        # length, so one entry never expands into multiple physical lines
        # downstream. This length cap is a preliminary safety net only —
        # the binding 300-char contract on the final Slack-bound line is
        # enforced after formatting+masking downstream (see module
        # docstring).
        normalized = " ".join(line.splitlines()) if line else line
        if len(normalized) > MAX_LINE_LENGTH:
            normalized = normalized[: MAX_LINE_LENGTH - 3] + "..."
        entries.append(
            {
                "ts": ts.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "job": job,
                "host": host,
                "line": normalized,
            }
        )
    return {"entries": entries, "hit_query_limit": hit_query_limit}, None


def main():
    end = now_jst()
    start = end - timedelta(hours=WINDOW_HOURS)

    series_result, series_err = collect_series(end)
    error_total, error_total_err = collect_error_total(end)
    error_entries_result, error_entries_err = collect_error_entries(start, end)

    # 2026-09-04是正4回目(Major、Coordinator再現): error_total(集計クエリ)
    # と error_entries(一覧クエリ)は別々のLoki問い合わせであり、それぞれ
    # 個別には成功していても、値そのものが食い違うことがありうる(実行
    # タイミング差、Loki側の集計と抽出の実装差 — この性質自体は
    # filter_plugins のdocstringに既知の限界として当初から記載済み)。
    # 旧実装はこの食い違いを一切見ておらず、`error_total.count == 0` を
    # そのまま信じて「0件でした」と言い切っていたため、
    # `error_entries.entries` に実際に観測した行があっても本文のどこにも
    # 出ない(AC2・AC5違反)ことをCoordinatorが再現した
    # (`error_total.count=0` / `error_entries.entries`=1件)。
    #
    # 「観測した行数(len(entries))の方が独立集計の総数(error_total)より
    # 多い」という向きは常に不整合である — 集計側が実際より少なく数えている
    # ことを意味し、これを見過ごすと観測済みの行を報告し損なう。
    #
    # 2026-09-04是正5回目(Major、Coordinator再現・Coordinatorの前回指示の
    # 訂正): 逆向き(error_total > len(entries))を無条件に正常として通して
    # いたが、Coordinatorが`total=5`・`entries=1`・`hit_query_limit=false`
    # を再現し、この場合はERROR_QUERY_LIMITでは説明できず(hit_query_limit
    # が偽)、文字数予算による省略はcollectorより後段のfilterで起きるため
    # collector段では理由にならない、と指摘した — 4件が理由不明で欠けて
    # いるのに正常として通り、しかもfilter側は「文字数予算に到達したため」
    # という**誤った理由**を本文へ出していた(黙ってはいないが、誤った
    # 理由を告げていた)。
    #
    # collector段で観測できる、entries不足の正当な理由は`hit_query_limit`
    # (entriesがERROR_QUERY_LIMITで頭打ちになったこと)だけである
    # (collect_error_entriesの実装を確認済み — 重複排除や他の暗黙の絞り
    # 込みは無い)。したがって、`error_total > len(entries)`のうち
    # `hit_query_limit`が真でない場合も、逆向きと同じく不整合として
    # fail-closedにする。`hit_query_limit`が真の場合は理由が観測できて
    # いるため通し、その理由(query limitの値)を出力の`error_entries`側に
    # 残す(filter側が「文字数予算」ではなく実際の理由を書けるようにする
    # ため — collectorが「なぜ欠けたか」を運び、filterがそれを書く形)。
    if error_total_err is None and error_entries_err is None:
        observed_entries = (error_entries_result or {}).get("entries", [])
        hit_query_limit = (error_entries_result or {}).get("hit_query_limit", False)
        inconsistency = None
        if error_total is not None:
            if error_total < len(observed_entries):
                inconsistency = (
                    "error_total.count ({}) is less than the number of "
                    "retrieved error_entries ({}); the two Loki queries "
                    "disagree and neither is trusted".format(error_total, len(observed_entries))
                )
            elif error_total > len(observed_entries) and not hit_query_limit:
                inconsistency = (
                    "error_total.count ({}) exceeds the number of retrieved "
                    "error_entries ({}) but hit_query_limit is false, so the "
                    "shortfall has no observable cause; the two Loki queries "
                    "disagree and neither is trusted".format(error_total, len(observed_entries))
                )
        if inconsistency:
            error_total_err = inconsistency
            error_entries_err = inconsistency
            error_total = None
            error_entries_result = None

    ok = series_err is None and error_total_err is None and error_entries_err is None

    series_result = series_result or {}
    error_entries_result = error_entries_result or {}

    output = {
        "collected_at": end.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "window": {
            "since": start.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "until": end.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "days": WINDOW_DAYS,
        },
        "ok": ok,
        "series": {
            "ok": series_err is None,
            "error": series_err,
            "rows": series_result.get("rows", []),
            "total_count": series_result.get("total_count", 0),
            "truncated": series_result.get("truncated", False),
            # 実際に適用した上限そのものを出力へ載せる(2026-09-04是正、
            # Coordinator指摘)。呼び出し側〔filter〕は自前の定数を持たず
            # ここを読む — MAX_SERIESの値を2箇所に複製すると、片方だけ
            # 変更されたときSlack本文の「上限Nに到達」という文言が現物と
            # 食い違う("通知文が嘘をつく")。正本はここ1箇所。
            "limit": MAX_SERIES,
        },
        "error_total": {
            "ok": error_total_err is None,
            "error": error_total_err,
            "count": error_total if error_total is not None else 0,
        },
        "error_entries": {
            "ok": error_entries_err is None,
            "error": error_entries_err,
            "hit_query_limit": error_entries_result.get("hit_query_limit", False),
            "query_limit": ERROR_QUERY_LIMIT,
            "entries": error_entries_result.get("entries", []),
        },
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
