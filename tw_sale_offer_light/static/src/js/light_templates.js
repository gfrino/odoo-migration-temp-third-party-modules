import { patch } from '@web/core/utils/patch';
import { SaleTemplateDropdown } from '@sale_management/views/components/template_dropdown';
import { SaleOrderLineOne2Many } from '@sale/js/sale_order_line_field/sale_order_line_field';

patch(SaleTemplateDropdown.prototype, {
    async onWillStart() {
        await super.onWillStart();
        const light = this.props.record?.data?.is_light_offer
            ?? this.action.currentAction?.context?.default_is_light_offer ?? false;
        this.state.quotationTemplates = await this.orm.searchRead(
            'sale.order.template',
            [['template_type', '=', 'quotation'], ['is_light_offer', '=', Boolean(light)]],
            ['id', 'name']
        );
    },
});

patch(SaleOrderLineOne2Many.prototype, {
    async loadSectionTemplates(companyId = this.props.record.data.company_id.id) {
        this.state.sectionTemplates = await this.orm.call(
            'sale.order.template', 'get_section_templates', [companyId],
            { context: { light_template_scope: Boolean(this.props.record.data.is_light_offer) } }
        );
    },
});
