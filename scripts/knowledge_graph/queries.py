# ---------------------------------------------------------------------------
# Discovery Queries — designed to work with actual graph schema
# Edge types: HAS_CONDITION, TAKES_DRUG, HAS_LAB_RESULT, IS_TEST,
#             TREATS, INTERACTS_WITH, KNOWN_COMORBIDITY, RISK_FACTOR_FOR,
#             MENTIONS, HAS_ENCOUNTER
# ---------------------------------------------------------------------------

QUERIES = {

    # -----------------------------------------------------------------------
    # 1. PATIENT SAFETY: Find patients on drugs that interact with each other
    # -----------------------------------------------------------------------
    "dangerous_drug_combos": {
        "description": "Patients actively taking high-severity interacting drug combinations",
        "cypher": """
            MATCH (p:Patient)-[t1:TAKES_DRUG]->(d1:Drug)-[i:INTERACTS_WITH]-(d2:Drug)<-[t2:TAKES_DRUG]-(p)
            WHERE d1.code < d2.code
              AND i.severity = 'high'
              AND t1.status = 'active' 
              AND t2.status = 'active'
            RETURN p.name AS patient,
                   d1.name AS drug1,
                   d2.name AS drug2,
                   i.severity AS severity,
                   i.description AS risk
            ORDER BY patient
            LIMIT 20
        """,
    },

    # -----------------------------------------------------------------------
    # 2. NOVEL SIGNALS: Drug combos in patients with NO published studies
    # -----------------------------------------------------------------------
    "unstudied_drug_combos": {
        "description": "Drug combinations used by patients but NOT co-mentioned in any PubMed study",
        "cypher": """
            MATCH (p:Patient)-[:TAKES_DRUG]->(d1:Drug)
            MATCH (p)-[:TAKES_DRUG]->(d2:Drug)
            WHERE d1.code < d2.code
            AND NOT EXISTS {
                MATCH (s:Study)-[:MENTIONS]->(d1)
                WHERE (s)-[:MENTIONS]->(d2)
            }
            WITH d1, d2, COUNT(DISTINCT p) AS patient_count
            WHERE patient_count >= 2
            RETURN d1.name AS drug1, d2.name AS drug2, patient_count
            ORDER BY patient_count DESC
            LIMIT 15
        """,
    },

    # -----------------------------------------------------------------------
    # 3. LITERATURE vs REALITY: Drugs studied for conditions our patients have
    # -----------------------------------------------------------------------
    "literature_patient_overlap": {
        "description": "Studies mentioning drugs that our patients are actually taking",
        "cypher": """
            MATCH (p:Patient)-[:TAKES_DRUG]->(d:Drug)<-[:MENTIONS]-(s:Study)
            RETURN d.name AS drug,
                   COUNT(DISTINCT p) AS patients_taking,
                   COUNT(DISTINCT s) AS studies_mentioning,
                   COLLECT(DISTINCT s.title)[0..3] AS sample_studies
            ORDER BY patients_taking DESC
            LIMIT 10
        """,
    },

    # -----------------------------------------------------------------------
    # 4. TRIAL CANDIDATES: Patients with a condition NOT on its standard treatment
    # -----------------------------------------------------------------------
    "trial_candidates": {
        "description": "Patients with active conditions strictly missing ANY active standard-of-care baseline treatment",
        "cypher": """
            MATCH (c:Condition)<-[hc:HAS_CONDITION]-(p:Patient)
            WHERE hc.status = 'active'
              AND EXISTS { MATCH (:Drug)-[:TREATS]->(c) }
              AND NOT EXISTS {
                  MATCH (p)-[t:TAKES_DRUG]->(d:Drug)-[:TREATS]->(c)
                  WHERE t.status = 'active'
              }
            RETURN c.name AS condition,
                   p.name AS patient,
                   p.dob AS date_of_birth
            LIMIT 15
        """,
    },

    # -----------------------------------------------------------------------
    # 5. UNEXPECTED COMORBIDITIES: Condition pairs in patients NOT known to be linked
    # -----------------------------------------------------------------------
    "unexpected_comorbidities": {
        "description": "Condition pairs co-occurring in patients that are NOT known comorbidities",
        "cypher": """
            MATCH (p:Patient)-[:HAS_CONDITION]->(c1:Condition)
            MATCH (p)-[:HAS_CONDITION]->(c2:Condition)
            WHERE c1.code < c2.code
            AND NOT (c1)-[:KNOWN_COMORBIDITY]-(c2)
            AND NOT (c1)-[:RISK_FACTOR_FOR]-(c2)
            WITH c1, c2, COUNT(DISTINCT p) AS frequency
            WHERE frequency >= 2
            RETURN c1.name AS condition1,
                   c2.name AS condition2,
                   frequency
            ORDER BY frequency DESC
            LIMIT 10
        """,
    },

    # -----------------------------------------------------------------------
    # 6. RISK CASCADE: Patients with risk factors for serious conditions
    # -----------------------------------------------------------------------
    "risk_cascade": {
        "description": "Patients who have risk factors for serious conditions but haven't been diagnosed yet",
        "cypher": """
            MATCH (rf:Condition)-[:RISK_FACTOR_FOR]->(serious:Condition)
            MATCH (p:Patient)-[:HAS_CONDITION]->(rf)
            WHERE NOT (p)-[:HAS_CONDITION]->(serious)
            RETURN p.name AS patient,
                   rf.name AS existing_risk_factor,
                   serious.name AS at_risk_for,
                   COUNT(*) AS num_risk_factors
            ORDER BY num_risk_factors DESC
            LIMIT 15
        """,
    },

    # -----------------------------------------------------------------------
    # 7. POLYPHARMACY: Patients on many drugs (higher interaction risk)
    # -----------------------------------------------------------------------
    "polypharmacy_risk": {
        "description": "Patients taking 5+ drugs simultaneously — higher risk of adverse interactions",
        "cypher": """
            MATCH (p:Patient)-[:TAKES_DRUG]->(d:Drug)
            WITH p, COUNT(d) AS drug_count, COLLECT(d.name) AS drugs
            WHERE drug_count >= 5
            RETURN p.name AS patient,
                   drug_count,
                   drugs
            ORDER BY drug_count DESC
            LIMIT 10
        """,
    },

    # -----------------------------------------------------------------------
    # 8. EVIDENCE GAPS: Conditions in our patients with NO literature coverage
    # -----------------------------------------------------------------------
    "evidence_gaps": {
        "description": "Conditions seen in patients but with NO PubMed studies mentioning them",
        "cypher": """
            MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition)
            WHERE NOT EXISTS { MATCH (s:Study)-[:MENTIONS]->(c) }
            WITH c, COUNT(DISTINCT p) AS patient_count
            RETURN c.name AS condition,
                   patient_count,
                   'No literature coverage' AS gap
            ORDER BY patient_count DESC
            LIMIT 10
        """,
    },

    # -----------------------------------------------------------------------
    # 9. GRAPH STATS: Overall connectivity summary
    # -----------------------------------------------------------------------
    "graph_health": {
        "description": "Overall graph connectivity — how well are the three layers linked?",
        "cypher": """
            MATCH (p:Patient) WITH COUNT(p) AS patients
            MATCH (s:Study) WITH patients, COUNT(s) AS studies
            MATCH (d:Drug) WITH patients, studies, COUNT(d) AS drugs
            MATCH (c:Condition) WITH patients, studies, drugs, COUNT(c) AS conditions
            OPTIONAL MATCH (:Study)-[m:MENTIONS]->() WITH patients, studies, drugs, conditions, COUNT(m) AS study_links
            OPTIONAL MATCH (:Patient)-[t:TAKES_DRUG]->() WITH patients, studies, drugs, conditions, study_links, COUNT(t) AS patient_drug_links
            OPTIONAL MATCH (:Patient)-[h:HAS_CONDITION]->() WITH patients, studies, drugs, conditions, study_links, patient_drug_links, COUNT(h) AS patient_cond_links
            RETURN patients, studies, drugs, conditions,
                   study_links AS literature_entity_links,
                   patient_drug_links AS patient_drug_edges,
                   patient_cond_links AS patient_condition_edges
        """,
    },
}