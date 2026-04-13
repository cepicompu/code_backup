odoo.define('ec_pos.SurchargeSelectionPopup', function (require) {
    'use strict';

    const AbstractAwaitablePopup = require('point_of_sale.AbstractAwaitablePopup');
    const Registries = require('point_of_sale.Registries');
    const { useState } = owl;

    class SurchargeSelectionPopup extends AbstractAwaitablePopup {
        constructor() {
            super(...arguments);
            const percentage = parseFloat(this.props.percentage) || 0;
            this.state = useState({
                lines: this.props.lines.map(line => {
                    const price = line.get_unit_price();
                    const newPrice = price * (1 + percentage / 100);
                    return {
                        id: line.id,
                        product_name: line.get_product().display_name,
                        price: price,
                        new_price: newPrice,
                        quantity: line.get_quantity(),
                    };
                }),
            });
        }
    }

    SurchargeSelectionPopup.template = 'SurchargeSelectionPopup';
    SurchargeSelectionPopup.defaultProps = {
        cancelText: 'Cancelar',
        confirmText: 'Confirmar',
        title: 'Seleccione ítems para recargo',
        body: '',
    };

    Registries.Component.add(SurchargeSelectionPopup);

    return SurchargeSelectionPopup;
});
