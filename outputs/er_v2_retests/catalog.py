"""Canonical identities: experiment letters are aliases, never executable identities."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
BASE_COMMIT='f8aa6a9440ce3a0b486a3b1245a1051b77b8d145'
SPECS={
 'REF':dict(stage=0,kind='reference'),
 'FAIL_EXIT':dict(stage=1,kind='import',parent_key='ER_V2_FAIL_EXIT'),
 'VOL_SIZE':dict(stage=1,kind='import',parent_key='ER_V2_VOL_SIZE'),
 'FIXED_LOW':dict(stage=1,kind='size',calibration='mean successful submitted target leverage in VOL_SIZE 2020:2022'),
 'ATR_STOP':dict(stage=2,kind='initial_stop',atr=96,multiple=2.,bounds=[.01,.03],risk=.06),
 'CANCEL':dict(stage=3,kind='order_cancel',delay_seconds=60),
 'CAP5':dict(stage=4,kind='ladder',exit_policy='fixed'),
 'TRAIL8':dict(stage=4,kind='ladder',exit_policy='trail_from_8pct'),
 'REGIME_SIZE':dict(stage=5,kind='size',weights=[1.3,.7]),
 'ETH030':dict(stage=6,kind='density',threshold=.30,scope='ETH'),
 'ETH035':dict(stage=6,kind='density',threshold=.35,scope='ETH'),
 'Q15':dict(stage=7,kind='adaptive',family='B',historical='B15',parameters=[.15,.40]),
 'Q20':dict(stage=7,kind='adaptive',family='B',historical='B20',parameters=[.20,.45]),
 'Q25':dict(stage=7,kind='adaptive',family='B',historical='B25',parameters=[.25,.50]),
 'N05':dict(stage=8,kind='adaptive',family='C',historical='C05',parameters=[.5,1.]),
 'N10':dict(stage=8,kind='adaptive',family='C',historical='C10',parameters=[1.,2.]),
 'N15':dict(stage=8,kind='adaptive',family='C',historical='C15',parameters=[1.5,3.]),
 'ADAPT_CORE_LIGHT':dict(stage=9,kind='union',priority=True,extra_ratio=1/3,scope='BOTH',source='FROZEN_B_OR_C'),
 'BTC_CONFIRM':dict(stage=10,kind='density',threshold=.30,scope='ETH',btc_confirm=True),
 'CORE_PRIORITY':dict(stage=10,kind='density',threshold=.30,scope='ETH',priority=True),
 'BOTH100':dict(stage=10,kind='density',threshold=.30,scope='ETH',btc_confirm=True,priority=True,extra_ratio=1.),
 'BOTH50':dict(stage=10,kind='density',threshold=.30,scope='ETH',btc_confirm=True,priority=True,extra_ratio=.5),
 'BOTH25':dict(stage=10,kind='density',threshold=.30,scope='ETH',btc_confirm=True,priority=True,extra_ratio=.25),
 'REBOUND':dict(stage=11,kind='rebound',scope='BOTH'),
}
ALIASES={'uncapped':'REF','ETH025':'REF','density_B':'REF','priority_B':'REF','priority_D':'ETH030','density_D':'ETH030','density_F':'ETH035','priority_G':'BTC_CONFIRM','priority_H':'CORE_PRIORITY','priority_I':'BOTH100','I100':'BOTH100','I50':'BOTH50','I25':'BOTH25'}
def canonical(key,asset):
 key=ALIASES.get(key,key)
 if SPECS[key].get('scope')=='ETH'and asset=='BTC':return 'REF'
 return key
STAGES={1:'提前退出／波动减仓导入与固定低杠杆',2:'ATR初始止损风险上限',3:'失效挂单撤销',4:'阶梯封顶',5:'120h方向仓位权重',6:'ETH历史密集阈值',7:'滚动分位数训练与冻结',8:'ATR归一化训练与冻结',9:'冻结自适应CORE优先轻仓',10:'ETH BTC确认／CORE优先／补充比例',11:'反弹续跌BTC／ETH／双币'}
