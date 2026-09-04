"""Jinja filters for syslog_weekly_digest.

責務分離(skills/ansible-implementation-style「check系shellの責務分離」):
collector(files/syslog-weekly-digest-collect.py)は観測だけを行いJSONを
返す。判定・整形・文字数予算での切り詰め(requirement §6.3)・マスク・
Slack本文の組み立てはすべてここ(Ansible task側の整形層)で行う。

是正内容(2026-09-04, docs/ai/reviews/syslog_weekly_digest/
2026-09-01_003_review_codex.md finding 1・2への対応。1回目是正):
旧版は「本文だけ300文字で切る collector」+「entry.lineだけをマスクする
filter」+「error本文だけの文字数予算」という3段構成だったが、これは
(a) 前置されるts/job/hostぶん最終行が300文字を超える、(b) series/
no-levelテーブルのjob・hostがマスクされない(IP形式のhost labelが素通り
する)、(c) 文字数予算がerror本文にしか効かずseries表を含む通知全体には
効かない、という3つの欠陥を生んだ。(a)(b)は解消したが、(c)は
`syslog_weekly_digest_render_message()`統合後も「seriesとno-levelを
無条件に全件出し、残額をerror行の選別に使うだけ」という実装のままで、
再レビューで500系列の入力から25,543文字(予算6000)・`[TRUNCATED]`無しが
再現された(2026-09-04是正2回目、finding 1)。

2回目是正・1周目: `_fit_lines()`を新設し、series・no-level・errorの
3セクションすべてを「残り予算に収まる分だけ表示」する仕組みへ変えたが、
このとき各セクションはそれぞれ「自分自身の注記」だけを予約し、まだ
出力していない後続の見出し・固定行(次セクションの見出し、"0件でした"、
`[取得失敗]`等)の分を予約していなかった。Coordinatorが500件の
levelラベル無しseries(host labelを長くしたもの)+error 0件の入力で
6003文字(予算6000)を再現し、この見落としを検出した。

2回目是正・2周目: 固定行(header・見出し3つ・区切りの空行・
`[取得失敗]`/`0件でした`/`(該当なし)`等のプレースホルダ・hit_query_limit
注記・末尾の失敗banner)は**すべてtruncationの選別より先に、実データから
正確な文字列として確定**する(`skeleton_cost`)。`content_budget =
char_budget - skeleton_cost`をseries→no-level→errorの順に可変長コンテン
ツへ割り当てることで、500系列の入力を6000字以下へ収めることには成功した
が、この周のセクション別ロジック(`_fit_section`+`_add_note`、旧版)は
「収まりきらなかったら注記の分を予約して再選別する」という**「全部
入りきる場合は注記を予約しない」設計**だったため、次の3回目是正で
見つかった欠陥を生んだ。

3回目是正(2026-09-04、最新): Coordinatorが**予算には収まっているのに
truncation注記が1つも出ないケース**を総当たりで再現した
(`error_total=21`・`entries=20`・1行258〜260文字 → 全体5,971〜5,994文字
〔予算6000以下〕・表示20/21件・`[TRUNCATED]`無し)。原因は、
`error_entries.entries`(collectorが実際に取得できた一覧)が
`error_total.count`(独立集計クエリの正確な総数)より**最初から**少ない
場合(Lokiの2つのqueryの実行タイミング差、既知の限界としてdocstringに
記載済み)、「全件が予算に収まるか」という判定だけでは truncation を
検出できない — 20件全部が余裕で収まるため「全部入った」と判定され、
注記の予約(`_NOTE_RESERVE`)が発動しないまま note 自体も追加されず、
「省略した事実が本文のどこにも出ない」という**AC3違反**になっていた。
no-levelセクションにも同型の欠陥があった(`series_rows_shown`由来の
候補がその時点で既に`total_no_level`より少ない場合)。

3回目是正の設計: `_render_truncatable_section()`へ全面的に置き換えた。
「予算に収まるか」ではなく「**そのセクションの真の総数
(`declared_total`)より少ししか見せられないか**」を先に判定し、
- 何も欠けていない(`declared_total <= 候補件数`)場合だけ、注記なしで
  全件表示を試みる高速経路を使う。
- それ以外(データの時点で既に欠けている、または全件が予算に収まらない)
  場合は、**表示件数を1件ずつ減らしながら「その件数の本文+その件数用の
  注記」が予算に収まる最大値を探す**。見つかった時点でその件数分の本文と
  注記を**両方**出力する。見つからなければ(=極端に小さい予算)何も
  出さない(既知の限界)。
この設計により、**「1件でも省略されていれば、必ず注記が付く」ことが
アルゴリズムの構造そのものから導かれる**(注記を出す条件と本文を減らす
条件が同じ探索ループに統合されているため、「本文は削ったが注記を忘れた」
という状態を作れない)。Coordinatorの指摘どおり「予算と注記が両立しない
なら表示件数を1件減らしてでも注記を出す」を文字どおり実装した。

`syslog_weekly_digest_render_message()`へ1関数に統合し、
- マスクは「フォーマット済みの行」に対して行い(job/host/lineすべて)、
- 300文字の上限はマスク後の最終行に対して判定し、
- 6,000字の予算はseries表・no-levelテーブル・error本文を合わせた通知
  全体の累積文字数に対して判定する。

さらに、組み立てた最終メッセージ全体に対してもう一度
`syslog_weekly_digest_redact_ipv4`を通す(関数の最後の1行)。個々の
フィールドをマスクし忘れた場合の単一の取りこぼし防止層であり、
「Slackへ渡る最終メッセージ全体を一箇所でsanitizeする」という是正指示の
文字どおりの実装でもある(冪等な正規表現なので二重適用しても安全)。

既知の限界:
- 固定行(skeleton)だけで`char_budget`を使い切るほど極端に小さい予算を
  渡した場合、`_render_truncatable_section`が「0件+注記」すら`budget`
  へ収められず、可変長セクションの内容(本文・注記とも)が一切表示され
  ないことがある。実測(series・error両方が失敗しclampされた500文字の
  error文言+失敗banner、という最悪ケース)でも`skeleton_cost`は2,311
  文字であり、本番で使う値(6000)には十分な余裕がある — この限界に
  当たるのはfuzzテストで用いたような意図的に小さい`char_budget`
  (300文字程度以下)のみで、production値では再現しない。
- error/no-level/seriesの「予算が尽きたら0件でも表示を打ち切る」という
  設計は、AC3が求める「省略した事実を明示する」ことと両立する。ただし
  「1件も表示できなくても構わないので必ず注記だけは出す」側へ優先順位を
  倒しているため、極端な予算不足時は「N件中0件のみ表示」という注記だけの
  本文になりうる(1回目是正時にあった「最低1件は表示する」という補助則は
  この3回目是正でも復活させていない — その補助則自体が「予算に余裕が
  あるように見えても実は注記の余地がない」という今回の欠陥と同じ構造の
  リスクを持つため)。

IPv4アドレス秘匿について(requirement §5「秘匿の保証はIPv4リテラルに
限る」、2026-09-04 Yoshinobu決定。EXEC-030により安全境界の緩和は
Yoshinobuの判断事項):
error行の全文はLokiに保存された生のログ本文であり、送信元machineの実装
次第でIPv4リテラルを含みうる(例: Sophosのdrop/deny行、DHCPリース関連の
journal行)。job/hostラベルもIP形式でありうる(実測: network-devicesの
AP/スイッチはIPアドレスをhostラベルに使うことがある)。このrepoの
`feedback_no_ip_in_repo.md` はpublic GitHub repo自体にIPを書かないという
制約で、Slack #info チャンネルへの送信は直接には対象外だが、(1) Slackの
内容は後からexport・screenshot・転記されうる、(2) このrepo全体がIPリテ
ラルを一切書かない運用を徹底しており、通知本文だけ例外にすると一貫性が
崩れる、という2点から、**送信前に一律で伏せる**方針を採る。正規表現
ベースの機械的な検出であり、IPv4以外(IPv6、意図的な難読化)は対象外。
ドット区切り4個の数値からなるバージョン文字列など非IPの4-tuple数値も
同じ形のため誤って伏せることがある — 過剰検出を許容し、見逃しより誤検出
を選ぶ(既知の限界としてrequirement実装記録に記載する)。

秘密値一般(IPv4以外のcredential/token)について: **requirement §5が
「秘匿の保証は機械的に検出できるIPv4リテラルに限る」と明示的に定めており、
この関数のIPv4一律マスクはその契約をそのまま満たす。** IPv4以外の
credential/tokenがerror本文に混じって#infoへ出る可能性は、実装で埋める
べき欠落ではなく、**requirement §5がYoshinobuの判断で受容すると明記した
残存リスクである**(§5「採らなかった案」参照。EXEC-030の安全境界緩和は
Coordinatorが受容できる範囲を超えるため、実装側でこれ以上の検出を追加
することも、追加を怠っていることもない — 契約どおりの状態)。
"""
import re

