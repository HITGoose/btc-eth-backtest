"""Quarantine corrupted download, retry official bytes; never relax validation."""
from pathlib import Path
from urllib.request import urlopen,Request
import argparse,json,hashlib,shutil,zipfile,time
OUT=Path(__file__).resolve().parent
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('path');args=parser.parse_args();file=Path(args.path).resolve();assert file.is_relative_to(OUT)
 symbol=file.name.split('-')[0];url=f'https://data.binance.vision/data/futures/um/daily/trades/{symbol}/{file.name}'
 evidence=OUT/'download_recovery'/file.stem;evidence.mkdir(parents=True,exist_ok=True);checks=[]
 if file.exists():
  sha=hashlib.sha256(file.read_bytes()).hexdigest();quarantine=evidence/(sha+'.badzip');shutil.move(file,quarantine);checks.append(dict(quarantined=str(quarantine),bytes=quarantine.stat().st_size,sha256=sha))
 expected=urlopen(url+'.CHECKSUM',timeout=30).read().decode().split()[0].lower()
 for attempt in range(3):
  target=evidence/f'fresh_{attempt}.zip'
  with urlopen(Request(url,headers={'Cache-Control':'no-cache'}),timeout=90)as response:
   headers=dict(response.headers)
   with target.open('wb')as f:shutil.copyfileobj(response,f,1024*1024)
  got=hashlib.sha256(target.read_bytes()).hexdigest();row=dict(attempt=attempt,sha256=got,official_sha256=expected,bytes=target.stat().st_size,headers=headers,match=got==expected);checks.append(row)
  (evidence/'evidence.json').write_text(json.dumps(dict(url=url,checks=checks),indent=2))
  if got==expected:
   with zipfile.ZipFile(target)as z:assert z.testzip()is None
   shutil.move(target,file);print('RECOVERED',file,got);break
 else:raise RuntimeError('Fresh official downloads still fail checksum; no results inferred')
