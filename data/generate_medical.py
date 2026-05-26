"""
Generate a synthetic medical records dataset with injected quality issues.

Deliberately includes a sparse notes column (>50% null) to exercise the
sparse escalation path, and no currency columns to test generalisation.

Run from repo root:
    python evals/datasets/generate_medical.py
"""
import os
import random
from datetime import datetime

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()
Faker.seed(99)
np.random.seed(99)
random.seed(99)

DIAGNOSES = ["Hypertension", "Diabetes", "Asthma", "Arthritis", "Migraine", "Anemia"]
GENDERS = ["Male", "Female", "Non-binary"]


def generate_clean_record() -> dict:
    return {
        "patient_id": fake.uuid4(),
        "first_name": fake.first_name(),
        "age": random.randint(18, 85),
        "gender": random.choice(GENDERS),
        "diagnosis": random.choice(DIAGNOSES),
        "bmi": round(random.uniform(17.0, 42.0), 1),
        "visit_date": str(fake.date_between(start_date="-5y", end_date="today")),
        "notes": fake.sentence() if random.random() > 0.55 else None,
    }


def inject_issues(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    n = len(df)

    # Additional nulls in several columns
    for col, pct in [("bmi", 0.06), ("age", 0.04)]:
        df.loc[random.sample(range(n), int(n * pct)), col] = None

    # Out-of-range ages
    for i in random.sample(range(n), 10):
        df.loc[i, "age"] = random.choice([-3, -1, 0, 130, 145, 200])

    # Out-of-range BMI values (biologically implausible)
    for i in random.sample(range(n), 8):
        df.loc[i, "bmi"] = random.choice([3.0, 5.5, 85.0, 92.0])

    # Inconsistent date formats
    for i in random.sample(range(n), 20):
        val = df.loc[i, "visit_date"]
        if val:
            try:
                dt = datetime.strptime(str(val), "%Y-%m-%d")
                df.loc[i, "visit_date"] = random.choice([
                    dt.strftime("%m/%d/%Y"),
                    dt.strftime("%d-%m-%Y"),
                    dt.strftime("%B %d, %Y"),
                ])
            except Exception:
                pass

    # Mixed case diagnoses
    for i in random.sample(range(n), 35):
        df.loc[i, "diagnosis"] = df.loc[i, "diagnosis"].lower()

    # Duplicate rows
    df = pd.concat([df, df.sample(10)], ignore_index=True)

    return df.sample(frac=1).reset_index(drop=True)


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__))
    os.makedirs(out_dir, exist_ok=True)

    records = [generate_clean_record() for _ in range(250)]
    df = pd.DataFrame(records)
    df = inject_issues(df)

    out_path = os.path.join(out_dir, "medical_messy.csv")
    df.to_csv(out_path, index=False)
    print(f"Generated {len(df)} rows -> {out_path}")
    print(f"Nulls per column:\n{df.isnull().sum()}")
    print(f"Duplicates: {df.duplicated().sum()}")
    print(f"Total nulls: {df.isnull().sum().sum()}")
    null_pct_notes = df["notes"].isnull().mean()
    print(f"Notes null%: {null_pct_notes:.1%}")
