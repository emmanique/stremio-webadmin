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

# The execution profile is persisted by the dedicated transcoding profile API.
# Register it with the generic configuration model so an already persisted
# profile is not treated as an unknown setting. Keep it read-only here because
# profile changes must pass the runtime capability validation.
legacy.DEFAULTS.setdefault("transcoding_profile", "")
legacy.DESCRIPTIONS.setdefault(
    "transcoding_profile",
    "Perfil de execução FFmpeg selecionado pelo painel Simple transcoding.",
)
legacy.READ_ONLY.add("transcoding_profile")

# Transcoding execution parameters are controlled by the verified profile UI.
# The generic All Configuration page must not overwrite hardware detection or
# profile-derived execution settings.
legacy.READ_ONLY.update({
    "transcoding_profile",
    "transcoding_mode",
    "transcoding_hwaccel",
    "transcoding_vaapi_device",
    "transcoding_video_codec",
    "transcoding_hw_decode",
})
