"""Offline fixtures only: no production hosts, quory commands or HTTP."""
import copy
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'roles/quory_health_monthly'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


logic = load('ansible.module_utils.quory_health', ROOT / 'module_utils/quory_health.py')
files = load('ansible.module_utils.quory_health_files', ROOT / 'module_utils/quory_health_files.py')
archive = load('quory_health_archive', ROOT / 'library/quory_health_archive.py')
notion = load('quory_health_notion', ROOT / 'library/quory_health_notion.py')
collector = load('quory_collect', ROOT / 'files/quory_collect.py')

THRESHOLDS = dict(fs_warning=80, fs_critical=90, mem_warning=15, mem_critical=5,
                   wear_warning=80, wear_critical=100, fs_growth_warning_points=10,
                   mem_drop_warning_points=10, swap_growth_warning_bytes=104_857_600)


def df(size=500_000_000_000, used=25_000_000_000, mountpoint='/', source='/dev/nvme0n1p2', fstype='ext4',
      pcent=None):
    avail = size - used
    raw_pcent = pcent if pcent is not None else str(round(used * 100 / size)) + "%"
    return {"mountpoint": mountpoint, "source": source, "fstype": fstype,
            "size_bytes": str(size), "used_bytes": str(used), "avail_bytes": str(avail),
            "use_percent_raw": raw_pcent}


def meminfo(total=16_000_000_000, available=14_000_000_000, swap_total=4_000_000_000, swap_free=4_000_000_000):
    return {"MemTotal": total, "MemAvailable": available, "SwapTotal": swap_total, "SwapFree": swap_free}


def device(namespace='/dev/nvme0n1', serial='fixture-serial', count=5, percent_used=1, spare=100):
    return {"namespace": namespace,
            "identity": {"rc": 0, "json": {"sn": serial, "mn": "fixture-model"}},
            "health": {"rc": 0, "json": {"critical_warning": 0, "temperature": 313,
                       "avail_spare": spare, "spare_thresh": 10, "percent_used": percent_used,
                       "media_errors": 0, "num_err_log_entries": count}}}


def lsblk_ok():
    return {"rc": 0, "json": {"blockdevices": []}}


def observation(root=None, efi=None, memory=None, devices=None, nvme_transport_observed=True, lsblk=None,
                lsblk_valid=True):
    return {"schema_version": 1, "collected_at": "2026-09-13T08:00:00+09:00",
            "filesystems": {"root": root or df(), "efi": efi or df(mountpoint='/boot/efi', fstype='vfat',
                                                                     size=500_000_000, used=50_000_000)},
            "memory": memory if memory is not None else meminfo(),
            "lsblk": lsblk if lsblk is not None else lsblk_ok(), "lsblk_valid": lsblk_valid,
            "devices": devices if devices is not None else [device()],
            "nvme_transport_observed": nvme_transport_observed}


def report(baseline=None, previous=None, obs=None, **kwargs):
    return logic.build_report({'quory': obs or observation()}, 'fixture-report',
                              '2026-09-13T08:00:00+09:00', baseline, previous, **{**THRESHOLDS, **kwargs})


def issue_codes(result, host='quory'):
    return [code for _, code, _ in result['hosts'][host]['issues']]


class FakeClient:
    def __init__(self):
        self.posts, self.patches, self.pages = 0, [], {}
        self.lose_create = False

    def call(self, method, path, body=None):
        if method == 'POST':
            self.posts += 1
            rows = copy.deepcopy(body['children'])
            for i, block in enumerate(rows):
                block['id'] = 'block-' + str(i)
            self.pages['page'] = rows
            if self.lose_create:
                raise notion.PublishError('response_unknown')
            return {'id': 'page'}
        self.patches.append((path, body))
        return {}

    def children(self, page):
        if page == 'parent':
            return [{'id': 'page', 'child_page': {'title': 'quoryヘルス月次点検 2026-09'}}] if self.pages else []
        return self.pages[page]


