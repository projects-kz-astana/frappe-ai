import frappe
from frappe.model.document import Document


class RAGIndexJob(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		data_source: DF.Link
		finished_on: DF.Datetime | None
		logs: DF.LongText | None
		processed_documents: DF.Int
		started_on: DF.Datetime | None
		status: DF.Literal["Queued", "Running", "Completed", "Completed with Errors", "Failed"]
		total_documents: DF.Int
	# end: auto-generated types

	pass
