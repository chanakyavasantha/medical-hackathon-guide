import os
import sys
import pandas as pd
from tabulate import tabulate

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from knowledge_graph.db import get_neo4j_driver

# ---------------------------------------------------------------------------
# STOPLIST: Non-therapeutic items that pollute drug interaction results
# These are IV fluids, flushes, supply items, and routine ICU supportive meds
# that show up in MIMIC-IV prescriptions but aren't clinically meaningful
# for interaction analysis
# ---------------------------------------------------------------------------
DRUG_STOPLIST = [
    # IV fluids and flushes
    "Sodium Chloride 0.9%", "0.9% Sodium Chloride", "Sodium Chloride 0.9%  Flush",
    "D5W", "Dextrose 5%", "Lactated Ringers", "Sterile Water",
    # Supply items that got loaded as drugs
    "Bag", "Syringe", "Vial",
    # Routine ICU supportive meds (present in nearly every ICU patient)
    "Magnesium Sulfate", "Calcium Gluconate", "Insulin", "Heparin", "Senna", 
    "Docusate Sodium", "Bisacodyl", "Acetaminophen", "Glucagon", "Docusate",
    "Iso-Osmotic Dextrose", "Dextrose 50%", "5% Dextrose", "Potassium Chloride",
    "Chlorhexidine Gluconate 0.12% Oral Rinse", "Glucose Gel", "OxycoDONE", 
    "Aspirin", "Vancomycin", "Metoprolol", "Soln", "Neutra-Phos", "Lorazepam",
    "HYDROmorphone (Dilaudid)", "Propofol", "Iso-Osmotic Sodium Chloride",
    "Polyethylene Glycol", "Famotidine", "Milk of Magnesia", "Fentanyl Citrate",
    "SW", "NS", "D5 1/2NS", "PNEUMOcoccal", "Multivitamins",
    "Citrate", "Sodium Sulfate", "Potassium Sulfate", "Sodium Bicarbonate",
    "Glucose", "Magnesium Citrate"
]

# Lowercase for matching
DRUG_STOPLIST_LOWER = [d.lower() for d in DRUG_STOPLIST]

def stoplist_filter():
    """Generate a Cypher WHERE clause to exclude stoplist drugs."""
    conditions = []
    for drug in DRUG_STOPLIST_LOWER:
        conditions.append(f'NOT toLower(d1.name) CONTAINS "{drug}"')
        conditions.append(f'NOT toLower(d2.name) CONTAINS "{drug}"')
    return " AND ".join(conditions)

def stoplist_filter_single(var="d"):
    """Generate a Cypher WHERE clause for a single drug variable."""
    conditions = []
    for drug in DRUG_STOPLIST_LOWER:
        conditions.append(f'NOT toLower({var}.name) CONTAINS "{drug}"')
    return " AND ".join(conditions)


def get_total_patients(session):
    result = session.run("MATCH (p:Patient) RETURN count(p) as total")
    return result.single()["total"]


def print_graph_stats(session):
    print("\n" + "=" * 90)
    print("📈 KNOWLEDGE GRAPH STATISTICS")
    print("=" * 90)

    # Node counts
    nodes_res = session.run("""
        MATCH (n) 
        RETURN labels(n)[0] AS Label, count(n) AS Count 
        ORDER BY Count DESC
    """)
    nodes_df = pd.DataFrame([r.data() for r in nodes_res])

    # Edge counts
    edges_res = session.run("""
        MATCH ()-[r]->() 
        RETURN type(r) AS Type, count(r) AS Count 
        ORDER BY Count DESC
    """)
    edges_df = pd.DataFrame([r.data() for r in edges_res])

    print("🟢 NODES:")
    if not nodes_df.empty:
        print(tabulate(nodes_df, headers='keys', tablefmt='simple_grid', showindex=False))
    else:
        print("  No nodes found.")

    print("\n🔗 EDGES:")
    if not edges_df.empty:
        print(tabulate(edges_df, headers='keys', tablefmt='simple_grid', showindex=False))
    else:
        print("  No edges found.")
    print()


def analyze_drug_interaction_aggregates(session):
    print("\n" + "=" * 90)
    print("🚨 CLINICAL SIGNAL 1: POPULATION-LEVEL DRUG INTERACTION ALERTS")
    print("=" * 90)

    cypher = f"""
        MATCH (p:Patient)-[:TAKES_DRUG]->(d1:Drug)-[r:INTERACTS_WITH]-(d2:Drug)<-[:TAKES_DRUG]-(p)
        WHERE elementId(d1) < elementId(d2)
          AND {stoplist_filter()}
        RETURN d1.name AS Drug1,
               d2.name AS Drug2,
               r.severity AS Severity,
               r.description AS Description,
               count(DISTINCT p) AS AffectedPatients
        ORDER BY AffectedPatients DESC
        LIMIT 10
    """
    result = session.run(cypher)
    df = pd.DataFrame([r.data() for r in result])

    if not df.empty:
        for _, row in df.iterrows():
            severity = row.get('Severity') or 'Unknown'
            desc = row.get('Description') or ''
            print(f"⚠️  {row['AffectedPatients']} patients: {row['Drug1']} + {row['Drug2']}")
            print(f"    Severity: {severity}")
            if desc:
                print(f"    Risk: {desc}")
            print()
    else:
        print("✅ No population-level interaction alerts found (after filtering ICU supportive meds).")


