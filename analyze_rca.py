
import pandas as pd

df = pd.read_csv("master_dataset.csv")

faults = (
    df[df["phase"] == "fault"]
    .groupby("experiment_id")
    .agg(
        actual_fault=("fault_location", "first"),
        rows=("fault_location", "size")
    )
    .reset_index()
)

print("EXPERIMENT-LEVEL FAULT LABELS")
print("=============================")
print(faults.to_string(index=False))

print("\nEXPERIMENT COUNTS BY FAULT LOCATION")
print("===================================")
print(faults["actual_fault"].value_counts().to_string())
