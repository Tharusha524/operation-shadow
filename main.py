"""OPERATION SHADOW - start the game.

    python main.py                 play
    python main.py --autotest      automated play-test (opens the window, exits by itself)
"""
from __future__ import annotations

import argparse
import logging
import sys

from config.settings import SettingsStore
from core.paths import user_data_dir


def setup_logging():
    log_dir = user_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(log_dir / "game.log", mode="w", encoding="utf-8")],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Operation Shadow")
    parser.add_argument("--autotest", action="store_true", help="run the automated play-test and exit")
    parser.add_argument("--screenshots", default=None, help="folder for autotest screenshots")
    parser.add_argument("--views", action="store_true", help="with --autotest: only photograph every map's views")
    parser.add_argument("--maps", default=None, help="with --views: comma-separated map names to photograph")
    parser.add_argument("--only", default=None, help="with --autotest: run only this mission test (e.g. m04)")
    args = parser.parse_args(argv)

    setup_logging()
    # The automated test uses separate files so it never changes the player's own settings.
    store = SettingsStore(user_data_dir() / ("autotest_settings.json" if args.autotest else "settings.json"))
    settings = store.load()

    from core.game import Game, configure_engine   # imported after logging is ready
    configure_engine(settings, uncapped=args.autotest)
    autotest = {"screenshot_dir": args.screenshots, "views_only": args.views,
                "maps": args.maps.split(",") if args.maps else None, "only": args.only} if args.autotest else None
    game = Game(store, settings, autotest=autotest)
    game.run()


if __name__ == "__main__":
    main()
