from playwright.sync_api import sync_playwright
from pathlib import Path
from urllib.parse import urlsplit
import os,json,hashlib,datetime,re
O=Path(__file__).resolve().parent;url='https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Trade-Streams';proxy=os.environ.get('https_proxy')or os.environ.get('HTTPS_PROXY');opts={}
if proxy:
 u=urlsplit(proxy);opts['proxy']={'server':f'{u.scheme}://{u.hostname}:{u.port}'}
 if u.username:opts['proxy'].update(username=u.username,password=u.password)
error=None;body=''
try:
 with sync_playwright()as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'],**opts);page=browser.new_page()
  try:page.goto(url,wait_until='networkidle',timeout=35000)
  except Exception as e:error=type(e).__name__
  page.wait_for_timeout(4000);body=page.locator('body').inner_text(timeout=10000);(O/'official_trade_doc_rendered.txt').write_text(body);page.screenshot(path=str(O/'official_trade_doc.png'),full_page=True);browser.close()
except Exception as e:error=repr(e)
matches=[body[max(0,m.start()-160):m.end()+240]for m in re.finditer(r'zero|placeholder|RPI|\bNA\b|ignored|ignore',body,re.I)][:20]
q=dict(url=url,error=error,received_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),rendered_bytes=len(body.encode()),SHA256=hashlib.sha256(body.encode()).hexdigest(),TLS_verification=True,matches=matches)
(O/'official_trade_doc_rendered.json').write_text(json.dumps(q,indent=2));print(json.dumps(q,indent=2))
