import sys
from pathlib import Path
SERVER=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(SERVER))
from app.db import reset_and_seed
from app.core.router import write_demo_maps
if __name__=="__main__":
    reset_and_seed(); write_demo_maps(); print("QD square demo database and two-floor map initialized")
