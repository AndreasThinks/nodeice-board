#!/usr/bin/env python3
"""
Entry point for the Nodeice Board matrix display.

Usage:
    nodeice-board-matrix [--db_path=<path>] [--config_path=<path>]
                         [--emulator] [--brightness=<0-100>] [--verbose]

Runs as a separate process from the notice board itself and only reads
the board's SQLite database, so the two services are fully independent.
"""

import sys
import signal
import logging
import argparse

from nodeice_board.config import load_config, get_matrix_config
from nodeice_board.matrix.driver import create_matrix, BackendNotAvailable
from nodeice_board.matrix.app import MatrixApp

logger = logging.getLogger("NodeiceMatrix")


def parse_args():
    parser = argparse.ArgumentParser(description="Nodeice Board RGB LED matrix display")
    parser.add_argument("--db_path", default="nodeice_board.db",
                        help="Path to the Nodeice Board database file")
    parser.add_argument("--config_path", default="config.yaml",
                        help="Path to the configuration file")
    parser.add_argument("--emulator", action="store_true",
                        help="Use the RGBMatrixEmulator backend even if hardware is available")
    parser.add_argument("--brightness", type=int, default=None, metavar="0-100",
                        help="Override the configured panel brightness")
    parser.add_argument("--duration", type=float, default=None, metavar="SECONDS",
                        help="Exit after this many seconds (for testing)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = load_config(args.config_path)
    matrix_config = get_matrix_config(config)

    try:
        matrix, gfx, is_emulator = create_matrix(
            matrix_config,
            prefer_emulator=args.emulator,
            brightness_override=args.brightness,
        )
    except BackendNotAvailable as e:
        logger.error(str(e))
        sys.exit(1)

    if is_emulator:
        logger.info("Running against the emulator (browser view on http://localhost:8888 by default)")

    app = MatrixApp(
        matrix, gfx,
        db_path=args.db_path,
        poll_interval=matrix_config["poll_interval"],
    )

    def shutdown(sig, frame):
        logger.info("Shutting down matrix display...")
        app.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    app.run(duration=args.duration)


if __name__ == "__main__":
    main()
