"""Generate the 星河里 AI service Mini Program code without logging credentials."""
from pathlib import Path
import sys

import httpx
from dotenv import load_dotenv

SERVER = Path(__file__).resolve().parents[1]
ROOT = SERVER.parent
load_dotenv(SERVER / ".env")
sys.path.insert(0, str(SERVER))

from app.config import settings


def main() -> int:
    if not settings.wx_app_id or not settings.wx_app_secret:
        raise RuntimeError("WX_APP_ID/WX_APP_SECRET are not configured in server/.env")
    with httpx.Client(timeout=30) as client:
        token_response = client.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={"grant_type": "client_credential", "appid": settings.wx_app_id, "secret": settings.wx_app_secret},
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        if "access_token" not in token_data:
            raise RuntimeError(f"WeChat access token request failed: {token_data.get('errcode')} {token_data.get('errmsg')}")
        code_response = client.post(
            "https://api.weixin.qq.com/wxa/getwxacodeunlimit",
            params={"access_token": token_data["access_token"]},
            json={
                "scene": "QD-AI-DEMO",
                "page": "pages/scan/scan",
                "check_path": False,
                "env_version": "develop",
                "width": 430,
            },
        )
        code_response.raise_for_status()
        if code_response.headers.get("content-type", "").startswith("application/json"):
            error = code_response.json()
            raise RuntimeError(f"WeChat code generation failed: {error.get('errcode')} {error.get('errmsg')}")
    output = ROOT / "docs" / "assets" / "qd-ai-service-code.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(code_response.content)
    print(f"Generated: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
