import os
import sys
import pandas as pd
from tabulate import tabulate

# Add backend directory to path so we can import knowledge_graph
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from knowledge_graph.db import get_neo4j_driver

def run_drug_interaction_rule(session):
    """
    Rule 1: Detect patients actively prescribed two interacting drugs.
    This provides an immediate, ground-truth clinical signal by cross-referencing
    the MIMIC-IV patient journeys with the ONC/DrugBank safety ontology.
    """
    print("\n" + "="*80)
    print("🚦 RULE 1: HIGH-SEVERITY DRUG-DRUG INTERACTIONS DETECTED IN PATIENT COHORT")
    print("="*80)
    
    # We use a purely deterministic graph path to lock down concrete signals:
    # Patient -> takes Drug 1 -> which INTERACTS_WITH -> Drug 2 <- which Patient also takes
    cypher = """
        MATCH (p:Patient)-[:TAKES_DRUG]->(d1:Drug)-[r:INTERACTS_WITH]-(d2:Drug)<-[:TAKES_DRUG]-(p)
        WHERE id(d1) < id(d2) // Prevent duplicate mirror pairs (A-B and B-A)
        RETURN p.id AS PatientID,
               d1.name AS OffendingDrug1,
               d2.name AS OffendingDrug2,
               r.severity AS Severity,
               r.description AS Description
        ORDER BY p.id
    """
    
    result = session.run(cypher)
    records = [record.data() for record in result]
    
    if not records:
        print("✅ No offending interacting drug pairs found in the patient cohort.")
        return
        
    df = pd.DataFrame(records)
    
    # We'll just display the total count and a sample of the first 20 critical patients
    print(f"⚠️  CRITICAL ALERT: Found {len(df)} concrete instances of contraindicated drug-drug prescriptions!\n")
    
    # To keep terminal output clean, we truncate descriptions if they are too long
    df['Description'] = df['Description'].apply(lambda x: (x[:60] + '...') if x and len(x) > 60 else x)
    
    print(tabulate(df.head(20), headers='keys', tablefmt='simple_grid', showindex=False))
    
    if len(df) > 20:
        print(f"\n... and {len(df) - 20} more critical patient safety alerts hidden.")
        
    return df

def run_literature_based_flagging(session):
    """
    Rule 2: Flag patients whose active drugs have massive co-occurrence in medical 
    literature with dangerous adverse events, acting as an 'early warning' system 
    before an official INTERACTS_WITH ontology rule is made.
    """
    # This acts as a bridge to show the PI the immense power of the BioBERT literature layer.
    print("\n" + "="*80)
    print("📖 RULE 2: LITERATURE-BASED EARLY WARNING SURVEILLANCE")
    print("="*80)
    
    # Look for patients taking drugs that have massive co-occurrence (e.g. > 10 abstracts) 
    # with "Hemothorax" or "Myocardial Infarction" or similar adverse concepts, 
    # BUT they don't have an explicit warning ontology edge yet.
    # For this POC, let's just find the top Co-Occurrences for drugs patients take.
    
    cypher = """
        MATCH (p:Patient)-[:TAKES_DRUG]->(d:Drug)-[r:CO_OCCURS_WITH]-(c:Condition)
        WHERE r.count > 5 // Must be mentioned in at least 5 different PubMed abstracts together
        RETURN p.id AS PatientID,
               d.name AS PrescribedDrug,
               c.name AS AssociatedCondition,
               r.count AS LiteratureMentions,
               size(r.pmid_references) AS UniquePapers
        ORDER BY r.count DESC
        LIMIT 20
    """
    
    result = session.run(cypher)
    records = [record.data() for record in result]
    
    if not records:
        print("✅ No high-frequency literature overlaps found.")
        return
        
    df = pd.DataFrame(records)
    print(f"🔍 Surveillance found strong PubMed signals for prescribed drugs in your cohort:\n")
    print(tabulate(df, headers='keys', tablefmt='simple_grid', showindex=False))
    print("\nNote: These are semantic co-occurrences. The drug could *cause* the condition (adverse event) or *treat* the condition. A GraphRAG LLM is required to determine the context of these papers.")

def main():
    driver = get_neo4j_driver()
    with driver.session() as session:
        print("⚙️  Initializing MedBridge Semantic Rules Engine...")
        run_drug_interaction_rule(session)
        run_literature_based_flagging(session)
    driver.close()

if __name__ == "__main__":
    main()
