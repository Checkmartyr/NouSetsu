"""CLI package with a lazy application entry point."""


def main() -> None:
    from nousetsu.cli.app import main as run_cli

    run_cli()


__all__ = ["main"]
