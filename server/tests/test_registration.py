from fastapi.testclient import TestClient
from app.db import connection, ensure_database, reset_and_seed
from app.main import app


def test_visitor_registration_persists_and_uses_normal_member_level():
    reset_and_seed(); client=TestClient(app)
    payload={"phone":"13800138000","password":"secure123"}
    registered=client.post("/api/auth/phone-register",json=payload)
    assert registered.status_code==200
    assert registered.json()["data"]["role"]=="visitor"

    duplicate=client.post("/api/auth/phone-register",json=payload)
    assert duplicate.status_code==409

    ensure_database()
    logged_in=client.post("/api/auth/phone-login",json=payload)
    assert logged_in.status_code==200
    user_id=logged_in.json()["data"]["user_id"]
    with connection() as db:
        credential=db.execute("SELECT password_hash FROM web_credentials WHERE username=?",(payload["phone"],)).fetchone()
        member=db.execute("SELECT points,level FROM members WHERE user_id=? AND mall_id='mall_demo'",(user_id,)).fetchone()
    assert credential["password_hash"]!=payload["password"]
    assert dict(member)=={"points":0,"level":"普通会员"}


def test_merchant_registration_requires_valid_unclaimed_code_and_password():
    reset_and_seed(); client=TestClient(app)
    with connection() as db:
        store=db.execute("""SELECT sp.store_code,sp.store_id FROM store_profiles sp
          LEFT JOIN merchant_credentials mc ON mc.store_id=sp.store_id
          WHERE mc.store_id IS NULL ORDER BY sp.store_id LIMIT 1""").fetchone()
    payload={"store_code":store["store_code"],"password":"merchant123"}

    registered=client.post("/api/merchant/auth/register",json=payload)
    assert registered.status_code==200
    assert registered.json()["data"]["store_id"]==store["store_id"]
    assert client.post("/api/merchant/auth/register",json=payload).status_code==409
    assert client.post("/api/merchant/auth/store-code",json={**payload,"password":"wrong-password"}).status_code==401
    assert client.post("/api/merchant/auth/store-code",json=payload).status_code==200
    assert client.post("/api/merchant/auth/store-code",json={"store_code":payload["store_code"]}).status_code==422

    with connection() as db:
        credential=db.execute("SELECT password_hash FROM merchant_credentials WHERE store_id=?",(store["store_id"],)).fetchone()
        access=db.execute("SELECT 1 FROM merchant_store_access WHERE store_id=?",(store["store_id"],)).fetchone()
    assert credential["password_hash"]!=payload["password"]
    assert access is not None
