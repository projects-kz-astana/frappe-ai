import json

import frappe

from frappe_ai.agent import permissions

MAX_ROWS = 50


def list_doctypes(keyword: str | None = None) -> list[dict]:
	filters = {"istable": 0, "issingle": 0}
	or_filters = None
	if keyword:
		or_filters = {"name": ["like", f"%{keyword}%"]}
	rows = frappe.get_list(
		"DocType",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "module"],
		limit_page_length=MAX_ROWS,
		ignore_permissions=False,
	)
	return [r for r in rows if frappe.has_permission(r["name"], "read")]


def get_doctype_fields(doctype: str) -> dict:
	permissions.assert_can_read(doctype)
	meta = frappe.get_meta(doctype)
	fields = [
		{
			"fieldname": f.fieldname,
			"label": f.label,
			"fieldtype": f.fieldtype,
			"options": f.options,
			"reqd": bool(f.reqd),
		}
		for f in meta.fields
		if f.fieldtype not in ("Section Break", "Column Break", "Tab Break", "HTML")
	]
	return {
		"doctype": doctype,
		"is_submittable": bool(meta.is_submittable),
		"title_field": meta.title_field,
		"fields": fields,
	}


def search_documents(
	doctype: str,
	keyword: str | None = None,
	filters: dict | None = None,
	fields: list | None = None,
	limit: int = 20,
) -> list[dict]:
	permissions.assert_can_read(doctype)
	query_fields = fields or ["name"]
	if "name" not in query_fields:
		query_fields = ["name", *query_fields]

	or_filters = None
	if keyword:
		meta = frappe.get_meta(doctype)
		search_fields = ["name"]
		if meta.title_field:
			search_fields.append(meta.title_field)
		for field in meta.get_search_fields():
			if field not in search_fields:
				search_fields.append(field)
		or_filters = {f: ["like", f"%{keyword}%"] for f in search_fields}

	return frappe.get_list(
		doctype,
		filters=normalize_filters(filters),
		or_filters=or_filters,
		fields=query_fields,
		limit_page_length=min(int(limit or 20), MAX_ROWS),
		ignore_permissions=False,
	)


def get_document(doctype: str, name: str) -> dict:
	permissions.assert_can_read(doctype, name)
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	return doc.as_dict(no_nulls=True)


def count_documents(doctype: str, filters: dict | None = None) -> dict:
	permissions.assert_can_read(doctype)
	count = frappe.db.count(doctype, filters=normalize_filters(filters))
	return {"doctype": doctype, "count": count}


def create_document(doctype: str, data: dict) -> dict:
	permissions.assert_can_create(doctype)
	payload = normalize_data(data)
	payload["doctype"] = doctype
	doc = frappe.get_doc(payload)
	doc.insert()
	frappe.db.commit()
	return {"doctype": doctype, "name": doc.name, "status": "created"}


def update_document(doctype: str, name: str, data: dict) -> dict:
	permissions.assert_can_write(doctype, name)
	doc = frappe.get_doc(doctype, name)
	doc.update(normalize_data(data))
	doc.save()
	frappe.db.commit()
	return {"doctype": doctype, "name": doc.name, "status": "updated"}


def submit_document(doctype: str, name: str) -> dict:
	permissions.assert_can_submit(doctype, name)
	doc = frappe.get_doc(doctype, name)
	doc.submit()
	frappe.db.commit()
	return {"doctype": doctype, "name": doc.name, "status": "submitted"}


def cancel_document(doctype: str, name: str) -> dict:
	permissions.assert_can_cancel(doctype, name)
	doc = frappe.get_doc(doctype, name)
	doc.cancel()
	frappe.db.commit()
	return {"doctype": doctype, "name": doc.name, "status": "cancelled"}


def run_report(report_name: str, filters: dict | None = None) -> dict:
	permissions.assert_can_read("Report", report_name)
	from frappe.desk.query_report import run as run_query_report

	result = run_query_report(report_name, filters=normalize_filters(filters))
	columns = [
		c.get("label") if isinstance(c, dict) else c
		for c in (result.get("columns") or [])
	]
	rows = (result.get("result") or [])[:MAX_ROWS]
	return {"report": report_name, "columns": columns, "rows": rows}


def list_my_tasks(status: str = "Open") -> list[dict]:
	filters = {"allocated_to": frappe.session.user}
	if status:
		filters["status"] = status
	return frappe.get_list(
		"ToDo",
		filters=filters,
		fields=["name", "description", "reference_type", "reference_name", "priority", "date"],
		limit_page_length=MAX_ROWS,
		ignore_permissions=False,
	)


def normalize_filters(filters):
	if filters is None:
		return {}
	if isinstance(filters, str):
		try:
			return json.loads(filters)
		except (ValueError, TypeError):
			return {}
	return filters


