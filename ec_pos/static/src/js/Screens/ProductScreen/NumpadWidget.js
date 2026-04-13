odoo.define('ec_pos.NumpadWidget', function (require) {
    'use strict';

    const NumpadWidget = require('point_of_sale.NumpadWidget');
    const Registries = require('point_of_sale.Registries');

    const EcNumpadWidget = (NumpadWidget) => class extends NumpadWidget {
        get hasPriceControlRights() {
            if (this.env.pos.config.restrict_price_control) {
                return false;
            }
            return super.hasPriceControlRights;
        }
    };

    Registries.Component.extend(NumpadWidget, EcNumpadWidget);

    return NumpadWidget;
});
