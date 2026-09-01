from dataclasses import dataclass
from fastapi import HTTPException
from app.db import connection, rows_to_dicts
from app.core.business_data import list_stores

@dataclass(frozen=True)
class DataSource:
    mall_id: str
    name: str

class Registry:
    def get(self,mall_id:str)->DataSource:
        with connection() as db: row=db.execute("SELECT id,name FROM malls WHERE id=?",(mall_id,)).fetchone()
        if not row: raise HTTPException(status_code=404,detail="unknown mall_id")
        return DataSource(row["id"],row["name"])
    def stores(self,mall_id:str,keyword:str=""):
        self.get(mall_id)
        return list_stores(mall_id,keyword)
registry=Registry()
