"""Canonical read models shared by APIs, pages and LLM tools.

Every function in this module returns business facts from the same SQLite rows.
Callers may format those facts differently, but must not re-implement eligibility
or availability rules.
"""
import json

from app.db import connection, rows_to_dicts


def list_stores(mall_id: str, keyword: str = "", reservable_only: bool = False):
    like=f"%{keyword.strip()}%"
    filters=["s.mall_id=?", "(s.name LIKE ? OR s.category LIKE ? OR s.tags LIKE ? OR UPPER(COALESCE(sp.store_code,'')) LIKE UPPER(?))"]
    params=[mall_id,like,like,like,like]
    if reservable_only:
        filters.append("s.reservable=1")
    with connection() as db:
        rows=db.execute(f"""SELECT s.*,COALESCE(ss.open_status,s.open_status) AS live_open_status,
          COALESCE(ss.queue_minutes,s.queue_minutes) AS live_queue_minutes,
          COALESCE(ss.seats_available,s.seats_available) AS live_seats_available,
          sp.store_code,sp.business_hours,sp.service_tags,b.source_key AS map_slot,b.source_label AS map_label,
          b.map_x,b.map_z,b.map_width,b.map_depth,b.source AS map_source,sd.details_json
          FROM stores s LEFT JOIN store_status ss ON ss.store_id=s.id
          LEFT JOIN store_profiles sp ON sp.store_id=s.id
          LEFT JOIN store_map_bindings b ON b.store_id=s.id AND b.mall_id=s.mall_id
          LEFT JOIN store_details sd ON sd.store_id=s.id
          WHERE {' AND '.join(filters)} ORDER BY s.floor,s.name""",params).fetchall()
    data=[]
    for row in rows:
        item=dict(row); details=json.loads(item.pop("details_json") or "{}")
        item.update({key:value for key,value in details.items() if key not in item or item[key] in (None,"")})
        raw_tags=details.get("tags") or item.get("tags") or item.get("service_tags") or ""
        item["tags"]=raw_tags if isinstance(raw_tags,list) else [tag for tag in str(raw_tags).split(",") if tag]
        item["open_status"]=item.pop("live_open_status")
        item["queue_minutes"]=item.pop("live_queue_minutes")
        item["seats_available"]=item.pop("live_seats_available")
        data.append(item)
    return data


def get_store(mall_id: str, store_id: str):
    return next((item for item in list_stores(mall_id) if item["id"]==store_id),None)


def list_reservations(user_id: str, mall_id: str | None = None, active_only: bool = False):
    filters=["r.user_id=?"]; params=[user_id]
    if mall_id is not None:
        filters.append("r.mall_id=?"); params.append(mall_id)
    if active_only:
        filters.append("r.status!='cancelled'")
    with connection() as db:
        rows=db.execute(f"""SELECT r.*,s.name AS store_name,s.floor,s.category
          FROM reservations r LEFT JOIN stores s ON s.id=r.store_id
          WHERE {' AND '.join(filters)}
          ORDER BY CASE WHEN r.status='cancelled' THEN 1 ELSE 0 END,
          CASE WHEN r.scheduled_at IS NULL THEN 1 ELSE 0 END,r.scheduled_at,r.created_at DESC""",params).fetchall()
    return rows_to_dicts(rows)


def list_coupons(mall_id: str, user_id: str, available_only: bool = False):
    availability=" AND c.stock>0" if available_only else ""
    with connection() as db:
        rows=db.execute(f"""SELECT c.*,s.name AS store_name,CASE WHEN uc.id IS NULL THEN 0 ELSE 1 END AS claimed,
          uc.claimed_at FROM coupons c LEFT JOIN stores s ON s.id=c.store_id
          LEFT JOIN user_coupons uc ON uc.coupon_id=c.id AND uc.user_id=? AND uc.mall_id=c.mall_id
          WHERE c.mall_id=?{availability} ORDER BY claimed,c.id""",(user_id,mall_id)).fetchall()
    return rows_to_dicts(rows)


def list_deals(mall_id: str, user_id: str | None = None, available_only: bool = False):
    availability=" AND d.stock>0" if available_only else ""
    with connection() as db:
        if user_id is None:
            rows=db.execute(f"""SELECT d.*,s.name AS store_name FROM deals d
              LEFT JOIN stores s ON s.id=d.store_id WHERE d.mall_id=?{availability} ORDER BY d.id""",(mall_id,)).fetchall()
        else:
            rows=db.execute(f"""SELECT d.*,s.name AS store_name,
              COALESCE((SELECT SUM(p.quantity) FROM deal_purchases p WHERE p.deal_id=d.id AND p.user_id=? AND p.status='paid'),0) AS purchased_quantity
              FROM deals d LEFT JOIN stores s ON s.id=d.store_id WHERE d.mall_id=?{availability} ORDER BY d.id""",(user_id,mall_id)).fetchall()
    return rows_to_dicts(rows)
