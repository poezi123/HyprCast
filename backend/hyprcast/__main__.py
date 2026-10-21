import argparse
import asyncio

from .server import main

parser = argparse.ArgumentParser(prog="hyprcast", description="HyprCast-Backend")
parser.add_argument("--exit-with-parent", action="store_true",
                    help="beenden, sobald der startende Prozess (die App) weg ist")
args = parser.parse_args()
asyncio.run(main(exit_with_parent=args.exit_with_parent))
