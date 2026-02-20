"""Run all seed scripts in order."""
import asyncio
import importlib
import sys
from pathlib import Path


async def run_seeds():
    seeds_dir = Path(__file__).parent
    seed_files = sorted(seeds_dir.glob("[0-9]*.py"))

    for seed_file in seed_files:
        module_name = f"seeds.{seed_file.stem}"
        print(f"\n--- Running {seed_file.name} ---")
        module = importlib.import_module(module_name)
        await module.seed()
        print(f"--- Done {seed_file.name} ---")


if __name__ == "__main__":
    asyncio.run(run_seeds())
