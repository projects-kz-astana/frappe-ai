frappe.ui.form.on("Agent", {
	refresh(frm) {
		if (frm.doc.__islocal) return;

		frm.add_custom_button(__("Chat"), () => {
			if (!frm.doc.enabled) {
				frappe.msgprint(__("Enable this agent before chatting."));
				return;
			}
			const chat = new frappe.ui.AgentChat(frm.doc.name);
			chat.show();
		});
	},
});
