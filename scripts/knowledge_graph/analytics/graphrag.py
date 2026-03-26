"""
GraphRAG: Text-to-Cypher Pipeline for MedBridge Knowledge Graph
================================================================
User question (English) → LLM → Cypher → Neo4j → LLM → Clinical answer with citations

Usage:
    python graphrag.py                          # interactive REPL
    python graphrag.py "your question here"     # one-shot mode
"""

import os
import sys
import json
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from knowledge_graph.db import get_neo4j_driver
from knowledge_graph.config import GEMINI_API_KEY

import google.generativeai as genai

# ---------------------------------------------------------------------------
# Step 0: Configuration
# ---------------------------------------------------------------------------

genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# Step 1: Graph Schema (injected into LLM context)
# ---------------------------------------------------------------------------

GRAPH_SCHEMA = """
Nodes:
  Patient   { id (string), gender (string), anchor_age (int), source = 'MIMIC-IV' }
  Drug      { name (string), lowercase_name (string), source (string), concept_class (string) }
  Condition { name (string), code (string), lowercase_name (string), source (string) }
  Article   { pmid (string), title (string), snippet (string), source = 'PubMed_Baseline' }

Edges:
  (Patient)-[:TAKES_DRUG]->(Drug)
  (Patient)-[:HAS_CONDITION]->(Condition)
  (Drug)-[:INTERACTS_WITH { severity (string), description (string) }]-(Drug)
  (Article)-[:MENTIONS_DRUG]->(Drug)
  (Article)-[:MENTIONS_CONDITION]->(Condition)
  (Drug)-[:CO_OCCURS_WITH { count (int), pmid_references (list of strings) }]->(Condition)

Key matching rules:
  - Drug nodes are matched via lowercase_name (always lowercase, generic ingredient name)
  - Condition nodes from MIMIC use code (ICD code without dots), from SNOMED use code (concept_code)
  - Use toLower() and CONTAINS for fuzzy text matching on names
  - Patient.id is a string, not an integer
"""

# ---------------------------------------------------------------------------
# Step 2: Cypher Generation
# ---------------------------------------------------------------------------

CYPHER_SYSTEM_PROMPT = f"""You are a Cypher query generator for a Neo4j clinical knowledge graph.

GRAPH SCHEMA:
{GRAPH_SCHEMA}

RULES:
1. Return ONLY a valid Cypher query. No markdown fences, no explanation, no comments.
2. Use toLower() and CONTAINS for drug/condition name matching.
3. For drug lookups, match on lowercase_name: WHERE d.lowercase_name CONTAINS toLower("drug name")
4. LIMIT results to 25 unless the user specifies otherwise.
5. NEVER use DELETE, SET, CREATE, MERGE, or any write operations. Read-only queries ONLY.
6. Use DISTINCT where appropriate to avoid duplicates.
7. When counting patients, always use count(DISTINCT p).
8. For drug interactions, the INTERACTS_WITH relationship is undirected — use (d1)-[:INTERACTS_WITH]-(d2).
9. When returning interaction info, include the severity and description properties.
10. For finding articles/studies about a drug, traverse (Article)-[:MENTIONS_DRUG]->(Drug).
11. Always return human-readable names (d.name, c.name) not just IDs.
"""


def generate_cypher(question: str) -> str:
    """Send user question to Gemini, get back a Cypher query."""
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(
        [
            {"role": "user", "parts": [{"text": CYPHER_SYSTEM_PROMPT}]},
            {"role": "model", "parts": [{"text": "Understood. I will generate read-only Cypher queries based on the schema provided. Send me a question."}]},
            {"role": "user", "parts": [{"text": question}]},
        ],
    )
    
    cypher = response.text.strip()
    
    # Strip markdown code fences if the LLM wraps them anyway
    cypher = re.sub(r'^```(?:cypher)?\s*', '', cypher)
    cypher = re.sub(r'\s*```$', '', cypher)
    
    return cypher.strip()


# ---------------------------------------------------------------------------
# Step 3: Execute Cypher against Neo4j
# ---------------------------------------------------------------------------

def execute_cypher(cypher: str, session) -> list[dict]:
    """Run a Cypher query and return results as a list of dicts."""
    result = session.run(cypher)
    return [record.data() for record in result]


