from pathlib import Path
import importlib.util,sys,json,hashlib
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent
OLD=ROOT/'outputs/eth_2025_anomaly_sensitivity'
sys.path.insert(0,str(OLD))
import bridge as b
import adapter as a
import observer as o
z=b.z;r=b.r;pe=b.pe;np=b.e.np
GROUPS={'B':('B',1.),'G':('G',1.),'H':('H',1.),'I100':('I',1.),'I50':('I',.5),'I25':('I',.25)}
COSTS={'C0':dict(fee=0.,slip=.0002,funding=False),'C1':dict(fee=.0005,slip=.0002,funding=False),'C3_NO_FUNDING':dict(fee=.0005,slip=.0005,funding=False),'C4_NO_FUNDING':dict(fee=.00075,slip=.001,funding=False)}
def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);z.dump(path,value)
def fp():return hashlib.sha256(b''.join((OUT/n).read_bytes()for n in ['shared.py','cost_engine.py','replay.py'])+b.PARENT_FP.encode()).hexdigest()
def activate(book):r.model.FEE=book.fee;r.model.SLIP=book.slippage
