import os
import sys

# Add backend directory to path so we can import knowledge_graph
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from knowledge_graph.db import get_neo4j_driver

def check_indexes():
    driver = get_neo4j_driver()
    with driver.session() as session:
        print("Checking Neo4j Index Status...")
        result = session.run("SHOW INDEXES YIELD name, state, type")
        for record in result:
            print(f"- {record['name']:<25} | State: {record['state']:<10} | Type: {record['type']}")
    driver.close()

if __name__ == "__main__":
    check_indexes()
