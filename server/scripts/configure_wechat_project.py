"""Copy WX_APP_ID from ignored server/.env into ignored DevTools private config."""
import json
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
env = dotenv_values(ROOT / "server" / ".env")
app_id = (env.get("WX_APP_ID") or "").strip()
if not app_id:
    raise RuntimeError("WX_APP_ID is not configured in server/.env")

private_path = ROOT / "app" / "project.private.config.json"
config = json.loads(private_path.read_text(encoding="utf-8")) if private_path.exists() else {}
config["appid"] = app_id
miniprogram = config.setdefault("condition", {}).setdefault("miniprogram", {})
compile_modes = miniprogram.setdefault("list", [])
qr_mode = {
    "name": "AI 服务二维码",
    "pathName": "pages/scan/scan",
    "query": "scene=QD-AI-DEMO",
    "scene": None,
}
compile_modes[:] = [item for item in compile_modes if item.get("name") != qr_mode["name"]]
compile_modes.append(qr_mode)
private_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("WeChat DevTools private AppID and AI QR compile mode configured. The AppID was not printed.")
