import pandas as pd

df = pd.read_csv("master_dataset.csv")

print("COLUMNS:")
print(df.columns.tolist())

for col in ["phase", "fault_location", "timestamp", "experiment_id"]:
    if col in df.columns:
        print(f"\n{col}:")
        print("Sample values:", df[col].dropna().unique()[:12])
        print("Missing:", df[col].isna().sum())

print("\nTotal rows:", len(df))