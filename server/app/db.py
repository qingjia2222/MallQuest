import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from app.config import settings

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()

@contextmanager
def connection():
    path = Path(settings.mall_db_path); path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10); conn.row_factory = sqlite3.Row; conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn; conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()

SCHEMA = """
CREATE TABLE IF NOT EXISTS malls(id TEXT PRIMARY KEY, name TEXT NOT NULL, is_demo_map INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, display_name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wx_identities(openid TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id));
CREATE TABLE IF NOT EXISTS web_credentials(username TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), salt TEXT NOT NULL, password_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS stores(id TEXT PRIMARY KEY, mall_id TEXT NOT NULL REFERENCES malls(id), name TEXT NOT NULL, category TEXT NOT NULL, floor INTEGER NOT NULL, pos_x REAL NOT NULL, pos_y REAL NOT NULL, route_node TEXT NOT NULL, avg_price REAL NOT NULL, open_status TEXT NOT NULL, queue_minutes INTEGER NOT NULL, reservable INTEGER NOT NULL, seats_available INTEGER NOT NULL, tags TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS parking(id TEXT PRIMARY KEY, mall_id TEXT NOT NULL, area TEXT NOT NULL, total INTEGER NOT NULL, free INTEGER NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS members(user_id TEXT NOT NULL, mall_id TEXT NOT NULL, points INTEGER NOT NULL, level TEXT NOT NULL, expires_on TEXT NOT NULL, PRIMARY KEY(user_id,mall_id));
CREATE TABLE IF NOT EXISTS deals(id TEXT PRIMARY KEY, mall_id TEXT NOT NULL, store_id TEXT, title TEXT NOT NULL, price REAL NOT NULL, stock INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS coupons(id TEXT PRIMARY KEY, mall_id TEXT NOT NULL, store_id TEXT, title TEXT NOT NULL, stock INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS user_coupons(id TEXT PRIMARY KEY, coupon_id TEXT NOT NULL, user_id TEXT NOT NULL, mall_id TEXT NOT NULL, claimed_at TEXT NOT NULL, UNIQUE(coupon_id,user_id,mall_id));
CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, mall_id TEXT NOT NULL, store_id TEXT NOT NULL, kind TEXT NOT NULL, reserved_for TEXT NOT NULL, people INTEGER NOT NULL, notes TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ticket_products(id TEXT PRIMARY KEY, mall_id TEXT NOT NULL, store_id TEXT NOT NULL, title TEXT NOT NULL, price REAL NOT NULL, stock INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS user_tickets(id TEXT PRIMARY KEY, product_id TEXT NOT NULL, user_id TEXT NOT NULL, mall_id TEXT NOT NULL, quantity INTEGER NOT NULL, purchased_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS store_status(store_id TEXT PRIMARY KEY, mall_id TEXT NOT NULL, open_status TEXT NOT NULL, queue_minutes INTEGER NOT NULL, seats_available INTEGER NOT NULL, ticket_stock INTEGER NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, mall_id TEXT NOT NULL, intent TEXT, slots_json TEXT NOT NULL, plan_id TEXT, plan_state TEXT NOT NULL, context_json TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, user_id TEXT NOT NULL, mall_id TEXT NOT NULL, scene TEXT NOT NULL, slots_json TEXT NOT NULL, state TEXT NOT NULL, itinerary_json TEXT NOT NULL, route_json TEXT NOT NULL, action_results_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
"""

MAIN_STORES = [
 ("s01","蜀香小院","川菜",1,220,210,180,12,1,26,"约会,家宴,包间"),("s02","锦城宴府","川菜",2,250,180,260,8,1,36,"家宴,包间,高端"),
 ("s03","樱海日料","日料",2,430,180,220,18,1,18,"约会"),("s04","Luma西餐厅","西餐",2,610,180,320,6,1,20,"安静,高端,约会"),
 ("s05","青岚茶社","茶歇",2,790,180,85,4,1,24,"商务,安静"),("s06","星云咖啡","咖啡",1,420,210,48,3,0,20,"休息,商务"),
 ("s07","茉语奶茶","奶茶",1,610,210,28,9,0,12,"约会"),("s08","糖屿甜品","甜品",1,790,210,46,5,0,16,"亲子,约会"),
 ("s09","QD星幕影院","影院",2,820,420,65,0,0,0,"电影,约会"),("s10","奇趣儿童乐园","儿童乐园",1,800,430,128,6,0,0,"亲子,儿童"),
 ("s11","木棉亲子餐厅","亲子餐厅",1,620,430,110,10,1,28,"亲子,儿童"),("s12","童梦玩具屋","玩具",1,430,430,180,0,0,0,"亲子,礼物"),
 ("s13","拾光礼物研究所","礼品",1,240,430,260,0,0,0,"礼物,设计"),("s14","雾岛香氛","香氛",2,250,420,420,0,0,0,"礼物,香氛,设计"),
 ("s15","墨白设计集","设计零售",2,430,420,360,0,0,0,"礼物,设计"),("s16","云庭商务会客厅","商务空间",2,610,420,500,0,1,12,"商务,安静,高端"),
 ("s17","臻味轩","高端餐厅",2,790,610,480,5,1,22,"商务,高端,安静"),("s18","QD服务台","服务台",1,160,610,0,0,0,0,"服务"),
 ("s19","花间礼盒","礼品",1,340,610,320,0,0,0,"家宴,礼物"),("s20","南风烘焙","烘焙",1,520,610,55,2,0,16,"甜品,亲子"),
 ("s21","轻食工坊","轻食",2,520,610,72,7,1,18,"商务"),("s22","海味坊","粤菜",2,340,610,230,11,1,30,"家宴,包间")]