_IPV4_RE = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
_IP_REDACTED = "[ip-redacted]"

DEFAULT_CHAR_BUDGET = 6000
DEFAULT_MAX_LINE = 300

# `[取得失敗] <理由>`のような固定メッセージ行に対する保険的な上限。
# collectorのエラー文字列は基本的に短い定型句だが、Lokiが返した値の
# `repr()`を含む経路(_parse_countの型違いエラー等)では理論上長くなり
# うるため、念のため切り詰める。この上限を適用した後の**正確な文字列**を
# skeleton(固定部)の一部として一度だけ計算し、そのまま再利用する。
_FAILURE_MESSAGE_MAX_LEN = 500


def syslog_weekly_digest_redact_ipv4(text):
    """Replace IPv4-shaped dotted-quad substrings with a fixed placeholder."""
    if text is None:
        return text
    return _IPV4_RE.sub(_IP_REDACTED, str(text))


def _mask(value):
    return syslog_weekly_digest_redact_ipv4(value if value is not None else "")


def _clamp(text, limit=_FAILURE_MESSAGE_MAX_LEN):
    text = text if text is not None else ""
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def _format_series_row(row, with_level=True):
    if with_level:
        return "- job={job} host={host} level={level} : {count}".format(
            job=_mask(row.get("job", "")),
            host=_mask(row.get("host", "")),
            level=_mask(row.get("level", "")),
            count=row.get("count", 0),
        )
    return "- job={job} host={host} : {count}".format(
        job=_mask(row.get("job", "")),
        host=_mask(row.get("host", "")),
        count=row.get("count", 0),
    )


