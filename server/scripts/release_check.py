import json
import subprocess
import sys
from pathlib import Path

SERVER=Path(__file__).resolve().parents[1]
ROOT=SERVER.parent
sys.path.insert(0,str(SERVER))

from app.db import assert_database_ready, connection


def business_fingerprint() -> dict:
    with connection() as db:
        instance=db.execute("SELECT value FROM app_meta WHERE key='database_instance_id'").fetchone()[0]
        counts={table:db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("plans","reservations","user_coupons","user_tickets","deal_purchases")}
    return {"database_instance_id":instance,"counts":counts}


def run(command: list[str], cwd: Path = ROOT) -> None:
    print("RUN",subprocess.list2cmdline(command),flush=True)
    subprocess.run(command,cwd=cwd,check=True)


def main() -> None:
    readiness=assert_database_ready()
    before=business_fingerprint()
    run([sys.executable,"-m","pytest","server/tests","-q"])
    run([sys.executable,"server/scripts/smoke_demo.py"])
    run([sys.executable,"server/scripts/smoke_demo.py"])
    run(["npm.cmd","run","build"],ROOT/"web")
    after=business_fingerprint()
    if after!=before:
        raise SystemExit(f"release checks modified the demo database: before={before}, after={after}")
    print(json.dumps({"ready":True,"database":readiness,"demo_data_unchanged":True,"tests":"passed","smoke_runs":2,"web_build":"passed"},ensure_ascii=False))


if __name__=="__main__":
    main()