class BuildReportTests(unittest.TestCase):
    def test_healthy_report_has_ok_status_and_rc_relevant_health(self):
        result = report()
        self.assertEqual(result['health'], 'OK')
        self.assertEqual(result['collection'], 'ok')
        self.assertEqual(result['hosts']['quory']['devices'][0]['comparison'], 'baseline')

    def test_filesystem_usage_warning_and_critical_thresholds(self):
        warn = report(obs=observation(root=df(size=100, used=85)))
        self.assertEqual(warn['health'], 'WARNING')
        crit = report(obs=observation(root=df(size=100, used=95)))
        self.assertEqual(crit['health'], 'CRITICAL')

    # --- Major #1: judge and display df's own use% field; never recompute --------
    def test_uses_dfs_own_percent_even_when_it_disagrees_with_used_over_size(self):
        # used/size would compute 10%, but df itself reports 95% (e.g. reserved
        # blocks skew the ratio). The stored/displayed percent must be df's.
        result = report(obs=observation(root=df(size=1000, used=100, pcent='95%')))
        fs = result['hosts']['quory']['filesystems']['root']
        self.assertEqual(fs['use_percent'], 95)
        self.assertEqual(result['health'], 'CRITICAL')

    def test_malformed_df_percent_is_unknown_not_a_silent_pass(self):
        result = report(obs=observation(root=df(pcent='n/a')))
        self.assertEqual(result['health'], 'UNKNOWN')
        self.assertEqual(result['hosts']['quory']['filesystems']['root']['collection'], 'error')
        self.assertIn('root: df usage percent unparsable', issue_codes(result))

    def test_missing_df_percent_field_is_unknown(self):
        raw = df()
        del raw['use_percent_raw']
        result = report(obs=observation(root=raw))
        self.assertEqual(result['hosts']['quory']['filesystems']['root']['collection'], 'error')

    def test_memory_available_warning_and_critical_thresholds(self):
        warn = report(obs=observation(memory=meminfo(total=100, available=14)))
        self.assertEqual(warn['health'], 'WARNING')
        crit = report(obs=observation(memory=meminfo(total=100, available=4)))
        self.assertEqual(crit['health'], 'CRITICAL')

    def test_swap_used_is_total_minus_free_not_a_separate_probe(self):
        result = report(obs=observation(memory=meminfo(swap_total=4_000_000_000, swap_free=1_000_000_000)))
        self.assertEqual(result['hosts']['quory']['memory']['swap_used_bytes'], 3_000_000_000)

    def test_missing_filesystem_observation_is_unknown_not_ok(self):
        obs = observation()
        obs['filesystems']['efi'] = {'error': 'not_mounted', 'actual_mount': '/'}
        result = report(obs=obs)
        self.assertEqual(result['health'], 'UNKNOWN')
        self.assertEqual(result['hosts']['quory']['collection'], 'error')

    # --- Major #6: an EFI path silently answered by the root filesystem --------
    def test_efi_not_mounted_is_unknown_never_reported_as_root_values(self):
        obs = observation(efi={'error': 'not_mounted', 'actual_mount': '/'})
        result = report(obs=obs)
        efi = result['hosts']['quory']['filesystems']['efi']
        self.assertEqual(efi['collection'], 'error')
        self.assertNotIn('use_percent', efi)

    # --- Major #5: one filesystem's failure must not erase other successes -----
    def test_efi_failure_still_preserves_root_and_memory_and_devices(self):
        obs = observation(efi={'error': 'not_mounted', 'actual_mount': '/'})
        result = report(obs=obs)
        entry = result['hosts']['quory']
        self.assertEqual(entry['collection'], 'error')  # job still fails (AC4)
        self.assertEqual(entry['filesystems']['root']['collection'], 'ok')
        self.assertEqual(entry['filesystems']['root']['use_percent'], 5)
        self.assertEqual(entry['memory']['collection'], 'ok')
        self.assertEqual(len(entry['devices']), 1)
        self.assertEqual(entry['devices'][0]['health_status'], 'OK')

    def test_memory_failure_does_not_erase_filesystem_results(self):
        obs = observation(memory={'MemTotal': 100})  # missing required keys
        result = report(obs=obs)
        entry = result['hosts']['quory']
        self.assertEqual(entry['collection'], 'error')
        self.assertEqual(entry['filesystems']['root']['collection'], 'ok')
        self.assertEqual(entry['memory']['collection'], 'error')

    # --- Major #4 / 006 Major#3: lsblk enumeration validity is a single ---------
    #     collector-owned signal (lsblk_valid); module_utils must trust it
    #     rather than re-derive validity from rc/json shape, which previously
    #     let rc=0 + {} (no blockdevices key) pass as "zero NVMe, healthy".
    def test_lsblk_failure_is_unknown_not_confused_with_no_nvme_present(self):
        result = report(obs=observation(lsblk={'rc': 1, 'error': 'CommandFailed'}, lsblk_valid=False, devices=[],
                                        nvme_transport_observed=False))
        entry = result['hosts']['quory']
        self.assertIsNone(entry['nvme_transport_observed'])
        self.assertEqual(result['health'], 'UNKNOWN')
        self.assertIn('NVMe device enumeration unavailable', issue_codes(result))

    def test_lsblk_invalid_json_is_also_unknown(self):
        result = report(obs=observation(lsblk={'rc': 0, 'error': 'InvalidJSON'}, lsblk_valid=False, devices=[]))
        self.assertIsNone(result['hosts']['quory']['nvme_transport_observed'])
        self.assertEqual(result['health'], 'UNKNOWN')

    def test_lsblk_rc0_with_empty_payload_is_unknown_not_zero_devices(self):
        # 006 Major#3 repro: rc=0 but the JSON has no `blockdevices` key at all
        # (e.g. {}). Must not be read as "we enumerated zero disks".
        result = report(obs=observation(lsblk={'rc': 0, 'json': {}}, lsblk_valid=False, devices=[],
                                        nvme_transport_observed=None))
        self.assertIsNone(result['hosts']['quory']['nvme_transport_observed'])
        self.assertEqual(result['health'], 'UNKNOWN')
        self.assertEqual(result['hosts']['quory']['collection'], 'error')

    def test_no_nvme_transport_observed_with_working_lsblk_is_ok_not_unknown(self):
        result = report(obs=observation(devices=[], nvme_transport_observed=False))
        self.assertFalse(result['hosts']['quory']['nvme_transport_observed'])
        self.assertEqual(result['hosts']['quory']['devices'], [])
        self.assertEqual(result['health'], 'OK')

    def test_nvme_tool_unavailable_is_unknown_never_healthy(self):
        obs = observation(devices=[{"namespace": "/dev/nvme0n1",
                                     "identity": {"rc": -1, "error": "FileNotFoundError"},
                                     "health": {"rc": -1, "error": "FileNotFoundError"}}])
        result = report(obs=obs)
        self.assertEqual(result['health'], 'UNKNOWN')
        device_out = result['hosts']['quory']['devices'][0]
        self.assertEqual(device_out['health_status'], 'UNKNOWN')
        self.assertEqual(device_out['reason'], 'tool_unavailable')
        self.assertEqual(result['hosts']['quory']['collection'], 'ok')

    def test_device_comparison_progression(self):
        base_report = report()
        baseline = {'schema_version': 1, 'report_id': 'baseline', 'collected_at': base_report['collected_at'],
                    'hosts': {'quory': base_report['hosts']['quory']}}
        compared = report(baseline=baseline, obs=observation(devices=[device(count=7)]))
        dev = compared['hosts']['quory']['devices'][0]
        self.assertEqual(dev['comparison'], 'compared')
        self.assertEqual(dev['delta']['num_err_log_entries'], 2)
        self.assertEqual(compared['health'], 'WARNING')

        reset = report(baseline=baseline, obs=observation(devices=[device(count=1)]))
        self.assertEqual(reset['hosts']['quory']['devices'][0]['comparison'], 'reset_suspected')
        self.assertEqual(reset['health'], 'WARNING')

        replaced = report(baseline=baseline, obs=observation(devices=[device(serial='new-serial')]))
        self.assertEqual(replaced['hosts']['quory']['devices'][0]['comparison'], 'replacement_or_added')
        self.assertEqual(replaced['health'], 'WARNING')

    # --- Major #2: filesystem/memory/swap must compare against the previous ----
    #     successful observation, not just NVMe counters.
    def test_filesystem_and_memory_compare_against_previous_successful_report(self):
        first = report(obs=observation(root=df(size=1000, used=100, pcent='10%'),
                                       memory=meminfo(total=100, available=50, swap_total=10, swap_free=10)))
        previous = {'quory': first}
        second = report(previous=previous, swap_growth_warning_bytes=1,
                        obs=observation(root=df(size=1000, used=250, pcent='25%'),
                                        memory=meminfo(total=100, available=30, swap_total=10, swap_free=5)))
        fs = second['hosts']['quory']['filesystems']['root']
        self.assertEqual(fs['comparison'], 'compared')
        self.assertEqual(fs['delta']['use_percent'], 15)
        self.assertIn('root: usage grew notably since last comparison', issue_codes(second))

        mem = second['hosts']['quory']['memory']
        self.assertEqual(mem['comparison'], 'compared')
        self.assertAlmostEqual(mem['delta']['available_percent'], -20.0)
        self.assertIn('memory available dropped notably since last comparison', issue_codes(second))
        self.assertIn('swap usage grew notably since last comparison', issue_codes(second))
        self.assertEqual(second['health'], 'WARNING')

    # --- 008 Major#1: swap's own growth issue must carry SWAP's prior/current/ --
    #     delta/comparison-source — not the unrelated memory-available% note,
    #     which uses different units and can look like it's describing swap.
    def test_swap_growth_issue_shows_swaps_own_prior_current_delta_and_source(self):
        first = logic.build_report(
            {'quory': observation(memory=meminfo(total=1_000_000_000, available=500_000_000,
                                                  swap_total=1_000_000_000, swap_free=950_000_000))},
            'swap-source-id', '2026-09-13T08:00:00+09:00', **THRESHOLDS)
        previous = {'quory': first}
        second = logic.build_report(
            {'quory': observation(memory=meminfo(total=1_000_000_000, available=500_000_000,
                                                  swap_total=1_000_000_000, swap_free=750_000_000))},
            'swap-current-id', '2026-09-13T08:05:00+09:00', None, previous,
            **{**THRESHOLDS, 'mem_drop_warning_points': 100})  # isolate the swap issue from the mem-drop one
        mem = second['hosts']['quory']['memory']
        self.assertEqual(mem['swap_used_bytes'], 250_000_000)
        self.assertEqual(mem['delta']['swap_used_bytes'], 200_000_000)
        swap_issue = next(item for item in second['hosts']['quory']['issues']
                          if item[1] == 'swap usage grew notably since last comparison')
        detail = swap_issue[2]
        # Both swap values, in swap's own bytes — not the memory-available %.
        self.assertIn('50000000 bytes', detail)  # prior swap usage
        self.assertIn('250000000 bytes', detail)  # current swap usage
        self.assertIn('+200000000 bytes', detail)  # delta
        self.assertIn('swap-source-id', detail)  # comparison source ID
        self.assertNotIn('%', detail)  # must not be the memory-available% note

        summary = logic.short_summary(second)
        self.assertIn('50000000 bytes', summary)
        self.assertIn('250000000 bytes', summary)
        self.assertIn('swap-source-id', summary)

    # --- 006 Major#2: an absolute-threshold breach must still carry comparison --
    #     source and delta, not just the bare current value.
    def test_absolute_threshold_issue_includes_comparison_source_and_delta(self):
        first = report(obs=observation(root=df(size=1000, used=900, pcent='90%')))
        previous = {'quory': first}
        # fs_growth_warning_points high enough that the separate "grew notably"
        # issue does not fire, isolating the absolute-threshold issue's own detail.
        second = report(previous=previous, fs_growth_warning_points=100,
                        obs=observation(root=df(size=1000, used=950, pcent='95%')))
        codes = second['hosts']['quory']['issues']
        root_issue = next(item for item in codes if item[1] == 'root: filesystem usage threshold')
        self.assertIn('90%', root_issue[2])
        self.assertIn('95%', root_issue[2])
        self.assertIn('+5', root_issue[2])

    # --- 007 Major#2: comparison text must include the comparison-source ------
    #     report ID itself, not only its date/time (which is only minute-
    #     precision and cannot disambiguate multiple runs within the same
    #     minute), so the source can be uniquely identified from the short
    #     report / Markdown alone.
    def test_short_summary_and_markdown_include_comparison_source_report_id(self):
        first = logic.build_report({'quory': observation(root=df(size=1000, used=900, pcent='90%'))},
                                   'source-report-id', '2026-09-13T08:00:00+09:00', **THRESHOLDS)
        previous = {'quory': first}
        second = logic.build_report({'quory': observation(root=df(size=1000, used=950, pcent='95%'))},
                                    'current-report-id', '2026-09-13T08:05:00+09:00', None, previous,
                                    **{**THRESHOLDS, 'fs_growth_warning_points': 100})
        source_id = second['hosts']['quory']['filesystems']['root']['comparison_source']['report_id']
        self.assertEqual(source_id, 'source-report-id')
        summary = logic.short_summary(second)
        self.assertIn('source-report-id', summary)
        self.assertIn('current-report-id', summary)  # the report's own ID (header) is also present
        body = logic.markdown(second)
        self.assertIn('source-report-id', body)

    def test_memory_absolute_threshold_issue_includes_comparison_source_and_delta(self):
        first = report(obs=observation(memory=meminfo(total=100, available=20)))
        previous = {'quory': first}
        second = report(previous=previous, mem_drop_warning_points=100,
                        obs=observation(memory=meminfo(total=100, available=4)))
        mem_issue = next(item for item in second['hosts']['quory']['issues']
                         if item[1] == 'memory available threshold')
        self.assertIn('20.0%', mem_issue[2])
        self.assertIn('4.0%', mem_issue[2])

    def test_small_filesystem_and_memory_changes_do_not_trigger_growth_warnings(self):
        first = report()
        previous = {'quory': first}
        second = report(previous=previous, obs=observation(root=df(size=500_000_000_000, used=25_500_000_000)))
        self.assertEqual(second['health'], 'OK')

    def test_history_corrupt_forces_unknown_and_marks_devices_and_filesystems(self):
        result = report(history_error=True)
        self.assertEqual(result['health'], 'UNKNOWN')
        self.assertEqual(result['hosts']['quory']['devices'][0]['comparison'], 'history_corrupt')
        self.assertEqual(result['hosts']['quory']['filesystems']['root']['comparison'], 'history_corrupt')
        self.assertEqual(result['hosts']['quory']['memory']['comparison'], 'history_corrupt')

    def test_endurance_and_critical_warning_thresholds(self):
        crit = report(obs=observation(devices=[device(percent_used=100)]))
        self.assertEqual(crit['health'], 'CRITICAL')
        spare = report(obs=observation(devices=[device(spare=5)]))
        self.assertEqual(spare['health'], 'CRITICAL')

    def test_markdown_and_short_summary_do_not_crash_and_mention_report_id(self):
        result = report()
        body = logic.markdown(result)
        summary = logic.short_summary(result)
        self.assertIn('fixture-report', body)
        self.assertIn('fixture-report', summary)
        self.assertIn('quory', summary)

    # --- Major #3: Slack short summary must show ID/host/values and never ------
    #     drop CRITICAL/UNKNOWN items behind a truncation count.
    def test_short_summary_never_truncates_critical_or_unknown_items(self):
        obs = observation(
            root=df(size=100, used=95),  # CRITICAL
            efi={'error': 'not_mounted', 'actual_mount': '/'},  # UNKNOWN
            memory=meminfo(total=100, available=4),  # CRITICAL
            devices=[device(spare=5), device(namespace='/dev/nvme1n1', serial='second', spare=5)],
        )
        result = report(obs=obs)
        summary = logic.short_summary(result)
        urgent_count = sum(1 for level, _, _ in result['hosts']['quory']['issues'] if level in ('CRITICAL', 'UNKNOWN'))
        self.assertGreaterEqual(urgent_count, 4)
        for level, code, _ in result['hosts']['quory']['issues']:
            if level in ('CRITICAL', 'UNKNOWN'):
                self.assertIn(logic.issue_text(code), summary)
        self.assertNotIn('ほか', summary.split('ほか(WARNING)')[0] if 'ほか(WARNING)' in summary else summary)

    def test_short_summary_caps_only_warning_items(self):
        first = report(obs=observation(
            root=df(size=1000, used=100, pcent='10%'),
            efi=df(mountpoint='/boot/efi', fstype='vfat', size=1000, used=100, pcent='10%'),
            memory=meminfo(total=100, available=50, swap_total=10, swap_free=10)))
        previous = {'quory': first}
        # Four independent WARNING-only signals: fs growth (root), fs growth
        # (efi), memory available drop, swap usage growth.
        obs = observation(
            root=df(size=1000, used=250, pcent='25%'),
            efi=df(mountpoint='/boot/efi', fstype='vfat', size=1000, used=250, pcent='25%'),
            memory=meminfo(total=100, available=30, swap_total=10, swap_free=5),
        )
        second = report(previous=previous, swap_growth_warning_bytes=1, obs=obs)
        warning_issues = [i for i in second['hosts']['quory']['issues'] if i[0] == 'WARNING']
        self.assertGreaterEqual(len(warning_issues), 4)
        summary = logic.short_summary(second)
        self.assertIn('ほか(WARNING)', summary)


