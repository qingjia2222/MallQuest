import os, sys
from pathlib import Path
os.environ["WX_AUTH_MODE"]="mock"; os.environ["LLM_MODE"]="scripted"
SERVER=Path(__file__).resolve().parents[1]; ROOT=SERVER.parent; sys.path.insert(0,str(SERVER))
from fastapi.testclient import TestClient
from app.db import reset_and_seed
from app.core.router import write_demo_maps
from app.main import app

SCENARIOS={
"date":{"text":"今晚7点两个人约会，人均250，想吃川菜还要看电影","slots":{"time":"今晚7点","people":2,"budget_per_person":250,"cuisine":"川菜","want_movie":True}},
"banquet":{"text":"周末6点8个人家宴，预算1500，川菜包间","slots":{"time":"周末6点","people":8,"total_budget":1500,"cuisine":"川菜","private_room":True}},
"gift":{"text":"给22岁女生挑生日礼物，预算500，喜欢香氛和设计感小物","slots":{"recipient":"22岁女生","budget":500,"preferences":"香氛和设计感小物","occasion":"生日"}},
"family_day":{"text":"带6岁孩子玩4小时，预算600，再吃饭","slots":{"child_age":6,"duration":4,"budget":600,"interests":"游乐","meal_preference":"亲子餐"}},
"business":{"text":"明天下午3点接待4位客户，预算2000，安静有档次，先谈事再吃饭","slots":{"time":"明天下午3点","people":4,"total_budget":2000,"level":"高端","quiet":True,"meal_preference":"高端中餐"}}}

def main():
    reset_and_seed(); write_demo_maps(); c=TestClient(app)
    login=c.post("/api/auth/web-login",json={"username":"demo","password":"demo123"}); login.raise_for_status(); token=login.json()["data"]["token"]; h={"Authorization":f"Bearer {token}"}
    wx=c.post("/api/auth/wx-login",json={"code":"mock-demo"}); wx.raise_for_status(); assert wx.json()["data"]["user_id"]==login.json()["data"]["user_id"]
    scan=c.post("/api/scan",headers=h,json={"mall_id":"mall_demo"}); scan.raise_for_status(); session=scan.json()["data"]["session_id"]
    assert c.get("/api/parking",headers=h,params={"session_id":session}).json()["data"]["total_free"]>0
    rag=c.post("/api/chat",headers=h,json={"session_id":session,"message":"积分多久过期？"}).json()["data"]; assert rag["result"]["sources"]
    for scene,payload in SCENARIOS.items():
        made=c.post("/api/plan/goal",headers=h,json={"session_id":session,"scene":scene,**payload}); made.raise_for_status(); plan=made.json()["data"]; assert plan["state"]=="CONFIRM" and plan["route"]["nodes"]
        done=c.post("/api/plan/confirm",headers=h,json={"plan_id":plan["plan_id"],"decision":"confirm"}); done.raise_for_status(); assert done.json()["data"]["state"]=="DONE"
    tts=c.post("/api/tts",headers=h,json={"text":"已为你规划好今天的行程。"}); tts.raise_for_status(); audio=c.get(tts.json()["data"]["audio_url"]); assert audio.status_code==200 and len(audio.content)>100
    metrics=c.get("/api/debug/metrics",headers=h); metrics.raise_for_status(); print(metrics.json()["data"]); print("SMOKE DEMO PASSED")
if __name__=="__main__": main()
