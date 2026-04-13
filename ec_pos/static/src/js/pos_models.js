odoo.define('ec_pos.pos_models', function (require) {
    "use strict";



    var { PosGlobalState, Order, Payment, Orderline } = require('point_of_sale.models');
    var rpc = require('web.rpc');
    const { _t } = require('web.core');
    const Registries = require('point_of_sale.Registries');
    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const { Gui } = require('point_of_sale.Gui');
    var field_utils = require('web.field_utils');

    const PosSAPaymentScreen = PaymentScreen => class extends PaymentScreen {
        //@Override
        toggleIsToInvoice() {

            if (this.env.pos.config.to_invoice)
                if (this.currentOrder.get_total_with_tax() > Number(this.env.pos.config.allowed_value_for_no_invoice)) {
                    return this.showPopup('ErrorPopup', {
                        title: _t('No puede cambiar la configuración..!!'),
                    });
                }
            return super.toggleIsToInvoice(...arguments);
        }
    };

    Registries.Component.extend(PaymentScreen, PosSAPaymentScreen);

    const EcPosGlobalState = (PosGlobalState) => class EcPosGlobalState extends PosGlobalState {
        async _processData(loadedData) {
            await super._processData(...arguments);
            this.l10n_latam_identification_types = loadedData['l10n_latam.identification.type'];
            this.res_citys = loadedData['res.city'];

            // Real-time Note Updates
            this.env.services.bus_service.addChannel('pos_product_sync');
            this.env.services.bus_service.addEventListener('notification', this._onProductNotification.bind(this));
        }

        _onProductNotification({ detail: notifications }) {
            for (const { payload, type } of notifications) {
                if (type === 'product_note_update') {
                    const product = this.db.get_product_by_id(payload.id);
                    if (product) {
                        product.x_pos_note = payload.x_pos_note;
                        // Trigger UI update if necessary (e.g. if info popup is open)
                        // This usually happens automatically via reactivity if observing the product
                    }
                }
            }
        }
    }
    Registries.Model.extend(PosGlobalState, EcPosGlobalState);


    const PosModel = (PosGlobalState) => class PosModel extends PosGlobalState {
        constructor(obj) {
            super(obj);
        }
        add_new_order() {
            const order = super.add_new_order();
            if (this.config.to_invoice) {
                order.to_invoice = this.config.to_invoice;
            }
            order.to_ship = this.config.ship_later_default_value;
            return order;
        }
        _flush_orders(orders, options) {
            var self = this;
            var result, data
            result = data = super._flush_orders(...arguments);
            _.each(orders, function (order) {
                if (order.data.to_invoice)
                    data.then(function (order_server_id) {
                        rpc.query({
                            model: 'pos.order',
                            method: 'get_info_invoice',
                            args: [order_server_id]
                        }).then(function (result_dict) {
                            self.get_order().invoice_number = result_dict.invoice_number[0]
                            self.get_order().invoice_xml_key = result_dict.invoice_xml_key
                            self.get_order().sale_shop_street = result_dict.sale_shop_street
                            self.get_order().sale_shop_phone = result_dict.sale_shop_phone
                            self.get_order().sale_shop_detail = result_dict.sale_shop_detail
                            self.get_order().backend_name = result_dict.backend_name
                            self.get_order().picking_name = result_dict.picking_name
                        }).catch(function (error) {
                            return result
                        })
                    })
            })
            return result
        }
    }
    Registries.Model.extend(PosGlobalState, PosModel);

    const EcOrder = (Order) => class EcOrder extends Order {
        export_for_printing() {
            var self = this;
            var result = super.export_for_printing(...arguments);
            var discount_without_tax = 0;
            for (var line in result.orderlines) {
                discount_without_tax += ((result.orderlines[line].fixed_lst_price * result.orderlines[line].quantity) * result.orderlines[line].discount) / 100;
            }
            result.discount_without_tax = discount_without_tax;
            if (self.invoice_number) {
                result.invoice_number = self.invoice_number;
                result.invoice_xml_key = self.invoice_xml_key;
                result.sale_shop_street = self.sale_shop_street;
                result.sale_shop_detail = self.sale_shop_detail;
                result.sale_shop_phone = self.sale_shop_phone;
                result.backend_name = self.backend_name;
                result.picking_name = self.picking_name;
            }
            result.company.business_name = false;
            if (self.pos.company.business_name) {
                result.company.business_name = self.pos.company.business_name;
            }
            if (self.is_proforma) {
                result.is_proforma = true;
                if (self.backend_proforma_name) {
                    result.backend_proforma_name = self.backend_proforma_name;
                }
            }
            return result;
        }
        init_from_JSON(json) {
            super.init_from_JSON(...arguments);
            if (this.pos.config.to_invoice) {
                this.to_invoice = json.to_invoice = this.pos.config.to_invoice;
            }
            this.to_ship = this.pos.config.ship_later_default_value;
        }

        set_pricelist(pricelist) {
            var self = this;
            this.pricelist = pricelist;

            // Force reset manually set price flag to ensure prices update when pricelist changes.
            // This is necessary because items loaded from Budgets/Orders are treated as manually priced.
            const lines = this.get_orderlines();
            for (const line of lines) {
                line.price_manually_set = false;
                line.price_automatically_set = false;

                // Manually recompute to ensure it happens
                var quantity = line.get_quantity();
                var price_extra = line.get_price_extra();
                var computed_price = line.product.get_price(self.pricelist, quantity, price_extra);

                line.set_unit_price(computed_price);
                self.fix_tax_included_price(line);
            }
            // We call super just in case, though we did the work. 
            // The super implementation filters lines that are not manually blocked, 
            // since we unblocked them, it would redo it, but that's safe.
            super.set_pricelist(...arguments);
        }
    }
    Registries.Model.extend(Order, EcOrder);

    const EcOrderline = (Orderline) => class EcOrderline extends Orderline {
        set_quantity(quantity, keep_price) {
            if (quantity === 'remove') {
                return super.set_quantity(...arguments);
            }

            var quant = typeof (quantity) === 'number' ? quantity : (field_utils.parse.float('' + (quantity ? quantity : 0)));

            // Check if stock is available
            if (this.product.warehouse_info && this.product.warehouse_info.length > 0) {
                if (quant > this.product.warehouse_info[0].quantity) {
                    Gui.showPopup('ErrorPopup', {
                        title: _t('Stock Insuficiente'),
                        body: _t('El producto ' + this.product.display_name + ' tiene un stock de '
                            + this.product.warehouse_info[0].quantity + ' y estas intentando agregar ' + quant + '.'),
                    });
                    // Revert to old quantity if possible, or just reject
                    // As set_quantity can be used to set to new value, we just don't allow setting it
                    if (this.quantity) {
                        // Prevent infinite loop if already at limit somehow
                        if (this.quantity > this.product.warehouse_info[0].quantity) {
                            super.set_quantity(this.product.warehouse_info[0].quantity, keep_price);
                        }
                    } else {
                        super.set_quantity(0, keep_price);
                    }
                    return false;
                }
            }

            return super.set_quantity(...arguments);
        }
    };
    Registries.Model.extend(Orderline, EcOrderline);

    const EcPayment = (Payment) => class EcPayment extends Payment {
        constructor(obj, options) {
            super(obj, options);
            this.x_payment_reference = this.x_payment_reference || "";
            this.lote_tc = this.lote_tc || "";
            this.auth_tc = this.auth_tc || "";
        }
        //@override
        export_as_JSON() {
            const json = super.export_as_JSON(...arguments);
            json.x_payment_reference = this.x_payment_reference;
            json.lote_tc = this.lote_tc;
            json.auth_tc = this.auth_tc;
            return json;
        }
        //@override
        init_from_JSON(json) {
            if (!this.pos.payment_methods_by_id[json.payment_method_id]) {
                const errMsg = `Falta el Método de Pago con ID: ${json.payment_method_id} en esta caja. Por favor, devuélvalo a la caja en Odoo o borre la caché del navegador.`;
                console.error("🚨 Error POS:", errMsg, "Datos corruptos:", json);
                throw new Error(errMsg);
            }
            super.init_from_JSON(...arguments);
            this.x_payment_reference = json.x_payment_reference;
            this.lote_tc = json.lote_tc;
            this.auth_tc = json.auth_tc;
        }
        set_payment_reference(reference) {
            this.x_payment_reference = reference;
        }
        get_payment_reference() {
            return this.x_payment_reference;
        }
        set_lote_tc(lote) {
            this.lote_tc = lote;
        }
        get_lote_tc() {
            return this.lote_tc;
        }
        set_auth_tc(auth) {
            this.auth_tc = auth;
        }
        get_auth_tc() {
            return this.auth_tc;
        }
    }
    Registries.Model.extend(Payment, EcPayment);

});