"""Root conftest — runs before any package-level conftest.py.

Prepends workspace src directories to sys.path so that
`from chain.config import ...` (and similar imports in the chain/
imdbapi/ and app/ test suites) resolve to the installed packages
rather than the bare workspace root directories (chain/, imdbapi/,
app/) which would otherwise be found as namespace packages when the
workspace root is the current working directory.

This is only needed when pytest is invoked from the workspace root
(e.g. by the VSCode Python extension).  Individual `make test-*`
targets run from their own package directories and are unaffected.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent

for _src in ("chain/src", "imdbapi/src", "app/src"):
    _path = str(_ROOT / _src)
    if _path not in sys.path:
        sys.path.insert(0, _path)
