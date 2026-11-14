"""Serialize only large2025 ETH worker processes; historical event clocks unchanged."""
from pathlib import Path
from contextlib import contextmanager
import fcntl
O=Path(__file__).resolve().parent
@contextmanager
def memory_guard(period,asset):
 if str(period)!='2025'or asset!='ETH':yield;return
 folder=O/'locks';folder.mkdir(exist_ok=True)
 with(folder/'ETH_2025.lock').open('a')as f:
  fcntl.flock(f,fcntl.LOCK_EX)
  try:yield
  finally:fcntl.flock(f,fcntl.LOCK_UN)
