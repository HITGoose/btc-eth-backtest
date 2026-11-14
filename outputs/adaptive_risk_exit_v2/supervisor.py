from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys

OUT = Path(__file__).resolve().parent


def run(job):
    year, asset = job
    folder = OUT / str(year) / asset
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'run.log').open('w') as log:
        result = subprocess.run([sys.executable, str(OUT / 'worker.py'), str(year), asset],
                                stdout=log, stderr=subprocess.STDOUT)
    print(year, asset, result.returncode, flush=True)
    return result.returncode


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(pool.map(run, [(y, a) for y in (2024, 2025) for a in ('BTC', 'ETH')]))
    sys.exit(1 if any(codes) else 0)
