import os
import sys
import csv
from time import time

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from knowledge_graph.db import get_neo4j_driver
from knowledge_graph.ingestion.normalize_drug import normalize_drug_name

# Config
INTERACTIONS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/poc_raw/db_drug_interactions.csv'))
BATCH_SIZE = 10000

def create_name_index(session):
    print("Ensuring index on Drug.name exists for fast matching...")
    try:
        session.run("CREATE INDEX drug_name_idx IF NOT EXISTS FOR (d:Drug) ON (d.name)")
        print("Index ensured.")
    except Exception as e:
        print(f"Error creating index (might already exist): {e}")

def get_drug_name_map(session):
    print("Building lowercase drug name lookup dictionary from the database...")
    start_time = time()
    result = session.run("MATCH (d:Drug) RETURN d.lowercase_name AS lname, d.name AS name")
    name_map = {}
    for record in result:
        lname = record["lname"]
        if lname:
            name_map[lname] = record["name"]
    print(f"Mapped {len(name_map)} unique lowercase drug names in {time() - start_time:.2f} seconds.")
    return name_map

def load_interactions(session, name_map):
    print(f"\nLoading Drug Interactions from {INTERACTIONS_FILE}...")
    
    # We use exact MATCH since we've already validated the names using the map
    cypher = """
        UNWIND $batch AS row
        MATCH (d1:Drug {name: row.drug1})
        MATCH (d2:Drug {name: row.drug2})
        MERGE (d1)-[r:INTERACTS_WITH]->(d2)
        SET r.description = row.description,
            r.source = 'DrugBank_Kaggle'
    """
    
    batch = []
    processed_rows = 0
    matched_edges = 0
    start_time = time()
    
    with open(INTERACTIONS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            processed_rows += 1
            drug1_raw = row.get('Drug 1', '').strip()
            drug2_raw = row.get('Drug 2', '').strip()
            desc = row.get('Interaction Description', '').strip()
            
            # Map the normalized CSV names to the exact casing stored in our Neo4j database
            real_drug1 = name_map.get(normalize_drug_name(drug1_raw))
            real_drug2 = name_map.get(normalize_drug_name(drug2_raw))
            
            if real_drug1 and real_drug2:
                batch.append({
                    'drug1': real_drug1,
                    'drug2': real_drug2,
                    'description': desc
                })
                
            if len(batch) >= BATCH_SIZE:
                result = session.run(cypher, batch=batch)
                matched_edges += len(batch)
                print(f"  Scanned {processed_rows} rows... (Created {matched_edges} edges)")
                batch = []
                
        if batch:
            result = session.run(cypher, batch=batch)
            matched_edges += len(batch)
            print(f"  Scanned {processed_rows} rows... (Created {matched_edges} edges)")
            
    print(f"Finished processing {processed_rows} rows in {time() - start_time:.2f} seconds.")
    print(f"Total new INTERACTS_WITH edges created: {matched_edges}")

def run_interaction_ingestion():
    if not os.path.exists(INTERACTIONS_FILE):
        print(f"Error: Could not find interactions data at {INTERACTIONS_FILE}")
        return

    driver = get_neo4j_driver()
    with driver.session() as session:
        create_name_index(session)
        name_map = get_drug_name_map(session)
        load_interactions(session, name_map)
    
    driver.close()
    print("\nDrug Interaction Ingestion Complete!")

if __name__ == "__main__":
    run_interaction_ingestion()
