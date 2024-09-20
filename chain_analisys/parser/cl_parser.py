"""Command line parser."""

import argparse


def build_argument_parser() -> argparse.ArgumentParser:
    """Parse command line strings."""
    parser = argparse.ArgumentParser(add_help=True)

    parser.add_argument(
        "--config-dir",
        required=True,
        type=str,
        help="path to configuration files directory",
        dest="config_dir",
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        required=False,
        help="log level",
        dest="log_level",
    )

    return parser