def _format_error_entry(entry, max_line):
    """Format+mask a single error entry, then cap the RESULT to max_line.

    requirement §6.3是正(finding 1): 300文字の上限は、ts/job/hostを前置し
    IPv4をマスクした後の最終文字列に対して適用する(生のログ本文だけを
    300で切ると、前置・マスクぶんで最終行が上限を超えるため)。
    """
    prefix = "{ts} [{job}/{host}] ".format(
        ts=entry.get("ts", ""),
        job=_mask(entry.get("job", "")),
        host=_mask(entry.get("host", "")),
    )
    body = _mask(entry.get("line", ""))
    formatted = prefix + body
    if len(formatted) > max_line:
        formatted = formatted[: max_line - 3] + "..."
    return formatted


def _fit_lines(candidate_lines, budget):
    """Greedily include candidate_lines while their cumulative length (each
    +1 for the joining newline) stays within budget. Returns the list of
    lines that fit -- never more than what genuinely fits, so the caller
    can rely on sum(len(l)+1 for l in result) <= max(budget, 0).
    """
    budget = max(budget, 0)
    shown = []
    used = 0
    for line in candidate_lines:
        added = len(line) + 1
        if used + added > budget:
            break
        shown.append(line)
        used += added
    return shown


def _render_truncatable_section(add, consume, remaining_fn, candidate_lines, declared_total, note_builder):
    """Render as many candidate_lines as fit, GUARANTEEING that a
    truncation note is shown whenever fewer than declared_total items end
    up represented -- whether that shortfall is already baked into the
    data (declared_total > len(candidate_lines), e.g. the error_entries
    list already being shorter than error_total.count due to the two
    Loki queries' timing skew) or caused by this function's own budget
    trimming (not all of candidate_lines fits).

    2026-09-04是正3回目(Coordinator再現): 旧`_fit_section`+`_add_note`は
    「全候補が予算に収まるか」だけを見て注記の要否を決めていたため、
    候補自体が(データの時点で)既に真の総数より少ない場合 —
    予算にはまだ十分な余裕があるのに — 注記が一切出ないまま「全部
    表示できた」と誤認していた。ここでは「候補件数 < declared_total」
    という事実そのものを最初に見るため、その欠陥の構造ごと塞ぐ。

    アルゴリズム: (a) 何も欠けていないと分かっている場合
    (declared_total <= len(candidate_lines))だけ、注記なしで全件表示を
    試す高速経路を使う。全部入りきればそれで終わり。(b) それ以外は、
    「表示件数Nの本文 + その時点のNで組み立てた注記」の両方が
    remaining_fn()に収まる最大のNを、貪欲な最大値から1件ずつ減らしながら
    探す。見つかった時点でN件の本文とその注記を**両方**出力する。1件も
    見つからなければ何も出力しない(既知の限界、module docstring参照)。

    note_builder(shown_count) -> 注記文字列 or None。呼び出し側は
    「shown_countしか見せられない場合の注記」をここで組み立てて返す
    (件数や理由がshown_countに依存するため、探索の各ステップで都度
    呼び出す)。declared_total<=len(candidate_lines)かつ全件表示できる
    ときは呼ばれない。

    戻り値: 実際に表示した candidate_lines の件数(shown_count)。
    呼び出し元が「実際にどのcandidateが表示されたか」を
    `candidate_lines[:戻り値]` で正確に取り出せるようにするため
    (文字列パターンマッチで復元する必要をなくす)。
    """
    total_candidates = len(candidate_lines)
    budget = max(remaining_fn(), 0)

    if declared_total <= total_candidates:
        # 何も既に欠けてはいない(候補自体が真の総数を満たしている) --
        # 注記の余地を予約せず、まず全件表示を試す。
        shown = _fit_lines(candidate_lines, budget)
        if len(shown) == total_candidates:
            for line in shown:
                add(line)
            consume(sum(len(line) + 1 for line in shown))
            return total_candidates

    # 何かが欠けている(データの時点で、または予算不足で)-- 表示件数Nを
    # 貪欲な最大値から1件ずつ減らし、「N件の本文+その注記」が両方収まる
    # 最大のNを探す。
    shown_count = len(_fit_lines(candidate_lines, budget))
    while shown_count >= 0:
        shown = candidate_lines[:shown_count]
        body_cost = sum(len(line) + 1 for line in shown)
        note = note_builder(shown_count)
        note_cost = (len(note) + 1) if note else 0
        if body_cost + note_cost <= budget:
            for line in shown:
                add(line)
            consume(body_cost)
            if note:
                add(note)
                consume(note_cost)
            return shown_count
        shown_count -= 1
    # shown_count が -1 まで下がった: 0件+注記すら収まらない極端な予算
    # 不足。本体・注記とも出さない(既知の限界、module docstring参照)。
    return 0


