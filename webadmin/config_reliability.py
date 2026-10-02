"""WebAdmin configuration reliability fixes.

Loaded last in the WebAdmin extension chain so configuration keys used by the
UI are registered before requests are handled. This keeps the generic
/api/config validator strict while allowing the logging mode exposed by the UI.
"""
from __future__ import annotations

import app as legacy
import transcoding_verified_status as base

# The Logs page persists this key through PUT /api/config.  The UI has exposed
# it for a long time, but it was missing from DEFAULTS, so the strict validator
# returned HTTP 400 ("unknown settings: debug_logs").
legacy.DEFAULTS.setdefault("debug_logs", False)
legacy.DESCRIPTIONS.setdefault(
    "debug_logs",
    "Activa logging detalhado para diagnóstico; requer reinício do servidor.",
)

app = base.app