# ---------------------------------------------------------------------------
# Step 4: Answer Synthesis
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM_PROMPT = """You are a clinical research assistant synthesizing findings from a medical knowledge graph.

RULES:
1. Write a clear, evidence-based answer to the user's question.
2. Cite specific data from the results: patient IDs, drug names, PMIDs, condition names, counts.
3. If results are empty, say so honestly — do not fabricate data.
4. Format numbers clearly (e.g., "34 patients", "across 7 studies").
5. Use bullet points or short paragraphs for readability.
6. If the query returned interaction data, highlight severity levels.
7. Keep the tone professional but accessible — like a clinical informatics report.
8. NEVER invent data that is not present in the provided results.
"""


def synthesize_answer(question: str, results: list[dict], cypher: str) -> str:
    """Send question + raw Neo4j results to Gemini for natural language synthesis."""
    model = genai.GenerativeModel(MODEL_NAME)
    
    # Truncate massive result sets to avoid token limits
    results_str = json.dumps(results[:50], indent=2, default=str)
    
    user_prompt = f"""Original question: {question}

Cypher query that was executed:
{cypher}

Raw results from the knowledge graph ({len(results)} rows, showing first {min(50, len(results))}):
{results_str}

Please synthesize a clear clinical answer based on these results."""
    
    response = model.generate_content(
        [
            {"role": "user", "parts": [{"text": SYNTHESIS_SYSTEM_PROMPT}]},
            {"role": "model", "parts": [{"text": "Ready to synthesize clinical findings. Send me the question and data."}]},
            {"role": "user", "parts": [{"text": user_prompt}]},
        ],
    )
    
    return response.text.strip()


# ---------------------------------------------------------------------------
# Orchestrator: The full pipeline
# ---------------------------------------------------------------------------

def ask(question: str, verbose: bool = True) -> str:
    """
    Full GraphRAG pipeline:
    Question → Cypher → Neo4j → Answer
    """
    driver = get_neo4j_driver()
    
    try:
        with driver.session() as session:
            # Step 1: Generate Cypher
            if verbose:
                print(f"\n🧠 Generating Cypher for: \"{question}\"")
            
            cypher = generate_cypher(question)
            
            if verbose:
                print(f"\n📝 Generated Cypher:\n{cypher}\n")
            
            # Step 2: Execute (with one retry on syntax error)
            try:
                results = execute_cypher(cypher, session)
            except Exception as e:
                if verbose:
                    print(f"⚠️  Cypher failed: {e}")
                    print("🔄 Asking LLM to self-correct...")
                
                # Self-correction: send error back to LLM
                correction_prompt = f"""The following Cypher query failed with this error:

Query: {cypher}
Error: {str(e)}

Please fix the query and return ONLY the corrected Cypher. No explanation."""
                
                cypher = generate_cypher(correction_prompt)
                
                if verbose:
                    print(f"\n📝 Corrected Cypher:\n{cypher}\n")
                
                try:
                    results = execute_cypher(cypher, session)
                except Exception as e2:
                    return f"❌ Query failed after retry: {e2}"
            
            if verbose:
                print(f"📊 Got {len(results)} results from Neo4j")
            
            # Step 3: Synthesize answer
            if not results:
                answer = synthesize_answer(question, [], cypher)
            else:
                answer = synthesize_answer(question, results, cypher)
            
            if verbose:
                print(f"\n{'='*80}")
                print(f"💬 ANSWER:")
                print(f"{'='*80}")
            
            return answer
            
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# CLI: Interactive REPL or one-shot
# ---------------------------------------------------------------------------

def main():
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY not set. Add it to your .env file or export it:")
        print("   export GEMINI_API_KEY='your-key-here'")
        sys.exit(1)
    
    # One-shot mode
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        answer = ask(question)
        print(answer)
        return
    
    # Interactive REPL
    print("=" * 80)
    print("🧬 MedBridge GraphRAG — Ask questions about the clinical knowledge graph")
    print("=" * 80)
    print("Type your question and press Enter. Type 'quit' to exit.\n")
    
    while True:
        try:
            question = input("❓ Ask: ").strip()
            if question.lower() in ('quit', 'exit', 'q'):
                print("👋 Goodbye!")
                break
            if not question:
                continue
            
            answer = ask(question)
            print(answer)
            print()
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
