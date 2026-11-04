// Copyright 2016 Camptocamp SA
// Copyright 2026 ticinoWEB
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

patch(FormController.prototype, {
    async onRootLoaded() {
        await super.onRootLoaded(...arguments);
        const record = this.model.root;
        if (!record.resId) {
            return;
        }
        let allowed = false;
        try {
            const access = await this.orm.call(record.resModel, "check_access_rule_all", [
                [record.resId], ["write"],
            ], { context: record.context });
            allowed = !!access.write;
        } finally {
            if (record === this.model.root) {
                this.canEdit = this.archInfo.activeActions.edit && !this.props.preventEdit && allowed;
                if (!this.canEdit) {
                    // Inside the root-loading hook: the public switchMode would wait
                    // on the same model mutex and deadlock.
                    record._switchMode("readonly");
                } else if (!this.props.readonly) {
                    record._switchMode("edit");
                }
            }
        }
    },
});
