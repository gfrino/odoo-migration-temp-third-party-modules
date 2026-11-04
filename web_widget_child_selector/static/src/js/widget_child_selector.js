// Copyright 2019 Creu Blanca
// Copyright 2026 ticinoWEB
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import { effect, proxy, t, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import {
    Many2OneField, many2OneFieldProps, buildM2OFieldDescription,
} from "@web/views/fields/many2one/many2one_field";

export class FieldChildSelector extends Many2OneField {
    static template = "web_widget_child_selector.FieldChildSelector";
    props = useProps({
        ...many2OneFieldProps,
        childSelectionField: t.string().optional("display_name"),
    });

    setup() {
        this.orm = useService("orm");
        this.hierarchy = proxy({ parents: [], childs: [], loading: true, failed: false });
        this.requestNumber = 0;
        effect(() => {
            const value = this.props.record.data[this.props.name];
            this.loadHierarchy(value?.id || false);
        });
    }
    async loadHierarchy(id) {
        const requestNumber = ++this.requestNumber;
        this.hierarchy.loading = true;
        try {
            const data = await this.orm.call(this.props.record.fields[this.props.name].relation,
                "get_record_direct_childs_parents", [
                    id ? [id] : [],
                    { child_selection_field: this.props.childSelectionField },
                    this.m2oProps.domain(),
                ], { context: this.props.context });
            if (requestNumber === this.requestNumber) {
                this.hierarchy.parents = data.parents;
                this.hierarchy.childs = data.childs;
                this.hierarchy.failed = false;
            }
        } catch {
            if (requestNumber === this.requestNumber) {
                this.hierarchy.parents = [];
                this.hierarchy.childs = [];
                this.hierarchy.failed = true;
            }
        } finally {
            if (requestNumber === this.requestNumber) {
                this.hierarchy.loading = false;
            }
        }
    }
    select(value) {
        return this.props.record.update({
            [this.props.name]: value ? { id: value[0], display_name: value[1] } : false,
        });
    }
}
const description = buildM2OFieldDescription(FieldChildSelector);
registry.category("fields").add("child_selector", {
    ...description,
    extractProps: (staticInfo, dynamicInfo) => ({
        ...description.extractProps(staticInfo, dynamicInfo),
        childSelectionField: staticInfo.options.child_selection_field,
    }),
});
