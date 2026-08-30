import base64, hashlib, hmac, json, time
from dataclasses import dataclass
from fastapi import Header, HTTPException
from app.config import settings

@dataclass(frozen=True)
class AuthContext:
    user_id: str
    login_channel: str

def issue_token(user_id: str, channel: str) -> str:
    payload={"user_id":user_id,"login_channel":channel,"issued_at":int(time.time())}
    encoded=base64.urlsafe_b64encode(json.dumps(payload,separators=(",",":")).encode()).decode().rstrip("=")
    sig=hmac.new(settings.token_secret.encode(),encoded.encode(),hashlib.sha256).hexdigest()
    return f"{encoded}.{sig}"

def decode_token(token: str) -> AuthContext:
    try:
        encoded,sig=token.split(".",1); expected=hmac.new(settings.token_secret.encode(),encoded.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig,expected): raise ValueError("bad signature")
        payload=json.loads(base64.urlsafe_b64decode(encoded+"="*(-len(encoded)%4)))
        if time.time()-int(payload["issued_at"])>settings.token_ttl_seconds: raise ValueError("expired")
        return AuthContext(payload["user_id"],payload["login_channel"])
    except (ValueError,KeyError,json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401,detail="invalid or expired token") from exc

def require_auth(authorization: str|None=Header(default=None)) -> AuthContext:
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(status_code=401,detail="missing bearer token")
    return decode_token(authorization[7:])
