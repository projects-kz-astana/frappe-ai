frappe.ui.form.on("RAG Data Source", {
	refresh(frm) {
		if (frm.doc.__islocal) return;

		frm.add_custom_button(__("Index Now"), () => {
			frappe.confirm(
				__("Queue an indexing job for <b>{0}</b>?", [frm.doc.name]),
				() => {
					frappe.call({
						method: "frappe_ai.rag.indexing.enqueue_indexing",
						args: { data_source_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Queuing indexing job…"),
						callback(r) {
							if (r.message) {
								frappe.show_alert({
									message: __("Job created: {0}", [r.message]),
									indicator: "green",
								});
							}
						},
					});
				}
			);
		}, __("RAG"));

		frm.add_custom_button(__("Ask"), () => _open_ask_dialog(frm), __("RAG"));
	},
});

function _open_ask_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Ask {0}", [frm.doc.name]),
		fields: [
			{
				fieldname: "question",
				fieldtype: "Small Text",
				label: __("Question"),
				reqd: 1,
			},
			{
				fieldname: "answer_section",
				fieldtype: "Section Break",
				label: __("Answer"),
				hidden: 1,
			},
			{
				fieldname: "answer",
				fieldtype: "Long Text",
				label: __("Answer"),
				read_only: 1,
				hidden: 1,
			},
		],
		primary_action_label: __("Ask"),
		primary_action(values) {
			if (!values.question) return;

			d.set_df_property("answer_section", "hidden", 1);
			d.set_df_property("answer", "hidden", 1);
			d.disable_primary_action();
			d.set_title(__("Thinking…"));

			frappe.call({
				method: "frappe_ai.rag.query.query",
				args: {
					question: values.question,
					data_source_name: frm.doc.name,
				},
				callback(r) {
					d.enable_primary_action();
					d.set_title(__("Ask {0}", [frm.doc.name]));

					if (r.message && r.message.error) {
						frappe.msgprint({ message: r.message.error, indicator: "red" });
						return;
					}

					if (r.message && r.message.answer) {
						d.set_value("answer", r.message.answer);
						d.set_df_property("answer_section", "hidden", 0);
						d.set_df_property("answer", "hidden", 0);
					}
				},
			});
		},
	});

	d.show();
}
