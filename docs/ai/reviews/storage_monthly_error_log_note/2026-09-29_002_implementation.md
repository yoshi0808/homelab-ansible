# implementation: NVMe error-log増加を参考表示へ分離

実装日: 2026-09-29 / Implementer

## 変更

- `storage_monthly.py` のreportへ後方互換な任意配列`references`を追加した。error-log増加時に媒体エラー0かつ重大警告なしかつ予備領域がしきい値以上(差し戻し対応で追加。末尾参照)なら、issueを作らず、増分・媒体エラー0・重大警告なしを含む参考行を格納する。
- `short_summary` とMarkdown本文が`references`を表示するため、Slack短報とNotion本文にも同じ参考行が出る。参考行はhealthを決める`issues`から分離されている。
- 媒体エラーまたは重大警告がある場合の既存issue/CRITICAL、counter reset、増分なし、旧report（`references`なし）の読み取りをテストで固定した。
- Operations Contextのerror-log判定の記述を実装に合わせた。

## 検証

- `python3 -m unittest discover -s tests -p test_storage_monthly.py -v` — 22 tests passed。AC1〜AC6（正常増分の参考表示、媒体エラー/重大警告のCRITICAL、reset、増分なし、旧形式report）を含む。
- `python3 scripts/check-doc-consistency.py` — 3 checks passed。
- `git diff --check` — passed。
- `scripts/git-pre-commit-check.sh` は未実行。Implementerはstageしないため、Coordinatorがstage後に実行する。

## 未解決事項

なし。実ホスト、SSH、Gitのstage/commit/pushには触れていない。

## 差し戻し対応

- 参考行を出す条件を既存のNVMe健康CRITICAL条件と同じく、`critical_warning == 0`、`media_errors == 0`、`avail_spare >= spare_thresh`に揃えた。予備領域不足でCRITICALとなるデバイスでは、従来どおりerror-log増分のWARNINGも出し、参考行は出さない。
- 予備領域不足とerror-log増分が同時にあるfixtureを追加し、CRITICALとWARNINGの両方、参考行なしを確認した。
- `python3 -m unittest tests.test_storage_monthly -v` — 23 tests passed。実ホスト、SSH、Gitのstage/commit/pushには触れていない。
