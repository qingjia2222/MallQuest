import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

SERVER=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SERVER))

from app.config import settings
from app.core.router import write_demo_maps
from app.db import assert_database_ready, ensure_database, reconcile_demo_catalog


def backup_database(keep: int = 5) -> Path | None:
    source=Path(settings.mall_db_path)
    if not source.exists() or source.stat().st_size==0:
        return None
    target_dir=source.parent/"backups"
    target_dir.mkdir(parents=True,exist_ok=True)
    target=target_dir/f"mall-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    backups=sorted(target_dir.glob("mall-*.db"),key=lambda item:item.stat().st_mtime,reverse=True)
    for old in backups[max(1,keep):]:
        old.unlink()
    return target


def main() -> None:
    parser=argparse.ArgumentParser(description="星河里启动前数据库备份和业务一致性检查")
    parser.add_argument("--no-backup",action="store_true",help="仅检查，不创建启动备份")
    parser.add_argument("--keep",type=int,default=5,help="保留最近 N 份启动备份")
    parser.add_argument("--reconcile-map",action="store_true",help="备份后按 3D 地图店铺目录迁移 SQLite")
    args=parser.parse_args()
    backup=None if args.no_backup else backup_database(args.keep)
    ensure_database()
    migration=None
    if args.reconcile_map:
        if backup is None:
            raise RuntimeError("地图目录迁移前必须先创建可恢复数据库备份")
        migration=reconcile_demo_catalog()
    write_demo_maps()
    status=assert_database_ready()
    print(json.dumps({"ready":True,"backup":str(backup) if backup else None,"migration":migration,"database":status},ensure_ascii=False))


if __name__=="__main__":
    main()