class ArchiveTests(unittest.TestCase):
    def test_first_run_creates_baseline_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, body = archive.archive(tmp, {'quory': observation()}, THRESHOLDS)
            root = Path(tmp)
            self.assertTrue((root / (result['report_id'] + '.json')).exists())
            self.assertTrue((root / (result['report_id'] + '.md')).exists())
            self.assertTrue((root / (result['month'] + '.baseline.json')).exists())
            self.assertIn(result['report_id'], body)

    # --- 006 Major#1: a judgment-failed (health=UNKNOWN) report must never ------
    #     become the next run's fs/memory comparison source or seed the device
    #     baseline, even though its own `collection` is 'ok' (NVMe-tool-
    #     unavailable does not fail `collection`, only `health`).
    def test_unknown_health_report_is_excluded_from_future_fs_mem_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            failed_obs = observation(
                root=df(size=1000, used=900, pcent='90%'),
                devices=[{"namespace": "/dev/nvme0n1", "identity": {"rc": -1, "error": "FileNotFoundError"},
                         "health": {"rc": -1, "error": "FileNotFoundError"}}])
            first, _ = archive.archive(tmp, {'quory': failed_obs}, THRESHOLDS)
            self.assertEqual(first['health'], 'UNKNOWN')
            self.assertEqual(first['hosts']['quory']['collection'], 'ok')  # collection ok, health UNKNOWN

            second, _ = archive.archive(
                tmp, {'quory': observation(root=df(size=1000, used=950, pcent='95%'))}, THRESHOLDS)
            fs = second['hosts']['quory']['filesystems']['root']
            self.assertEqual(fs['comparison'], 'baseline')
            self.assertNotIn('comparison_source', fs)

    def test_unknown_health_report_does_not_seed_the_device_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            failed_obs = observation(
                devices=[{"namespace": "/dev/nvme0n1", "identity": {"rc": -1, "error": "FileNotFoundError"},
                         "health": {"rc": -1, "error": "FileNotFoundError"}}])
            archive.archive(tmp, {'quory': failed_obs}, THRESHOLDS)
            second, _ = archive.archive(tmp, {'quory': observation(devices=[device()])}, THRESHOLDS)
            dev = second['hosts']['quory']['devices'][0]
            self.assertEqual(dev['comparison'], 'baseline')

    # --- 007 Major#1: a report whose OWN host-local data looks healthy but ------
    #     whose overall judgment is UNKNOWN because of history corruption must
    #     still be excluded — the per-host health check alone is not enough.
    def test_history_corrupt_report_is_excluded_even_though_host_itself_looks_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.mkdir(exist_ok=True)
            bogus_id = '20260101T000000000000+0900-' + ('b' * 32)
            bogus_path = root / (bogus_id + '.json')
            bogus_path.write_text('{"not": "valid"}', encoding='utf-8')
            first, _ = archive.archive(tmp, {'quory': observation(root=df(size=1000, used=100, pcent='10%'))},
                                       THRESHOLDS)
            self.assertTrue(first['history_error'])
            self.assertEqual(first['hosts']['quory']['health'], 'OK')  # host-local data looks fine
            self.assertEqual(first['health'], 'UNKNOWN')  # but the report as a whole is judgment-failed

            bogus_path.unlink()  # clear the corruption so the second run's OWN history read is clean
            second, _ = archive.archive(tmp, {'quory': observation(root=df(size=1000, used=950, pcent='95%'))},
                                        THRESHOLDS)
            self.assertFalse(second['history_error'])
            fs = second['hosts']['quory']['filesystems']['root']
            self.assertEqual(fs['comparison'], 'baseline')
            self.assertNotIn('comparison_source', fs)

    def test_second_run_compares_devices_against_frozen_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive.archive(tmp, {'quory': observation(devices=[device(count=5)])}, THRESHOLDS)
            second, _ = archive.archive(tmp, {'quory': observation(devices=[device(count=6)])}, THRESHOLDS)
            dev = second['hosts']['quory']['devices'][0]
            self.assertEqual(dev['comparison'], 'compared')
            self.assertEqual(dev['delta']['num_err_log_entries'], 1)

    def test_second_run_compares_filesystem_and_memory_against_previous_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive.archive(tmp, {'quory': observation(root=df(size=1000, used=100, pcent='10%'))}, THRESHOLDS)
            second, _ = archive.archive(
                tmp, {'quory': observation(root=df(size=1000, used=300, pcent='30%'))}, THRESHOLDS)
            fs = second['hosts']['quory']['filesystems']['root']
            self.assertEqual(fs['comparison'], 'compared')
            self.assertEqual(fs['delta']['use_percent'], 20)

    def test_corrupt_history_file_is_detected_and_marks_history_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.mkdir(exist_ok=True)
            bogus_id = '20260101T000000000000+0900-' + ('a' * 32)
            (root / (bogus_id + '.json')).write_text('{"not": "valid"}', encoding='utf-8')
            result, _ = archive.archive(tmp, {'quory': observation()}, THRESHOLDS)
            self.assertTrue(result['history_error'])
            self.assertEqual(result['health'], 'UNKNOWN')

    def test_check_mode_preview_does_not_write_files(self):
        module_cls = archive.AnsibleModule

        class Halt(Exception):
            pass

        class FakeCheckModule:
            check_mode = True
            params = {'operation': 'collect', 'observations': {'quory': observation()},
                      'thresholds': THRESHOLDS, 'directory': '', 'report_id': ''}
            exited = None

            def exit_json(self, **kwargs):
                self.exited = kwargs
                raise Halt()  # AnsibleModule.exit_json terminates the process; emulate that here.

            def fail_json(self, **kwargs):
                raise AssertionError('should not fail: ' + str(kwargs))

        fake = FakeCheckModule()
        archive.AnsibleModule = lambda argument_spec, supports_check_mode: fake
        try:
            with tempfile.TemporaryDirectory() as tmp:
                fake.params['directory'] = tmp
                with self.assertRaises(Halt):
                    archive.main()
                self.assertIsNotNone(fake.exited)
                self.assertFalse(fake.exited['changed'])
                self.assertEqual(list(Path(tmp).iterdir()), [])
        finally:
            archive.AnsibleModule = module_cls


