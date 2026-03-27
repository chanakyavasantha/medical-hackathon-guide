# 🤖 LLM Applications in Medicine

This directory focuses on leveraging Large Language Models (LLMs) to extract, summarize, and reason over medical data. 

## 🩺 MedGemma: The Medical LLM

MedGemma is a suite of fine-tuned Gemma models designed for medical tasks, such as answering clinical questions and summarizing medical literature.

### 🔑 Hugging Face Setup

To use MedGemma, you need to set up your Hugging Face account and obtain an access token.

1.  **Create an Account**: Sign up at [huggingface.co](https://huggingface.co/).
2.  **Request Access**: Some medical models require access requests. Visit the [google/med-gemma-7b-it](https://huggingface.co/google/med-gemma-7b-it) page and follow the instructions.
3.  **Generate a Token**: Go to **Settings > Access Tokens** and create a new token with `read` permissions.
4.  **Login in Python**:
    ```python
    from huggingface_hub import login
    login("YOUR_HF_TOKEN")
    ```

### 🛠️ Installation

```bash
pip install transformers accelerate bitsandbytes sentencepiece
```

## 🧪 Starter Notebook

Check out [medgemma_starter.ipynb](./medgemma_starter.ipynb) for a hands-on guide to:
-   Loading MedGemma using 4-bit quantization.
-   Generating clinical summaries from patient data.
-   Integrating the Knowledge Graph with LLM prompts (RAG).
