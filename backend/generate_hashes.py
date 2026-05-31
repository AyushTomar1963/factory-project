import bcrypt

def generate_hash(password: str) -> str:
    # Generates a bcrypt hash string safe for storage
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

print("--- Kirloskar User Hash Generator ---")
admin_pw = input("Enter password for ADMIN: ")
print(f"Admin Hash: {generate_hash(admin_pw)}\n")

worker_pw = input("Enter password for WORKER: ")
print(f"Worker Hash: {generate_hash(worker_pw)}")