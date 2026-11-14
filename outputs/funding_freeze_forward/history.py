"""Full raw-trade accounts with explicitly retrospective approximate funding only."""
from pathlib import Path
import sys,json,hashlib,inspect
R=Path('/workspace/btc-eth-backtest');OLD=R/'outputs/extra_sizing_cost_stress';O=Path(__file__).resolve().parent
sys.path.insert(0,str(OLD));import shared as s;import funded_replay as w
MODE=[];FEEDS=None;idx=0
ORIGBOOK=w.E.book

def fp():return hashlib.sha256((O/'history.py').read_bytes()+w.s.fp().encode()+b''.join((OLD/n).read_bytes()for n in ['funding_engine.py','funded_replay.py'])).hexdigest()
def configs(asset,stage):
 global MODE
 MODE=[dict(key='APPROX_'+m+'_'+g+'_F_TOUCH',cost='APPROX_'+m,group=g,fill='F_TOUCH',fee=.0005,slip=.0002,funding=True,price_estimate=m,strict_exact_status='UNVERIFIED')for m in ['OPEN','HIGH','LOW']for g in(['B','I100','I50','I25']if asset=='ETH'else['B'])];return MODE

def feed(period,asset):
 global FEEDS,idx
 p=O/'funding_feeds'/period/asset/'result.json';FEEDS=json.loads(p.read_text());assert FEEDS['status']=='APPROXIMATE_FUNDING'and not FEEDS['missing'];idx=0;return hashlib.sha256(p.read_bytes()).hexdigest()
def make(*args,**kw):
 global idx
 cfg=MODE[idx];idx+=1;w.E.FEED=FEEDS['feeds'][cfg['price_estimate']];return ORIGBOOK(*args,**kw)
def main(period,asset):
 w.OUT=O/'historical';w.fund_fp=fp;w.configurations=configs;w.E.configure_feed=feed;w.E.book=make
 src=inspect.getsource(w.output).replace("funding='INCLUDED_OFFICIAL'","funding='APPROXIMATE_FUNDING'").replace("else 'COMPLETE'","else 'APPROXIMATE_FUNDING'")
 ns=dict(w.__dict__);exec(compile(src,'<label-only historical output>','exec'),ns);w.output=ns['output']
 w.run(period,asset,'funded')
 p=w.OUT/'runs'/period/asset/'funded/status.json';q=json.loads(p.read_text());q.update(status='APPROXIMATE_FUNDING',strict_exact_status='UNVERIFIED',retrospective_minute_extremes_not_account_bounds=True);p.write_text(json.dumps(q))
if __name__=='__main__':main(*sys.argv[1:3])
