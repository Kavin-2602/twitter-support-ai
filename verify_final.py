import pandas as pd

df = pd.read_csv("golden_set.csv")

# 1. Total row count
total_rows = len(df)
print(f"1. Total row count: {total_rows}")

# 2. Fully labelled check
mask_labelled = (
    df["true_intent"].notna() & (df["true_intent"] != "") &
    df["true_action"].notna() & (df["true_action"] != "") &
    df["good_reply_notes"].notna() & (df["good_reply_notes"] != "")
)
fully_labelled_count = mask_labelled.sum()
print(f"2. Fully labelled rows: {fully_labelled_count} / {total_rows}")

if fully_labelled_count != total_rows:
    unlabelled_ids = df[~mask_labelled]["thread_id"].tolist()
    print(f"   WARNING: The following {len(unlabelled_ids)} rows are missing labels: {unlabelled_ids}")

# 3. Duplicate thread_ids check
duplicates = df[df.duplicated(subset="thread_id", keep=False)]["thread_id"].unique()
if len(duplicates) == 0:
    print("3. Duplicate thread_ids: None")
else:
    print(f"3. Duplicate thread_ids found: {list(duplicates)}")

# 4. Distribution of true_intent values
print("4. Distribution of true_intent:")
intent_counts = df["true_intent"].value_counts()
for intent, count in intent_counts.items():
    print(f"   - {intent}: {count}")

