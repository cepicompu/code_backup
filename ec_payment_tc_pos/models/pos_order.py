##############################################################################
#
#    Copyright (C) 2022-Present Speeduplight (<https://speeduplight.com>)
#
##############################################################################
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _payment_fields(self, order, ui_paymentline):
        res = super(PosOrder, self)._payment_fields(order, ui_paymentline)
        payment_method = self.env['pos.payment.method'].browse(ui_paymentline['payment_method_id'])
        if payment_method.credit_card_information == True:
            res.update({'credit_card_authorization': ui_paymentline.get('credit_card_authorization'),
                        'credit_card_lote': ui_paymentline.get('credit_card_lote'),
                        'credit_card_reference': ui_paymentline.get('credit_card_reference'),
                        })
        return res