class NotionTests(unittest.TestCase):
    def test_publish_refuses_when_parent_is_unconfirmed(self):
        with self.assertRaises(notion.PublishError) as ctx:
            notion.publish(Path('/tmp'), report(), '', FakeClient())
        self.assertEqual(str(ctx.exception), 'parent_unconfirmed')

    def test_publish_creates_then_reuses_existing_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = FakeClient()
            result = report()
            files.save_json(root / (result['report_id'] + '.json'), result)
            url = notion.publish(root, result, 'parent', client)
            self.assertEqual(client.posts, 1)
            self.assertTrue(url.startswith('https://www.notion.so/'))

            second = report()
            second['report_id'] = 'fixture-report-2'
            second['collected_at'] = '2026-09-13T09:00:00+09:00'
            files.save_json(root / (second['report_id'] + '.json'), second)
            notion.publish(root, second, 'parent', client)
            # Same month, same page: no second page creation.
            self.assertEqual(client.posts, 1)

    def test_older_report_is_refused_to_avoid_rolling_back_the_published_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = FakeClient()
            newer = report()
            newer['collected_at'] = '2026-09-13T09:00:00+09:00'
            files.save_json(root / (newer['report_id'] + '.json'), newer)
            notion.publish(root, newer, 'parent', client)

            older = report()
            older['report_id'] = 'older-report'
            older['collected_at'] = '2026-09-13T07:00:00+09:00'
            files.save_json(root / (older['report_id'] + '.json'), older)
            with self.assertRaises(notion.PublishError) as ctx:
                notion.publish(root, older, 'parent', client)
            self.assertEqual(str(ctx.exception), 'older_report_refused')

    def test_check_mode_and_suppress_never_touch_network_or_disk(self):
        class Halt(Exception):
            pass

        class FakeModule:
            check_mode = True
            params = {'directory': '/nonexistent', 'report_id': 'x', 'parent': 'parent',
                      'token_file': '/nonexistent/token', 'suppress': False}
            exited = None

            def exit_json(self, **kwargs):
                self.exited = kwargs
                raise Halt()  # AnsibleModule.exit_json terminates the process; emulate that here.

            def fail_json(self, **kwargs):
                raise AssertionError('should not fail under check mode: ' + str(kwargs))

        fake = FakeModule()
        module_cls = notion.AnsibleModule
        notion.AnsibleModule = lambda argument_spec, supports_check_mode: fake
        try:
            with self.assertRaises(Halt):
                notion.main()
            self.assertEqual(fake.exited, {'changed': False, 'publication': 'suppressed', 'url': ''})
        finally:
            notion.AnsibleModule = module_cls


