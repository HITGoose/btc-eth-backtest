from pathlib import Path
from collections import defaultdict
import json,csv
import shared as s
O=s.OUT

def main():
 found=defaultdict(lambda:defaultdict(list))
 for root in [O,s.b.PARENT,s.OLD]:
  for path in root.rglob('raw_sources.json'):
   try:data=json.loads(path.read_text())
   except Exception:continue
   vals=data.values()if isinstance(data,dict)else data
   for x in vals:
    if not isinstance(x,dict):continue
    url=x.get('url','');sha=x.get('sha256')
    if url.startswith('https://data.binance.vision/data/futures/um/')and'/trades/'in url and sha:
     assert x['official_checksum_match'],str(path);found[url][sha].append(str(path.relative_to(s.ROOT)))
 conflicts=[dict(url=u,SHA256_versions={h:files for h,files in d.items()})for u,d in found.items()if len(d)>1]
 s.dump(O/'raw_source_consistency.json',dict(all_observed_raw_archive_versions_consistent=not conflicts,unique_raw_URLs=len(found),scope='all retained strict-source metadata in current and locked prior cache; not an independent market-completeness proof',conflicts=conflicts,known_exception_original_SHA256=s.b.EXPECTED_SHA))
 print('RAW_SOURCE_URLS',len(found),'CONFLICTING_ARCHIVE_VERSIONS',len(conflicts))
 if conflicts:raise SystemExit('Investigate raw source versions before comparison')
if __name__=='__main__':main()
