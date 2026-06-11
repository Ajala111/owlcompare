"""MkDocs hook that overlays the custom landing page on the built site.

After `mkdocs build` runs, the site_dir contains Material's docs index at
site/index.html. This hook replaces it with the hand-written marketing
landing page from site_src/index.html.

Runs on both `mkdocs build` and `mkdocs serve`, so local development and
deployed builds show the same homepage. The publish workflow no longer
needs a manual copy step — the hook does it during build.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

log = logging.getLogger("mkdocs.hooks.overlay_landing_page")


def on_post_build(config) -> None:
    site_dir = Path(config["site_dir"])
    # site_src/index.html lives at the project root relative to mkdocs.yml,
    # which is the directory containing the config file.
    config_file = Path(config["config_file_path"])
    landing_source = config_file.parent / "site_src" / "index.html"

    if not landing_source.exists():
        log.warning(
            "Landing page source not found at %s; skipping overlay.",
            landing_source,
        )
        return

    landing_dest = site_dir / "index.html"
    shutil.copyfile(landing_source, landing_dest)
    log.info("Overlaid custom landing page from %s", landing_source)
