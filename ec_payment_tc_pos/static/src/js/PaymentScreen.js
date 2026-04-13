odoo.define('ec_payment_tc_pos.PaymentScreenWidget', function(require){
    'use strict';

    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const { useListener } = require("@web/core/utils/hooks");
    const { PosGlobalState, Order, Orderline, Payment } = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');

    const PosCreditCardOrder = (Order) => class PosCreditCardOrder extends Order {
        constructor(obj, options) {
            super(...arguments);
            this.credit_card_authorization = this.credit_card_authorization || false;
            this.credit_card_lote = this.credit_card_lote || false;
            this.credit_card_reference = this.credit_card_reference || false;
        }

        export_as_JSON() {
            const json = super.export_as_JSON(...arguments);
            return json;
        }
        init_from_JSON(json) {
            super.init_from_JSON(...arguments);
        }

        get_auth() {
            return this.credit_card_authorization
        }
        set_auth(credit_card_authorization) {
            this.credit_card_authorization = credit_card_authorization;
        }

        get_lote() {
            return this.credit_card_lote
        }
        set_lote(credit_card_lote) {
            this.credit_card_lote = credit_card_lote;
        }

        get_ref() {
            return this.credit_card_reference
        }
        set_ref(credit_card_reference) {
            this.credit_card_reference = credit_card_reference;
        }

    }
    Registries.Model.extend(Order, PosCreditCardOrder);

    const PaymentScreenWidget = (PaymentScreen) =>
        class extends PaymentScreen {
//        constructor() {
//            super(...arguments);
//            useListener('cheque-bank', this.chequeBank);
//        }
            setup() {
                super.setup();
                useListener('credit-card', this.creditCard);
            }

            validateTC(){
                var self = this;
                var order = self.env.pos.get_order();
                var pass_validate_tc = true;
                // for (let line of this.paymentLines){
                //     if (line.payment_method.credit_card_information){
                //         if (!line.credit_card_authorization || !line.medianet_authorization){
                //             pass_validate_tc = false;
                //         }
                //     }
                // }
                return pass_validate_tc;
            }

            async validateOrder(isForceValidate) {
                var self = this;
                var pass_validate_tc = this.validateTC();
                // if (pass_validate_tc){
                //     super.validateOrder(isForceValidate);
                // }
                // else{
                //     return this.showPopup('ErrorPopup', {
                //         title: this.env._t('Error'),
                //         body: this.env._t('Debe llenar los datos de la tarjeta de credito'),
                //     });
                // }
            }

            async creditCard(event) {
                var self = this;
                const { cid } = event.detail;
                const line = this.paymentLines.find((line) => line.cid === cid);
                await this.showPopup('CreditCardInformationPopup', {
                    body: 'Tarjeta de Credito',
                    startingValue: self,
                    list: self.env.pos.bank,
                    title: this.env._t('Ingrese los datos de la tarjeta de credito'),
                });

            }

        }

    Registries.Component.extend(PaymentScreen, PaymentScreenWidget);

    const EcPaymentTc = (Payment) => class extends Payment {
        export_as_JSON() {
            var result = super.export_as_JSON();
            if (this.credit_card_authorization) {
                result.credit_card_authorization = this.credit_card_authorization;
                result.credit_card_lote = this.credit_card_lote;
                result.credit_card_reference = this.credit_card_reference;
            }
            return result;
        }
    }
    Registries.Model.extend(Payment, EcPaymentTc);

});
