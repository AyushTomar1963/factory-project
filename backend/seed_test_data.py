"""Seed local/dev test users, products, and suppliers. Safe to re-run (skips existing rows)."""

import bcrypt
from database import SessionLocal, engine
from models import Base, User, Product, Supplier

TEST_USERS = [
    {"username": "admin", "password": "admin123", "role": "admin"},
    {"username": "worker", "password": "worker123", "role": "worker"},
    {"username": "store", "password": "store123", "role": "store_keeper"},
]

TEST_SUPPLIERS = [
    {"supplier_name": "Acme Parts Ltd", "contact_info": "contact@acme.test"},
    {"supplier_name": "Precision Metals Co", "contact_info": "sales@precision.test"},
]

TEST_PRODUCTS = [
    {
        "part_number": "PN-1001",
        "part_name": "Hydraulic Valve Body",
        "group_name": "Valves",
        "parameters": ["OD", "ID", "Length"],
    },
    {
        "part_number": "PN-2002",
        "part_name": "Pump Impeller",
        "group_name": "Pumps",
        "parameters": ["Diameter", "Thickness", "Runout"],
    },
]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for u in TEST_USERS:
            if db.query(User).filter(User.username == u["username"]).first():
                print(f"  skip user: {u['username']}")
                continue
            db.add(
                User(
                    username=u["username"],
                    hashed_password=hash_password(u["password"]),
                    role=u["role"],
                )
            )
            print(f"  created user: {u['username']} ({u['role']})")

        for s in TEST_SUPPLIERS:
            if db.query(Supplier).filter(Supplier.supplier_name == s["supplier_name"]).first():
                print(f"  skip supplier: {s['supplier_name']}")
                continue
            db.add(Supplier(**s))
            print(f"  created supplier: {s['supplier_name']}")

        for p in TEST_PRODUCTS:
            if db.query(Product).filter(Product.part_number == p["part_number"]).first():
                print(f"  skip product: {p['part_number']}")
                continue
            db.add(Product(**p))
            print(f"  created product: {p['part_number']}")

        db.commit()
        print("\nSeed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding test data...")
    seed()
