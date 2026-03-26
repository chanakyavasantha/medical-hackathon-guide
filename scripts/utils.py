import pandas as pd
import os
import json

def load_local_data(data_path):
    """
    Utility function to load local data files.
    """
    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found.")
        return None
    
    if data_path.endswith('.csv') or data_path.endswith('.csv.gz'):
        return pd.read_csv(data_path)
    elif data_path.endswith('.json'):
        with open(data_path, 'r') as f:
            return json.load(f)
    else:
        print("Unsupported file format.")
        return None

if __name__ == "__main__":
    # Example usage
    print("MedBridge Hackathon Utils Loaded.")
