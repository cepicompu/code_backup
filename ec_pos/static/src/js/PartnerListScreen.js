odoo.define('ec_pos.PartnerListScreen', function(require) {
    "use strict";

    const PartnerListScreen = require('point_of_sale.PartnerListScreen');
    const Registries = require('point_of_sale.Registries');


    const EcPartnerListScreen = PartnerListScreen => class extends PartnerListScreen {
        //@Override
        async getNewPartners() {
            var results = await super.getNewPartners();
            let domain = [];
            const limit = 30;
            if(this.state.query) {
                const search_fields = ["name", "parent_name", "phone_mobile_search", "email", 'vat'];
                domain = [
                    ...Array(search_fields.length - 1).fill('|'),
                    ...search_fields.map(field => [field, "ilike", this.state.query + "%"])
                ];
            }
            const result = await this.env.services.rpc(
                {
                    model: 'pos.session',
                    method: 'get_pos_ui_res_partner_by_params',
                    args: [
                        [odoo.pos_session_id],
                        {
                            domain,
                            limit: limit,
                            offset: this.state.currentOffset,
                        },
                    ],
                    context: this.env.session.user_context,
                },
                {
                    timeout: 3000,
                    shadow: true,
                }
            );
            return result;
        }
    };

    Registries.Component.extend(PartnerListScreen, EcPartnerListScreen);

    return PartnerListScreen;
});
