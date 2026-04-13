odoo.define('ec_payment_medianet_pos.PaymentScreenWidget', function(require) {
    'use strict';

    var rpc = require('web.rpc');
    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const {useListener} = require("@web/core/utils/hooks");
    const {PosGlobalState, Order, Orderline, Payment} = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');

    const PosMedianetOrder = (Order) => class PosMedianetOrder extends Order {
        constructor(obj, options) {
            super(...arguments);
            this.medianet_authorization = this.medianet_authorization || false;
            this.medianet_lote = this.medianet_lote || false;
            this.medianet_reference = this.medianet_reference || false;
        }

        export_for_printing() {
            var self = this;
            var result = super.export_for_printing(...arguments);
            if (this.data_medianet){
                result.medianet_receipt = true;
                result.data_medianet = this.data_medianet;
            }
            return result;
        }

        export_as_JSON() {
            const json = super.export_as_JSON(...arguments);
            return json;
        }

        init_from_JSON(json) {
            super.init_from_JSON(...arguments);
        }

    }
    Registries.Model.extend(Order, PosMedianetOrder);

    const EcPayment = (Payment) => class extends Payment {
        export_as_JSON() {
            var result = super.export_as_JSON();
            if (this.trama) {
                result.trama_medianet = this.trama;
                result.credit_card_authorization = this.medianet_authorization;
                result.credit_card_lote = this.medianet_lote;
                result.credit_card_reference = this.medianet_reference;
                result.have_deferred = this.have_deferred;
                result.month_interest = this.month_interest;
                result.month_interest_free = this.month_interest_free;
                result.with_interest = this.with_interest;
            }
            return result;
        }
    }
    Registries.Model.extend(Payment, EcPayment);

    const PaymentScreenWidget = (PaymentScreen) => class extends PaymentScreen {
        setup() {
            super.setup();
            useListener('medianet', this.medianet);
        }
        validateTC(){
            var self = this;
            var order = self.env.pos.get_order();
            var pass_validate_tc = true;
            // for (let line of this.paymentLines){
            //     if (line.payment_method.credit_card_information || line.payment_method.payment_medianet){
            //         if (!line.credit_card_authorization){
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
        async medianet(event) {
            var self = this;
            const {cid} = event.detail;
            const line = this.paymentLines.find((line) => line.cid === cid);
            await this.showPopup('MedianetInformationPopup', {
                body: 'Portal Medianet',
                startingValue: self,
                interes: self.env.pos.interes,
                title: this.env._t('Ingrese los datos de la tarjeta de credito'),
            });

        }

    }
    Registries.Component.extend(PaymentScreen, PaymentScreenWidget);

    const EcPosMedianetGlobalState = (PosGlobalState) => class EcPosMedianetGlobalState extends PosGlobalState {

        async _processData(loadedData) {
            await super._processData(...arguments);
            this.interes = loadedData['res.bank'];
        }

        _flush_orders(orders, options) {
            var self = this;
            var result, data
            result = data = super._flush_orders(...arguments);
            _.each(orders,function(order){
                if (order.data.to_invoice)
                    data.then(function(order_server_id){
                        rpc.query({
                            model: 'pos.order',
                            method: 'get_info_medianet',
                            args:[order_server_id]
                        }).then(function(result_dict){
                            if (result_dict.data_medianet){
                                self.get_order().data_medianet = result_dict.data_medianet
                            }
                        }).catch(function(error){
                            return result
                        })
                    })
            })
            return result
        }
    }
    Registries.Model.extend(PosGlobalState, EcPosMedianetGlobalState);
});



