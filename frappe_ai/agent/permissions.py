import frappe


def assert_can_read(doctype: str, docname: str | None = None) -> None:
	if not frappe.has_permission(doctype, "read", docname):
		frappe.throw(
			f"Not permitted to read {doctype} {docname or ''}".strip(),
			frappe.PermissionError,
		)


def assert_can_create(doctype: str) -> None:
	if not frappe.has_permission(doctype, "create"):
		frappe.throw(f"Not permitted to create {doctype}", frappe.PermissionError)


def assert_can_write(doctype: str, docname: str | None = None) -> None:
	ptype = "create" if not docname else "write"
	if not frappe.has_permission(doctype, ptype, docname):
		frappe.throw(
			f"Not permitted to {ptype} {doctype} {docname or ''}".strip(),
			frappe.PermissionError,
		)


def assert_can_submit(doctype: str, docname: str) -> None:
	if not frappe.has_permission(doctype, "submit", docname):
		frappe.throw(
			f"Not permitted to submit {doctype} {docname}", frappe.PermissionError
		)


def assert_can_cancel(doctype: str, docname: str) -> None:
	if not frappe.has_permission(doctype, "cancel", docname):
		frappe.throw(
			f"Not permitted to cancel {doctype} {docname}", frappe.PermissionError
		)
