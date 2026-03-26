import os
import sys

# Add backend directory to path so we can import knowledge_graph
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from knowledge_graph.db import get_neo4j_driver

def normalize_omop():
    driver = get_neo4j_driver()
    with driver.session() as session:
        print("Normalizing OMOP Drug nodes for fuzzy string NER matching...")
        session.run("MATCH (d:Drug) WHERE d.lowercase_name IS NULL CALL { WITH d SET d.lowercase_name = toLower(d.name) } IN TRANSACTIONS OF 10000 ROWS")
        
        print("Normalizing OMOP Condition nodes for fuzzy string NER matching...")
        session.run("MATCH (c:Condition) WHERE c.lowercase_name IS NULL CALL { WITH c SET c.lowercase_name = toLower(c.name) } IN TRANSACTIONS OF 10000 ROWS")
    driver.close()
    print("Pre-computation normalization complete!")

if __name__ == "__main__":
    normalize_omop()
