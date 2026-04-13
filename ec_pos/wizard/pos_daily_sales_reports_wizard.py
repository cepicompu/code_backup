# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

class PosDailyReport(models.TransientModel):
    _inherit = 'pos.daily.sales.reports.wizard'

    def generate_report(self):
        if self.pos_session_id.config_id.blind_closure:
            if self.pos_session_id.state != 'closed':
                raise UserError(_('Debe cerrar la sesión antes de generar el reporte.'))
        res = super(PosDailyReport, self).generate_report()
        return res