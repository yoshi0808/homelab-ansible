# Role routing index (fixture: check2 model/effort mismatch)

`.claude/agents/sample.md` declares `effort: high`, but this table below
still says `medium` — deliberately left out of sync for
`scripts/check-doc-consistency.py` check2.

| Role | model | effort | 根拠 |
| --- | --- | --- | --- |
| Sample | sonnet | medium | fixture |
