from pathlib import Path
import numpy as np
from restore_early_gaps import restore

def normalize(rows,expected,step,asset,year,out,d,r):
 extra=rows[~np.isin(rows[:,0],expected)]
 unique,counts=np.unique(rows[:,0],return_counts=True);duplicates=unique[counts>1]
 days=set((extra[:,0]//86400).astype(int).tolist())
 days.update((duplicates//86400).astype(int).tolist())
 if not days:return rows
 # Rebuild every aligned bar of affected UTC days from complete real trade IDs;
 # never shift an irregular timestamp or discard its underlying prices.
 keep=~np.isin((rows[:,0]//86400).astype(int),list(days));clean=rows[keep]
 d.dump(out/str(year)/f'{asset}_{step}s_offgrid_reconstruction.json',dict(off_grid_rows=len(extra),duplicate_timestamps=len(duplicates),UTC_days=list(sorted(days)),method='Entire affected UTC day rebuilt on canonical grid from same-venue complete aggTrades; no timestamp shifting'))
 return restore(clean,expected,step,asset,year,out,d,r)
