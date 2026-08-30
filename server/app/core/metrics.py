from collections import Counter, deque
from threading import Lock
class Metrics:
    def __init__(self): self.lock=Lock(); self.requests=0; self.errors=0; self.latencies=deque(maxlen=500); self.counters=Counter()
    def record_request(self,status,latency):
        with self.lock: self.requests+=1; self.errors+=int(status>=400); self.latencies.append(latency)
    def increment(self,name):
        with self.lock: self.counters[name]+=1
    def snapshot(self):
        with self.lock:
            vals=sorted(self.latencies); p95=vals[min(len(vals)-1,int(len(vals)*.95))] if vals else 0
            return {"total_requests":self.requests,"error_count":self.errors,"avg_latency_ms":round(sum(vals)/len(vals),2) if vals else 0,"p95_latency_ms":round(p95,2),**dict(self.counters)}
metrics=Metrics()
