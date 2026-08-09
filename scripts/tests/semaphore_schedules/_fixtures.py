"""Shared fixture builders for semaphore_schedules filter plugin tests.

Shapes mirror the requirement's 2026-08-09 real-API measurements
(docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md
§6, §6.5) exactly -- these are not invented shapes. Names, ids and cron
values below are made-up-but-realistic stand-ins; docs/ai/core.md forbids
real internal IPs in this repo and none appear here.

Every function returns a fresh object on each call (no shared mutable
defaults), so tests can freely mutate what they get back without
affecting other tests.
"""


def catalog_entry(name, template, cron, active, task_params=None):
    if task_params is None:
        task_params = {'environment': '{}'}
    return {
        'name': name,
        'template': template,
        'cron': cron,
        'active': active,
        'task_params': task_params,
    }


def baseline_catalog():
    """2 entries whose names, resolved templates, and cron/active/
    task_params all agree exactly with baseline_observed_schedules() /
    baseline_detail_by_id() / baseline_observed_templates() -- a preflight
    run against this baseline (in either phase) returns zero errors, and a
    diff run against it returns everything "unchanged".
    """
    return [
        catalog_entry(
            'SAFE: Time sync check', 'SAFE: Time sync check', '50 5 * * *', True,
        ),
        catalog_entry(
            'SAFE: Authy healthcheck daily', 'SAFE: Authy healthcheck daily', '30 6 * * *', False,
            task_params={'environment': '{"debug_level": 4}'},
        ),
    ]


def baseline_observed_templates():
    return [
        {
            'id': 10, 'name': 'SAFE: Time sync check',
            'playbook': 'playbooks/time_sync_check.yml',
            'arguments': [], 'survey_vars': [], 'description': '',
        },
        {
            'id': 11, 'name': 'SAFE: Authy healthcheck daily',
            'playbook': 'playbooks/authy_healthcheck.yml',
            'arguments': [], 'survey_vars': [], 'description': '',
        },
    ]


def baseline_observed_schedules():
    """Shape: GET /api/project/<n>/schedules list rows -- no task_params,
    has tpl_name (requirement §6.5, real 2.18.4 measurement).
    """
    return [
        {
            'active': True, 'cron_format': '50 5 * * *', 'delete_after_run': False,
            'id': 21, 'name': 'SAFE: Time sync check', 'project_id': 3,
            'repository_id': None, 'template_id': 10,
            'tpl_name': 'SAFE: Time sync check', 'type': '',
        },
        {
            'active': False, 'cron_format': '30 6 * * *', 'delete_after_run': False,
            'id': 22, 'name': 'SAFE: Authy healthcheck daily', 'project_id': 3,
            'repository_id': None, 'template_id': 11,
            'tpl_name': 'SAFE: Authy healthcheck daily', 'type': '',
        },
    ]


def baseline_observed_by_name(observed_schedules=None):
    """The shape semaphore_schedules_preflight actually returns as
    `observed_by_name` -- the list-GET rows keyed by `name`. Callers of
    semaphore_schedules_diff() pass this, never the raw list.
    """
    if observed_schedules is None:
        observed_schedules = baseline_observed_schedules()
    return {row['name']: row for row in observed_schedules}


def baseline_detail_by_id():
    """Shape: GET /api/project/<n>/schedules/<id> single rows -- has
    task_params, no tpl_name (requirement §6.5, real 2.18.4 measurement).
    """
    return {
        21: {
            'active': True, 'cron_format': '50 5 * * *', 'delete_after_run': False,
            'id': 21, 'name': 'SAFE: Time sync check', 'project_id': 3,
            'repository_id': None, 'task_params': {'environment': '{}'},
            'template_id': 10, 'type': '',
        },
        22: {
            'active': False, 'cron_format': '30 6 * * *', 'delete_after_run': False,
            'id': 22, 'name': 'SAFE: Authy healthcheck daily', 'project_id': 3,
            'repository_id': None,
            'task_params': {'environment': '{"debug_level": 4}'},
            'template_id': 11, 'type': '',
        },
    }


def baseline_template_ids():
    return {'SAFE: Time sync check': 10, 'SAFE: Authy healthcheck daily': 11}


# The 4 distinct task_params shapes actually observed across all 19 real
# ansy schedules (2026-08-09, Coordinator fetched each with a single GET
# and ran the batch through semaphore_schedules_preflight). Not written
# down anywhere in the requirement (6.5 only measured 3 named keys exist
# and that unknown keys are silently dropped by the API on write -- it did
# not record that `environment`'s decoded values are strings, or that
# `params` is a distinct, natively-typed top-level key). The first version
# of the R9(7) allowlist (2026-08-09, independent review High #3) rejected
# 3 of these 4 shapes -- every real schedule with a non-empty
# `environment` -- which would have made closed-world unreachable (R17
# requires 0 unmanaged, but these are real, already-running schedules that
# must be transcribable into the catalog).
REAL_TASK_PARAMS_FIXTURES = [
    {'environment': '{}'},                                    # 16 of 19
    {'environment': '{"force_renew":"false"}'},                # 1 of 19
    {'environment': '{"dry_run":"true"}'},                     # 1 of 19
    {
        'environment': '{"dry_run":"true"}',
        'params': {'debug_level': 4, 'dry_run': False},
    },                                                          # 1 of 19
]


# 実測19件(requirement 2026-08-09、稼働中の cron 文字列そのもの)。
VALID_CRON_FIXTURES = [
    '30 5 * * *', '35 5 * * *', '45 5 * * *', '40 5 * * *', '30 3 * * *', '30 17 * * 5',
    '00 06 * * 6', '0 6 * * 0', '15 18 * * 5', '10 0 1 * *', '30 18 28 * *', '30 18 * * 5',
    '0 18 * * 4', '50 5 * * *', '0 17 * * 5', '15 18 2 * *', '5 17 * * 5', '30 6 * * *',
    '40 0 * * *',
]

# 当該版が拒否すると期待される代表値。grammar の実測確定は test_plan へ引き継ぎ
# (requirement §9) -- ここでは「標準5フィールドcronとして明らかに不正」なものだけ。
INVALID_CRON_FIXTURES = [
    '30 5 * * * *',   # 6 フィールド
    '30 5 * *',       # 4 フィールド
    '',                # 空文字列
    None,              # 文字列でない
    '60 5 * * *',      # 分が範囲外
    '30 24 * * *',     # 時が範囲外
    '30 5 32 * *',     # 日が範囲外
    '30 5 * 13 *',     # 月が範囲外
    '30 5 * * 8',      # 曜日が範囲外
    'abc 5 * * *',     # 数値でないトークン
    '30 5 * * mon',    # 名前付き曜日(この grammar は非対応)
]
