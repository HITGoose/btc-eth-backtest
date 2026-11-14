"""Explicitly whitelist confirmed immutable findings; never repair their fields."""
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timezone,timedelta
import csv,json,hashlib,zipfile,io,inspect
import numpy as np
import bridge as b
OUT=b.OUT
KNOWN_QUOTES={1493267:['6299490401','4390.0','2424.705','1.0644454','1756451673678','false'],1513648:['6299510796','4390.0','4112.137','1.8052281','1756451762717','false'],7261393:['6305263311','4344.0','2907.024','1.2628112','1756505656216','true']}
if __name__=='__main__':
 f=OUT/'raw_audit';audit=json.loads((f/'audit.json').read_text());assert hashlib.file_digest(b.ARCHIVE.open('rb'),'sha256').hexdigest()==b.EXPECTED_SHA==audit['archive_sha256']
 assert audit['data_rows']==7454972 and audit['duplicate_ids']=={str(x):2 for x in b.IDS}and audit['nonincreasing_ID_events']==3 and audit['negative_ID_steps']==0 and audit['timestamp_reversals']==2
 with(f/'all_field_issues.csv').open(encoding='utf-8-sig',newline='')as h:issues=list(csv.DictReader(h))
 assert {int(x['source_line']):json.loads(x['original_fields'])for x in issues}==KNOWN_QUOTES
 assert all(x['issues']=='QUOTE_NOT_EXACT_PRICE_TIMES_QTY'for x in issues)
 ids=np.load(f/'id.npy',mmap_mode='r');t=np.load(f/'time_ms.npy',mmap_mode='r');prices=np.load(f/'price.npy',mmap_mode='r');assert ids.dtype==np.int64 and t.dtype==np.int64 and len(ids)==len(t)==len(prices)==audit['data_rows']
 needed={i for line in KNOWN_QUOTES for i in range(line-3,line+4)};neighbors=[]
 with zipfile.ZipFile(b.ARCHIVE)as z,z.open(audit['uncompressed_member'])as raw:
  reader=csv.reader(io.TextIOWrapper(raw,encoding='utf-8',newline=''));next(reader)
  for fields in reader:
   line=reader.line_num
   if line in needed:neighbors.append(dict(source_line=line,fields=fields))
   if line in KNOWN_QUOTES:assert fields==KNOWN_QUOTES[line]and int(fields[0])==ids[line-2]and int(fields[4])==t[line-2]and float(fields[1])==prices[line-2]
   if line>max(needed):break
 b.dump(f/'additional_field_neighbors.json',dict(records=neighbors,quote_issues=[dict(source_line=line,fields=fields,expected_quote_exact=str(Decimal(fields[1])*Decimal(fields[2])))for line,fields in KNOWN_QUOTES.items()]))
 # Explicitly document all no-print minutes; no interpolation or native fill.
 day_start=int(datetime(2025,8,29,tzinfo=timezone.utc).timestamp());count=np.bincount(((t-day_start*1000)//60000).astype(int),minlength=1440);empty=np.flatnonzero(count==0)
 ordered=np.sort(t,kind='stable');gaps=np.flatnonzero(np.diff(ordered)>=60000)
 b.csv_dump(f/'all_no_print_intervals_ge_60s.csv',[dict(previous_time_integer=int(ordered[i]),next_time_integer=int(ordered[i+1]),gap_ms=int(ordered[i+1]-ordered[i]))for i in gaps])
 _,data,start,end,first,sources=b.z.inputs('2025','ETH');native=np.load(data/'ETH_1m.npy',mmap_mode='r');emptyrows=[]
 for minute in empty:
  stamp=day_start+int(minute)*60;row=native[(stamp-first)//60]
  emptyrows.append(dict(minute_UTC=datetime.fromtimestamp(stamp,timezone.utc).isoformat(),minute_Beijing=b.r.local_s(stamp),raw_print_count=0,native_open=float(row[0]),native_high=float(row[1]),native_low=float(row[2]),native_close=float(row[3]),native_volume=float(row[4])))
 b.csv_dump(f/'all_empty_raw_minutes_vs_native.csv',emptyrows)
 assert "read_zip(path,[0,1,4])"in inspect.getsource(b.e.RawCache.load)
 reassess=dict(decision='ID_HYPOTHESES_ELIGIBLE_WITH_ADDITIONAL_UNMODELED_FINDINGS',identified_duplicate_ids_only=list(b.IDS),additional_quote_issues_retained_unchanged=KNOWN_QUOTES,quote_fields_not_consumed_by_frozen_execution=True,original_execution_raw_columns=[0,1,4],sizing='unchanged account balance times3; full touch proxy ignores market qty/quote',positive_ID_gaps_preserved=audit['positive_ID_gaps'],raw_empty_minutes=len(empty),native_positive_volume_in_empty_raw_minutes=sum(x['native_volume']>0 for x in emptyrows),largest_no_print_gap_ms=int(np.diff(ordered).max()),explanation='Nine scenarios only select the six conflicting-ID records. Quote inconsistencies, ID gaps and raw no-print periods are NOT repaired or covered; their fields and stale-last-real-quote behavior remain unchanged. Cannot establish all official fields are correct.',monthly_archive_not_redownloaded=True)
 b.dump(f/'coverage_reassessment.json',reassess)
 manifest=dict(allowed_asset=b.ASSET,allowed_symbol=b.SYMBOL,allowed_UTC_date=b.DAY,allowed_file_SHA256=b.EXPECTED_SHA,rows=audit['data_rows'],integer_unit='ms',duplicate_ids=audit['duplicate_ids'],conflicts=audit['conflicts'],confirmed_timestamp_reversals=2,confirmed_quote_issue_lines=list(KNOWN_QUOTES),additional_findings=reassess,parsed_arrays_SHA256={n:hashlib.sha256((f/(n+'.npy')).read_bytes()).hexdigest()for n in('id','time_ms','price')},audit_JSON_SHA256=hashlib.sha256((f/'audit.json').read_bytes()).hexdigest(),audit_parser_executed_SHA256=hashlib.sha256((f/'audit_parser_executed.py').read_bytes()).hexdigest(),first_conflict_ms=audit['first_conflict_ms'],last_conflict_ms=audit['last_conflict_ms'],fork_second=audit['fork_second'],merge_second=audit['merge_second'])
 b.dump(OUT/'whitelist_manifest.json',manifest);print('REASSESSMENT',json.dumps(reassess),flush=True)