def analyze_polypharmacy(session):
    print("\n" + "=" * 90)
    print("💊 CLINICAL SIGNAL 2: POLYPHARMACY (CONCURRENT MEDICATIONS)")
    print("=" * 90)

    # Count distinct drugs per patient, excluding stoplist items
    # This counts unique drug entities, not individual orders
    cypher = f"""
        MATCH (p:Patient)-[:TAKES_DRUG]->(d:Drug)
        WHERE {stoplist_filter_single('d')}
        WITH p, count(DISTINCT d) AS DrugCount, collect(DISTINCT d.name) AS DrugNames
        WHERE DrugCount >= 8
        OPTIONAL MATCH (p)-[:TAKES_DRUG]->(d1:Drug)-[:INTERACTS_WITH]-(d2:Drug)<-[:TAKES_DRUG]-(p)
        WHERE elementId(d1) < elementId(d2)
          AND {stoplist_filter()}
        WITH p, DrugCount, count(DISTINCT d1) AS InteractionPairs
        RETURN p.id AS PatientID,
               DrugCount AS UniqueDrugs,
               InteractionPairs,
               InteractionPairs > 0 AS HasInteraction
        ORDER BY DrugCount DESC
        LIMIT 10
    """
    result = session.run(cypher)
    df = pd.DataFrame([r.data() for r in result])

    if not df.empty:
        total_poly = len(df)
        with_interactions = df['HasInteraction'].sum()
        print(f"⚠️  Top {total_poly} patients by unique drug count (excluding IV fluids/flushes).")
        print(f"    {with_interactions} of them have known interaction pairs.\n")
        print(tabulate(df, headers='keys', tablefmt='simple_grid', showindex=False))
    else:
        print("✅ No excessive polypharmacy flags found.")


def analyze_evidence_gaps(session):
    print("\n" + "=" * 90)
    print("🔬 CLINICAL SIGNAL 3: DRUG EVIDENCE GAPS")
    print("=" * 90)

    cypher = f"""
        MATCH (p:Patient)-[:TAKES_DRUG]->(d:Drug)
        WHERE {stoplist_filter_single('d')}
        WITH d, count(DISTINCT p) AS PatientCount
        WHERE PatientCount > 5
        OPTIONAL MATCH (d)<-[:MENTIONS_DRUG]-(a:Article)
        WITH d, PatientCount, count(DISTINCT a) AS ArticleCount
        WHERE ArticleCount = 0
        RETURN d.name AS Drug, PatientCount
        ORDER BY PatientCount DESC
        LIMIT 10
    """
    result = session.run(cypher)
    df = pd.DataFrame([r.data() for r in result])

    if not df.empty:
        for _, row in df.iterrows():
            print(f"⚠️  {row['Drug']} — prescribed to {row['PatientCount']} patients, ZERO PubMed articles mention it.")
    else:
        print("✅ All frequently prescribed drugs have literature coverage.")


def analyze_unexpected_comorbidities(session, total_patients):
    print("\n" + "=" * 90)
    print("🧬 CLINICAL SIGNAL 4: COMORBIDITY CLUSTERS")
    print("=" * 90)

    # Known high-frequency comorbidity pairs (expected, not interesting)
    # These are well-documented associations — filter them out
    KNOWN_PAIRS = [
        ("hypertension", "hyperlipidemia"),
        ("hypertension", "diabetes"),
        ("diabetes", "hyperlipidemia"),
        ("hypertension", "obesity"),
        ("diabetes", "obesity"),
        ("coronary atherosclerosis", "hypertension"),
        ("coronary atherosclerosis", "hyperlipidemia"),
    ]

    cypher = """
        MATCH (p:Patient)-[:HAS_CONDITION]->(c1:Condition)
        MATCH (p)-[:HAS_CONDITION]->(c2:Condition)
        WHERE elementId(c1) < elementId(c2)
        WITH c1, c2, count(DISTINCT p) AS PatientCount
        WHERE PatientCount > 5
        RETURN c1.name AS Condition1,
               c1.code AS Code1,
               c2.name AS Condition2,
               c2.code AS Code2,
               PatientCount
        ORDER BY PatientCount DESC
        LIMIT 20
    """
    result = session.run(cypher)
    df = pd.DataFrame([r.data() for r in result])

    if not df.empty:
        # Try to resolve ICD codes to names if name is just a code
        for _, row in df.iterrows():
            c1 = row['Condition1'] or f"ICD: {row['Code1']}"
            c2 = row['Condition2'] or f"ICD: {row['Code2']}"
            pct = (row['PatientCount'] / total_patients) * 100

            # Check if this is a known boring pair
            c1_lower = c1.lower()
            c2_lower = c2.lower()
            is_known = False
            for kp1, kp2 in KNOWN_PAIRS:
                if (kp1 in c1_lower and kp2 in c2_lower) or (kp2 in c1_lower and kp1 in c2_lower):
                    is_known = True
                    break

            marker = "   (known)" if is_known else " ⭐ (potentially novel)"
            print(f"{'  ' if is_known else '⚠️'} {c1} + {c2} — {pct:.1f}% ({row['PatientCount']} patients){marker}")
    else:
        print("✅ No high-frequency comorbidity clusters found.")


