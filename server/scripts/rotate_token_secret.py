import secrets
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def main() -> None:
    if not ENV_PATH.exists():
        raise SystemExit("server/.env does not exist")
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    replacement = f"TOKEN_SECRET={secrets.token_urlsafe(48)}"
    updated = []
    replaced = False
    for line in lines:
        if line.startswith("TOKEN_SECRET="):
            updated.append(replacement)
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.insert(0, replacement)
    ENV_PATH.write_text("\n".join(updated) + "\n", encoding="utf-8")
    print("TOKEN_SECRET rotated in ignored server/.env; existing tokens are invalidated.")


if __name__ == "__main__":
    main()
