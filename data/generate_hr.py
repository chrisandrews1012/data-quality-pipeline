import os
import random
from datetime import datetime

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()
Faker.seed(42)
np.random.seed(42)
random.seed(42)


def generate_clean_record() -> dict:
    """
    Generate a single clean employee record with no injected issues.

    :returns: Dictionary of field values for one employee.
    :rtype: dict
    """
    return {
        "employee_id": fake.uuid4(),
        "name": fake.name(),
        "email": fake.email(),
        "age": random.randint(18, 80),
        "gender": random.choice(["Male", "Female", "Non-binary"]),
        "salary": round(random.uniform(30000, 150000), 2),
        "department": random.choice(["Engineering", "Marketing", "Sales", "HR", "Finance"]),
        "hire_date": str(fake.date_between(start_date="-10y", end_date="today")),
        "is_active": random.choice([True, False]),
    }


def inject_issues(df: pd.DataFrame) -> pd.DataFrame:
    """
    Inject a variety of data quality issues so every repair path gets exercised.

    Issues injected: nulls, out-of-range ages, malformatted emails, currency
    symbols in salary, inconsistent date formats, mixed-case departments,
    and duplicate rows.

    :param df: Clean DataFrame to inject issues into.
    :type df: pd.DataFrame
    :returns: DataFrame with injected issues, shuffled.
    :rtype: pd.DataFrame
    """
    df = df.copy()
    n = len(df)

    # Nulls across multiple columns
    for col, pct in [("email", 0.08), ("age", 0.05), ("salary", 0.04)]:
        df.loc[random.sample(range(n), int(n * pct)), col] = None

    # Out-of-range ages
    for i in random.sample(range(n), 15):
        df.loc[i, "age"] = random.choice([-5, -1, 0, 130, 150, 999])

    # Malformatted emails
    for i in random.sample(range(n), 20):
        df.loc[i, "email"] = random.choice([
            "notanemail", "missing@", "@nodomain.com",
            fake.name().replace(" ", ""),
        ])

    # Currency symbols in salary -- cast to object first so strings can be mixed in
    df["salary"] = df["salary"].astype(object)
    for i in random.sample(range(n), 25):
        val = df.loc[i, "salary"]
        if pd.notna(val):
            df.loc[i, "salary"] = f"${float(val):,.2f}"

    # Inconsistent date formats
    for i in random.sample(range(n), 30):
        val = df.loc[i, "hire_date"]
        if val:
            try:
                dt = datetime.strptime(str(val), "%Y-%m-%d")
                df.loc[i, "hire_date"] = random.choice([
                    dt.strftime("%m/%d/%Y"),
                    dt.strftime("%d-%m-%Y"),
                    dt.strftime("%B %d, %Y"),
                ])
            except Exception:
                pass

    # Mixed case departments
    for i in random.sample(range(n), 40):
        df.loc[i, "department"] = df.loc[i, "department"].lower()

    # Duplicate rows
    df = pd.concat([df, df.sample(20)], ignore_index=True)

    return df.sample(frac=1).reset_index(drop=True)


if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)
    records = [generate_clean_record() for _ in range(500)]
    df = pd.DataFrame(records)
    df = inject_issues(df)
    df.to_csv("data/raw/hr_messy.csv", index=False)
    print(f"Generated {len(df)} rows")
    print(f"Nulls per column:\n{df.isnull().sum()}")
