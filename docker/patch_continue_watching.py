#!/usr/bin/env python3
"""Patch bundled Stremio Web so Continue Watching centre Play resumes safely.

Upstream ContinueWatchingItem -> LibItem creates onPlayClick only when Core provides
deepLinks.player. The handler already carries the exact StreamBucket source and Core
resume position. Keep normal poster/details navigation untouched; mark only a click
inside Continue Watching's play overlay so MetaItem's parent click handler does not
also navigate to details/streams after React handles Play.
"""
from __future__ import annotations

import pathlib
import sys

BUILD = pathlib.Path("/srv/stremio-server/build")
MARKER = "stremio-webadmin: continue-watching-centre-play"

INJECTION = r"""
;/* stremio-webadmin: continue-watching-centre-play */
(()=>{if(window.__stremioWebadminContinueWatchingCentrePlay)return;
window.__stremioWebadminContinueWatchingCentrePlay=true;
document.addEventListener("click",e=>{
 const t=e.target instanceof Element?e.target:null;if(!t)return;
 const play=t.closest('[class*="play-icon-layer"]');if(!play)return;
 const poster=play.closest('[class*="poster-change-cursor"]');if(!poster)return;
 e.selectPrevented=true;
},true);})();
"""


def patch_text(text: str) -> tuple[str, int]:
    if MARKER in text:
        return text, 0
    return text + INJECTION, 1


def main() -> int:
    files = sorted(BUILD.rglob("scripts/main.js"))
    if len(files) != 1:
        print(f"[web-player] continue-watching patch skipped: main.js count={len(files)}")
        return 0

    path = files[0]
    text = path.read_text(encoding="utf-8")
    patched, status = patch_text(text)
    if status == 1:
        path.write_text(patched, encoding="utf-8")
        print(
            "[web-player] Continue Watching centre Play uses Core player "
            f"without parent stream navigation ({path})"
        )
    else:
        print("[web-player] continue-watching patch already applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
