

odoo.define('ec_pos.OrderSummary', function (require) {
    "use strict";

    const OrderSummary = require('point_of_sale.OrderSummary');
    const Registries = require('point_of_sale.Registries');
    const { float_is_zero } = require('web.utils');

    const EcOrderSummary = OrderSummary => class extends OrderSummary {
        //@Override
        getTax() {
            var result = super.getTax(...arguments);
            let taxAmount0 = 0;
            let taxAmount12 = 0;
            for (let line of this.props.order.get_orderlines()) {
                const tax_id = this.env.pos.taxes_by_id[line.product.taxes_id]
                if (tax_id) {
                    if (tax_id.amount == 0) {
                        taxAmount0 += line.price * line.quantity;
                    }
                    if (tax_id.amount == 12) {
                        taxAmount12 += line.price * line.quantity;
                    }
                }
                else {
                    taxAmount0 += line.price;
                }
            }
            result.displayAmount0 = this.env.pos.format_currency(taxAmount0);
            result.displayAmount12 = this.env.pos.format_currency(taxAmount12);
            return result
        }
    };

    Registries.Component.extend(OrderSummary, EcOrderSummary);

    return OrderSummary;
});
