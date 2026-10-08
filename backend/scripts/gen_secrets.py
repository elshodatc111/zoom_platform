"""JWT_SECRET va FERNET_KEY yaratadi. Natijani .env ga qo'ying."""
import secrets

from cryptography.fernet import Fernet

print("JWT_SECRET=" + secrets.token_urlsafe(48))
print("FERNET_KEY=" + Fernet.generate_key().decode())
