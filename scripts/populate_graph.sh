#!/bin/bash
# populate_graph.sh
# Master script to wipe the Neo4j Graph and rebuild it completely from the raw data files
# using the normalized entity ingestion scripts.

set -e # Exit immediately if a command exits with a non-zero status

PYTHON_EXEC="venv/bin/python"
INGEST_DIR="knowledge_graph/ingestion"

echo "=========================================================================="
echo "🚨 MEDBRIDGE KNOWLEDGE GRAPH : MASTER RE-POPULATION PIPELINE 🚨"
echo "=========================================================================="
echo "This script will permanently WIPE the Neo4j database and rebuild it."
echo "Starting in 3 seconds (Ctrl+C to abort)..."
sleep 3

echo -e "\n[1/5] 🗑️  PURGING EXISTING GRAPH DATABASE..."
$PYTHON_EXEC $INGEST_DIR/hard_clear.py

echo -e "\n[2/5] 📘 INGESTING OMOP ONTOLOGY (Standards & Hierarchies)..."
$PYTHON_EXEC $INGEST_DIR/omop_loader.py

echo -e "\n[3/5] 📄 INGESTING PUBMED LITERATURE (BioBERT Vectors & Semantics)..."
$PYTHON_EXEC $INGEST_DIR/pubmed_loader.py

echo -e "\n[4/5] 🧑‍⚕️ INGESTING MIMIC-IV PATIENTS (Real-world Medical Journeys)..."
$PYTHON_EXEC $INGEST_DIR/mimic_loader.py

echo -e "\n[5/5] ⚠️  INGESTING DRUGBANK INTERACTIONS (Safety Rules)..."
$PYTHON_EXEC $INGEST_DIR/interaction_loader.py

echo -e "\n=========================================================================="
echo "✅ MASTER RE-POPULATION COMPLETE! The graph is now fully reconciled."
echo "You can now run 'venv/bin/python knowledge_graph/analytics/clinical_signals.py'"
echo "to view the cross-layer insights!"
echo "=========================================================================="
