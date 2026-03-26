import os
import sys
import gzip
import csv
from time import time

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from knowledge_graph.db import get_neo4j_driver
from knowledge_graph.ingestion.normalize_drug import normalize_drug_name

# Config
MIMIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/mimic_demo'))
PATIENTS_FILE = os.path.join(MIMIC_DIR, 'patients.csv.gz')
DIAGNOSES_FILE = os.path.join(MIMIC_DIR, 'diagnoses_icd.csv.gz')
PRESCRIPTIONS_FILE = os.path.join(MIMIC_DIR, 'prescriptions.csv.gz')
BATCH_SIZE = 5000

def load_patients(session):
    """Load Patient nodes from patients.csv.gz"""
    print(f"\nLoading Patients from {PATIENTS_FILE}...")
    
    cypher = """
        UNWIND $batch AS row
        MERGE (p:Patient {id: row.subject_id})
        SET p.gender = row.gender,
            p.anchor_age = toInteger(row.anchor_age),
            p.anchor_year = toInteger(row.anchor_year),
            p.source = 'MIMIC-IV'
    """
    
    batch = []
    count = 0
    start_time = time()
    
    with gzip.open(PATIENTS_FILE, 'rt') as f:
        reader = csv.DictReader(f)
        for row in reader:
            batch.append(row)
            if len(batch) >= BATCH_SIZE:
                session.run(cypher, batch=batch)
                count += len(batch)
                batch = []
                
        if batch:
            session.run(cypher, batch=batch)
            count += len(batch)
            
    print(f"Finished loading {count} Patients in {time() - start_time:.2f} seconds.")

def load_diagnoses(session):
    """Link Patients to Conditions using ICD codes.
    Note: Real implementation would need OMOP concept mapping from ICD to SNOMED.
    For POC, we will create direct HAS_CONDITION links to custom ICD nodes if SNOMED isn't found.
    """
    print(f"\nLoading Diagnoses from {DIAGNOSES_FILE}...")
    
    # We create the condition if it doesn't exist, and link patient to condition
    cypher = """
        UNWIND $batch AS row
        MATCH (p:Patient {id: row.subject_id})
        MERGE (c:Condition {code: row.icd_code})
        ON CREATE SET c.system = row.icd_version, c.name = 'ICD Code: ' + row.icd_code, c.source = 'MIMIC-IV'
        MERGE (p)-[r:HAS_CONDITION]->(c)
        SET r.seq_num = toInteger(row.seq_num),
            r.status = 'active'
    """
    
    batch = []
    count = 0
    start_time = time()
    
    with gzip.open(DIAGNOSES_FILE, 'rt') as f:
        reader = csv.DictReader(f)
        for row in reader:
            icd_code = row.get('icd_code', '').strip()
            icd_version = f"ICD{row.get('icd_version', '').strip()}"
                
            if icd_code:
                batch.append({
                    'subject_id': row['subject_id'],
                    'icd_code': icd_code,
                    'icd_version': icd_version,
                    'seq_num': row['seq_num']
                })
                
            if len(batch) >= BATCH_SIZE:
                session.run(cypher, batch=batch)
                count += len(batch)
                batch = []
                
        if batch:
            session.run(cypher, batch=batch)
            count += len(batch)
            
    print(f"Finished loading {count} HAS_CONDITION edges in {time() - start_time:.2f} seconds.")

def load_prescriptions(session):
    """Link Patients to Drugs using RxNorm codes."""
    print(f"\nLoading Prescriptions from {PRESCRIPTIONS_FILE}...")
    
    # Try to match existing RxNorm drug by name, otherwise create a placeholder
    cypher = """
        UNWIND $batch AS row
        MATCH (p:Patient {id: row.subject_id})
        
        // Find by unified lowercase generic name rather than isolated NDC code
        MERGE (d:Drug {lowercase_name: row.lowercase_name})
        ON CREATE SET d.name = row.drug_name, d.ndc_code = row.ndc, d.system = 'MIMIC_NDC', d.source = 'MIMIC-IV'
        
        MERGE (p)-[r:TAKES_DRUG]->(d)
        SET r.dose = row.dose,
            r.route = row.route,
            r.status = 'active'
    """
    
    batch = []
    count = 0
    start_time = time()
    
    with gzip.open(PRESCRIPTIONS_FILE, 'rt') as f:
        reader = csv.DictReader(f)
        for row in reader:
            drug_name = row.get('drug', '').strip()
            if drug_name:
                ndc = row.get('ndc', '').strip()
                if not ndc or ndc == '0':
                    ndc = f"MIMIC_DRUG_{drug_name}"
                
                batch.append({
                    'subject_id': row['subject_id'],
                    'drug_name': drug_name,
                    'lowercase_name': normalize_drug_name(drug_name),
                    'ndc': ndc,
                    'dose': f"{row.get('dose_val_rx', '')} {row.get('dose_unit_rx', '')}",
                    'route': row.get('route', '')
                })
                
            if len(batch) >= BATCH_SIZE:
                session.run(cypher, batch=batch)
                count += len(batch)
                batch = []
                
        if batch:
            session.run(cypher, batch=batch)
            count += len(batch)
            
    print(f"Finished loading {count} TAKES_DRUG edges in {time() - start_time:.2f} seconds.")

def run_mimic_ingestion():
    if not os.path.exists(PATIENTS_FILE):
        print(f"Error: Could not find MIMIC data at {MIMIC_DIR}")
        return

    driver = get_neo4j_driver()
    with driver.session() as session:
        load_patients(session)
        load_diagnoses(session)
        load_prescriptions(session)
    
    driver.close()
    print("\nMIMIC-IV Ingestion Complete!")

if __name__ == "__main__":
    run_mimic_ingestion()
