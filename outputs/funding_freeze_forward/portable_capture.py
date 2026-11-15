"""Lossless derived backup of capture DATA, original gzip remains untouched.
Hash-chain fields are deterministically restored; exact plaintext SHA must match.
"""
from pathlib import Path
import json,gzip,hashlib,sys,datetime
O=Path(__file__).resolve().parent

def digest(q):return hashlib.sha256(json.dumps(q,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def original_row(event,sequence,previous):
 row=dict(sequence=sequence,previous_SHA256=previous,body_SHA256=digest(event),event=event);row['chain_SHA256']=digest(row);return row

def pack(folder):
 folder=Path(folder).resolve();source=folder/'events.jsonl.gz';A=O/'artifacts';A.mkdir(exist_ok=True);dest=A/(folder.name+'.portable_events.jsonl.gz');plain=hashlib.sha256();seq=0;previous='0'*64;wire={};zero=[];lat=[];closed=[];actualgaps=[];lastsystem=None;first=None;last=None;errors=0
 with gzip.open(source,'rb')as f,gzip.open(dest,'wt',compresslevel=9,encoding='utf-8',newline='')as out:
  for line in f:
   plain.update(line);row=json.loads(line);seq+=1;event=row['event'];expected=original_row(event,seq,previous);assert row==expected and line==(json.dumps(expected,separators=(',',':'))+'\n').encode(),'source chain or exact plaintext changed';previous=row['chain_SHA256'];out.write(json.dumps(event,separators=(',',':'))+'\n')
   typ=event['type'];lastsystem=typ;first=event if first is None else first;last=event
   if 'raw_UTF8'in event:assert hashlib.sha256(event['raw_UTF8'].encode()).hexdigest()==event['SHA256']
   if typ=='TRADES':
    for trade in event['data']:
     a=event['asset'];i=trade['id'];t=trade['time'];assert type(i)is int and type(t)is int
     if a in wire and i>wire[a]and i!=wire[a]+1:actualgaps.append(dict(asset=a,previous=wire[a],current=i))
     wire[a]=max(wire.get(a,i),i);lat.append(event['received_us']-t*1000)
     if float(trade['price'])==0:zero.append(dict(asset=a,id=i,time=t,raw=event['raw_UTF8'],sequence=seq))
   elif typ=='KLINES'and event.get('confirmed_exchange_closed'):
    d=json.loads(event['raw_UTF8'])['data'];assert d['e']=='kline'and d['k']['x']is True;closed.append(dict(asset=event['asset'],close_ms=d['k']['T']+1,received_us=event['received_us']))
   elif typ=='PROCESSING_ERROR':errors+=1
 q=dict(run=folder.name,source_container_SHA256=hashlib.file_digest(source.open('rb'),'sha256').hexdigest(),source_bytes=source.stat().st_size,source_plain_SHA256=plain.hexdigest(),portable_file=str(dest.relative_to(O)),portable_SHA256=hashlib.file_digest(dest.open('rb'),'sha256').hexdigest(),portable_bytes=dest.stat().st_size,records=seq,ending_chain_SHA256=previous,lossless_plaintext_reconstruction=True,original_source_gzip_unchanged=True,original_container_not_bitwise_reconstructed=True,last_system_event=lastsystem,first_event_received_us=first['received_us'],last_event_received_us=last['received_us'],wire_ID_gaps_including_zero_NA=actualgaps,zero_price_messages=len(zero),processing_error_messages=errors,native_closed_Kline_events=closed,trade_latency_us=dict(minimum=min(lat)if lat else None,maximum=max(lat)if lat else None,mean=sum(lat)/len(lat)if lat else None))
 (A/(folder.name+'.capture_manifest.json')).write_text(json.dumps(q,indent=2));(O/(folder.name+'_capture_audit.json')).write_text(json.dumps(q,indent=2))
 if zero:(O/(folder.name+'_zero_events_sample.json')).write_text(json.dumps(zero[:10],indent=2))
 print('CAPTURE_PACK',q['run'],seq,q['source_bytes'],q['portable_bytes']);return q

def restore(manifest_path,destination):
 p=Path(manifest_path).resolve();m=json.loads(p.read_text());source=p.parent/Path(m['portable_file']).name;assert hashlib.file_digest(source.open('rb'),'sha256').hexdigest()==m['portable_SHA256'];plain=hashlib.sha256();previous='0'*64;seq=0;target=Path(destination)
 with gzip.open(source,'rt',encoding='utf-8')as inp,gzip.open(target,'wb',compresslevel=9)as out:
  for line in inp:
   event=json.loads(line);seq+=1;row=original_row(event,seq,previous);previous=row['chain_SHA256'];raw=(json.dumps(row,separators=(',',':'))+'\n').encode();plain.update(raw);out.write(raw)
 assert seq==m['records']and previous==m['ending_chain_SHA256']and plain.hexdigest()==m['source_plain_SHA256'];print('RESTORED_EXACT_PLAINTEXT',str(target),seq)
if __name__=='__main__':
 if sys.argv[1]=='pack':pack(sys.argv[2])
 else:restore(sys.argv[2],sys.argv[3])
