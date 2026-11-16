"""Relocate only path literals at import; original files/manifest bytes remain intact."""
import importlib.machinery,os
from pathlib import Path
ROOT=Path(os.environ.get('BTC_REPO_ROOT',Path(__file__).resolve().parents[2])).resolve()
_original=importlib.machinery.SourceFileLoader.get_code

def _code(self,fullname):
 path=Path(self.path)
 if path.suffix=='.py' and path.is_relative_to(ROOT):
  text=self.get_data(self.path).decode('utf-8')
  return compile(text.replace('/workspace/btc-eth-backtest',str(ROOT)),self.path,'exec',dont_inherit=True)
 return _original(self,fullname)
importlib.machinery.SourceFileLoader.get_code=_code
