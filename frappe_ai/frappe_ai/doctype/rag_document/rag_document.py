import frappe
from frappe.model.document import Document


class RAGDocument(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		content_hash: DF.Data | None
		data_source: DF.Link
		error_log: DF.LongText | None
		file: DF.Attach | None
		last_indexed_on: DF.Datetime | None
		status: DF.Literal["Pending", "Indexing", "Indexed", "Failed"]
		version: DF.Int
	# end: auto-generated types

	def on_update(self):
		if not self.file:
			return
		if self.status == "Indexing":
			return

		before = self.get_doc_before_save()
		file_changed = (not before) or (before.get("file") != self.file)

		if file_changed or self.status in ("Pending", "Failed"):
			self.db_set("status", "Pending", notify=True)
			from frappe_ai.rag.indexing import enqueue_indexing
			enqueue_indexing(self.data_source)
