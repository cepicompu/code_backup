odoo.define('ec_pos.PaymentScreen', function (require) {
    "use strict";

    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const Registries = require('point_of_sale.Registries');


    const PosDePaymentScreen = PaymentScreen => class extends PaymentScreen {
        async addNewPaymentLine({ detail: paymentMethod }) {
            const order = this.currentOrder;
            const orderLines = order.get_orderlines();

            // Logic to determine if we should revert prices
            const hasSurcharge = paymentMethod.x_surcharge_percentage > 0;
            const existingSurchargeLines = order.get_paymentlines().filter(l => l.payment_method.x_surcharge_percentage > 0);

            let shouldRevert = false;
            if (hasSurcharge) {
                // Always revert if adding a surcharge method (to recalculate from base)
                shouldRevert = true;
            } else {
                // If adding a non-surcharge method, only revert if NO surcharge payments exist
                if (existingSurchargeLines.length === 0) {
                    shouldRevert = true;
                }
            }

            // STEP 1: Revert prices to original if needed
            if (shouldRevert) {
                orderLines.forEach(line => {
                    if (line.price_before_surcharge !== undefined) {
                        line.set_unit_price(line.price_before_surcharge);
                        line.price_before_surcharge = undefined;
                    }
                });
            }

            // If we reverted prices, we might need to recalculate totals or just proceed.
            // Odoo's set_unit_price triggers recalculations.

            if (paymentMethod.x_surcharge_percentage) {
                // Show confirmation popup
                const { confirmed } = await this.showPopup('SurchargeSelectionPopup', {
                    title: this.env._t('Confirmar Recargo (' + paymentMethod.x_surcharge_percentage + '%)'),
                    lines: order.get_orderlines(), // Pass current lines (which are now reverted)
                    percentage: paymentMethod.x_surcharge_percentage,
                });

                if (confirmed) {
                    let totalPaymentAmount = 0;

                    // Update ALL lines
                    orderLines.forEach(line => {
                        const currentPrice = line.get_unit_price();
                        // Store original price before modification
                        line.price_before_surcharge = currentPrice;

                        const percentage = parseFloat(paymentMethod.x_surcharge_percentage);
                        const newPrice = currentPrice * (1 + (percentage / 100));

                        console.log('Updating line:', line.get_product().display_name, 'Old:', currentPrice, 'New:', newPrice);

                        // Update price
                        line.set_unit_price(newPrice);

                        // Accumulate total for this payment
                        totalPaymentAmount += line.get_price_with_tax();
                    });

                    // Proceed to add payment line
                    await super.addNewPaymentLine(...arguments);

                    // Update the last added payment line amount
                    const paymentLines = order.get_paymentlines();
                    if (paymentLines.length > 0) {
                        const lastLine = paymentLines[paymentLines.length - 1];
                        if (lastLine.payment_method.id === paymentMethod.id) {
                            lastLine.set_amount(totalPaymentAmount);
                        }
                    }
                } else {
                    // User cancelled. 
                    // If we reverted prices at the start, they remain reverted. 
                    // This is probably correct behavior: if I click "Card", then Cancel, I expect to be back to normal state?
                    // Or should I revert back to "Card" state if I was already there? 
                    // The user said "siempre que de click en tarjeta deben ponerse el valor original".
                    // So reverting is fine.
                    return;
                }
            } else {
                // For non-surcharge methods (e.g. Cash), we already reverted prices at Step 1.
                // So we just proceed to add the payment line with the original prices.
                return super.addNewPaymentLine(...arguments);
            }
        }


        async _isOrderValid(isForceValidate) {
            // Override to remove strict address validation for ship later
            if (this.currentOrder.get_orderlines().length === 0 && this.currentOrder.is_to_invoice()) {
                this.showPopup('ErrorPopup', {
                    title: this.env._t('Empty Order'),
                    body: this.env._t(
                        'There must be at least one product in your order before it can be validated and invoiced.'
                    ),
                });
                return false;
            }

            if (this.currentOrder.electronic_payment_in_progress()) {
                this.showPopup('ErrorPopup', {
                    title: this.env._t('Pending Electronic Payments'),
                    body: this.env._t(
                        'There is at least one pending electronic payment.\n' +
                        'Please finish the payment with the terminal or ' +
                        'cancel it then remove the payment line.'
                    ),
                });
                return false;
            }

            const splitPayments = this.paymentLines.filter(payment => payment.payment_method.split_transactions)
            if (splitPayments.length && !this.currentOrder.get_partner()) {
                const paymentMethod = splitPayments[0].payment_method
                const { confirmed } = await this.showPopup('ConfirmPopup', {
                    title: this.env._t('Customer Required'),
                    body: _.str.sprintf(this.env._t('Customer is required for %s payment method.'), paymentMethod.name),
                });
                if (confirmed) {
                    this.selectPartner();
                }
                return false;
            }

            if ((this.currentOrder.is_to_invoice() || this.currentOrder.is_to_ship()) && !this.currentOrder.get_partner()) {
                const { confirmed } = await this.showPopup('ConfirmPopup', {
                    title: this.env._t('Please select the Customer'),
                    body: this.env._t(
                        'You need to select the customer before you can invoice or ship an order.'
                    ),
                });
                if (confirmed) {
                    this.selectPartner();
                }
                return false;
            }

            // REMOVED STRICT ADDRESS CHECK FROM ORIGINAL ODOO CODE
            // let partner = this.currentOrder.get_partner()
            // if (this.currentOrder.is_to_ship() && !(partner.name && partner.street && partner.city && partner.country_id)) {
            //     this.showPopup('ErrorPopup', {
            //         title: this.env._t('Incorrect address for shipping'),
            //         body: this.env._t('The selected customer needs an address.'),
            //     });
            //     return false;
            // }

            if (this.currentOrder.get_total_with_tax() != 0 && this.currentOrder.get_paymentlines().length === 0) {
                this.showNotification(this.env._t('Select a payment method to validate the order.'));
                return false;
            }

            if (!this.currentOrder.is_paid() || this.invoicing) {
                return false;
            }

            if (this.currentOrder.has_not_valid_rounding()) {
                var line = this.currentOrder.has_not_valid_rounding();
                this.showPopup('ErrorPopup', {
                    title: this.env._t('Incorrect rounding'),
                    body: this.env._t(
                        'You have to round your payments lines.' + line.amount + ' is not rounded.'
                    ),
                });
                return false;
            }

            // The exact amount must be paid if there is no cash payment method defined.
            if (
                Math.abs(
                    this.currentOrder.get_total_with_tax() - this.currentOrder.get_total_paid() + this.currentOrder.get_rounding_applied()
                ) > 0.00001
            ) {
                var cash = false;
                for (var i = 0; i < this.env.pos.payment_methods.length; i++) {
                    cash = cash || this.env.pos.payment_methods[i].is_cash_count;
                }
                if (!cash) {
                    this.showPopup('ErrorPopup', {
                        title: this.env._t('Cannot return change without a cash payment method'),
                        body: this.env._t(
                            'There is no cash payment method available in this point of sale to handle the change.\n\n Please pay the exact amount or add a cash payment method in the point of sale configuration'
                        ),
                    });
                    return false;
                }
            }

            // if the change is too large, it's probably an input error, make the user confirm.
            if (
                !isForceValidate &&
                this.currentOrder.get_total_with_tax() > 0 &&
                this.currentOrder.get_total_with_tax() * 1000 < this.currentOrder.get_total_paid()
            ) {
                this.showPopup('ConfirmPopup', {
                    title: this.env._t('Please Confirm Large Amount'),
                    body:
                        this.env._t('Are you sure that the customer wants to  pay') +
                        ' ' +
                        this.env.pos.format_currency(this.currentOrder.get_total_paid()) +
                        ' ' +
                        this.env._t('for an order of') +
                        ' ' +
                        this.env.pos.format_currency(this.currentOrder.get_total_with_tax()) +
                        ' ' +
                        this.env._t('? Clicking "Confirm" will validate the payment.'),
                }).then(({ confirmed }) => {
                    if (confirmed) this.validateOrder(true);
                });
                return false;
            }

            if (!this.currentOrder._isValidEmptyOrder()) return false;

            return true;
        }

        async printProforma() {
            const order = this.currentOrder;
            const partner = order.get_partner();
            if (!partner) {
                return this.showPopup('ErrorPopup', {
                    title: this.env._t('Error'),
                    body: this.env._t('Debe seleccionar un cliente para imprimir proforma.'),
                });
            }

            // Prepare lines
            const lines = order.get_orderlines().map(line => ({
                product_id: line.get_product().id,
                qty: line.get_quantity(),
                price_unit: line.get_unit_price(),
                discount: line.get_discount(),
            }));

            const orderData = {
                partner_id: partner.id,
                lines: lines,
            };

            try {
                // Call backend to create Sale Order
                // Using this.rpc if available, or rpc.query
                // PaymentScreen inherits Registry > Component, usually has rpc in env or this.rpc
                // Checking previous code... pos_models uses require('web.rpc')
                // PaymentScreen is a component.

                const result = await this.rpc({
                    model: 'pos.order',
                    method: 'create_sale_order_from_pos_ui',
                    args: [orderData],
                });

                if (result.ok) {
                    order.backend_proforma_name = result.name;
                    order.is_proforma = true;
                    await this.showScreen('ReprintReceiptScreen', { order: order });
                } else {
                    return this.showPopup('ErrorPopup', {
                        title: this.env._t('Error al Crear Proforma'),
                        body: result.error || 'Unknown error',
                    });
                }
            } catch (error) {
                return this.showPopup('ErrorPopup', {
                    title: this.env._t('Error de Conexión'),
                    body: this.env._t('No se pudo contactar con el servidor para crear la proforma.'),
                });
            }
        }

        //@Override
        async validateOrder(isForceValidate) {
            this.currentOrder.is_proforma = false;
            const order = this.currentOrder;
            const change = order.get_change();
            var pass_validation = true;
            if (order.get_total_with_tax() > Number(this.env.pos.config.allowed_value_for_no_client)) {
                if (order.get_partner().vat == '9999999999999') {
                    pass_validation = false;
                    return this.showPopup('ErrorPopup', {
                        title: this.env._t('Error'),
                        body: this.env._t('No puede escoger consumidor final para una factura mayor $' + this.env.pos.config.allowed_value_for_no_client),
                    });
                }
            }
            if (pass_validation) {
                // Validate Payment References
                const lines = order.get_paymentlines();
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i];
                    if (line.payment_method.x_ask_reference && !line.x_payment_reference) {
                        return this.showPopup('ErrorPopup', {
                            title: this.env._t('Referencia Faltante'),
                            body: this.env._t('Por favor ingrese la referencia de pago para: ' + line.payment_method.name),
                        });
                    }
                }
                await super.validateOrder(...arguments);
            }
            // if (this.env.pos.isCountryGermanyAndFiskaly()) {
            //     if (this.validateOrderFree) {
            //         this.validateOrderFree = false;
            //         try {
            //             await super.validateOrder(...arguments);
            //         } finally {
            //             this.validateOrderFree = true;
            //         }
            //     }
            // } else {
            //     await super.validateOrder(...arguments);
            // }
        }
    };

    Registries.Component.extend(PaymentScreen, PosDePaymentScreen);

    return PaymentScreen;
});
