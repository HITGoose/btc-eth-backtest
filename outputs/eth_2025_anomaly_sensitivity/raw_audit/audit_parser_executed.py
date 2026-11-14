"""Exhaustive one-file integer and Decimal audit, not a three-sample check."""
from pathlib import Path
from array import array
from decimal import Decimal,getcontext,InvalidOperation
from datetime import datetime,timezone
import csv,zipfile,json,hashlib,math,time
import numpy as np
import bridge as b
OUT=b.OUT;getcontext().prec=60

def write(path,rows,fields):
 with path.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
def audit():
 folder=OUT/'raw_audit';folder.mkdir(exist_ok=True)
 sha=hashlib.file_digest(b.ARCHIVE.open('rb'),'sha256').hexdigest();assert sha==b.EXPECTED_SHA
 with zipfile.ZipFile(b.ARCHIVE)as z:
  members=[x for x in z.namelist()if x.endswith('.csv')];assert members==['ETHUSDT-trades-2025-08-29.csv'],members
  member=members[0];digest=hashlib.sha256()
  with z.open(member)as f:
   while block:=f.read(1024*1024):digest.update(block)
  ids=array('q');times=array('q');prices=array('d');issues=[];decimal_quote_mismatch=0;n=0
  lower=int(datetime(2025,8,29,tzinfo=timezone.utc).timestamp())*1000;upper=lower+86400000
  import io
  with z.open(member)as raw:
   reader=csv.reader(io.TextIOWrapper(raw,encoding='utf-8',newline=''));header=next(reader);assert header==['id','price','qty','quote_qty','time','is_buyer_maker'],header
   for fields in reader:
    line=reader.line_num;n+=1;flags=[];trade=-1;ts=-1;price=math.nan
    if len(fields)!=6:flags.append('FIELD_COUNT')
    else:
     if not fields[0].isascii()or not fields[0].isdecimal():flags.append('ID_NOT_UNSIGNED_INTEGER')
     else:
      trade=int(fields[0])
      if not 0<trade<2**63:flags.append('ID_RANGE');trade=-1
     if not fields[4].isascii()or not fields[4].isdecimal():flags.append('TIME_NOT_UNSIGNED_INTEGER')
     else:
      ts=int(fields[4])
      if not lower<=ts<upper:flags.append('TIME_UNIT_OR_UTC_DAY_RANGE')
     try:
      px,qty,quote=map(Decimal,fields[1:4])
      if not all(x.is_finite()for x in(px,qty,quote)):flags.append('NONFINITE_DECIMAL')
      elif px<=0 or qty<=0 or quote<=0:flags.append('NONPOSITIVE_FINANCIAL_FIELD')
      else:
       price=float(px)
       if quote!=px*qty:flags.append('QUOTE_NOT_EXACT_PRICE_TIMES_QTY');decimal_quote_mismatch+=1
     except InvalidOperation:flags.append('DECIMAL_PARSE')
     if fields[5]not in('true','false'):flags.append('INVALID_MAKER_FLAG')
    ids.append(trade);times.append(ts);prices.append(price)
    if flags:issues.append(dict(source_line=line,issues=';'.join(flags),original_fields=json.dumps(fields,ensure_ascii=False)))
    if n%1000000==0:print('AUDITED',n,flush=True)
  assert reader.line_num==n+1,'Unexpected multiline fields'
 a=np.asarray(ids,dtype=np.int64);t=np.asarray(times,dtype=np.int64);px=np.asarray(prices,dtype=np.float64)
 unique,counts=np.unique(a,return_counts=True);duplicates=unique[counts>1];pairs={int(x):np.flatnonzero(a==x).tolist()for x in duplicates}
 steps=np.diff(a);bad=np.flatnonzero(steps<=0)+1;gaps=np.flatnonzero(steps>1)+1;rev=np.flatnonzero(np.diff(t)<0)+1
 def neighbors(indices,reason):return[dict(reason=reason,before_line=int(i)+1,line=int(i)+2,before_id=int(a[i-1]),id=int(a[i]),before_time_integer=int(t[i-1]),time_integer=int(t[i]),id_step=int(steps[i-1]),time_step_ms=int(t[i]-t[i-1]))for i in indices]
 write(folder/'all_nonincreasing_ids.csv',neighbors(bad,'ID_NONINCREASING'),['reason','before_line','line','before_id','id','before_time_integer','time_integer','id_step','time_step_ms'])
 write(folder/'all_timestamp_reversals.csv',neighbors(rev,'TIMESTAMP_REVERSAL'),['reason','before_line','line','before_id','id','before_time_integer','time_integer','id_step','time_step_ms'])
 write(folder/'all_id_gaps.csv',neighbors(gaps,'POSITIVE_ID_GAP_ORIGINAL_STRICT_ACCEPTS_LOGGED'),['reason','before_line','line','before_id','id','before_time_integer','time_integer','id_step','time_step_ms'])
 write(folder/'all_field_issues.csv',issues,['source_line','issues','original_fields'])
 wanted={i+2 for entries in pairs.values()for index in entries for i in range(max(0,index-3),min(n,index+4))};records={}
 with zipfile.ZipFile(b.ARCHIVE)as z,z.open(member)as raw:
  reader=csv.reader(io.TextIOWrapper(raw,encoding='utf-8',newline=''));next(reader)
  for fields in reader:
   if reader.line_num in wanted:records[reader.line_num]=dict(source_line=reader.line_num,fields=fields,trade_id_integer=int(fields[0]),timestamp_integer=int(fields[4]))
   if reader.line_num>max(wanted,default=0):break
 conflicts=[]
 for trade,indices in pairs.items():
  order=sorted(indices,key=lambda i:(int(t[i]),i));entries=[records[i+2]for i in order]
  conflicts.append(dict(trade_id=trade,records=entries,delta_time_ms=int(t[order[-1]]-t[order[0]]),exact_duplicate_fields=len({tuple(x['fields'])for x in entries})==1))
 b.dump(folder/'conflicts_and_neighbors.json',dict(header=header,conflicts=conflicts,all_neighbor_records=[records[k]for k in sorted(records)]))
 eligible=not issues and set(pairs)==set(b.IDS)and all(len(x)==2 for x in pairs.values())and not np.any(steps<0)and all(int(a[i])in b.IDS or int(a[i-1])in b.IDS for i in rev)
 first=min(int(t[i])for values in pairs.values()for i in values);last=max(int(t[i])for values in pairs.values()for i in values)
 report=dict(archive=str(b.ARCHIVE),archive_sha256=sha,archive_bytes=b.ARCHIVE.stat().st_size,uncompressed_member=member,uncompressed_SHA256=digest.hexdigest(),header=header,data_rows=n,integer_dtypes=dict(id=str(a.dtype),timestamp=str(t.dtype)),time_unit='milliseconds since Unix UTC',timestamp_min_integer=int(t.min()),timestamp_max_integer=int(t.max()),all_ids_exact_below_2pow53=bool(np.max(a)<2**53),all_times_exact_below_2pow53=bool(np.max(t)<2**53),duplicate_ids={str(x):len(pairs[x])for x in pairs},nonincreasing_ID_events=len(bad),negative_ID_steps=int(np.sum(steps<0)),positive_ID_gaps=len(gaps),timestamp_reversals=len(rev),field_issues=len(issues),exact_Decimal_quote_product_mismatches=decimal_quote_mismatch,scenario_coverage_eligible=eligible,conflicts=conflicts,first_conflict_ms=first,last_conflict_ms=last,fork_second=first//60000*60,merge_second=(last//60000+1)*60,source_line_identity='physical original CSV line incl header; data start line2; never rewrite raw ID',scope='all rows checked for structure/integer ID/time/Decimal price qty quote/maker/date/order/duplicates/gaps; not a proof of all possible market-data correctness')
 prior=json.loads((b.ROOT/'outputs/eth_density_experiment/recovery_20250829_ETH/result.json').read_text());report['prior_monthly_evidence_reused']=prior;report['daily_matches_prior_monthly_day']=digest.hexdigest()==prior['sha256_filtered_day'];assert report['daily_matches_prior_monthly_day']
 b.dump(folder/'audit.json',report)
 for name,values in [('id',a),('time_ms',t),('price',px)]:np.save(folder/(name+'.npy'),values)
 print('AUDIT_COMPLETE',json.dumps({k:v for k,v in report.items()if k not in('conflicts','prior_monthly_evidence_reused')}),flush=True)
 if not eligible:raise RuntimeError('Additional anomaly or coverage mismatch: do not create the nine requested scenarios without reassessment')
if __name__=='__main__':audit()
