import frappe
from frappe.model.document import Document


class AgentTool(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		tool: DF.Literal["list_doctypes", "get_doctype_fields", "search_documents", "get_document", "count_documents", "create_document", "update_document", "submit_document", "cancel_document", "run_report", "list_my_tasks"]
	# end: auto-generated types

	pass
