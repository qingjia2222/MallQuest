from fastapi.testclient import TestClient
from app.db import connection, reset_and_seed
from app.main import app
CASES={"date":{"time":"今晚7点","people":2,"budget_per_person":250,"cuisine":"川菜","want_movie":True},"banquet":{"time":"周末6点","people":8,"total_budget":1500,"cuisine":"川菜","private_room":True},"gift":{"recipient":"22岁女生","budget":500,"preferences":"香氛","occasion":"生日"},"family_day":{"child_age":6,"duration":4,"budget":600,"interests":"游乐","meal_preference":"亲子餐"},"business":{"time":"明天下午3点","people":4,"total_budget":2000,"level":"高端","quiet":True,"meal_preference":"中餐"}}
def test_all_scenarios_confirm_gate_and_writes():
    reset_and_seed(); c=TestClient(app); token=c.post("/api/auth/web-login",json={"username":"demo","password":"demo123"}).json()["data"]["token"]; h={"Authorization":f"Bearer {token}"}; s=c.post("/api/scan",headers=h,json={"mall_id":"mall_demo"}).json()["data"]["session_id"]
    for scene,slots in CASES.items():
        with connection() as db: before=db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]+db.execute("SELECT COUNT(*) FROM user_tickets").fetchone()[0]+db.execute("SELECT COUNT(*) FROM user_coupons").fetchone()[0]
        made=c.post("/api/plan/goal",headers=h,json={"session_id":s,"scene":scene,"slots":slots}); assert made.status_code==200; plan=made.json()["data"]; assert plan["state"]=="CONFIRM" and plan["route"]["nodes"] and all(x["mall_id"]=="mall_demo" for x in plan["itinerary"])
        with connection() as db: assert before==db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]+db.execute("SELECT COUNT(*) FROM user_tickets").fetchone()[0]+db.execute("SELECT COUNT(*) FROM user_coupons").fetchone()[0]
        done=c.post("/api/plan/confirm",headers=h,json={"plan_id":plan["plan_id"],"decision":"confirm"}); assert done.status_code==200 and done.json()["data"]["state"]=="DONE" and done.json()["data"]["action_results"]
