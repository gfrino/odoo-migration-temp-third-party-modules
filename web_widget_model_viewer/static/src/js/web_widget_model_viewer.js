// Copyright 2020 TAKOBI, Openindustry.it
// Copyright 2026 ticinoWEB
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import { onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { BinaryField, binaryField } from "@web/views/fields/binary/binary_field";

export class FieldBinaryModelViewer extends BinaryField {
    static template = "web_widget_model_viewer.FieldBinaryModelViewer";
    setup() {
        super.setup();
        onMounted(() => {
            loadJS("/web_widget_model_viewer/static/lib/model-viewer.min.js", { type: "module" })
                .catch(() => this.notification.add(_t("The 3D viewer could not be loaded."), { type: "warning" }));
        });
    }
    get modelURL() {
        const value = this.props.record.data[this.props.name];
        if (!value) {
            return "";
        }
        if (value.content) {
            return `data:model/gltf-binary;base64,${value.content}`;
        }
        if (this.props.record.resId) {
            const query = new URLSearchParams({
                model: this.props.record.resModel, id: this.props.record.resId,
                field: this.props.name,
            });
            return `/web/content?${query}`;
        }
        return "";
    }
    async fullscreen(event) {
        const viewer = event.currentTarget.parentElement.querySelector("model-viewer");
        if (document.fullscreenElement) {
            await document.exitFullscreen();
        } else if (viewer?.requestFullscreen) {
            await viewer.requestFullscreen();
        }
    }
}
registry.category("fields").add("model_viewer", {
    ...binaryField, component: FieldBinaryModelViewer,
    extractProps: (staticInfo, dynamicInfo) => ({
        ...binaryField.extractProps(staticInfo, dynamicInfo),
        acceptedFileExtensions: ".glb,.gltf",
    }),
});
