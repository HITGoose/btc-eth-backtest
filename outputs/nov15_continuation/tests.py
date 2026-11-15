from pathlib import Path
import sys,json,gzip,pickle,hashlib
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'outputs/extra_sizing_cost_stress'));import funded_replay as w
checks=[]
def ok(n,v):assert v,n;checks.append(dict(name=n,passed=True))
for a in ['BTC','ETH']:
 old=w.z.prepare('NOV',a);np=w.np;before=np.load(old['data']/f'{a}_1m.npy');after=np.load(O/'data'/f'{a}_1m.npy');ok(a+' old minute prefix exact',np.array_equal(before,after[:len(before)]))
 before=np.loadtxt(old['data']/f'{a}_15m.csv',delimiter=',',skiprows=1);after=np.loadtxt(O/'data'/f'{a}_15m.csv',delimiter=',',skiprows=1);ok(a+' old 15m prefix exact',np.array_equal(before,after[:len(before)]))
 path=w.OUT/'runs/NOV'/a/'funded/whole/checkpoint.pkl.gz'
 with gzip.open(path,'rb')as f:cp=pickle.load(f)
 ok(a+' parent runtime fingerprint exact',cp['fp']==w.fund_fp());proof=json.loads((O/'runs'/a/'continuity_proof.json').read_text());ok(a+' parent checkpoint SHA exact',hashlib.sha256(path.read_bytes()).hexdigest()==proof['parent_checkpoint_SHA256'])
 for group in ['B']if a=='BTC'else ['B','I100','I50','I25']:
  key=f'C2_{group}_F_TOUCH';oldq=json.loads((w.OUT/'runs/NOV'/a/'funded/results/STRICT'/f'{key}_result.json').read_text());q=json.loads((O/'runs'/a/'results'/f'{key}_result.json').read_text());n=len(oldq['trades']);ok(a+group+' complete old trade prefix exact',q['trades'][:n]==oldq['trades']);ok(a+group+' cash event accounting',abs(q['cash']-500-sum(x['delta']for x in q['cash_events']))<1e-7)
  eq=np.load(O/'runs'/a/'results'/f'{key}_equity.npz')['marks'];prior=np.load(w.OUT/'runs/NOV'/a/'funded/results/STRICT'/f'{key}_equity.npz')['marks'];ok(a+group+' complete old minute equity prefix exact',np.array_equal(prior,eq[:len(prior)]))
  if a=='BTC':ok('BTC new original signals remain CORE',all(t['origin']=='CORE'for t in q['trades']))
w.s.dump(O/'tests.json',dict(passed=True,total=len(checks),checks=checks));print('PASS',len(checks))