class CollectorTests(unittest.TestCase):
    """Exercise the collector's own mount-verification logic (Major #6)."""

    def test_df_entry_reports_not_mounted_when_findmnt_disagrees(self):
        def fake_run(argv):
            if argv[0] == 'findmnt':
                return {'rc': 0, 'stdout': '/\n'}  # /boot/efi resolves to root, not itself
            raise AssertionError('df should not be invoked once the mount mismatch is detected')

        with patch.object(collector, 'run', side_effect=fake_run):
            result = collector.df_entry('/boot/efi')
        self.assertEqual(result['error'], 'not_mounted')
        self.assertEqual(result['actual_mount'], '/')

    def test_df_entry_proceeds_when_findmnt_confirms_the_mount(self):
        def fake_run(argv):
            if argv[0] == 'findmnt':
                return {'rc': 0, 'stdout': '/boot/efi\n'}
            return {'rc': 0, 'stdout': 'SOURCE FSTYPE 1B-blocks Used Avail Use%\n'
                                       '/dev/sda15 vfat 100 10 90 10%\n'}

        with patch.object(collector, 'run', side_effect=fake_run):
            result = collector.df_entry('/boot/efi')
        self.assertNotIn('error', result)
        self.assertEqual(result['use_percent_raw'], '10%')

    def test_df_entry_reports_not_mounted_when_findmnt_itself_fails(self):
        with patch.object(collector, 'run', return_value={'rc': 1, 'stdout': ''}):
            result = collector.df_entry('/boot/efi')
        self.assertEqual(result['error'], 'not_mounted')
        self.assertIsNone(result['actual_mount'])

    # --- Coordinator follow-up (2026-09-13): nvme_namespaces() must check rc ---
    #     itself, not rely on decoded() never attaching `json` when rc != 0.
    #     A non-zero rc with a structurally-valid (even empty) payload must
    #     still raise — it must never be read as "checked, zero devices".
    def test_nvme_namespaces_raises_when_rc_nonzero_even_with_well_formed_empty_json(self):
        with self.assertRaises(ValueError):
            collector.nvme_namespaces({'rc': 1, 'json': {'blockdevices': []}})

    def test_nvme_namespaces_raises_when_rc_nonzero_even_with_well_formed_devices_json(self):
        with self.assertRaises(ValueError):
            collector.nvme_namespaces({'rc': 1, 'json': {'blockdevices': [
                {'name': '/dev/nvme0n1', 'type': 'disk'}]}})

    def test_collect_marks_lsblk_invalid_when_lsblk_command_itself_fails(self):
        def fake_run(argv):
            if argv[0] == 'findmnt':
                return {'rc': 0, 'stdout': '/\n'}
            if argv[0] == 'df':
                return {'rc': 0, 'stdout': 'SOURCE FSTYPE 1B-blocks Used Avail Use%\n'
                                           '/dev/sda1 ext4 100 10 90 10%\n'}
            if argv[0] == 'lsblk':
                return {'rc': 1, 'stdout': ''}  # command failed; decoded() attaches no `json`
            raise AssertionError('unexpected command: ' + str(argv))

        with patch.object(collector, 'run', side_effect=fake_run):
            result = collector.collect()
        self.assertFalse(result['lsblk_valid'])
        self.assertIsNone(result['nvme_transport_observed'])
        self.assertEqual(result['devices'], [])

    def test_build_report_treats_lsblk_rc_failure_as_unknown_not_zero_devices(self):
        # End-to-end: even if some future caller assembled a raw observation
        # with lsblk_valid computed incorrectly from json shape alone (rc
        # ignored), the collector's own nvme_namespaces() must have already
        # refused to call the payload valid — this pins that contract at the
        # unit actually responsible for it, matching the collect()-level test
        # above but exercised through build_report's consumption of the flag.
        result = report(obs=observation(lsblk={'rc': 1, 'json': {'blockdevices': []}}, lsblk_valid=False,
                                        devices=[], nvme_transport_observed=None))
        self.assertIsNone(result['hosts']['quory']['nvme_transport_observed'])
        self.assertEqual(result['health'], 'UNKNOWN')
        self.assertEqual(result['hosts']['quory']['collection'], 'error')

    # --- 006 Major#3: rc=0 with a payload missing `blockdevices` must never ----
    #     be silently read as "zero NVMe devices enumerated".
    def test_nvme_namespaces_raises_when_blockdevices_key_is_absent(self):
        with self.assertRaises(ValueError):
            collector.nvme_namespaces({'rc': 0, 'json': {}})

    def test_nvme_namespaces_raises_on_malformed_row(self):
        with self.assertRaises(ValueError):
            collector.nvme_namespaces({'rc': 0, 'json': {'blockdevices': ['not-an-object']}})

    # --- 007 Major#3: a present-but-empty row {} must not read as "checked, ----
    #     not NVMe" — we asked for exactly NAME,TYPE so both must be strings.
    def test_nvme_namespaces_raises_on_row_missing_name_and_type(self):
        with self.assertRaises(ValueError):
            collector.nvme_namespaces({'rc': 0, 'json': {'blockdevices': [{}]}})

    def test_collect_marks_lsblk_invalid_when_row_missing_name_and_type(self):
        def fake_run(argv):
            if argv[0] == 'findmnt':
                return {'rc': 0, 'stdout': '/\n'}
            if argv[0] == 'df':
                return {'rc': 0, 'stdout': 'SOURCE FSTYPE 1B-blocks Used Avail Use%\n'
                                           '/dev/sda1 ext4 100 10 90 10%\n'}
            if argv[0] == 'lsblk':
                return {'rc': 0, 'stdout': '{"blockdevices": [{}]}'}
            raise AssertionError('unexpected command: ' + str(argv))

        with patch.object(collector, 'run', side_effect=fake_run):
            result = collector.collect()
        self.assertFalse(result['lsblk_valid'])
        self.assertIsNone(result['nvme_transport_observed'])

    def test_nvme_namespaces_accepts_a_genuinely_empty_list(self):
        self.assertEqual(collector.nvme_namespaces({'rc': 0, 'json': {'blockdevices': []}}), [])

    def test_collect_marks_lsblk_invalid_and_transport_unknown_on_empty_payload(self):
        def fake_run(argv):
            if argv[0] == 'findmnt':
                return {'rc': 0, 'stdout': '/\n' if 'efi' in argv[-1] else '/\n'}
            if argv[0] == 'df':
                return {'rc': 0, 'stdout': 'SOURCE FSTYPE 1B-blocks Used Avail Use%\n'
                                           '/dev/sda1 ext4 100 10 90 10%\n'}
            if argv[0] == 'lsblk':
                return {'rc': 0, 'stdout': '{}'}
            raise AssertionError('unexpected command: ' + str(argv))

        with patch.object(collector, 'run', side_effect=fake_run):
            result = collector.collect()
        self.assertFalse(result['lsblk_valid'])
        self.assertIsNone(result['nvme_transport_observed'])
        self.assertEqual(result['devices'], [])


if __name__ == '__main__':
    unittest.main()
