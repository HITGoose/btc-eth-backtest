from pathlib import Path
import os,sys,json,hashlib,importlib.util
ROOT=Path(os.environ.get('BTC_REPO_ROOT',Path(__file__).resolve().parents[2])).resolve();HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'outputs/er_v2_colab'))
import variant_engine as v
import data as D
w=v.w;s=v.s;np=v.np
OUT=Path(os.environ.get('BTC_OUTPUT_ROOT',ROOT/'colab_results/er_v2_retests')).resolve();OUT.mkdir(parents=True,exist_ok=True)
from datetime import datetime,timezone,timedelta
END2026=int(datetime(2026,11,16,tzinfo=timezone(timedelta(hours=8))).timestamp())
def digest(p):return D.sha(p)
def dump(p,q):p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(q,ensure_ascii=False,indent=2,default=lambda x:x.item()));tmp.replace(p)
def fingerprint():return hashlib.sha256(b''.join(p.read_bytes()for p in sorted(HERE.glob('*.py')))+b''.join((ROOT/'outputs/er_v2_colab'/n).read_bytes()for n in ['variant_engine.py','data.py','portable.py','run.py'])+v.BASE_FINANCIAL_FP.encode()+b''.join(p.read_bytes()for p in sorted((HERE/'history').rglob('*.py')))+(HERE/'source_manifest.json').read_bytes()+b'2026_END_BJT_20261116').hexdigest()
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def folder(key,year,asset):return OUT/'runs'/key/str(year)/asset
def existing(key,year,asset):
 for root in [OUT/'runs',OUT/'imported',HERE/'reused']:
  p=root/key/str(year)/asset
  if(p/'status.json').exists():
   st=json.loads((p/'status.json').read_text())
   if not st.get('complete'):continue
   q=json.loads((p/'result.json').read_text())
   end=q.get('retest_end')
   if end is None:
    win=q.get('window',q.get('period'));end=int(datetime.fromisoformat(win[1]).timestamp())if isinstance(win,list)else None
   if year==2026 and end!=END2026:continue
   if root==OUT/'runs':assert st['fingerprint']==fingerprint(),'Incompatible checkpoint/result: use a new run root'
   else:
    assert st['result_SHA256']==digest(p/'result.json')and st['equity_SHA256']==digest(p/'equity.npz')
   return p
 if key=='REF'and year!=2026:return ROOT/f'outputs/baseline_registry/reused/ER_V2_REFERENCE/{year}/{asset}'
 return None
def backup(p):
 dest=os.environ.get('BTC_DRIVE_RESULTS')
 if not dest:return
 import shutil
 target=Path(dest)/p.relative_to(OUT);target.mkdir(parents=True,exist_ok=True)
 for f in p.rglob('*'):
  if not f.is_file()or'temporary'in f.parts or f.suffix in ['.tmp','.zip','.part']:continue
  t=target/f.relative_to(p);t.parent.mkdir(parents=True,exist_ok=True)
  if t.exists()and t.stat().st_mtime>=f.stat().st_mtime and t.stat().st_size==f.stat().st_size:continue
  z=t.with_suffix(t.suffix+'.copying');shutil.copy2(f,z);z.replace(t)
# Parent loaders add legacy folders to sys.path; local coordinator modules must win.
sys.path.insert(0,str(HERE))
