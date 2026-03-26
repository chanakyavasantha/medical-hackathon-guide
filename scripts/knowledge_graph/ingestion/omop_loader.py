import os
import sys
import argparse
import csv
from time import time

csv.field_size_limit(sys.maxsize)

# Add backend directory to path so we can import knowledge_graph
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from knowledge_graph.db import get_neo4j_driver
from knowledge_graph.ingestion.normalize_drug import normalize_drug_name

# Config
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/poc_raw/omop_vocab/vocabulary_download_v5_{11e8f6b0-bec3-4c54-8916-7294e94ce001}_1772575559382'))
CONCEPT_FILE = os.path.join(DATA_DIR, 'CONCEPT.csv')
RELATIONSHIP_FILE = os.path.join(DATA_DIR, 'CONCEPT_RELATIONSHIP.csv')
BATCH_SIZE = 10000

def load_concepts(session, vocabulary_id, domain_id, node_label):
    """Load concepts of a specific vocabulary and domain as nodes in Neo4j."""
    print(f"\nLoading {vocabulary_id} {domain_id} concepts as {node_label}...")
    
    if node_label == 'Drug':
        cypher = f"""
            UNWIND $batch AS row
            MERGE (n:Drug {{lowercase_name: row.lowercase_name}})
            ON CREATE SET n.name = row.concept_name,
                n.code = row.concept_code,
                n.concept_id = row.concept_id,
                n.system = row.vocabulary_id,
                n.concept_class = row.concept_class_id,
                n.source = 'OMOP_Athena'
        """
    else:
        cypher = f"""
            UNWIND $batch AS row
            MERGE (n:Condition {{code: row.concept_code}})
            SET n.name = row.concept_name,
                n.lowercase_name = row.lowercase_name,
                n.concept_id = row.concept_id,
                n.system = row.vocabulary_id,
                n.concept_class = row.concept_class_id,
                n.source = 'OMOP_Athena'
        """
    
    batch = []
    count = 0
    start_time = time()
    
    with open(CONCEPT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row['vocabulary_id'] == vocabulary_id and row['domain_id'] == domain_id and row['invalid_reason'] == '':
                if node_label == 'Drug':
                    if row['concept_class_id'] not in ('Ingredient', 'Precise Ingredient'):
                        continue
                    row['lowercase_name'] = normalize_drug_name(row['concept_name'])
                else:
                    if row['concept_class_id'] in ('Procedure', 'Context-dependent'):
                        continue
                    row['lowercase_name'] = row['concept_name'].lower().strip()
                    # Strip dots from ICD codes to match MIMIC-IV format (e.g. 401.9 -> 4019)
                    if vocabulary_id in ['ICD9CM', 'ICD10CM']:
                        row['concept_code'] = row['concept_code'].replace('.', '')
                
                batch.append(row)
                
                if len(batch) >= BATCH_SIZE:
                    session.run(cypher, batch=batch)
                    count += len(batch)
                    batch = []
                    print(f"  Loaded {count} {node_label}s...")
                    
        # Load remaining
        if batch:
            session.run(cypher, batch=batch)
            count += len(batch)
            
    elapsed = time() - start_time
    print(f"Finished loading {count} {node_label}s in {elapsed:.2f} seconds.")

def create_indexes(session):
    """Create indexes for faster loading and querying."""
    print("Creating indexes on concept_id and code...")
    session.run("CREATE INDEX IF NOT EXISTS FOR (n:Condition) ON (n.concept_id)")
    session.run("CREATE INDEX IF NOT EXISTS FOR (n:Drug) ON (n.concept_id)")
    session.run("CREATE INDEX IF NOT EXISTS FOR (n:Condition) ON (n.code)")
    session.run("CREATE INDEX IF NOT EXISTS FOR (n:Drug) ON (n.code)")
    print("Indexes created.")

def run_omop_ingestion():
    if not os.path.exists(CONCEPT_FILE):
        print(f"Error: Could not find OMOP data at {CONCEPT_FILE}")
        return

    driver = get_neo4j_driver()
    with driver.session() as session:
        create_indexes(session)
        
        # Load SNOMED Conditions
        load_concepts(session, 'SNOMED', 'Condition', 'Condition')
        # Load ICD9/ICD10 so MIMIC condition codes resolve to actual English names!
        load_concepts(session, 'ICD9CM', 'Condition', 'Condition')
        load_concepts(session, 'ICD10CM', 'Condition', 'Condition')
        
        # Load RxNorm Drugs
        load_concepts(session, 'RxNorm', 'Drug', 'Drug')
    
    driver.close()
    print("\nOMOP Ingestion Complete!")

if __name__ == "__main__":
    run_omop_ingestion()
