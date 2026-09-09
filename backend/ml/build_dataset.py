import sqlite3
import pandas as pd
import numpy as np

# SQLite connection
conn = sqlite3.connect("asteria.db")
df = pd.read_sql_query("SELECT * FROM telemetry_history ORDER BY scenario_id, junction_id, simulation_time_s", conn)
conn.close()

# Prepare feature dataframe
features = []

for (scenario, junction), group in df.groupby(['scenario_id', 'junction_id']):
    group = group.sort_values('simulation_time_s').reset_index(drop=True)
    
    # Create lag features (5s intervals)
    for lag in [1, 2, 3, 4]:
        group[f'queue_minus_{lag*5}'] = group['queue_length_m'].shift(lag)
        
    # Target label: t + 60s
    # Since intervals are 5s, 60s future is shift(-12)
    group['target_queue_60s'] = group['queue_length_m'].shift(-12)
    
    # Calculate slope (delta over last 20s)
    group['queue_slope'] = (group['queue_length_m'] - group['queue_minus_20']) / 20.0
    
    features.append(group)

df_feat = pd.concat(features, ignore_index=True)
# Drop rows with NaN (due to shifts)
df_feat = df_feat.dropna()

print(f"Total scenarios: {df_feat['scenario_id'].nunique()}")
print(f"Total rows collected (after dropping NaNs): {len(df_feat)}")
for sc in df_feat['scenario_id'].unique():
    print(f"Rows for {sc}: {len(df_feat[df_feat['scenario_id'] == sc])}")

# Split methodology: Chronological (80/20) per scenario and junction
train_list = []
test_list = []

for (scenario, junction), group in df_feat.groupby(['scenario_id', 'junction_id']):
    group = group.sort_values('simulation_time_s')
    split_idx = int(len(group) * 0.8)
    train_list.append(group.iloc[:split_idx])
    test_list.append(group.iloc[split_idx:])

df_train = pd.concat(train_list, ignore_index=True)
df_test = pd.concat(test_list, ignore_index=True)

print(f"\nTrain rows: {len(df_train)}")
print(f"Test rows: {len(df_test)}")

df_train.to_csv("backend/ml/train.csv", index=False)
df_test.to_csv("backend/ml/test.csv", index=False)
