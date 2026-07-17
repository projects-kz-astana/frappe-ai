import frappe
import numpy as np

from frappe_ai.rag.settings import embedding_api_key


def embed_text(text: str, settings) -> np.ndarray:
	provider = (settings.get("embedding_provider") or "").strip()
	model = (settings.get("embedding_model") or "").strip()
	api_key = embedding_api_key(settings)

	if not model:
		frappe.throw("Embedding model is not configured in RAG Settings.")

	if provider == "Google":
		from google import genai as google_genai

		client = google_genai.Client(api_key=api_key)
		response = client.models.embed_content(model=model, contents=text)
		return np.array(response.embeddings[0].values, dtype=np.float32)

	elif provider == "OpenAI":
		from openai import OpenAI

		base_url = (settings.get("embedding_base_url") or "").strip()
		kwargs = {"api_key": api_key}
		if base_url:
			kwargs["base_url"] = base_url
		client = OpenAI(**kwargs)
		response = client.embeddings.create(model=model, input=text)
		return np.array(response.data[0].embedding, dtype=np.float32)

	else:
		frappe.throw(f"Unsupported embedding provider: '{provider}'")
