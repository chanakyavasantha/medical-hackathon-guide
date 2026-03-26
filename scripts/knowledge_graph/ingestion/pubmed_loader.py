import os
import sys
import json
from time import time
from tqdm import tqdm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from knowledge_graph.db import get_neo4j_driver
from knowledge_graph.ingestion.normalize_drug import normalize_drug_name

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/poc_raw'))
PUBMED_FILE = os.path.join(DATA_DIR, 'processed_edges_pubmed26n0001.json')
BATCH_SIZE = 250

def load_pubmed_data(session):
    print(f"Loading PubMed data from {PUBMED_FILE}...")
    
    # Separate the operations into distinct queries so the Neo4j planner executes perfect IndexSeeks
    
    cypher_articles = """
        UNWIND $batch AS row
        MERGE (a:Article {pmid: row.pmid})
        SET a.title = row.title,
            a.snippet = row.snippet,
            a.source = 'PubMed_Baseline'
    """
    
    cypher_drugs = """
        UNWIND $batch AS row
        WITH row
        MATCH (a:Article {pmid: row.pmid})
        UNWIND row.drugs AS drug
        MATCH (d:Drug {lowercase_name: drug.lname})
        MERGE (a)-[:MENTIONS_DRUG]->(d)
    """
    
    cypher_conditions = """
        UNWIND $batch AS row
        WITH row
        MATCH (a:Article {pmid: row.pmid})
        UNWIND row.conditions AS condition
        MATCH (c:Condition {lowercase_name: condition.lname})
        MERGE (a)-[:MENTIONS_CONDITION]->(c)
    """
    
    cypher_edges = """
        UNWIND $batch AS row
        WITH row
        UNWIND row.drugs AS drug
        UNWIND row.conditions AS condition
        MATCH (d:Drug {lowercase_name: drug.lname})
        MATCH (c:Condition {lowercase_name: condition.lname})
        MERGE (d)-[r:CO_OCCURS_WITH]-(c)
        ON CREATE SET r.count = 1, r.pmid_references = [row.pmid]
        ON MATCH SET r.count = r.count + 1,
                     r.pmid_references = CASE WHEN NOT row.pmid IN r.pmid_references THEN r.pmid_references + [row.pmid] ELSE r.pmid_references END
    """
    
    with open(PUBMED_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    batch = []
    start_time = time()
    
    for abstract in tqdm(data, desc="Ingesting to Neo4j"):
        drugs = [{"name": d, "lname": normalize_drug_name(d)} for d in abstract.get('drugs', []) if isinstance(d, str)]
        conditions = [{"name": c, "lname": c.lower().strip()} for c in abstract.get('conditions', []) if isinstance(c, str)]
        
        if not drugs or not conditions: continue
        
        abstract['drugs'] = drugs
        abstract['conditions'] = conditions
        batch.append(abstract)
        
        if len(batch) >= BATCH_SIZE:
            session.run(cypher_articles, batch=batch)
            session.run(cypher_drugs, batch=batch)
            session.run(cypher_conditions, batch=batch)
            session.run(cypher_edges, batch=batch)
            batch = []
            
    if batch:
        session.run(cypher_articles, batch=batch)
        session.run(cypher_drugs, batch=batch)
        session.run(cypher_conditions, batch=batch)
        session.run(cypher_edges, batch=batch)
        
    elapsed = time() - start_time
    print(f"\nFinished loading PubMed Co-occurrences in {elapsed:.2f} seconds.")

def create_indexes(session):
    print("Creating indexes...")
    session.run("CREATE INDEX pubmed_pmid IF NOT EXISTS FOR (a:Article) ON (a.pmid)")
    session.run("CREATE INDEX pubmed_drug_lname IF NOT EXISTS FOR (d:Drug) ON (d.lowercase_name)")
    session.run("CREATE INDEX pubmed_cond_lname IF NOT EXISTS FOR (c:Condition) ON (c.lowercase_name)")

def run_pubmed_ingestion():
    driver = get_neo4j_driver()
    with driver.session() as session:
        create_indexes(session)
        load_pubmed_data(session)
    driver.close()
    print("\nPubMed Literature Ingestion Complete!")

if __name__ == "__main__":
    run_pubmed_ingestion()
