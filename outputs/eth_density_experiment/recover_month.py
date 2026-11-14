"""Targeted official same-market monthly backup check; never edits a price."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json,zipfile,hashlib,shutil,time,csv
import strategy as s
OUT=s.OUT;folder=OUT/'recovery_20250829_ETH';folder.mkdir(exist_ok=True)
url='https://data.binance.vision/data/futures/um/monthly/trades/ETHUSDT/ETHUSDT-trades-2025-08.zip';archive=folder/'ETHUSDT-trades-2025-08.zip'
required=2168800971+600_000_000;assert shutil.disk_usage(folder).free>required,'Insufficient disk for targeted monthly ZIP plus filtered day'
try:
 for attempt in range(4):
  try:meta=s.d.acquire(url,archive);break
  except Exception:
   if attempt==3:raise
   time.sleep(2+attempt)
 (folder/'monthly_source.json').write_text(json.dumps(meta,indent=2));print('DOWNLOADED',meta,flush=True)
 lower=int(datetime(2025,8,29,tzinfo=timezone.utc).timestamp()*1000);upper=lower+86400000;out=folder/'ETHUSDT-trades-2025-08-29-monthly.csv'
 count=0;bad_id=0;bad_time=0;prior_id=None;prior_tm=None;samples=[];seen=0
 with zipfile.ZipFile(archive)as z:
  member=max((x for x in z.infolist()if x.filename.endswith('.csv')),key=lambda x:x.file_size)
  with z.open(member)as f,out.open('wb')as target:
   for line in f:
    if not line[:1].isdigit():
     if seen==0:target.write(line)
     continue
    seen+=1
    # Split from the right; final columns are timestamp,buyer_maker.
    tm=int(line.rsplit(b',',2)[1])
    if lower<=tm<upper:
     ID=int(line.split(b',',1)[0]);count+=1
     if prior_id is not None and ID<=prior_id:
      bad_id+=1
      if len(samples)<10:samples.append(line.decode().strip())
     if prior_tm is not None and tm<prior_tm:bad_time+=1
     prior_id=ID;prior_tm=tm;target.write(line)
    if seen%20000000==0:print('SCANNED',seen,'selected',count,flush=True)
 r=dict(official_monthly=meta,total_rows_scanned=seen,selected_day_rows=count,nonincreasing_ids=bad_id,timestamp_reversals=bad_time,sha256_filtered_day=hashlib.sha256(out.read_bytes()).hexdigest(),samples=samples,usable=count>0 and bad_id==0)
 (folder/'result.json').write_text(json.dumps(r,indent=2));print('MONTHLY_CHECK',json.dumps(r),flush=True)
 # Monthly file can be reacquired from recorded SHA; remove to free disk only
 # after the filtered day and result have been saved.
 archive.unlink()
except Exception as error:
 import traceback
 (folder/'failure.json').write_text(json.dumps(dict(error=repr(error),traceback=traceback.format_exc()),indent=2));raise
