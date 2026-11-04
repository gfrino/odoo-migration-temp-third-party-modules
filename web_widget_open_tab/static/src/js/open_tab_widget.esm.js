// Copyright 2023 Quartile Limited
// Copyright 2026 ticinoWEB
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import { Component, t, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class OpenTabWidget extends Component {
    static template = "web_widget_open_tab.openTab";
    props = useProps({ ...standardFieldProps, title: t.string().optional() });

    openNewTab(event) {
        event.stopPropagation();
    }
    get reference() {
        return `/odoo/${encodeURIComponent(this.props.record.resModel)}/${this.props.record.resId}`;
    }
}
export const openTabWidget = {
    component: OpenTabWidget,
    displayName: _t("Open Tab"),
    supportedTypes: ["integer"],
    extractProps: () => ({ title: _t("Open in a new tab") }),
};
registry.category("fields").add("open_tab", openTabWidget);
