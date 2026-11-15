"""Fresh-run entry for the unchanged worker with its logging-only adapter fix."""
import worker as w
import hashlib,inspect
cls=w.s.a.ScenarioCache
load_SHA=hashlib.sha256(inspect.getsource(cls.load).encode()).hexdigest()
cls.sources=property(lambda self:self.strict.sources)
assert hashlib.sha256(inspect.getsource(cls.load).encode()).hexdigest()==load_SHA
if __name__=='__main__':w.run('2025','ETH')
