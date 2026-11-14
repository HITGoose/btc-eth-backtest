import inspect,json,hashlib
import shared as s
import replay as old
import sizing_only_replay as new
checks=[]
for name in ['segment','output','raw_cache','oldpath']:
 a=inspect.getsource(getattr(old,name));b=inspect.getsource(getattr(new,name)).replace('sizing_fp()','s.fp()');assert a==b,name
 checks.append(dict(name='identical financial execution '+name,passed=True))
selected=[x for x in old.configurations('ETH','experiment')if x['key']in {c['key']for c in new.configurations('ETH','experiment')}]
assert selected==new.configurations('ETH','experiment');checks.append(dict(name='new four-book schedule is exact existing account subset',passed=True))
proof=s.OUT/'sizing_subset_compatibility_2024.json'
if proof.exists():
 d=json.loads(proof.read_text());assert hashlib.file_digest(open(d['source_checkpoint'],'rb'),'sha256').hexdigest()==d['source_checkpoint_SHA256']
 assert d['financial_code_identical']and d['history_preserved']and d['source_runtime_fingerprint']==s.fp()
 checks.append(dict(name='migration source SHA remains exact and proof is explicit',passed=True))
s.dump(s.OUT/'subset_tests.json',dict(passed=True,total=len(checks),checks=checks));print('PASS',len(checks))
