import csv,json,hashlib
from pathlib import Path
import shared as s
O=s.OUT

def main():
 with(O/'availability.csv').open(encoding='utf-8-sig')as f:rows=list(csv.DictReader(f))
 allowed=[];unexpected=[];complete=[];primary=[];supp=[]
 for r in rows:
  is_supp=r['cost'].endswith('NO_FUNDING')or(r['cost']=='C1'and r['fill']=='F_THROUGH')
  (supp if is_supp else primary).append(r)
  if r['status']in ('COMPLETE','COMPLETED_WITH_DATA_ANOMALY'):complete.append(r)
  elif r['period']in ('2020','2021','2022','2023')and r['cost']in ('C2','C3','C4')and'OFFICIAL_SETTLEMENT_MARK_PRICE_MISSING'in r['reason']:allowed.append(r)
  else:unexpected.append(r)
 for name,sha in json.loads((O/'frozen_code.json').read_text()).items():assert hashlib.file_digest((O/name).open('rb'),'sha256').hexdigest()==sha
 for name,sha in json.loads((O/'frozen_funding_code.json').read_text()).items():assert hashlib.file_digest((O/name).open('rb'),'sha256').hexdigest()==sha
 s.b.verify_parent()
 result=dict(all_executable_cases_completed=not unexpected,portfolio_cases_completed=len(complete),primary_planned=len(primary),primary_completed=sum(r['status']in ('COMPLETE','COMPLETED_WITH_DATA_ANOMALY')for r in primary),primary_UNVERIFIED_official_funding_missing=len(allowed),supplemental_completed=sum(r['status']in ('COMPLETE','COMPLETED_WITH_DATA_ANOMALY')for r in supp),conditional2025_completed=sum(r['period']=='2025'for r in complete),other_strict_completed=sum(r['period']!='2025'for r in complete),unexpected_incomplete=unexpected,original_strict_failures_untouched=True,all_history_strict_verified=False,unverified2019=True,year2020_window='02-16 to12-31',year2026_window='01-01 to10-31',NOV='independent2026-11-01 to11-13 08:00 UTC+8',original_financial_source_unchanged=True)
 s.dump(O/'coverage_audit.json',result);print(json.dumps({k:v for k,v in result.items()if k!='unexpected_incomplete'}))
 if unexpected:raise SystemExit('Executable cases still incomplete: '+str(len(unexpected)))
if __name__=='__main__':main()
