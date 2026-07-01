import frappe


def boot_session(bootinfo) -> None:
    try:
        from frappe_ai.clients import initialize_all_ai_clients
        initialize_all_ai_clients()
    except Exception:
        frappe.log_error("Frappe AI: Failed to initialize AI Clients on boot. Check the error log for details.", frappe.get_traceback())
