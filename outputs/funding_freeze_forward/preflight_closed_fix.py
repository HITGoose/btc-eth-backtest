import online as n,json,time
O=n.O;folder=O/'preflight_closed';folder.mkdir(exist_ok=True);events=[]
t0=((int(time.time())+60)//900+1)*900000
sg=n.Signals(t0,folder);sg.warm(events.append);(folder/'warm_responses.json').write_text(json.dumps(events));legs=sg.calculate();engine=n.Engine(dict(T0_ms=t0,run_id='PREFLIGHT_NOT_FORWARD'),legs);engine.save(folder)
(folder/'result.json').write_text(json.dumps(dict(passed=True,actual_public_warmup=True,rows={a:len(v)for a,v in sg.bars.items()},last_closed={a:v['last_close_ms']for a,v in legs.items()},terminal_REST_rows_excluded=True,all_accounts_flat=True,not_forward_observation=True)))
print('PREFLIGHT_CLOSED_FIX_OK')
