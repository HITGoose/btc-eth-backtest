"""Import corrected existing FAIL/VOL only; never silently recompute earlier years."""
import common as c
from pathlib import Path
import json,shutil,zipfile,io
prior=c.module('retest_prior_runner',c.ROOT/'outputs/er_v2_colab/run.py')
EXPECTED_FP=prior.fingerprint()
def validate(folder,key,year,asset):
 old='ER_V2_FAIL_EXIT'if key=='FAIL_EXIT'else'ER_V2_VOL_SIZE';st=json.loads((folder/'status.json').read_text());cfg=json.loads((folder/'config.json').read_text())
 assert st['complete']and st['fingerprint']==cfg['fingerprint']==EXPECTED_FP,'Incorrect or superseded prior implementation (including old shifted-feature outputs)'
 m=c.D.spec(year,asset);assert cfg['input']['hashes']==m['hashes']and cfg['fee']==0 and cfg['funding']==0 and cfg['slippage']==.0002 and cfg['signals_exact']
 result=folder/'results'/f'{old}_result.json';equity=folder/'results'/f'{old}_equity.npz';q=json.loads(result.read_text());start,end=[int(c.datetime.fromisoformat(t).timestamp())for t in q['window']]
 assert(start,end)==(m['start'],c.END2026 if year==2026 else m['end']), 'Only complete requested interval accepted; Jan-Oct2026 is prefix only'
 assert q['no_OHLC_fallback']and q['fee']==0 and abs(q.get('funding_total_USDT',0))<1e-12
 marks=c.np.load(equity)['marks'];assert len(marks)==(end-start)//60 and abs(marks[-1]-q['ending_equity'])<1e-7
 assert abs(q['cash']-500-sum(x['delta']for x in q['cash_events']))<1e-7
 dest=c.OUT/'imported'/key/str(year)/asset;dest.mkdir(parents=True,exist_ok=True);shutil.copy2(result,dest/'result.json');shutil.copy2(equity,dest/'equity.npz');c.dump(dest/'status.json',dict(complete=True,source='IMPORTED_COMPLETED_CORRECTED_PARENT',parent_fingerprint=EXPECTED_FP,result_SHA256=c.digest(dest/'result.json'),equity_SHA256=c.digest(dest/'equity.npz')));c.backup(dest)
def unpack_archive(path):
 from pathlib import PurePosixPath
 root=c.OUT/'provided_prior_results'/c.digest(Path(path))[:12];root.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(path)as z:
  members=z.infolist();assert len(members)<20000 and sum(x.file_size for x in members)<2*2**30,'Unexpected archive size'
  for member in members:
   parts=PurePosixPath(member.filename);assert not parts.is_absolute()and'..'not in parts.parts
   if member.is_dir()or parts.suffix not in ['.json','.npz']:continue
   dest=root/str(parts);dest.parent.mkdir(parents=True,exist_ok=True)
   with z.open(member)as src,dest.open('wb')as out:shutil.copyfileobj(src,out)
 return root
def main():
 root=Path(c.os.environ.get('BTC_IMPORT_ROOT',c.OUT/'provided_prior_results'));errors=[];count=0
 archive=c.os.environ.get('BTC_IMPORT_ZIP')
 if archive:root=unpack_archive(archive)
 for year in range(2020,2027):
  for asset in ['BTC','ETH']:
   candidates=list(root.glob(f'**/runs/{year}/{asset}/status.json'))
   for key in ['FAIL_EXIT','VOL_SIZE']:
    if c.existing(key,year,asset):continue
    for p in candidates:
     try:validate(p.parent,key,year,asset);count+=1;break
     except (AssertionError,OSError,KeyError,ValueError)as e:errors.append(dict(year=year,asset=asset,key=key,error=str(e)))
 c.dump(c.OUT/'import_status.json',dict(imported_now=count,required_parent_fingerprint=EXPECTED_FP,diagnostics=errors,missing_is_not_zero=True));print('Imported corrected prior accounts:',count,flush=True)
if __name__=='__main__':main()
