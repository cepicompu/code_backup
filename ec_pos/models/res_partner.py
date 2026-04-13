# -*- encoding: utf-8 -*-
from odoo import models, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def check_vat_pos(self, vat, partner_id=False):
        domain = [('vat', '=', vat)]
        if partner_id:
            domain.append(('id', '!=', partner_id))
        count = self.search_count(domain)
        return count > 0