def reset_and_seed() -> None:
    path=Path(settings.mall_db_path)
    if path.exists(): path.unlink()
    with connection() as db:
        db.executescript(SCHEMA)
        db.executemany("INSERT INTO malls VALUES(?,?,?)",[("mall_demo","QD square",1),("mall_alt","邻里荟",1)])
        db.executemany("INSERT INTO users VALUES(?,?,?)",[("user_demo","演示会员",now_iso()),("user_alt","隔离测试会员",now_iso())])
        for username,user_id,password in [("demo","user_demo","demo123"),("alt","user_alt","alt123")]:
            salt=f"mall-{username}-salt"; db.execute("INSERT INTO web_credentials VALUES(?,?,?,?)",(username,user_id,salt,hash_password(password,salt)))
        db.executemany("INSERT INTO wx_identities VALUES(?,?)",[("mock-openid-demo","user_demo"),("mock-openid-alt","user_alt")])
        for sid,name,cat,floor,x,y,price,queue,reservable,seats,tags in MAIN_STORES:
            db.execute("INSERT INTO stores VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,"mall_demo",name,cat,floor,x,y,f"f{floor}_{sid}",price,"open",queue,reservable,seats,tags))
        alt=[("a01","邻里咖啡","咖啡",1,250,250,35,2,0,10,"休息"),("a02","邻里餐厅","家常菜",1,500,250,80,5,1,16,"家庭"),("a03","邻里服务台","服务台",1,150,500,0,0,0,0,"服务"),("a04","邻里亲子屋","儿童乐园",1,500,500,50,3,0,0,"亲子")]
        for sid,name,cat,floor,x,y,price,queue,reservable,seats,tags in alt:
            db.execute("INSERT INTO stores VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,"mall_alt",name,cat,floor,x,y,f"a_{sid}",price,"open",queue,reservable,seats,tags))
        db.executemany("INSERT INTO parking VALUES(?,?,?,?,?,?)",[("p1","mall_demo","B1-A",320,86,now_iso()),("p2","mall_demo","B1-B",280,42,now_iso()),("p3","mall_demo","B2-C",260,119,now_iso()),("pa","mall_alt","地面停车区",80,21,now_iso())])
        db.executemany("INSERT INTO members VALUES(?,?,?,?,?)",[("user_demo","mall_demo",2680,"金卡","2027-12-31"),("user_demo","mall_alt",120,"普卡","2027-06-30"),("user_alt","mall_demo",60,"普卡","2027-03-31")])
        deals=[("d1","s01","川菜双人餐",238,30),("d2","s09","双人电影套票",108,50),("d3","s10","儿童乐园下午票",88,40),("d4","s13","生日礼物满减",399,12),("d5","s16","商务会议两小时",680,8),("d6","s17","商务晚宴套餐",1288,10),("d7","s07","第二杯半价",18,80),("d8","s11","亲子套餐",198,25)]
        db.executemany("INSERT INTO deals VALUES(?,?,?,?,?,?)",[(i,"mall_demo",s,t,p,stock) for i,s,t,p,stock in deals])
        coupons=[("c1","s01","蜀香小院满200减30",50),("c2","s13","礼物研究所满300减50",30),("c3","s10","儿童乐园减20",40),("c4","s16","商务空间减100",12),("c5","s17","臻味轩满1000减120",20),("c6","s07","奶茶第二杯半价券",60)]
        db.executemany("INSERT INTO coupons VALUES(?,?,?,?,?)",[(i,"mall_demo",s,t,stock) for i,s,t,stock in coupons])
        products=[("t_movie","s09","QD星幕影院电影票",54,120),("t_child","s10","奇趣儿童乐园单次票",88,80)]
        db.executemany("INSERT INTO ticket_products VALUES(?,?,?,?,?,?)",[(i,"mall_demo",s,t,p,stock) for i,s,t,p,stock in products])
        rows=db.execute("SELECT id,mall_id,open_status,queue_minutes,seats_available FROM stores").fetchall()
        db.executemany("INSERT INTO store_status VALUES(?,?,?,?,?,?,?)",[(r["id"],r["mall_id"],r["open_status"],r["queue_minutes"],r["seats_available"],120 if r["id"]=="s09" else 80 if r["id"]=="s10" else 0,now_iso()) for r in rows])

def ensure_database() -> None:
    with connection() as db:
        db.executescript(SCHEMA); exists=db.execute("SELECT 1 FROM malls LIMIT 1").fetchone()
    if not exists: reset_and_seed()

def rows_to_dicts(rows): return [dict(row) for row in rows]
def load_json(value: str): return json.loads(value) if value else {}
