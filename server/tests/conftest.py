import os, sys
from pathlib import Path
os.environ["WX_AUTH_MODE"]="mock"
os.environ["LLM_MODE"]="scripted"
SERVER=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(SERVER))
