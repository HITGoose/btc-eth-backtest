"""Only targeted mechanics + eight hours; never launches the annual pipeline."""
from pathlib import Path
import os,sys,subprocess,json
HERE=Path(__file__).resolve().parent
subprocess.run([sys.executable,str(HERE/'short_checks.py')],check=True)
keys=['REF','ATR_STOP','CANCEL','CAP5','TRAIL8','REGIME_SIZE','Q15','N05']
subprocess.run([sys.executable,str(HERE/'worker.py'),'2020','ETH',*keys,'--hours','8'],check=True)
import common as c
p=c.OUT/'smoke/REF/2020/ETH';q=json.loads((p/'result.json').read_text());m=c.np.load(p/'equity.npz')['marks'];cfg=json.loads((p/'config.json').read_text());base=c.np.load(c.ROOT/'outputs/baseline_registry/reused/ER_V2_REFERENCE/2020/ETH/equity.npz')['marks'];offset=(q['retest_start']-cfg['inputs']['start'])//60
assert c.np.array_equal(m,base[offset:offset+len(m)]),'Original V2 prefix differs'
c.dump(c.OUT/'validation_summary.json',dict(annual_replays=0,short_hours=8,independent_books=keys,original_V2_minutes_exact=True,mechanics_pass=True,extended_2026_official_data_available='NOT_TESTED_HERE_USER_COLAB_FETCH',runtime_fingerprint=c.fingerprint()))
print('8h RAW+V2 reference minute curve exact; targeted checks PASS; annual pipeline not started.')