def syslog_weekly_digest_render_message(
    data,
    char_budget=DEFAULT_CHAR_BUDGET,
    max_line=DEFAULT_MAX_LINE,
):
    """Render the full Slack-bound digest body from the collector's raw JSON.

    requirement §4 AC2/AC3, §6.3(是正版、2026-09-04是正3回目)。

    設計(module docstring参照): 固定行(header・見出し・区切りの空行・
    `[取得失敗]`/`0件でした`等のプレースホルダ・hit_query_limit注記・
    末尾の失敗banner)を実データから確定して`skeleton_cost`を正確に求め、
    `content_budget = char_budget - skeleton_cost`を series → no-level →
    error の順に`_render_truncatable_section()`で可変長コンテンツへ割り
    当てる。**`char_budget`は通知全体(3セクション+固定行すべて)の累積
    文字数に対して効き、この関数が返す文字列の長さは実測で`char_budget`
    以下になる**(既知の限界は module docstring 参照)。**1件でも省略が
    あれば、その事実を伝える注記が必ず本文へ出る**(3回目是正でこの
    不変条件をアルゴリズム構造そのもので保証するよう作り直した)。

    - series (job×host×level) テーブルの行数上限は`data.series.limit`
      (collectorが実際に適用した値)を読んで通知文へ反映する — この
      関数自身は上限値の定数を持たない。
    - levelラベルを持たない系統の内訳は、上表に実際に表示された行の
      部分集合(見出しの「件数は上表の内訳と同じ」を文字どおり守る)。
    - error全文の1行はフォーマット+マスク後に max_line 文字以下へ切り
      詰める。
    - Loki問い合わせが失敗したセクションは `[取得失敗] <理由>` を出す
      (理由もマスク・長さの保険的な切り詰めを通す)。
    - 収集が一部失敗した場合(data.ok is false)、末尾に警告文を追加する。

    戻り値は文字列1本。関数の最後で全体をもう一度
    `syslog_weekly_digest_redact_ipv4` に通す(単一の取りこぼし防止層)。
    """
    window = data.get("window", {}) or {}
    series = data.get("series", {}) or {}
    error_total = data.get("error_total", {}) or {}
    error_entries_block = data.get("error_entries", {}) or {}

    series_ok = bool(series.get("ok"))
    all_series_rows = series.get("rows", []) or [] if series_ok else []
    series_has_rows = series_ok and bool(all_series_rows)
    series_failure_line = None
    if not series_ok:
        series_failure_line = "[取得失敗] {}".format(_mask(_clamp(series.get("error") or "(no error)")))

    # no_levelがプレースホルダ("(該当なし)")固定になるか、可変長コンテンツ
    # になりうるかは、series全体(まだ予算で切られる前)にlevel無し行が
    # 1件でもあるかどうかで決まる(series側が予算で切られた結果ゼロ件に
    # なる可能性はあるが、その場合でも「候補はあった」ので可変長セクション
    # として扱い、切り詰め注記を出す)。
    has_any_no_level_row = any(r.get("level") == "(no level label)" for r in all_series_rows)
    no_level_has_rows = series_ok and has_any_no_level_row
    total_no_level = sum(1 for r in all_series_rows if r.get("level") == "(no level label)")

    error_ok = bool(error_total.get("ok")) and bool(error_entries_block.get("ok"))
    total_error_count = error_total.get("count", 0) if error_ok else 0
    error_has_rows = error_ok and total_error_count != 0
    error_failure_line = None
    if not error_ok:
        error_failure_line = "[取得失敗] error_total: {} / error_entries: {}".format(
            _mask(_clamp(error_total.get("error") or "(no error)")),
            _mask(_clamp(error_entries_block.get("error") or "(no error)")),
        )
    hit_query_limit_line = None
    if error_ok and error_has_rows and error_entries_block.get("hit_query_limit"):
        hit_query_limit_line = "(注: Loki問い合わせ自体の取得件数上限 {} にも達しています)".format(
            error_entries_block.get("query_limit")
        )

    header_line = "対象期間: {since} 〜 {until} (JST、直近{days}日)".format(
        since=window.get("since", ""), until=window.get("until", ""), days=window.get("days", "")
    )
    failure_banner = None
    if not data.get("ok", False):
        failure_banner = (
            "*** このダイジェストは一部のLoki問い合わせに失敗した状態で"
            "送信されています。上記の[取得失敗]箇所を確認し、必要なら"
            "手動でmonnieのLokiを確認してください。 ***"
        )

    # --- skeleton_cost: 可変長コンテンツの選別より先に確定する固定行 ----
    skeleton_lines = [
        header_line,
        "",
        "--- job×host×level 件数 ---",
    ]
    if not series_ok:
        skeleton_lines.append(series_failure_line)
    elif not series_has_rows:
        skeleton_lines.append("(該当ログなし)")
    skeleton_lines.append("")
    skeleton_lines.append("--- levelラベルを持たない系統(件数は上表の内訳と同じ) ---")
    if not series_ok:
        skeleton_lines.append(series_failure_line)
    elif not no_level_has_rows:
        skeleton_lines.append("(該当なし)")
    skeleton_lines.append("")
    skeleton_lines.append("--- error 全文(level=error) ---")
    if not error_ok:
        skeleton_lines.append(error_failure_line)
    elif not error_has_rows:
        skeleton_lines.append("対象期間中、level=error の行は0件でした。")
    if hit_query_limit_line:
        skeleton_lines.append(hit_query_limit_line)
    if failure_banner:
        skeleton_lines.append("")
        skeleton_lines.append(failure_banner)

    skeleton_cost = sum(len(l) + 1 for l in skeleton_lines)
    content_budget = [max(char_budget - skeleton_cost, 0)]  # mutable cell

    def content_remaining():
        return content_budget[0]

    def consume_content(amount):
        content_budget[0] = max(content_budget[0] - amount, 0)

    # downstream予約(fuzzテストで発見した派生ケースへの対応、2026-09-04
    # 是正3回目): `_render_truncatable_section`はセクション単体では
    # 「注記なしで省略しない」を保証するが、series・no-level・errorが
    # 同じcontent_budgetを順番に奪い合う設計そのものは変えていない。
    # series単体の候補行数がcontent_budget全体を上回るほど多い場合
    # (例: 165件の短いseries行だけで6000字近くを使い切る)、seriesの
    # 貪欲な最大化がno-level/errorに何も残さず、それらのセクションが
    # 「0件表示・注記も出せない」まま完全に空白になりうることをfuzz
    # テストで発見した — 表示はしていないが理由も示さない、という点で
    # 元のfinding 1と同じ性質の欠陥である。
    #
    # 対策: 後続セクションが何かを報告しうる(has_rows)場合、そのセクション
    # の番が来るまで`_DOWNSTREAM_MIN_RESERVE`ぶんを手前のセクションから
    # 見えない予算として隠しておく。手前のセクションは自分の取り分の中で
    # 最大化してよいが、この隠し分までは食い潰せない。実際に消費しなかった
    # 分は後続セクションへ順に引き継がれる(内部的にはcontent_budgetから
    # 引いていないため、自然に繰り越される)。
    _DOWNSTREAM_MIN_RESERVE = 300
    downstream_reserve_after_series = (_DOWNSTREAM_MIN_RESERVE if no_level_has_rows else 0) + (
        _DOWNSTREAM_MIN_RESERVE if error_has_rows else 0
    )
    downstream_reserve_after_no_level = _DOWNSTREAM_MIN_RESERVE if error_has_rows else 0

    def series_remaining():
        return max(content_remaining() - downstream_reserve_after_series, 0)

    def no_level_remaining():
        return max(content_remaining() - downstream_reserve_after_no_level, 0)

    # --- assemble the real output, resolving each variable section against
    # the shared content_budget in order (series -> no-level -> error) ----
    lines = []

    def add(text):
        lines.append(text)

    add(header_line)
    add("")

    add("--- job×host×level 件数 ---")
    series_rows_shown = []
    if not series_ok:
        add(series_failure_line)
    elif not series_has_rows:
        add("(該当ログなし)")
    else:
        candidate_lines = [_format_series_row(r, with_level=True) for r in all_series_rows]
        declared_total_series = series.get("total_count", len(all_series_rows))

        def series_note_builder(shown_count, _candidates=candidate_lines):
            reasons = []
            if series.get("truncated"):
                reasons.append(
                    "collectorの件数上限{}件への到達".format(series.get("limit", declared_total_series))
                )
            if shown_count < len(_candidates):
                reasons.append("文字数予算{}字への到達".format(char_budget))
            if not reasons:
                reasons.append("原因不明")
            return (
                "[TRUNCATED] series は{total}件中{shown}件のみ表示"
                "({reason}により残りは省略)".format(
                    total=declared_total_series, shown=shown_count, reason="・".join(reasons)
                )
            )

        shown_count = _render_truncatable_section(
            add, consume_content, series_remaining, candidate_lines, declared_total_series, series_note_builder
        )
        series_rows_shown = all_series_rows[:shown_count]
    add("")

    add("--- levelラベルを持たない系統(件数は上表の内訳と同じ) ---")
    if not series_ok:
        add(series_failure_line)
    elif not no_level_has_rows:
        add("(該当なし)")
    else:
        no_level_candidates = [
            _format_series_row(r, with_level=False)
            for r in series_rows_shown
            if r.get("level") == "(no level label)"
        ]
        # series_rows_shown 自体が予算で切られていて no-level 候補が
        # total_no_level より少ないこともある(series側の切り詰めが
        # no-levelの行も道連れにした場合)。declared_total を
        # all_series_rows 基準の total_no_level(候補生成元の
        # series_rows_shownより広い、真の全体集合)にすることで、この
        # ケースでも「本当は足りていない」ことを検出できる。

        def no_level_note_builder(shown_count):
            return (
                "[TRUNCATED] levelラベルを持たない系統は{total}件中{shown}件のみ表示"
                "(文字数予算{budget}字への到達により残りは省略)".format(
                    total=total_no_level, shown=shown_count, budget=char_budget
                )
            )

        _render_truncatable_section(
            add, consume_content, no_level_remaining, no_level_candidates, total_no_level, no_level_note_builder
        )
    add("")

    add("--- error 全文(level=error) ---")
    if not error_ok:
        add(error_failure_line)
    elif not error_has_rows:
        add("対象期間中、level=error の行は0件でした。")
    else:
        entries = error_entries_block.get("entries", []) or []
        candidate_lines = [_format_error_entry(e, max_line) for e in entries]

        def error_note_builder(shown_count, _entries=entries):
            reasons = []
            if shown_count < len(_entries):
                reasons.append("文字数予算{}字への到達".format(char_budget))
            if len(_entries) < total_error_count:
                # 2026-09-04是正5回目(Coordinator再現・Coordinatorの前回
                # 指示の訂正): collector側(finding: main()の不整合検出)が
                # `error_total > len(entries)`を通すのは`hit_query_limit`
                # が真の場合だけに限定された(理由が観測できない食い違いは
                # collectorがfail-closedにするため、ここへは到達しない)。
                # したがってこの分岐へ来る時点で理由は`hit_query_limit`
                # (ERROR_QUERY_LIMIT到達)だと分かっており、旧版の
                # 「Lokiから取得できた件数(collector側)が総数に届いていない
                # こと」という**理由を決め打ちしない曖昧な文言**ではなく、
                # 実際の理由(query limitの値)を名指しする。3回目是正時は
                # 「文字数予算に到達したため」という**誤った理由**が出る
                # ケースをCoordinatorが再現しており、この書き方も同じ誤りを
                # 生まないよう、憶測(タイミング差など)を理由に含めない。
                reasons.append(
                    "Loki問い合わせ自体の取得件数上限{}件への到達".format(
                        error_entries_block.get("query_limit")
                    )
                )
            if not reasons:
                reasons.append("原因不明")
            return (
                "[TRUNCATED] error全文は{total}件中{shown}件のみ表示"
                "({reason}により残りは省略)".format(
                    total=total_error_count, shown=shown_count, reason="・".join(reasons)
                )
            )

        _render_truncatable_section(
            add, consume_content, content_remaining, candidate_lines, total_error_count, error_note_builder
        )
        if hit_query_limit_line:
            add(hit_query_limit_line)

    if failure_banner:
        add("")
        add(failure_banner)

    message = "\n".join(lines)
    # 単一の取りこぼし防止層(module docstring参照)。上のコードパスは
    # すでにjob/host/line/エラー文字列を個別にマスクしているため、通常
    # ここで置換が発生することはない。将来この関数へ新しいフィールドが
    # 追加され、そのフィールドを_mask()に通し忘れた場合の保険。
    return syslog_weekly_digest_redact_ipv4(message)


class FilterModule(object):
    def filters(self):
        return {
            "syslog_weekly_digest_redact_ipv4": syslog_weekly_digest_redact_ipv4,
            "syslog_weekly_digest_render_message": syslog_weekly_digest_render_message,
        }