def analyze_unstudied_combinations(session):
    print("\n" + "=" * 90)
    print("🧪 CLINICAL SIGNAL 5: UNSTUDIED DRUG PAIR COMBINATIONS")
    print("=" * 90)

    # Changed from triple to pair — much less memory, more reliable results
    # Find drug PAIRS that many patients take but NO article mentions both
    cypher = f"""
        MATCH (p:Patient)-[:TAKES_DRUG]->(d1:Drug)
        MATCH (p)-[:TAKES_DRUG]->(d2:Drug)
        WHERE elementId(d1) < elementId(d2)
          AND {stoplist_filter()}
        WITH d1, d2, count(DISTINCT p) AS PatientCount
        WHERE PatientCount >= 5
        AND NOT EXISTS {{
            MATCH (a:Article)-[:MENTIONS_DRUG]->(d1)
            WHERE (a)-[:MENTIONS_DRUG]->(d2)
        }}
        RETURN d1.name AS Drug1, d2.name AS Drug2, PatientCount
        ORDER BY PatientCount DESC
        LIMIT 10
    """
    result = session.run(cypher)
    df = pd.DataFrame([r.data() for r in result])

    if not df.empty:
        for _, row in df.iterrows():
            print(f"⚠️  {row['Drug1']} + {row['Drug2']} — {row['PatientCount']} patients, ZERO co-mention in PubMed")
    else:
        print("✅ All common drug pairs have at least some literature coverage.")


def analyze_literature_contradictions(session):
    print("\n" + "=" * 90)
    print("📚 CLINICAL SIGNAL 6: LITERATURE vs PATIENT DATA CONTRADICTIONS")
    print("=" * 90)

    # Find drugs that literature associates with a condition (via CO_OCCURS_WITH)
    # but patients on that drug also have that condition — potential adverse signal
    cypher = f"""
        MATCH (d:Drug)-[co:CO_OCCURS_WITH]->(c:Condition)
        WHERE co.count > 3
          AND {stoplist_filter_single('d')}
        MATCH (p:Patient)-[:TAKES_DRUG]->(d)
        MATCH (p)-[:HAS_CONDITION]->(c)
        WITH d, c, co.count AS LiteratureMentions,
             count(DISTINCT p) AS PatientsAffected,
             co.pmid_references AS PMIDs
        WHERE PatientsAffected >= 3
        RETURN d.name AS Drug,
               c.name AS Condition,
               LiteratureMentions,
               PatientsAffected,
               size(PMIDs) AS StudyCount
        ORDER BY PatientsAffected DESC
        LIMIT 10
    """
    result = session.run(cypher)
    df = pd.DataFrame([r.data() for r in result])

    if not df.empty:
        for _, row in df.iterrows():
            cond = row['Condition'] or "Unknown Condition"
            print(f"⚠️  {row['Drug']} + {cond}")
            print(f"    Literature: {row['LiteratureMentions']} co-occurrences across {row.get('StudyCount', '?')} studies")
            print(f"    Our patients: {row['PatientsAffected']} patients on this drug HAVE this condition")
            print()
    else:
        print("✅ No literature-vs-patient contradictions detected.")
        print("   (This may mean CO_OCCURS_WITH edges need to be populated.)")


def main():
    driver = get_neo4j_driver()
    with driver.session() as session:
        print("⚙️  Running Clinical Analytics (filtered for signal quality)...")
        total_patients = get_total_patients(session)
        print(f"📊 Cohort: {total_patients} patients\n")

        print_graph_stats(session)

        analyze_drug_interaction_aggregates(session)
        analyze_evidence_gaps(session)
        analyze_unstudied_combinations(session)
        analyze_unexpected_comorbidities(session, total_patients)
        analyze_literature_contradictions(session)
        analyze_polypharmacy(session)

    driver.close()
    print("\n✅ Analytics complete.")


if __name__ == "__main__":
    main()