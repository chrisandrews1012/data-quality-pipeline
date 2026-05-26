"""
Generate a synthetic e-commerce orders dataset with injected quality issues.

Run from repo root:
    python evals/datasets/generate_ecommerce.py
"""
import os
import random
from datetime import datetime

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()
Faker.seed(7)
np.random.seed(7)
random.seed(7)

STATUSES = ["Pending", "Shipped", "Delivered", "Cancelled", "Refunded"]
PRODUCTS = [
    "Wireless Headphones", "Laptop Stand", "USB Hub", "Mechanical Keyboard",
    "Monitor", "Webcam", "Mouse Pad", "External SSD", "Phone Case", "Charger",
]


def generate_clean_record() -> dict:
    return {
        "order_id": fake.uuid4(),
        "customer_email": fake.email(),
        "product": random.choice(PRODUCTS),
        "price": round(random.uniform(9.99, 499.99), 2),
        "quantity": random.randint(1, 10),
        "order_date": str(fake.date_between(start_date="-3y", end_date="today")),
        "status": random.choice(STATUSES),
        "is_returned": random.choice([True, False]),
    }


def inject_issues(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    n = len(df)

    # Nulls scattered across columns
    for col, pct in [("customer_email", 0.06), ("quantity", 0.04), ("price", 0.03)]:
        df.loc[random.sample(range(n), int(n * pct)), col] = None

    # Malformatted emails
    for i in random.sample(range(n), 18):
        df.loc[i, "customer_email"] = random.choice([
            "notanemail", "bad@", "@nodomain.com", fake.first_name(),
        ])

    # Currency symbols in price
    df["price"] = df["price"].astype(object)
    for i in random.sample(range(n), 30):
        val = df.loc[i, "price"]
        if pd.notna(val):
            df.loc[i, "price"] = f"${float(val):,.2f}"

    # Inconsistent date formats
    for i in random.sample(range(n), 25):
        val = df.loc[i, "order_date"]
        if val:
            try:
                dt = datetime.strptime(str(val), "%Y-%m-%d")
                df.loc[i, "order_date"] = random.choice([
                    dt.strftime("%m/%d/%Y"),
                    dt.strftime("%d-%m-%Y"),
                    dt.strftime("%B %d, %Y"),
                ])
            except Exception:
                pass

    # Mixed case status
    for i in random.sample(range(n), 45):
        df.loc[i, "status"] = df.loc[i, "status"].lower()

    # Duplicate rows
    df = pd.concat([df, df.sample(12)], ignore_index=True)

    return df.sample(frac=1).reset_index(drop=True)


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__))
    os.makedirs(out_dir, exist_ok=True)

    records = [generate_clean_record() for _ in range(300)]
    df = pd.DataFrame(records)
    df = inject_issues(df)

    out_path = os.path.join(out_dir, "ecommerce_messy.csv")
    df.to_csv(out_path, index=False)
    print(f"Generated {len(df)} rows -> {out_path}")
    print(f"Nulls per column:\n{df.isnull().sum()}")
    print(f"Duplicates: {df.duplicated().sum()}")
    print(f"Total nulls: {df.isnull().sum().sum()}")
