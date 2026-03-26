from neo4j import GraphDatabase
from .config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def get_neo4j_driver():
    """Returns a Neo4j driver instance."""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def init_db(driver):
    """Sets up constraints and indexes to ensure data integrity and performance."""
    with driver.session() as session:
        # Constraints for uniqueness
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Patient) REQUIRE p.id IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Condition) REQUIRE c.code IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Drug) REQUIRE d.code IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (l:LabTest) REQUIRE l.code IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Study) REQUIRE s.pmid IS UNIQUE")

        # Indexes for fast lookups
        session.run("CREATE INDEX IF NOT EXISTS FOR (c:Condition) ON (c.name)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (d:Drug) ON (d.name)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (l:LabTest) ON (l.name)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (s:Study) ON (s.title)")

        print("Database initialized with constraints and indexes.")


def clear_db(driver):
    """Wipe all nodes and relationships. Use for re-running POC from scratch."""
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
        print("Database cleared.")


def get_stats(driver):
    """Print current graph statistics."""
    with driver.session() as session:
        result = session.run("""
            MATCH (n)
            RETURN labels(n)[0] AS label, COUNT(n) AS count
            ORDER BY count DESC
        """)
        print("\n--- Graph Stats ---")
        total = 0
        for record in result:
            print(f"  {record['label']}: {record['count']}")
            total += record['count']

        rel_result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS type, COUNT(r) AS count
            ORDER BY count DESC
        """)
        print("  ---")
        for record in rel_result:
            print(f"  {record['type']}: {record['count']}")
            total += record['count']
        print(f"  Total elements: {total}")
        print("-------------------\n")