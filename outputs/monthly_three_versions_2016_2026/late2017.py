from pathlib import Path
import importlib.util,inspect,sys,json
OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('monthly_worker',OUT/'worker.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
asset=sys.argv[1]
raw_source=inspect.getsource(w.p.DayCache).replace('class DayCache:', 'class RawDayCache:').replace("for kind,column in (('aggTrades',5),('trades',4)):", "for kind,column in (('trades',4),):")
raw_source=raw_source.replace("raw=d.read_zip(file,[0,1,column]);scale=", "raw=d.read_zip(file,[0,1,column]);assert np.all(np.diff(raw[:,0])==1), 'Raw trade IDs incomplete';scale=")
raw_ns=dict(w.p.__dict__);raw_ns['OUT']=OUT/'2017'/asset;exec(compile(raw_source,'<2017 complete raw prints only>','exec'),raw_ns);w.p.DayCache=raw_ns['RawDayCache']
w.f.OUT=OUT/'spot_inputs';w.f.OUT.mkdir(exist_ok=True)
source=inspect.getsource(w.f.prepare).replace('datetime(year,1,1,tzinfo=r.TZ)','datetime(year,11,1,tzinfo=r.TZ)')
from normalize_early import normalize
old="  if len(missing) or len(extra) or len(np.unique(rows[:,0]))!=len(rows):"
new="  if len(extra) or len(np.unique(rows[:,0]))!=len(rows):\n   rows=normalize(rows,expected,step,asset,year,OUT,d,r);missing=np.setdiff1d(expected,rows[:,0]);extra=np.setdiff1d(rows[:,0],expected)\n"+old
source=source.replace(old,new)
ns=dict(w.f.__dict__);ns['normalize']=normalize;exec(compile(source,'<same spot acquisition, full November-December2017 window>','exec'),ns);w.f.prepare=ns['prepare']
w.main(2017,asset)
folder=OUT/'2017'/asset
status=folder/'status.json'
if status.exists() and json.loads(status.read_text()).get('completed'):
 c=json.loads((folder/'config.json').read_text());c.update(full_year=False,coverage='2017 November-December only');w.d.dump(folder/'config.json',c)
