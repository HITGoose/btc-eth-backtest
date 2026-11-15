"""Complete reporting for the already-running fixed matrix; never start extra runs."""
from pathlib import Path
import json,time,subprocess,sys,datetime
O=Path(__file__).resolve().parent
while True:
 p=O/'final_execution.json'
 if p.exists():
  rows=json.loads(p.read_text())
  if len(rows)==16:break
 if (O/'pipeline_blocked.json').exists():raise SystemExit('Training blocked: retain incomplete status')
 time.sleep(5)
r=subprocess.run([sys.executable,'-u',str(O/'report.py')]);assert r.returncode==0,'Report/accounting failed; do not publish complete status'
missing=json.loads((O/'incomplete.json').read_text())
(O/'STATUS.md').write_text('# 状态\n\n'+('固定矩阵已完成，见CONCLUSION.md。'if not missing else f'已保存可完成结果；{len(missing)}项未验证，见incomplete.json及运行日志。')+'\n四组均原CONTROL、pause_transition=True、无V2。2025 S_ALL及近期K线假设标签不变。每年度独立重置和回撤，不拼接重置账户算累计回撤。\n截止UTC：'+datetime.datetime.now(datetime.timezone.utc).isoformat()+'\n')
r=subprocess.run([sys.executable,'/tmp/publish_adaptive_density.py']);assert r.returncode==0,'Publication failed; local results retained'
print('REPORT_AND_PUBLICATION_FINISHED',flush=True)
