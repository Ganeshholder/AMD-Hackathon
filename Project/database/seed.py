"""
Database seeding script.
Run once to create tables and populate them with synthetic data.

Usage:
    python -m database.seed
"""

import sqlite3
import random
from datetime import datetime, timedelta

import pandas as pd
from faker import Faker

from config.settings import DB_PATH

fake = Faker()


def seed_transactions(conn: sqlite3.Connection, n: int = 5000) -> None:
    countries = ["India", "USA", "UK", "Germany", "Singapore"]
    statuses = ["SUCCESS", "FAILED", "PENDING"]

    records = [
        {
            "transaction_id": i + 1,
            "customer_id": random.randint(1000, 5000),
            "amount": round(random.uniform(100, 100_000), 2),
            "country": random.choice(countries),
            "status": random.choice(statuses),
            "created_at": fake.date_time_between(
                start_date="-1y", end_date="now"
            ).strftime("%Y-%m-%d %H:%M:%S"),
        }
        for i in range(n)
    ]

    df = pd.DataFrame(records)
    df.to_sql("transactions", conn, if_exists="replace", index=False)
    print(f"[seed] Inserted {n} transactions.")


def seed_log_table(conn: sqlite3.Connection, n: int = 5000) -> None:
    event_types = ["LOGIN", "LOGOUT", "FILE_ACCESS", "PAYMENT", "TRANSFER", "FAILED_LOGIN"]
    device_types = ["Mobile", "Laptop", "Desktop", "Tablet"]
    statuses = ["SUCCESS", "FAILED", "PENDING"]

    records = []
    for _ in range(n):
        random_time = datetime.now() - timedelta(
            days=random.randint(0, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        records.append(
            (
                fake.city(),
                random_time.strftime("%Y-%m-%d %H:%M:%S"),
                fake.ipv4(),
                fake.user_name(),
                random.choice(event_types),
                random.choice(device_types),
                random.choice(statuses),
            )
        )

    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS log_table")
    cursor.execute(
        """
        CREATE TABLE log_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT,
            log_time TEXT,
            ip_address TEXT,
            user_name TEXT,
            event_type TEXT,
            device_type TEXT,
            status TEXT
        )
        """
    )
    cursor.executemany(
        """
        INSERT INTO log_table
            (location, log_time, ip_address, user_name, event_type, device_type, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    print(f"[seed] Inserted {n} log records.")


def run() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        seed_transactions(conn)
        seed_log_table(conn)
        print("[seed] Database seeded successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
