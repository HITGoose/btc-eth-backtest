"""Run from the ORIGINAL Colab terminal while stage8 continues. No kernel interruption."""
from pathlib import Path
import argparse,json,hashlib,shutil,subprocess,os
p=argparse.ArgumentParser();p.add_argument('--main-local',default='/content/ma_direction_resume_results_cad3c8c');p.add_argument('--main-drive',default='/content/drive/MyDrive/btc_eth_ma_direction_optimizations/ec73e9c/MA_AUDITED_RESUME_cad3c8c');q=p.parse_args()
main=Path(q.main_local);drive=Path(q.main_drive);boot=main/'sources_compat_bootstrap';site=boot/'sitecustomize.py';assert site.is_file()and(main/'data_revision.json').is_file(),'Use original active runtime; do not change paths blindly'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plans=[]
for stage in [10,11]:
 src=drive/f'delegate_stage{stage}.json';assert src.is_file(),'First run setup in BOTH parallel notebooks'
 plan=json.loads(src.read_text());assert plan['data_manifest_sha256']==sha(main/'data_revision.json')and plan['stage']==stage
 dst=main/src.name
 if dst.exists():assert dst.read_bytes()==src.read_bytes()
 else:shutil.copy2(src,dst)
 plans.append(plan)
assert plans[0]['fingerprint']==plans[1]['fingerprint'],'Parallel financial fingerprints differ'
active=None
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  args=(proc/'cmdline').read_bytes().split(b'\0');env=dict(x.split(b'=',1)for x in(proc/'environ').read_bytes().split(b'\0')if b'='in x)
  if any(x.endswith(b'/outputs/ma_direction_resume/run.py')for x in args)and env.get(b'BTC_OUTPUT_ROOT',b'').decode()==str(main):active=(proc,env);break
 except (OSError,ValueError):continue
assert active,'Original coordinator not found; do not claim current stage8 is still running'
proc,rawenv=active;env={k.decode():v.decode()for k,v in rawenv.items()};assert str(boot)in env.get('PYTHONPATH',''),'Active coordinator does not inherit compatibility bootstrap; stop here'
repo=Path(env['BTC_REPO_ROOT'])
code="import sys;sys.path.insert(0,"+repr(str(repo/'outputs/ma_direction_retests'))+");import common as c;sys.path.insert(0,"+repr(str(repo/'outputs/ma_direction_resume'))+");import revision;revision.install(c);print(c.fingerprint())"
fp=subprocess.check_output([str((proc/'exe').resolve()),'-c',code],env=env,text=True).strip().splitlines()[-1]
assert fp==plans[0]['fingerprint'],'Running main financial fingerprint differs; no handoff installed'

helper=Path(__file__).parent/'delegation_guard.py';assert helper.is_file();dest=boot/'delegation_guard.py';shutil.copy2(helper,dest)
text=site.read_text();marker='# MA_STAGE_DELEGATION_V1'
if marker not in text:
 (boot/'sitecustomize.before_parallel_handoff.txt').write_text(text)
 extra='''\n# MA_STAGE_DELEGATION_V1
try:
 import delegation_guard
 delegation_guard.maybe_delegate()
except BaseException as error:
 import os,sys,traceback
 traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(70)
'''
 compile(text+extra,str(site),'exec');tmp=site.with_name('sitecustomize.py.parallel_installing');tmp.write_text(text+extra);tmp.replace(site)
(main/'parallel_handoff_receipt.json').write_text(json.dumps(dict(financial_fingerprint=fp,stages=[10,11],original_source_unmodified=True,guard_sha256=sha(dest)),indent=2))
print('HANDOFF_INSTALLED: current stage8 untouched; stage9 runs normally; stage10/11 wait/import verified parallel results.',flush=True)
print('Do NOT stop current cell or run another main coordinator.',flush=True)
