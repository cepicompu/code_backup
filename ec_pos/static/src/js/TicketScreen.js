odoo.define('ec_pos.TicketScreen', function(require) {
    "use strict";

    const TicketScreen = require('point_of_sale.TicketScreen');
    const Registries = require('point_of_sale.Registries')
    const { useState } = owl;


    const PosTicketScreen = (TicketScreen) =>
        class extends TicketScreen {
            async _onDoRefund() {
                const order = this.getSelectedSyncedOrder();
                if (order.get_partner().vat == '9999999999999'){
                    return this.showPopup('ErrorPopup', {
                        title: this.env._t('Error'),
                        body: this.env._t('No puede escoger consumidor final para realizar una devolución'),
                    });
                }
                else {
                    await super._onDoRefund();
                }
            }

        }

    Registries.Component.extend(TicketScreen, PosTicketScreen);

    return TicketScreen;
});