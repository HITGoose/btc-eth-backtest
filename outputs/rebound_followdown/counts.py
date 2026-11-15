from signals import *
from datetime import datetime,timezone
O=Path(__file__).resolve().parent
WINDOWS=[('2020','2020-03-08','2020-03-15'),('2021','2021-05-15','2021-05-22'),('2023','2023-08-07','2023-08-14'),('2024','2024-06-10','2024-06-17')]
if __name__=='__main__':
 rows=[]
 for y,aa,bb in WINDOWS:
  start=int(datetime.fromisoformat(aa).replace(tzinfo=timezone.utc).timestamp());end=int(datetime.fromisoformat(bb).replace(tzinfo=timezone.utc).timestamp())
  for asset in ['BTC','ETH']:
   info=z.prepare(y,asset);leg,core,new,diag,policy,pair=build(asset,info['data'],start,end);s.dump(O/'candidate_diagnostics'/f'{y}_{asset}.json',diag);rows.append(dict(period=y,asset=asset,start=start,end=end,core=len(core),new=len(new),shape_count=len(diag),range_rejections=sum(x['regime']in['range','transition']for x in diag)));print(rows[-1],flush=True)
 s.dump(O/'candidate_counts.json',rows)
