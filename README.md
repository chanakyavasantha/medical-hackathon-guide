# 🏥 MedBridge Hackathon Starter Guide

Welcome to the **MedBridge Hackathon!** This repository is your gateway to building the next generation of AI-driven medical insights. We've compiled the core infrastructure and data ingestion pipelines you'll need to hit the ground running.

## 🚀 Overview

MedBridge focuses on reconciling clinical signals across three critical layers:

1. **Clinical Reality**: Real-world patient data (MIMIC-IV).
2. **Medical Knowledge**: Scientific literature and semantics (PubMed).
3. **Safety & Standards**: Standardized ontologies (OMOP/Athena) and drug safety (DrugBank).

## 📊 Data Overview & Use Cases

| Data Source           | Type                  | Download Link                                                                 | Potential ML/AI Use Cases                                             |
| :-------------------- | :-------------------- | :---------------------------------------------------------------------------- | :-------------------------------------------------------------------- |
| **MIMIC-IV**          | Clinical Records      | [PhysioNet (v2.2)](https://physionet.org/content/mimiciv/2.2/)                | Mortality prediction, Length of Stay (LOS), Sepsis/AKI risk scoring   |
| **OMOP (Athena)**     | Standardized Ontology | [OHDSI Athena](https://athena.ohdsi.org)                                      | Entity normalization, patient cohort building, domain-specific search |
| **PubMed Baseline**   | Scientific Literature | [NCBI FTP Baseline](https://ftp.ncbi.nlm.nih.gov/pubmed/baseline/)            | RAG for medical Q&A, Knowledge Graph extraction, Semantic Search      |
| **DrugBank (Kaggle)** | Drug Safety           | [Kaggle DDI Dataset](https://www.kaggle.com/datasets/mghobashy/drug-drug-interactions) | Interaction prediction, drug repositioning, treatment safety guards   |
| **Clinical Signals**  | Derived Graph         | *Build using provided scripts*                                                | Graph Neural Networks (GNNs), link prediction, explainable medical AI |

---

## 📥 Data Download Instructions

To respect data privacy and licensing, you must download the following datasets directly from their official sources and place them in the `data/` directory.

### 1. MIMIC-IV (Clinical Reality)

- **Source**: [PhysioNet MIMIC-IV v2.2](https://physionet.org/content/mimiciv/2.2/)
- **Files Needed**:
  - `hosp/patients.csv.gz`
  - `hosp/diagnoses_icd.csv.gz`
  - `hosp/prescriptions.csv.gz`
  - `hosp/labevents.csv.gz`
- **Placement**: `/data/mimiciv/`

### 2. OMOP Vocabularies (Standards)

- **Source**: [OHDSI Athena](athena.ohdsi.org)
- **Instructions**: Select the following vocabularies: `SNOMED`, `RxNorm`, `ICD9CM`, `ICD10CM`.
- **Files Needed**: `CONCEPT.csv`, `CONCEPT_RELATIONSHIP.csv`.
- **Placement**: `/data/poc_raw/omop_vocab/`

### 3. PubMed Literature (Medical Knowledge)

- **Source**: [PubMed Baseline](https://ftp.ncbi.nlm.nih.gov/pubmed/baseline/)
- **Note**: For this hackathon, we recommend using the pre-processed JSON edges file if available, or downloading the XML baselines and processing them using the Provided `pubmed_loader.py`.
- **Placement**: `/data/poc_raw/`

### 4. DrugBank Interactions (Safety)

- **Source**: https://www.kaggle.com/datasets/mghobashy/drug-drug-interactions
- **File Needed**: `db_drug_interactions.csv`.
- **Placement**: `/data/poc_raw/`

---

## 🛠️ Environment Setup

### 1. Prerequisites

- **Python 3.10+**
- **Neo4j Desktop/AuraDB**: Ensure you have a running Neo4j instance.

### 2. Installations

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuration

Copy the sample config and add your Neo4j credentials:

```bash
cp scripts/knowledge_graph/config.sample.py scripts/knowledge_graph/config.py
```

---

## 🏗️ Rebuilding the Graph

Once your data is in place, run the master ingestion script to populate your Neo4j Knowledge Graph:

```bash
cd scripts
chmod +x populate_graph.sh
./populate_graph.sh
```

---

## 💡 ML/AI Project Ideas

Beyond building the Knowledge Graph, here are some high-impact ways you can use this data for ML/AI projects:

### 1. Predictive Clinical Analytics (MIMIC-IV)

- **Risk Scoring**: Build a model to predict the probability of Acute Kidney Injury (AKI) or Sepsis based on lab events and patient history.
- **Length of Stay (LOS) Optimization**: Predict how long a patient will stay in the hospital to help with resource allocation.
- **Mortality Prediction**: Use longitudinal lab data and diagnoses to predict patient outcomes.

### 2. Knowledge Graph Reasoning (Neo4j + GNNs)

- **Link Prediction**: Predict unrecognized drug-drug interactions or potential new uses for existing drugs (Drug Repositioning).
- **Entity Resolution**: Harmonize clinical entities from different sources (e.g., matching a local patient record to a global OMOP concept).
- **Path-based Reasoning**: Use Meta-paths to explain *why* a certain treatment is recommended based on literature (PubMed) and safety rules (DrugBank).

### 3. Natural Language Processing (PubMed + Clinical Notes)

- **Medical Q&A (RAG)**: Build a Retrieval-Augmented Generation system that answers medical queries using the Knowledge Graph as a "Fact Layer" to ground the LLM's responses.
- **Semantic Search**: Implement a search engine for medical literature that understands relationships (e.g., find all papers discussing "Drug X" interacting with "Condition Y").

### 4. Personalized & Precision Medicine

- **Treatment Suggestion**: Suggest safer alternative medications for patients with high-risk drug-drug interaction profiles.
- **Phenotype Discovery**: Group patients into clusters based on their medical journeys to discover new disease subtypes.

---

## 🧪 Getting Started

Check out the `notebooks/` directory for starter code on:

- Querying the Neo4j graph for patient journeys.
- Analyzing co-occurrence between drugs and conditions.
- Building simple GNN models using the provided structure.

Happy Coding! 🧬💻
