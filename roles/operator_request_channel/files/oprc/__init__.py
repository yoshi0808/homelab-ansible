"""oprc -- shared library for the Operator Request Channel MVP.

Deployed byte-identical to ansy and quory (plan §2.1, `copy`-only). Entry
points on both hosts import from this package and call the same functions
against the same `dlp-rules.json` / `request-schema-v1.json`, which is what
lets requirement §9.1's "same engine, same ruleset at all four inspection
points" hold structurally rather than by convention.

This module carries only version constants -- no logic -- so a quick
sanity check ("does ansy's oprc report the same version as quory's") never
has to import anything with side effects.
"""

__version__ = "1"
