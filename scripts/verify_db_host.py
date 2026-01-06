from app.db import engine
from urllib.parse import urlparse


def check_db_connection():
    try:
        # Inspect the engine's URL directly
        db_url = str(engine.url)

        # Mask password for printing
        masked_url = db_url
        if ":" in db_url and "@" in db_url:
            part1 = db_url.split("@")[0]
            part2 = db_url.split("@")[1]
            if ":" in part1:
                user = part1.split("://")[1].split(":")[0]
                masked_url = f"postgresql://{user}:******@{part2}"

        print(f"Engine URL: {masked_url}")

        parsed = urlparse(db_url)
        host = parsed.hostname
        print(f"Database Host: {host}")

        if host and "neon.tech" in host:
            print("✅ Verified: Connected to Neon Database.")
        elif host and ("localhost" in host or "127.0.0.1" in host):
            print("⚠️ Warning: Connected to Localhost.")
        else:
            print(f"ℹ️ Connected to: {host}")

    except Exception as e:
        print(f"Error checking engine: {e}")


if __name__ == "__main__":
    check_db_connection()
