from signals import *
import json,hashlib
from datetime import datetime,timezone
O=Path(__file__).resolve().parent;checks=[]
def ok(name,value):assert value,name;checks.append(dict(name=name,passed=True))
valid=(True,'down',6,True,-1.,True,True)
ok('fixed down admission',admission(*valid))
for i,value in [(0,False),(1,'range'),(1,'transition'),(1,'up'),(2,5),(3,False),(4,0.),(5,False),(6,False)]:
 a=list(valid);a[i]=value;ok(f'individual gate {i}={value} rejected',not admission(*a))
prev=[0,100,104,99,102,2];a=[0,101,103,97,98,2];ok('closed rebound then strict break',form(a,prev));a[4]=99;ok('equal low is not strict break',not form(a,prev))
info=z.prepare('2020','ETH');start=1583625600;cut=start+3*86400;end=1584230400
_,core,new,diag,_,_=build('ETH',info['data'],start,end);_,c2,n2,d2,_,_=build('ETH',info['data'],start,cut)
ok('future bars do not alter prefix CORE',c2=={t:v for t,v in core.items()if t<cut*1000});ok('future bars do not alter new signals',n2=={t:v for t,v in new.items()if t<cut*1000})
ok('new signals never overwrite CORE',not(set(new)&set(core)))
_,ref,_,_,_=z.s.prepare('ETH',info['data'],start,end,.25)
ok('original density CORE remains exact',core=={t:v for t,v in ref.items()if start*1000<=t<end*1000})
ok('range shape rejected',all(not x['new_signal']for x in diag if x['regime']in ['range','transition']))
s.dump(O/'tests.json',dict(passed=True,total=len(checks),checks=checks));print('PASS',len(checks))
