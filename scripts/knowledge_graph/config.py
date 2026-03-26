import os
from dotenv import load_dotenv

load_dotenv()

# Neo4j Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://f6216740.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "<YOUR_NEO4J_PASSWORD>")

# Gemini LLM Configuration (uses GOOGLE_API_KEY from .env)
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", ""))

# NCBI Configuration
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
NCBI_EMAIL = os.getenv("NCBI_EMAIL", "")

# Synthea patient data directory
PATIENT_DATA_DIR = os.getenv("PATIENT_DATA_DIR", os.path.join(os.path.dirname(__file__), "../data/patients"))