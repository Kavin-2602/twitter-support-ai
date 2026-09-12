import pandas as pd

df = pd.read_csv("golden_set.csv")

# 1. Total row count
total_rows = len(df)

# Mask for fully labelled rows
# Need to handle NaN/NaT/None as well as empty strings if any exist
mask_labelled = (
    df["true_intent"].notna() & (df["true_intent"] != "") &
    df["true_action"].notna() & (df["true_action"] != "") &
    df["good_reply_notes"].notna() & (df["good_reply_notes"] != "")
)

# 2. Fully labelled row count
fully_labelled = mask_labelled.sum()

# 3. Unlabelled row count
unlabelled = total_rows - fully_labelled

# 4. List of thread_ids of still-unlabelled rows
unlabelled_thread_ids = df[~mask_labelled]["thread_id"].tolist()

print(f"Total row count: {total_rows}")
print(f"Fully labelled rows: {fully_labelled}")
print(f"Unlabelled rows: {unlabelled}")
print(f"Thread IDs of unlabelled rows ({len(unlabelled_thread_ids)} items):")
for tid in unlabelled_thread_ids:
    print(tid)
