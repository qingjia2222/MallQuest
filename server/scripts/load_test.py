import concurrent.futures, statistics, sys, time
from pathlib import Path
SERVER=Path(__file__).resolve().parents[1]; ROOT=SERVER.parent; sys.path.insert(0,str(SERVER))
from fastapi.testclient import TestClient
from app.db import reset_and_seed
from app.main import app

def main(total=120,workers=16):
    reset_and_seed(); c=TestClient(app); login=c.post("/api/auth/web-login",json={"username":"demo","password":"demo123"}).json()["data"]; h={"Authorization":f"Bearer {login['token']}"}; session=c.post("/api/scan",headers=h,json={"mall_id":"mall_demo"}).json()["data"]["session_id"]
    def hit(i):
        start=time.perf_counter()
        if i%3==0:r=c.get("/health")
        elif i%3==1:r=c.get("/api/parking",headers=h,params={"session_id":session})
        else:r=c.post("/api/chat",headers=h,json={"session_id":session,"message":"今天有什么特惠"})
        return r.status_code,(time.perf_counter()-start)*1000
    begin=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool: results=list(pool.map(hit,range(total)))
    elapsed=time.perf_counter()-begin; lat=sorted(v for _,v in results); success=sum(s==200 for s,_ in results); p50=statistics.median(lat); p95=lat[min(len(lat)-1,int(len(lat)*.95))]
    report={"requests":total,"success":success,"errors":total-success,"avg_ms":round(statistics.mean(lat),2),"p50_ms":round(p50,2),"p95_ms":round(p95,2),"throughput_rps":round(total/elapsed,2)}
    out=ROOT/"docs"/"load-test-report.md"; out.parent.mkdir(exist_ok=True); out.write_text("# 轻量压力测试报告\n\n"+"\n".join(f"- {k}: {v}" for k,v in report.items())+"\n\n模式：scripted；16 并发，混合 health/parking/chat 只读请求。\n",encoding="utf-8"); print(report)
    if success!=total: raise SystemExit(1)
if __name__=="__main__": main()
