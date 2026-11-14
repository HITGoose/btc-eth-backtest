"""Record exact existing native inputs for restore; does not download or change them."""
import hashlib
import shared as s
O=s.OUT

def main():
 inputs=[]
 for period in ['2020','2021','2022','2023','2024','2025','2026','NOV']:
  for asset in ['BTC','ETH']:
   _,data,start,end,_,_=s.z.inputs(period,asset)
   inputs.append(dict(period=period,asset=asset,start_seconds=start,end_seconds=end,files=[dict(path=str(data/name),bytes=(data/name).stat().st_size,SHA256=hashlib.file_digest((data/name).open('rb'),'sha256').hexdigest())for name in[asset+'_15m.csv',asset+'_1m.npy']]))
 s.dump(O/'native_input_manifest.json',dict(native_inputs=inputs,raw_anomaly_archive=str(s.b.ARCHIVE),raw_anomaly_SHA256=s.b.EXPECTED_SHA,original_audited_arrays_manifest=str(s.OLD/'whitelist_manifest.json'),restore_exact_paths_required=True,saved_trades_are_not_price_inputs=True))
 print('NATIVE_INPUT_MANIFEST',len(inputs))
if __name__=='__main__':main()
