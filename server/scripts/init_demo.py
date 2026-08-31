import sys
from pathlib import Path
SERVER=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(SERVER))
from app.db import ensure_database
from app.core.router import write_demo_maps
if __name__=="__main__":
    # 日常启动只补表和 Seed，不删除 mall.db；测试/显式重置仍可调用 reset_and_seed。
    ensure_database(); write_demo_maps(); print("星河里 demo database checked and two-floor map initialized")