def normalize_data(data):
	if isinstance(data, str):
		try:
			return json.loads(data)
		except (ValueError, TypeError):
			frappe.throw("Tool argument 'data' must be a JSON object.")
	return dict(data or {})


REGISTRY = {
	"list_doctypes": list_doctypes,
	"get_doctype_fields": get_doctype_fields,
	"search_documents": search_documents,
	"get_document": get_document,
	"count_documents": count_documents,
	"create_document": create_document,
	"update_document": update_document,
	"submit_document": submit_document,
	"cancel_document": cancel_document,
	"run_report": run_report,
	"list_my_tasks": list_my_tasks,
}


TOOL_SCHEMAS = [
	{
		"name": "list_doctypes",
		"description": "List DocTypes the current user can read. Optionally filter by a keyword in the name.",
		"input_schema": {
			"type": "object",
			"properties": {
				"keyword": {"type": "string", "description": "Substring to match against DocType names."}
			},
		},
	},
	{
		"name": "get_doctype_fields",
		"description": "Return the field definitions of a DocType so you know which fields exist before reading or writing records.",
		"input_schema": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string", "description": "Exact DocType name."}
			},
			"required": ["doctype"],
		},
	},
	{
		"name": "search_documents",
		"description": "Search records of a DocType by keyword and/or filters. Returns matching record names and requested fields.",
		"input_schema": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string", "description": "Exact DocType name."},
				"keyword": {"type": "string", "description": "Free text matched against the title and search fields."},
				"filters": {"type": "object", "description": "Frappe filter dict, e.g. {\"status\": \"Open\"}."},
				"fields": {"type": "array", "items": {"type": "string"}, "description": "Fields to return."},
				"limit": {"type": "integer", "description": "Maximum rows (capped at 50)."},
			},
			"required": ["doctype"],
		},
	},
	{
		"name": "get_document",
		"description": "Fetch a single record by its exact name.",
		"input_schema": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string", "description": "Exact DocType name."},
				"name": {"type": "string", "description": "Exact record name (ID)."},
			},
			"required": ["doctype", "name"],
		},
	},
	{
		"name": "count_documents",
		"description": "Count records of a DocType matching optional filters.",
		"input_schema": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string", "description": "Exact DocType name."},
				"filters": {"type": "object", "description": "Frappe filter dict."},
			},
			"required": ["doctype"],
		},
	},
	{
		"name": "create_document",
		"description": "Create a new record. Requires create permission on the DocType.",
		"input_schema": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string", "description": "Exact DocType name."},
				"data": {"type": "object", "description": "Field values for the new record."},
			},
			"required": ["doctype", "data"],
		},
	},
	{
		"name": "update_document",
		"description": "Update fields on an existing record. Requires write permission.",
		"input_schema": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string", "description": "Exact DocType name."},
				"name": {"type": "string", "description": "Exact record name (ID)."},
				"data": {"type": "object", "description": "Field values to change."},
			},
			"required": ["doctype", "name", "data"],
		},
	},
	{
		"name": "submit_document",
		"description": "Submit a submittable document. Requires submit permission.",
		"input_schema": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string", "description": "Exact DocType name."},
				"name": {"type": "string", "description": "Exact record name (ID)."},
			},
			"required": ["doctype", "name"],
		},
	},
	{
		"name": "cancel_document",
		"description": "Cancel a submitted document. Requires cancel permission.",
		"input_schema": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string", "description": "Exact DocType name."},
				"name": {"type": "string", "description": "Exact record name (ID)."},
			},
			"required": ["doctype", "name"],
		},
	},
	{
		"name": "run_report",
		"description": "Run a saved Report and return its columns and rows.",
		"input_schema": {
			"type": "object",
			"properties": {
				"report_name": {"type": "string", "description": "Exact Report name."},
				"filters": {"type": "object", "description": "Report filter values."},
			},
			"required": ["report_name"],
		},
	},
	{
		"name": "list_my_tasks",
		"description": "List ToDo tasks assigned to the current user.",
		"input_schema": {
			"type": "object",
			"properties": {
				"status": {"type": "string", "description": "Open, Closed, or Cancelled. Defaults to Open."}
			},
		},
	},
]


def get_tool_schemas(allowed: list[str] | None, provider: str) -> list[dict]:
	schemas = TOOL_SCHEMAS
	if allowed:
		allowed_set = set(allowed)
		schemas = [s for s in TOOL_SCHEMAS if s["name"] in allowed_set]
	if provider == "OpenAI":
		return [to_openai_schema(s) for s in schemas]
	return schemas


def to_openai_schema(schema: dict) -> dict:
	return {
		"type": "function",
		"function": {
			"name": schema["name"],
			"description": schema["description"],
			"parameters": schema["input_schema"],
		},
	}
