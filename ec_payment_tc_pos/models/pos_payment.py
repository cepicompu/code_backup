##############################################################################
#
#    Copyright (C) 2022-Present Speeduplight (<https://speeduplight.com>)
#
##############################################################################
from odoo import api, fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    credit_card_information = fields.Boolean(string="Credit Card Information", related="payment_method_id.credit_card_information")
    credit_card_authorization = fields.Char(string="Autorización")
    credit_card_lote = fields.Char(string="Lote")
    credit_card_reference = fields.Char(string="Referencia")
    type_net = fields.Selection([('medianet', 'Medianet'),
                                 ('datafast', 'Datafast'),
                                 ('austro', 'Austro')], string="Tipo de Red")
    state_conciliation_tc = fields.Selection([('conciliated', 'Conciliado'),
                                              ('not_conciliate', 'No Conciliado')],
                                             'Estado Regularización TC', required=False)
