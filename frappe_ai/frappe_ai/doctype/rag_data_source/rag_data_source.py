import frappe
from frappe.model.document import Document


class RAGDataSource(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		doctype_fields: DF.SmallText | None
		doctype_filters: DF.JSON | None
		enabled: DF.Check
		index_name: DF.Data
		source_type: DF.Literal["PDF", "DocType"]
		target_doctype: DF.Link | None
		title: DF.Data
	# end: auto-generated types

	pass
