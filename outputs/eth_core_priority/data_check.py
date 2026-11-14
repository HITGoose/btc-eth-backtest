from pathlib import Path
from urllib.request import urlopen
import json,hashlib,shutil
import strategy as z
OUT=z.OUT
if __name__=='__main__':
 rows=[]
 for period in z.PERIODS:
  for asset in('BTC','ETH'):
   ref,data,start,end,first,sources=z.inputs(period,asset)
   rows.append(dict(period=period,asset=asset,start=z.r.local_s(start),end_exclusive=z.r.local_s(end),minute_first=z.r.local_s(first),native_source_manifests=len(sources),official_acquisition_checksums_recorded=all(x['official_checksum_match']for x in sources),only_binance_USDT_perpetual=all('/data/futures/um/'in x['url']for x in sources),CSV_15m_SHA256=hashlib.sha256((data/f'{asset}_15m.csv').read_bytes()).hexdigest(),NPY_1m_SHA256=hashlib.sha256((data/f'{asset}_1m.npy').read_bytes()).hexdigest(),grid_and_warmup='checked by inputs; inherited 1m grid evidence, current shape+coverage checked',input_folder=str(data)))
 z.csv_dump(OUT/'data_coverage.csv',rows)
 url='https://data.binance.vision/data/futures/um/daily/trades/ETHUSDT/ETHUSDT-trades-2025-08-29.zip'
 expected=urlopen(url+'.CHECKSUM',timeout=30).read().decode().split()[0].lower();archive=z.OLD/'runs/2025/ETH/temporary/ETHUSDT-trades-2025-08-29.zip';actual=hashlib.sha256(archive.read_bytes()).hexdigest();assert actual==expected
 evidence=OUT/'data_evidence';evidence.mkdir(exist_ok=True)
 for name,file in [('daily_conflict_prior.json',z.OLD/'data_issue_20250829_ETH.json'),('monthly_source_prior.json',z.OLD/'recovery_20250829_ETH/monthly_source.json'),('monthly_day_comparison_prior.json',z.OLD/'recovery_20250829_ETH/result.json')]:
  if file.exists():shutil.copyfile(file,evidence/name)
 z.dump(evidence/'current_conflict_archive.json',dict(url=url,official_checksum_url=url+'.CHECKSUM',bytes=archive.stat().st_size,current_SHA256=actual,official_SHA256=expected,official_checksum_match=True,current_source='same untouched official daily archive, strict replays reject conflicting IDs',prior_monthly_evidence_source_commit=z.BASE_COMMIT,monthly_not_redownloaded_this_experiment=True,prices_not_modified=True,rows_not_deleted=True))
 lines=['# 数据核对','','本轮市场仅币安USDT永续。原生15m、1m缓存先核对时间覆盖、预热、15m完整网格及当前SHA；ZIP取得时的官方checksum证据保留，不冒充本轮重新下载了所有原生K线。1m.npy无原时间列，采用原已验证网格证据和本轮形状/起止检查。','新增ETH路径实际访问daily/trades官方原始逐笔，逐次核对CHECKSUM及严格ID，未用旧交易结果或OHLC替代。raw_sources记录实际访问档案；不声称下载了全年所有无持仓日期或独立证明了市场档案全集无缺漏。','','|区间|资产|已验证原生起止（右端不含）|','|---|---|---|']
 lines += [f"|{x['period']}|{x['asset']}|{x['start']} — {x['end_exclusive']}|"for x in rows]
 lines+=['','2025-08-29 ETH当前日ZIP与官方checksum相同：'+actual+'。严格逐笔任务拒绝重复/逆序ID，未删除记录。月度目标日与daily逐字节一致的旧证据从锁定提交复用，本轮没有再次下载2GB月包。','2019未验证；2020仅02-16起；2026仅Jan—Oct；NOV独立起算至11-13 08:00北京时间。','2025-03-25一次传输文件SHA失败，错误文件隔离；重新完整取得文件SHA b15192b1bc53f974333c3c3dd430535c5ced2e335e00ef53721b7f306349a2f7匹配官方并通过ZIP CRC。见download_recovery/evidence.json。没有使用错误文件计算。','资金费数据未计；账户实际费率未知，每边.05%仅假设压力；成交是逐笔触价全量模拟，不保证真实排队/深度可成交。']
 (OUT/'data_check.md').write_text('\n'.join(lines)+'\n');print('DATA_CHECK',len(rows),'native ranges; official conflict archive SHA verified')
