# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)


class WizardPayBatchSlip(models.TransientModel):
    '''
    Asistente para pago de Lotes de Nominas
    '''

    _name = 'wizard.pay.batch.slip'
    _description = 'Asistente para pago de Lotes de Nominas'

    date = fields.Date(string=u'Fecha de Pago', required=True)
    journal_id = fields.Many2one('account.journal', string=u'Forma de Pago', required=True)
    employee_ids = fields.Many2many('hr.employee', string='Empleados')
    ref = fields.Char(string='Referencia')
    bank_reference = fields.Char(string='Referencia Bancaria')
    journal_type = fields.Selection(related='journal_id.type', store=True, string='Journal Type')

    @api.depends('journal_id')
    def _compute_payment_method_line_fields(self):
        for pay in self:
            pay.available_payment_method_line_ids = pay.journal_id._get_available_payment_method_lines('outbound')

    available_payment_method_line_ids = fields.Many2many('account.payment.method.line',
                                                         compute='_compute_payment_method_line_fields')

    payment_method_line_id = fields.Many2one(
        'account.payment.method.line',
        string='Método de Pago',
        required=True,
    )

    @api.model
    def default_get(self, fields_list):
        batch = self.env['hr.payslip.run'].browse(self.env.context.get('active_ids', [])[0])
        values = super(WizardPayBatchSlip, self).default_get(fields_list)
        values['date'] = batch.date_end
        return values


    def action_pay_and_confirm(self):
        payment_ids = self._action_pay()
        payment_ids.action_post()
        util_model = self.env['ecua.utils']
        ctx = self.env.context.copy()
        ctx['active_ids'] = payment_ids.ids
        domain = [('id', 'in', payment_ids.ids)]
        return util_model.with_context(ctx).show_action('account.action_account_payments_payable', domain)


    def _action_pay(self):
        wizard = self[0]
        batch = self.env['hr.payslip.run'].browse(self.env.context.get('active_ids', [])[0])
        payment_model = self.env['account.payment']
        payments = payment_model.browse()
        if self.employee_ids:
            slips = batch.slip_ids.filtered(lambda x: x.employee_id in self.employee_ids)
        else:
            slips = batch.slip_ids
        for slip in slips:
            if not slip.paid and slip.payslip_net > 0:
                payment = payment_model.create({
                    'date': wizard.date,
                    'payment_type': 'outbound',
                    'journal_id': wizard.journal_id.id,
                    'forma_pago_id': wizard.journal_id.forma_pago_id.id,
                    'partner_id': slip.employee_id.address_home_id.id,
                    'hr_payment_type': 'pago_nomina',
                    'slip_id': slip.id,
                    'partner_type': 'supplier',
                    'ref': _(u'Pago de %s') % slip.display_name,
                    'amount': slip.payslip_net,
                    'payment_method_line_id': wizard.payment_method_line_id.id,
                    'bank_reference': wizard.bank_reference,
                })
                payments += payment
        batch.write({'state': 'paid'})
        return payments


    def action_pay(self):
        payments = self._action_pay()
        util_model = self.env['ecua.utils']
        ctx = self.env.context.copy()
        ctx['active_ids'] = payments.ids
        domain = [('id', 'in', payments.ids)]
        return util_model.with_context(ctx).show_action('account.action_account_payments_payable', domain)
