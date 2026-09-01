import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from app.config import settings
from app.core.map_catalog import map_catalog, stable_store_id

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()

@contextmanager
def connection(immediate: bool = False):
    path = Path(settings.mall_db_path); path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15); conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    if immediate:
        conn.execute("BEGIN IMMEDIATE")
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
CREATE TABLE IF NOT EXISTS merchant_credentials(store_id TEXT PRIMARY KEY REFERENCES stores(id), user_id TEXT NOT NULL UNIQUE REFERENCES users(id), mall_id TEXT NOT NULL REFERENCES malls(id), salt TEXT NOT NULL, password_hash TEXT NOT NULL, registered_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS stores(id TEXT PRIMARY KEY, mall_id TEXT NOT NULL REFERENCES malls(id), name TEXT NOT NULL, category TEXT NOT NULL, floor INTEGER NOT NULL, pos_x REAL NOT NULL, pos_y REAL NOT NULL, route_node TEXT NOT NULL, avg_price REAL NOT NULL, open_status TEXT NOT NULL, queue_minutes INTEGER NOT NULL, reservable INTEGER NOT NULL, seats_available INTEGER NOT NULL, tags TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS parking(id TEXT PRIMARY KEY, mall_id TEXT NOT NULL, area TEXT NOT NULL, total INTEGER NOT NULL, free INTEGER NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS members(user_id TEXT NOT NULL, mall_id TEXT NOT NULL, points INTEGER NOT NULL, level TEXT NOT NULL, expires_on TEXT NOT NULL, PRIMARY KEY(user_id,mall_id));
CREATE TABLE IF NOT EXISTS deals(id TEXT PRIMARY KEY, mall_id TEXT NOT NULL, store_id TEXT, title TEXT NOT NULL, price REAL NOT NULL, stock INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS deal_purchases(id TEXT PRIMARY KEY, deal_id TEXT NOT NULL, user_id TEXT NOT NULL, mall_id TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price REAL NOT NULL, status TEXT NOT NULL, purchased_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS coupons(id TEXT PRIMARY KEY, mall_id TEXT NOT NULL, store_id TEXT, title TEXT NOT NULL, stock INTEGER NOT NULL, face_value REAL, min_spend REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS user_coupons(id TEXT PRIMARY KEY, coupon_id TEXT NOT NULL, user_id TEXT NOT NULL, mall_id TEXT NOT NULL, claimed_at TEXT NOT NULL, UNIQUE(coupon_id,user_id,mall_id));
CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, mall_id TEXT NOT NULL, store_id TEXT NOT NULL, kind TEXT NOT NULL, reserved_for TEXT NOT NULL, people INTEGER NOT NULL, notes TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ticket_products(id TEXT PRIMARY KEY, mall_id TEXT NOT NULL, store_id TEXT NOT NULL, title TEXT NOT NULL, price REAL NOT NULL, stock INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS user_tickets(id TEXT PRIMARY KEY, product_id TEXT NOT NULL, user_id TEXT NOT NULL, mall_id TEXT NOT NULL, quantity INTEGER NOT NULL, purchased_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS store_status(store_id TEXT PRIMARY KEY, mall_id TEXT NOT NULL, open_status TEXT NOT NULL, queue_minutes INTEGER NOT NULL, seats_available INTEGER NOT NULL, ticket_stock INTEGER NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, mall_id TEXT NOT NULL, intent TEXT, slots_json TEXT NOT NULL, plan_id TEXT, plan_state TEXT NOT NULL, context_json TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, user_id TEXT NOT NULL, mall_id TEXT NOT NULL, scene TEXT NOT NULL, slots_json TEXT NOT NULL, state TEXT NOT NULL, itinerary_json TEXT NOT NULL, route_json TEXT NOT NULL, action_results_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS plan_snapshots(id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, revision INTEGER NOT NULL, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(plan_id,revision));
CREATE TABLE IF NOT EXISTS store_details(store_id TEXT PRIMARY KEY REFERENCES stores(id), details_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS store_profiles(store_id TEXT PRIMARY KEY REFERENCES stores(id), store_code TEXT NOT NULL UNIQUE, manager_name TEXT NOT NULL, employees_json TEXT NOT NULL, business_hours TEXT NOT NULL, service_tags TEXT NOT NULL, contact TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS merchant_store_access(user_id TEXT NOT NULL REFERENCES users(id), mall_id TEXT NOT NULL, store_id TEXT NOT NULL REFERENCES stores(id), PRIMARY KEY(user_id,store_id));
CREATE TABLE IF NOT EXISTS manager_access(user_id TEXT NOT NULL REFERENCES users(id), mall_id TEXT NOT NULL, PRIMARY KEY(user_id,mall_id));
CREATE TABLE IF NOT EXISTS mall_service_codes(code TEXT PRIMARY KEY, mall_id TEXT NOT NULL REFERENCES malls(id), entry_node TEXT NOT NULL, active INTEGER NOT NULL, label TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS analytics_snapshots(id TEXT PRIMARY KEY, mall_id TEXT NOT NULL, grain TEXT NOT NULL, label TEXT NOT NULL, footfall INTEGER NOT NULL, revenue REAL NOT NULL, conversion_rate REAL NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS map_jobs(id TEXT PRIMARY KEY, mall_id TEXT NOT NULL, source_name TEXT NOT NULL, map_mode TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS store_map_bindings(
  store_id TEXT PRIMARY KEY REFERENCES stores(id),
  mall_id TEXT NOT NULL REFERENCES malls(id),
  source_key TEXT NOT NULL,
  source_label TEXT NOT NULL,
  floor INTEGER NOT NULL,
  map_x REAL NOT NULL,
  map_z REAL NOT NULL,
  map_width REAL NOT NULL,
  map_depth REAL NOT NULL,
  source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_plans_owner ON plans(user_id,mall_id,updated_at);
CREATE INDEX IF NOT EXISTS idx_sessions_owner ON sessions(user_id,mall_id,updated_at);
"""

def _ensure_columns(db) -> None:
    """Small in-place migrations keep an existing demo database usable after updates."""
    columns={row["name"] for row in db.execute("PRAGMA table_info(reservations)").fetchall()}
    if "scheduled_at" not in columns:
        db.execute("ALTER TABLE reservations ADD COLUMN scheduled_at TEXT")
    if "duration_minutes" not in columns:
        db.execute("ALTER TABLE reservations ADD COLUMN duration_minutes INTEGER NOT NULL DEFAULT 60")
    plan_columns={row["name"] for row in db.execute("PRAGMA table_info(plans)").fetchall()}
    if "revision" not in plan_columns:
        db.execute("ALTER TABLE plans ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")
    coupon_columns={row["name"] for row in db.execute("PRAGMA table_info(coupons)").fetchall()}
    if "face_value" not in coupon_columns:
        db.execute("ALTER TABLE coupons ADD COLUMN face_value REAL")
    if "min_spend" not in coupon_columns:
        db.execute("ALTER TABLE coupons ADD COLUMN min_spend REAL NOT NULL DEFAULT 0")
    db.execute("INSERT OR IGNORE INTO app_meta VALUES('database_instance_id',?)",("db_"+uuid.uuid4().hex,))
    db.execute("INSERT OR REPLACE INTO app_meta VALUES('schema_version','3')")

def _party_a_assets():
    root=Path(__file__).resolve().parents[2]/"web"/"src"/"store"
    info_path=root/"store_info.json"; ring_path=root/"mall_ring.json"
    if not info_path.exists(): return {}, {"stores":[],"corners":{}}
    return json.loads(info_path.read_text(encoding="utf-8")), json.loads(ring_path.read_text(encoding="utf-8"))

def seed_party_a_catalog(db) -> None:
    """Import only the business blocks that the active 3D map really renders.

    Bathrooms, security, front desk, waterfall hall and vertical facilities stay
    in the map occupancy model but are not exposed as merchant stores.
    """
    for entry in map_catalog()["businesses"]:
        details=entry.get("details") or {}; name=entry["name"]; store_id=stable_store_id(name); floor=entry["floor"]
        queue=int(details.get("queue_minutes") or 0); seats=int(details.get("seats_available") or 0); category=details.get("category") or "零售"; tags=",".join(details.get("tags") or [])
        avg_price=88 if category=="餐饮" else 38 if category=="饮品甜品" else 160
        pos_x=round((entry["x"]+29)/58*1000,2); pos_y=round((entry["z"]+29)/58*760,2); route_node=f"f{floor}_store_{store_id}"
        db.execute("""INSERT INTO stores(id,mall_id,name,category,floor,pos_x,pos_y,route_node,avg_price,open_status,queue_minutes,reservable,seats_available,tags)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,category=excluded.category,floor=excluded.floor,pos_x=excluded.pos_x,pos_y=excluded.pos_y,route_node=excluded.route_node,avg_price=excluded.avg_price,open_status=excluded.open_status,queue_minutes=excluded.queue_minutes,reservable=excluded.reservable,seats_available=excluded.seats_available,tags=excluded.tags""",
          (store_id,"mall_demo",name,category,floor,pos_x,pos_y,route_node,avg_price,details.get("open_status") or "open",queue,int(category=="餐饮"),seats,tags))
        db.execute("INSERT OR REPLACE INTO store_details VALUES(?,?)",(store_id,json.dumps({**details,"asset_name":name},ensure_ascii=False)))
        db.execute("INSERT OR IGNORE INTO store_status VALUES(?,?,?,?,?,?,?)",(store_id,"mall_demo",details.get("open_status") or "open",queue,seats,0,now_iso()))
        db.execute("INSERT OR REPLACE INTO store_map_bindings VALUES(?,?,?,?,?,?,?,?,?,?)",(store_id,"mall_demo",entry["source_key"],name,floor,entry["x"],entry["z"],entry["width"],entry["depth"],"party_a_mall_ring"))

MAIN_STORES = [
 ("s01","蜀香小院","川菜",1,220,210,180,12,1,26,"约会,家宴,包间"),("s02","锦城宴府","川菜",2,250,180,260,8,1,36,"家宴,包间,高端"),
 ("s03","樱海日料","日料",2,430,180,220,18,1,18,"约会"),("s04","Luma西餐厅","西餐",2,610,180,320,6,1,20,"安静,高端,约会"),
 ("s05","青岚茶社","茶歇",2,790,180,85,4,1,24,"商务,安静"),("s06","星云咖啡","咖啡",1,420,210,48,3,0,20,"休息,商务"),
 ("s07","茉语奶茶","奶茶",1,610,210,28,9,0,12,"约会"),("s08","糖屿甜品","甜品",1,790,210,46,5,0,16,"亲子,约会"),
 ("s09","星河里星幕影院","影院",2,820,420,65,0,0,0,"电影,约会"),("s10","奇趣儿童乐园","儿童乐园",1,800,430,128,6,0,0,"亲子,儿童"),
 ("s11","木棉亲子餐厅","亲子餐厅",1,620,430,110,10,1,28,"亲子,儿童"),("s12","童梦玩具屋","玩具",1,430,430,180,0,0,0,"亲子,礼物"),
 ("s13","拾光礼物研究所","礼品",1,240,430,260,0,0,0,"礼物,设计"),("s14","雾岛香氛","香氛",2,250,420,420,0,0,0,"礼物,香氛,设计"),
 ("s15","墨白设计集","设计零售",2,430,420,360,0,0,0,"礼物,设计"),("s16","云庭商务会客厅","商务空间",2,610,420,500,0,1,12,"商务,安静,高端"),
 ("s17","臻味轩","高端餐厅",2,790,610,480,5,1,22,"商务,高端,安静"),("s18","星河里服务台","服务台",1,160,610,0,0,0,0,"服务"),
 ("s19","花间礼盒","礼品",1,340,610,320,0,0,0,"家宴,礼物"),("s20","南风烘焙","烘焙",1,520,610,55,2,0,16,"甜品,亲子"),
 ("s21","轻食工坊","轻食",2,520,610,72,7,1,18,"商务"),("s22","海味坊","粤菜",2,340,610,230,11,1,30,"家宴,包间")]

# 甲组 3D 地图几何与乙组业务店铺的稳定绑定。业务状态仍以 stores/store_status 为准；
# source_key/map_* 保留甲组 oakwood_plan 的槽位与坐标，公共设施继续留在前端地图中。
STORE_MAP_BINDINGS = [
 ("s01","shop102114","蜀香小院",1,-12.60,5.66,5.08,2.49),
 ("s02","shop204","锦城宴府",2,-12.60,9.45,5.08,4.90),
 ("s03","shop220","樱海日料",2,0.61,0.00,3.23,7.83),
 ("s04","shop203_tl","Luma西餐厅",2,-18.58,0.00,6.90,9.91),
 ("s05","shop206","青岚茶社",2,-5.06,9.45,3.30,4.90),
 ("s06","shop106","星云咖啡",1,4.91,0.00,3.38,4.86),
 ("s07","shop103113","茉语奶茶",1,-18.56,4.03,6.94,5.75),
 ("s08","shop101118_tr","糖屿甜品",1,17.49,0.00,8.35,8.90),
 ("s09","shop201","星河里星幕影院",2,-11.04,0.00,5.34,7.83),
 ("s10","儿童乐园","奇趣儿童乐园",1,9.00,-1.00,11.00,8.00),
 ("s11","shop107","木棉亲子餐厅",1,8.20,0.00,3.26,4.86),
 ("s12","shop108","童梦玩具屋",1,11.59,0.00,3.56,4.86),
 ("s13","shop103","拾光礼物研究所",1,-6.20,0.00,3.45,4.86),
 ("s14","shop205","雾岛香氛",2,-8.39,9.45,3.41,4.90),
 ("s15","shop216","墨白设计集",2,-2.63,0.00,3.30,7.83),
 ("s16","观影天桥","云庭商务会客厅",2,-0.79,0.61,8.20,6.00),
 ("s17","shop224","臻味轩",2,8.61,0.00,5.64,7.83),
 ("s18","shop101118_tl","星河里服务台",1,-18.52,0.00,7.01,8.90),
 ("s19","shopinfo","花间礼盒",1,17.60,3.77,8.12,3.93),
 ("s20","shop101","南风烘焙",1,-13.10,0.00,4.08,4.86),
 ("s21","shop203_bl","轻食工坊",2,-18.56,8.37,6.94,7.09),
 ("s22","shop222","海味坊",2,4.01,0.00,3.64,7.83),
]

def seed_commercial(db) -> None:
    now=now_iso()
    db.execute("UPDATE malls SET name=? WHERE id=?",("星河里","mall_demo"))
    phone_salt="mall-phone-demo-salt"
    db.execute("INSERT OR IGNORE INTO web_credentials VALUES(?,?,?,?)",("11111111111","user_demo",phone_salt,hash_password("123456",phone_salt)))
    db.executemany("INSERT OR REPLACE INTO mall_service_codes VALUES(?,?,?,?,?)",[("QD-AI-DEMO","mall_demo","f1_entrance",1,"星河里 AI 服务二维码"),("ALT-AI-DEMO","mall_alt","a_a03",1,"邻里荟 AI 服务二维码")])
    db.execute("INSERT OR IGNORE INTO users VALUES(?,?,?)",("manager_demo","星河里管理员",now))
    demo_merchant_store=stable_store_id("蜀签成都串串香")
    db.execute("INSERT OR IGNORE INTO users VALUES(?,?,?)",("merchant_s01","蜀签成都串串香商户",now))
    salt="mall-manager-salt"; db.execute("INSERT OR IGNORE INTO web_credentials VALUES(?,?,?,?)",("manager","manager_demo",salt,hash_password("manager123",salt)))
    db.execute("INSERT OR IGNORE INTO manager_access VALUES(?,?)",("manager_demo","mall_demo"))
    db.execute("INSERT OR IGNORE INTO merchant_store_access VALUES(?,?,?)",("merchant_s01","mall_demo",demo_merchant_store))
    stores=db.execute("SELECT id,name,tags FROM stores WHERE mall_id='mall_demo'").fetchall()
    for index,store in enumerate(stores,1):
        code="QD-S01-DEMO" if store["id"]==demo_merchant_store else f"QD-{store['id'].upper()}-DEMO"
        manager="陈店长" if store["id"]==demo_merchant_store else f"{store['name'][:1]}店长"
        db.execute("INSERT OR IGNORE INTO store_profiles VALUES(?,?,?,?,?,?,?,?)",(store["id"],code,manager,json.dumps(["值班员工A","值班员工B"],ensure_ascii=False),"10:00-22:00",store["tags"] or "到店服务","400-800-%04d"%index,now))
    merchant_salt="mall-merchant-demo-salt"
    db.execute("INSERT OR IGNORE INTO merchant_credentials VALUES(?,?,?,?,?,?)",(demo_merchant_store,"merchant_s01","mall_demo",merchant_salt,hash_password("123456",merchant_salt),now))
    metrics=[
        ("a_day_1","day","08-25",18620,1286000,0.184),("a_day_2","day","08-26",19480,1362000,0.191),("a_day_3","day","08-27",20310,1428000,0.196),("a_day_4","day","08-28",21890,1586000,0.204),("a_day_5","day","08-29",24760,1812000,0.218),("a_day_6","day","08-30",28640,2159000,0.231),("a_day_7","day","08-31",26380,1984000,0.226),
        ("a_month_6","month","3月",488000,35600000,0.186),("a_month_5","month","4月",512000,37100000,0.192),("a_month_4","month","5月",536000,38900000,0.198),("a_month_3","month","6月",561000,40800000,0.205),("a_month_2","month","7月",594000,43900000,0.214),("a_month_1","month","8月",628000,47200000,0.223),
        ("a_year_3","year","2024",6120000,438000000,0.191),("a_year_2","year","2025",6840000,502000000,0.207),("a_year_1","year","2026",7310000,548000000,0.221)]
    db.executemany("INSERT OR IGNORE INTO analytics_snapshots VALUES(?,?,?,?,?,?,?,?)",[(i,"mall_demo",grain,label,footfall,revenue,rate,now) for i,grain,label,footfall,revenue,rate in metrics])
    db.execute("INSERT OR IGNORE INTO map_jobs VALUES(?,?,?,?,?,?)",("map_demo_seed","mall_demo","星河里-demo.svg","demo_2_5d","published",now))

def seed_marketplace(db) -> None:
    ids={name:stable_store_id(name) for name in ("蜀签成都串串香","格瑞特运动馆","金伯利","星巴克","川食公馆","世界茶饮","拼桌茶餐厅")}
    deals=[("d1",ids["蜀签成都串串香"],"川味双人餐",238,30),("d2",ids["格瑞特运动馆"],"双人运动体验",108,50),("d3",ids["格瑞特运动馆"],"亲子运动体验票",88,40),("d4",ids["金伯利"],"礼赠满减",399,12),("d5",ids["星巴克"],"商务咖啡套餐",68,30),("d6",ids["川食公馆"],"商务晚宴套餐",688,10),("d7",ids["世界茶饮"],"第二杯半价",18,80),("d8",ids["拼桌茶餐厅"],"家庭套餐",198,25)]
    db.executemany("INSERT OR REPLACE INTO deals VALUES(?,?,?,?,?,?)",[(i,"mall_demo",s,t,p,stock) for i,s,t,p,stock in deals])
    coupons=[("c1",ids["蜀签成都串串香"],"蜀签成都串串香满200减30",50,30,200),("c2",ids["金伯利"],"礼赠满300减50",30,50,300),("c3",ids["格瑞特运动馆"],"运动体验减20",40,20,0),("c4",ids["星巴克"],"商务咖啡减10",30,10,0),("c5",ids["川食公馆"],"川食公馆满500减60",20,60,500),("c6",ids["世界茶饮"],"茶饮第二杯半价券",60,None,0)]
    db.executemany("""INSERT INTO coupons(id,mall_id,store_id,title,stock,face_value,min_spend) VALUES(?,?,?,?,?,?,?)
      ON CONFLICT(id) DO UPDATE SET mall_id=excluded.mall_id,store_id=excluded.store_id,title=excluded.title,
      face_value=excluded.face_value,min_spend=excluded.min_spend""",[(i,"mall_demo",s,t,stock,value,minimum) for i,s,t,stock,value,minimum in coupons])
    db.execute("DELETE FROM ticket_products WHERE mall_id='mall_demo' AND id!='t_sport'")
    db.execute("INSERT OR REPLACE INTO ticket_products VALUES(?,?,?,?,?,?)",("t_sport","mall_demo",ids["格瑞特运动馆"],"格瑞特运动馆单次体验票",88,120))

def reset_and_seed() -> None:
    path=Path(settings.mall_db_path)
    if path.exists(): path.unlink()
    with connection() as db:
        db.executescript(SCHEMA)
        _ensure_columns(db)
        db.executemany("INSERT INTO malls VALUES(?,?,?)",[("mall_demo","星河里",1),("mall_alt","邻里荟",1)])
        db.executemany("INSERT INTO users VALUES(?,?,?)",[("user_demo","演示会员",now_iso()),("user_alt","隔离测试会员",now_iso())])
        for username,user_id,password in [("demo","user_demo","demo123"),("alt","user_alt","alt123")]:
            salt=f"mall-{username}-salt"; db.execute("INSERT INTO web_credentials VALUES(?,?,?,?)",(username,user_id,salt,hash_password(password,salt)))
        db.executemany("INSERT INTO wx_identities VALUES(?,?)",[("mock-openid-demo","user_demo"),("mock-openid-alt","user_alt")])
        alt=[("a01","邻里咖啡","咖啡",1,250,250,35,2,0,10,"休息"),("a02","邻里餐厅","家常菜",1,500,250,80,5,1,16,"家庭"),("a03","邻里服务台","服务台",1,150,500,0,0,0,0,"服务"),("a04","邻里亲子屋","儿童乐园",1,500,500,50,3,0,0,"亲子")]
        for sid,name,cat,floor,x,y,price,queue,reservable,seats,tags in alt:
            db.execute("INSERT INTO stores VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,"mall_alt",name,cat,floor,x,y,f"a_{sid}",price,"open",queue,reservable,seats,tags))
        seed_party_a_catalog(db)
        db.executemany("INSERT INTO parking VALUES(?,?,?,?,?,?)",[("p1","mall_demo","B1-A",320,86,now_iso()),("p2","mall_demo","B1-B",280,42,now_iso()),("p3","mall_demo","B2-C",260,119,now_iso()),("pa","mall_alt","地面停车区",80,21,now_iso())])
        db.executemany("INSERT INTO members VALUES(?,?,?,?,?)",[("user_demo","mall_demo",2680,"金卡","2027-12-31"),("user_demo","mall_alt",120,"普卡","2027-06-30"),("user_alt","mall_demo",60,"普卡","2027-03-31")])
        seed_marketplace(db)
        rows=db.execute("SELECT id,mall_id,open_status,queue_minutes,seats_available FROM stores").fetchall()
        ticket_store=stable_store_id("格瑞特运动馆")
        db.executemany("INSERT OR REPLACE INTO store_status VALUES(?,?,?,?,?,?,?)",[(r["id"],r["mall_id"],r["open_status"],r["queue_minutes"],r["seats_available"],120 if r["id"]==ticket_store else 0,now_iso()) for r in rows])
        seed_commercial(db)

LEGACY_STORE_REPLACEMENTS={
    "s01":"蜀签成都串串香","s02":"川食公馆","s03":"鸿匠铁板烧日本料理","s04":"吉布鲁牛排海鲜自助餐厅",
    "s05":"星巴克","s06":"途尚咖啡","s07":"世界茶饮","s08":"满记甜品","s09":"格瑞特运动馆",
    "s10":"格瑞特运动馆","s11":"拼桌茶餐厅","s12":"小米之家","s13":"金伯利","s14":"阅江轩",
    "s15":"大众书局","s16":"星巴克","s17":"川食公馆","s18":"蜀签成都串串香","s19":"福气糖",
    "s20":"面包新语","s21":"星巴克","s22":"鱼螺满筐",
}

def reconcile_demo_catalog() -> dict:
    """Destructively align mall_demo to the visible 3D map after an external backup."""
    target={stable_store_id(entry["name"]) for entry in map_catalog()["businesses"]}
    with connection(immediate=True) as db:
        current={row["id"]:row["name"] for row in db.execute("SELECT id,name FROM stores WHERE mall_id='mall_demo'").fetchall()}
        extras=sorted(set(current)-target)
        for old_id,new_name in LEGACY_STORE_REPLACEMENTS.items():
            db.execute("UPDATE reservations SET store_id=? WHERE mall_id='mall_demo' AND store_id=?",(stable_store_id(new_name),old_id))
        if extras:
            marks=",".join("?" for _ in extras)
            db.execute(f"DELETE FROM reservations WHERE mall_id='mall_demo' AND store_id IN ({marks})",extras)
            db.execute(f"DELETE FROM merchant_credentials WHERE mall_id='mall_demo' AND store_id IN ({marks})",extras)
            db.execute(f"DELETE FROM merchant_store_access WHERE mall_id='mall_demo' AND store_id IN ({marks})",extras)
            db.execute(f"DELETE FROM store_profiles WHERE store_id IN ({marks})",extras)
            db.execute(f"DELETE FROM store_details WHERE store_id IN ({marks})",extras)
            db.execute(f"DELETE FROM store_map_bindings WHERE mall_id='mall_demo' AND store_id IN ({marks})",extras)
            db.execute(f"DELETE FROM store_status WHERE mall_id='mall_demo' AND store_id IN ({marks})",extras)
            db.execute(f"DELETE FROM stores WHERE mall_id='mall_demo' AND id IN ({marks})",extras)
        plan_ids=[row[0] for row in db.execute("SELECT id FROM plans WHERE mall_id='mall_demo'").fetchall()]
        if plan_ids:
            marks=",".join("?" for _ in plan_ids); db.execute(f"DELETE FROM plan_snapshots WHERE plan_id IN ({marks})",plan_ids)
            db.execute(f"DELETE FROM plans WHERE id IN ({marks})",plan_ids)
        db.execute("UPDATE sessions SET plan_id=NULL,plan_state='IDLE',updated_at=? WHERE mall_id='mall_demo'",(now_iso(),))
        # Rebuild all map-derived rows so names, codes, positions and live status share one source.
        db.execute("DELETE FROM merchant_credentials WHERE mall_id='mall_demo'")
        db.execute("DELETE FROM merchant_store_access WHERE mall_id='mall_demo'")
        db.execute("DELETE FROM store_profiles WHERE store_id IN (SELECT id FROM stores WHERE mall_id='mall_demo')")
        db.execute("DELETE FROM store_map_bindings WHERE mall_id='mall_demo'")
        seed_party_a_catalog(db); seed_marketplace(db); seed_commercial(db)
        ticket_store=stable_store_id("格瑞特运动馆")
        db.execute("UPDATE store_status SET ticket_stock=CASE WHEN store_id=? THEN 120 ELSE 0 END WHERE mall_id='mall_demo'",(ticket_store,))
        final=db.execute("SELECT COUNT(*) FROM stores WHERE mall_id='mall_demo'").fetchone()[0]
    return {"before":len(current),"removed":len(extras),"removed_stores":[{"id":item,"name":current[item]} for item in extras],"after":final,"map_businesses":len(target),"plans_invalidated":len(plan_ids)}

def ensure_database() -> None:
    with connection() as db:
        db.executescript(SCHEMA); _ensure_columns(db); exists=db.execute("SELECT 1 FROM malls LIMIT 1").fetchone()
        if exists: seed_party_a_catalog(db); seed_marketplace(db); seed_commercial(db)
    if not exists: reset_and_seed()

def database_health() -> dict:
    """Read-only readiness check used by startup, /health and the ops guard."""
    required={"malls","stores","store_status","store_map_bindings","sessions","plans","plan_snapshots","app_meta"}
    try:
        with connection() as db:
            integrity=db.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_key_errors=len(db.execute("PRAGMA foreign_key_check").fetchall())
            tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            missing=sorted(required-tables)
            stores=db.execute("SELECT COUNT(*) FROM stores WHERE mall_id=?",(settings.default_mall_id,)).fetchone()[0] if "stores" in tables else 0
            statuses=db.execute("SELECT COUNT(*) FROM store_status WHERE mall_id=?",(settings.default_mall_id,)).fetchone()[0] if "store_status" in tables else 0
            bindings=db.execute("SELECT COUNT(*) FROM store_map_bindings WHERE mall_id=?",(settings.default_mall_id,)).fetchone()[0] if "store_map_bindings" in tables else 0
            instance=db.execute("SELECT value FROM app_meta WHERE key='database_instance_id'").fetchone() if "app_meta" in tables else None
        issues=[]
        if integrity!="ok": issues.append(f"integrity_check={integrity}")
        if foreign_key_errors: issues.append(f"foreign_key_errors={foreign_key_errors}")
        if missing: issues.append("missing_tables="+",".join(missing))
        if stores<=0: issues.append("default_mall_has_no_stores")
        expected=map_catalog()["business_store_count"] if settings.default_mall_id=="mall_demo" else stores
        if stores!=expected: issues.append(f"map_catalog_mismatch={stores}/{expected}")
        if statuses!=stores: issues.append(f"store_status_mismatch={statuses}/{stores}")
        if bindings!=stores: issues.append(f"map_binding_mismatch={bindings}/{stores}")
        return {"ok":not issues,"instance_id":instance[0] if instance else None,"integrity":integrity,"foreign_key_errors":foreign_key_errors,"stores":stores,"expected_map_stores":expected,"store_statuses":statuses,"map_bindings":bindings,"issues":issues}
    except (sqlite3.Error,OSError) as exc:
        return {"ok":False,"instance_id":None,"issues":[f"database_unavailable:{type(exc).__name__}:{exc}"]}

def assert_database_ready() -> dict:
    status=database_health()
    if not status["ok"]:
        raise RuntimeError("database readiness check failed: "+"; ".join(status["issues"]))
    return status

def rows_to_dicts(rows): return [dict(row) for row in rows]
def load_json(value: str): return json.loads(value) if value else {}
