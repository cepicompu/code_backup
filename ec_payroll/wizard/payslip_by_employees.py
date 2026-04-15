# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api
import logging
_logger = logging.getLogger(__name__)


class HrPayslipEmployees(models.TransientModel):

    _inherit = 'hr.payslip.employees'

    date_start = fields.Date(string='Date From')
    date_end = fields.Date(string='Date To')


    def _get_available_contracts_domain(self):
        prun = self.env['hr.payslip.run'].browse(self.env.context.get('active_ids')[0]).structure_type_id.id
        srun = self.env['hr.payslip.run'].browse(self.env.context.get('active_ids')[0]).structure_id.id
        trun = self.env['hr.payslip.run'].browse(self.env.context.get('active_ids')[0]).type_slip_pay

        
        if trun == 'thirteenth':
            return [('contract_ids.state', 'in', ('open', 'close')), ('company_id', '=', self.env.company.id),('contract_ids.structure_type_id.id', '=', prun),
                    ('contract_ids.thirteenth_payment', '=', 'accumulated')]
        if trun=='fourteenth':
            return [('contract_ids.state', 'in', ('open', 'close')), ('company_id', '=', self.env.company.id),('contract_ids.structure_type_id.id', '=', prun),
                    ('contract_ids.fourteenth_payment', '=', 'accumulated')]

        return [('contract_ids.state', 'in', ['open']), ('company_id', '=', self.env.company.id),('contract_ids.structure_type_id.id', '=', prun),('contract_ids.struct_id.id', '=', srun)]

    
    @api.model
    def default_get(self, fields_list):
        values = super(HrPayslipEmployees, self).default_get(fields_list)
        prun = self.env['hr.payslip.run'].browse(self.env.context.get('active_ids')[0])
        values['date_start'] = prun.date_start
        values['date_end'] = prun.date_end
        values['structure_id'] = prun.structure_id.id
        return values
