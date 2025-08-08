#!/usr/bin/env python3
import secrets

admin_key = secrets.token_urlsafe(32)

print("Add to your .env file:")
print(f"COSMICAM_ADMIN_API_KEY={admin_key}")