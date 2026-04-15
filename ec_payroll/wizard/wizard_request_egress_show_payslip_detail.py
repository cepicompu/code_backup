# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api
import odoo.addons.decimal_precision as dp
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)


class WizardRequestEgressShowPayslipDetail(models.TransientModel):
    '''
    Asistente para solicitud de egreso
    '''
    _name = 'wizard.request.egress.show.payslip.detail'
    _description = 'Asistente para solicitud de egreso'

    line_ids = fields.One2many('wizard.request.egress.show.payslip.detail.line', 'wizard_id', string=u'Label', 
                               required=False, readonly=False, states={}, help=u"") 
    
    @api.model
    def default_get(self, fields_list):
        values = super(WizardRequestEgressShowPayslipDetail, self).default_get(fields_list)
        request_model = self.env['request.egress.detail']
        payslip_model = self.env['hr.payslip']
        request_line = request_model.browse(self.env.context.get('active_ids'))
        request_date = fields.Date.from_string(request_line.date)
        date_from = (request_date + relativedelta(day=1)).strftime(DF)
        date_to = (request_date + relativedelta(day=1, months=+1, days=-1)).strftime(DF)
        slip_lines  = payslip_model.get_payslip_lines_simulate(request_line.request_egress_id.employee_id.id, date_from, date_to)
        slip_lines_data = []
        for line in slip_lines:
            slip_lines_data.append((0, 0, line._convert_to_write({
                name: line[name] for name in line._cache}))) 
        values.update({
            'line_ids': slip_lines_data,
            })            
        return values
        

class WizardRequestEgressShowPayslipDetailLine(models.TransientModel):
    '''
    Asistente para solicitud de egreso
    '''
    _name = 'wizard.request.egress.show.payslip.detail.line'
    _description = 'Lineas Asistente para solicitud de egreso'

    wizard_id = fields.Many2one('wizard.request.egress.show.payslip.detail', u'ID', required=False, help=u"",)
    description = fields.Char(string=u'Descripción', index=True, required=False, readonly=False, states={}, help=u"")
   
    amount = fields.Float(u'Monto', digits_compute=dp.get_precision('Account'), readonly=False, required=False,
                          states={}, help=u"")
    
    transaction_id = fields.Many2one('hr.scheduled.transaction', string=u'Transacción Programada', ondelete="restrict") 
    category_transaction_id = fields.Many2one('hr.scheduled.transaction.category', string=u'Rubro Programado',
                                              store=True)
    date_from = fields.Date(string='Date From', store=True)
    date_to = fields.Date(string='Date To', store=True)
    name = fields.Char()
    code = fields.Char(help="The code that can be used in the salary rules")
    rate = fields.Float(string='Rate (%)', digits=dp.get_precision('Payroll Rate'), default=100.0)
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Rule', required=False, ondelete="restrict")    
    quantity = fields.Float(digits=dp.get_precision('Payroll'), default=1.0)
    total = fields.Float(compute='_compute_total', string='Total', digits=dp.get_precision('Payroll'), store=True)
