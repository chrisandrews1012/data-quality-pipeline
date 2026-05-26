"""
Generate a clean HR dataset with no injected issues.

Used as a "no false positives" eval: the pipeline should profile and validate
it without flagging critical issues, and the repairer should apply zero actions.

Run from repo root:
    python data/generate_hr_clean.py
"""
import os
import random

import pandas as pd
from faker import Faker

fake = Faker()
Faker.seed(0)
random.seed(0)

DEPARTMENTS = ["Engineering", "Marketing", "Sales", "Hr", "Finance"]
GENDERS = ["Male", "Female", "Non-Binary"]


def generate_clean_record() -> dict:
    return {
        "employee_id": fake.uuid4(),
        "name": fake.name(),
        "email": fake.email(),
        "age": random.randint(22, 65),
        "gender": random.choice(GENDERS),
        "salary": round(random.uniform(40000, 140000), 2),
        "department": random.choice(DEPARTMENTS),
        "hire_date": str(fake.date_between(start_date="-10y", end_date="today")),
        "is_active": random.choice([True, False]),
    }


if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)
    records = [generate_clean_record() for _ in range(200)]
    df = pd.DataFrame(records)

    assert df.isnull().sum().sum() == 0, "Clean dataset should have no nulls"
    assert df.duplicated().sum() == 0, "Clean dataset should have no duplicates"

    out_path = "data/raw/hr_clean.csv"
    df.to_csv(out_path, index=False)
    print(f"Generated {len(df)} rows -> {out_path}")
    print(f"Nulls: {df.isnull().sum().sum()}")
    print(f"Duplicates: {df.duplicated().sum()}")
