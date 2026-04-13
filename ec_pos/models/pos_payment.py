# -*- encoding: utf-8 -*-
from odoo import models, api, fields
from bs4 import BeautifulSoup
import requests

class PosPayment(models.Model):
    _inherit = 'pos.payment'

    # @api.model_create_multi
    # def create(self, vals_list):
    #     res = super().create(vals_list)
        # for payment in res:
        #     payment.date = self.env['ec.tools'].get_date_now()
        # return res

    date = fields.Date(string='Fecha de pago', default=lambda self: self.env['ec.tools'].get_date_now())
    x_payment_reference = fields.Char(string='Referencia de Pago')
    lote_tc = fields.Char(string='Lote')
    auth_tc = fields.Char(string='Autorización')
