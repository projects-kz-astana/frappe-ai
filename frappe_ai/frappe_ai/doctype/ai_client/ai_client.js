// Copyright (c) 2026, Sambhav Saxena and contributors
// For license information, please see license.txt

frappe.ui.form.on("AI Client", {

	refresh(frm) {
		if (!frm.is_new() && frm.doc.organization && frm.doc.api_key) {
			fetch_and_set_models(frm);
		}
		if (!frm.is_new() && frm.doc.model) {
			add_test_button(frm);
		}
	},

	organization(frm) {
		frm.set_value("model", "");
		frm.set_df_property("model", "options", "");
		frm.refresh_field("model");

		// Reset org-specific generation fields when switching providers.
		frm.set_value("reasoning_effort", "");
		frm.set_value("thinking_level", "");
		frm.set_value("enable_thinking", 0);
		frm.set_value("thinking_budget", 0);
		frm.set_value("top_k", 0);

		if (frm.is_new()) {
			frappe.show_alert({
				message: __("Save the document after entering your API key to load available models."),
				indicator: "blue",
			});
			return;
		}

		if (!frm.doc.api_key) {
			frappe.show_alert({
				message: __("Enter an API key and save the document first."),
				indicator: "orange",
			});
			return;
		}

		fetch_and_set_models(frm);
	},

	after_save(frm) {
		if (frm.doc.organization && frm.doc.api_key) {
			fetch_and_set_models(frm);
		}
	},
});


function fetch_and_set_models(frm) {
	frappe.call({
		method: "frappe_ai.api.models.get_models_for_org",
		args: {
			organization: frm.doc.organization,
			docname: frm.doc.name,
		},
		freeze: true,
		freeze_message: __("Fetching models for {0}…", [frm.doc.organization]),
		callback(r) {
			if (r.message && r.message.length) {
				set_model_options(frm, r.message);
			} else {
				frappe.show_alert({
					message: __("No models returned for this API key."),
					indicator: "orange",
				});
			}
		},
	});
}


function set_model_options(frm, models) {
	const options = ["", ...models].join("\n");
	frm.set_df_property("model", "options", options);
	frm.refresh_field("model");
}


function add_test_button(frm) {
	frm.add_custom_button(__("Test"), function () {
		const d = new frappe.ui.Dialog({
			title: __("Test {0}", [frm.doc.name1 || frm.doc.name]),
			fields: [
				{
					fieldtype: "Small Text",
					fieldname: "system_prompt",
					label: __("System Prompt (optional)"),
					default: frm.doc.system_prompt || "",
				},
				{
					fieldtype: "Small Text",
					fieldname: "user_message",
					label: __("Your Message"),
					reqd: 1,
				},
			],
			primary_action_label: __("Send"),
			primary_action(values) {
				d.disable_primary_action();
				d.set_secondary_action_label(__("Waiting…"));

				frappe.call({
					method: "frappe_ai.api.chat.chat",
					args: {
						docname: frm.doc.name,
						user_message: values.user_message,
						system_prompt: values.system_prompt || null,
					},
					callback(r) {
						d.enable_primary_action();
						d.set_secondary_action_label(__("Close"));
						if (r.message) {
							const text = frappe.utils.escape_html(r.message.text || "");
							const model = r.message.model || frm.doc.model;
							const usage = r.message.usage || {};
							const tokens = (usage.input || usage.output)
								? `<small style="color:var(--text-muted)">↑ ${usage.input || 0} / ↓ ${usage.output || 0} tokens</small>`
								: "";

							frappe.msgprint({
								title: __("Response · {0}", [model]),
								message: `<pre style="white-space:pre-wrap;margin:0">${text}</pre>${tokens ? "<br>" + tokens : ""}`,
								indicator: "green",
							});
						}
					},
					error() {
						d.enable_primary_action();
						d.set_secondary_action_label(__("Close"));
					},
				});
			},
		});
		d.show();
	});
}
