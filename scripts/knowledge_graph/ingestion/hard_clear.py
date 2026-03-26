import os
import sys

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from knowledge_graph.db import get_neo4j_driver

def hard_clear_db():
    driver = get_neo4j_driver()
    print("Executing standard Cypher batched deletion...")
    with driver.session() as session:
        # Delete relationships in batches
        while True:
            result = session.run("""
                MATCH ()-[r]->() 
                WITH r LIMIT 50000 
                DELETE r 
                RETURN count(r) as deleted
            """).single()
            deleted = result["deleted"]
            print(f"Deleted {deleted} relationships...")
            if deleted == 0:
                break
                
        # Delete nodes in batches       
        while True:
            result = session.run("""
                MATCH (n) 
                WITH n LIMIT 50000 
                DELETE n 
                RETURN count(n) as deleted
            """).single()
            deleted = result["deleted"]
            print(f"Deleted {deleted} nodes...")
            if deleted == 0:
                break
                
    driver.close()
    print("Database is completely wiped.")

if __name__ == "__main__":
    hard_clear_db()
