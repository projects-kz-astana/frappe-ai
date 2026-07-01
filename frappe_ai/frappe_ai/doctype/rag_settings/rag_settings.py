import frappe
from frappe.model.document import Document


class RAGSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		chunk_overlap: DF.Int
		chunk_size: DF.Int
		embedding_api_key: DF.Data | None
		embedding_model: DF.Data
		embedding_provider: DF.Literal["Google", "OpenAI"]
		hybrid_search_enabled: DF.Check
		llm_client: DF.Link
		reindex_schedule: DF.Data | None
		system_prompt: DF.LongText | None
		top_k: DF.Int
		vector_store_type: DF.Literal["FAISS"]
	# end: auto-generated types

	pass
