# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tools.misc import formatLang
from odoo.tools import float_is_zero, float_compare, float_round
from odoo.osv import expression
from collections import OrderedDict
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
from odoo import SUPERUSER_ID
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from lxml import etree
import logging
_logger = logging.getLogger(__name__)


class hrLiquidationCategory(models.Model):
    
    _name = 'hr.liquidation.category'
    
    name = fields.Char('Descripción de Tipo de Liquidación', required=True, readonly=False)
    percentage_compensation = fields.Float('Porcentaje de Indemnización', digits=dp.get_precision('Account'))
    percentage_eviction = fields.Float('Porcentaje de Deshaucio', digits=dp.get_precision('Account'))


FIELD_STATE = {'draft': [('readonly', False)]}

class hrLiquidation(models.Model):

    _name = 'hr.liquidation'
    _description = 'Liquidación de Personal'

    _inherit = ['mail.thread', 'mail.activity.mixin']

    
    @api.depends(
        'line_ids',
        'line_ids.amount',
        'percentage_compensation',
        'last_remuneration',
        'percentage_eviction',
        'aged_policy',
        'date_end_contract',
        )
    def _get_total(self):
        for sline in self:
            company = sline.env.user.company_id
            total_compensation = ((sline.percentage_compensation / 100.0) or 0) * (sline.last_remuneration or 0)
            if sline.aged_policy == '3_anios':
                total_compensation = total_compensation * 3.0
            elif sline.aged_policy == 'all':
                total_compensation = total_compensation * sline.aged_years
            elif sline.aged_policy == 'all_total':
                total_compensation = total_compensation * sline.aged_years_completed
            elif sline.aged_policy == 'all_months':
                total_compensation = total_compensation * sline.aged_month
            total_eviction = 0.0
            if sline.aged_years_completed >= 1:
                total_eviction = ((sline.percentage_eviction / 100.0) or 0) * (sline.last_remuneration or 0)
                total_eviction = total_eviction * sline.aged_years_completed
            total_eviction = company.currency_id.compute(total_eviction, company.currency_id)
            total_compensation = company.currency_id.compute(total_compensation, company.currency_id)
            total = total_compensation + total_eviction
            for line in sline.line_ids:
                total += line.amount
            
            sline.total_compensation = total_compensation
            sline.total_eviction = total_eviction
            sline.total = total
    
    
    @api.depends(
        'date_start_contract',
        'date_end_contract',
        )
    def _get_total_days(self):
        total = 0
        for sline in self:
            if sline.date_end_contract:
                start_date = sline.date_start_contract
                end_date = sline.date_end_contract
                total = (end_date - start_date).days + 1
            sline.total_days = total

    
    @api.depends(
        'date_start_contract',
        'date_end_contract',
                 )
    def _get_aged_years(self):
        aged_years = 0
        aged_years_completed = 0
        for sline in self:
            if sline.date_start_contract and sline.date_end_contract:
                start_date = sline.date_start_contract
                end_date =sline.date_end_contract
                total = relativedelta(end_date, start_date)
                aged_years = abs(total.years) + (abs(total.months) != 0 and 1 or 0)
                aged_years_completed = abs(total.years)
            sline.aged_years = aged_years
            sline.aged_years_completed = aged_years_completed


    
    @api.depends(
        'date_start_contract',
        'date_end_contract',
        )
    def _get_aged_month(self):
        total = 0
        for sline in self:
            if sline.date_start_contract and sline.date_end_contract:
                start_date = sline.date_start_contract
                end_date = sline.date_end_contract
                end_year_date = start_date + relativedelta(year=1)
                r = relativedelta(start_date, end_date)
                month_start = start_date.month
                month_end = end_date.month + (start_date.month > end_date.month and 12 or 0)
                if abs(r.years) < 1:
                    total = 12 - ((month_end - month_start) > 0 and (month_end - month_start) or 11)
            sline.aged_month = total
    
    _rec_name = 'number'    
    
    number = fields.Char('Número', required=False, readonly=True)
    last_remuneration = fields.Float('Última Remuneración', digits=dp.get_precision('Account'), required=True, readonly=True, states=FIELD_STATE,)
    total_days = fields.Integer(compute="_get_total_days", string='Total de Dias Evaluados', store=True)
    employee_id = fields.Many2one('hr.employee', 'Empleado', required=True, readonly=True, states=FIELD_STATE, ondelete="restrict")
    aged_years = fields.Integer(compute="_get_aged_years", string=u'Años de Servicio Incluidos Parciales', store=True)
    aged_years_completed = fields.Integer(compute="_get_aged_years", string=u'Años de Servicio Completos', store=True)
    aged_month = fields.Integer(compute="_get_aged_month", string=u'Meses antes de cumplir 1 Año', store=True)
    date = fields.Date('Fecha de Liquidación', required=True, readonly=True, states=FIELD_STATE, default=fields.Date.today(),)
    date_end_contract = fields.Date(string='Fecha de Salida del Personal', required=True, readonly=True, states=FIELD_STATE,)
    date_start_contract = fields.Date(string='Fecha de Ingreso', required=True, readonly=True, states=FIELD_STATE,)
    contract_ids = fields.Many2many('hr.contract', 'hr_liquidation_contract_rel', 
                                    'liquidation_id', 'contract_id', string=u'Contratos', 
                                    required=True, readonly=True, states=FIELD_STATE, help=u"") 
    category_id = fields.Many2one('hr.liquidation.category', 'Tipo de Liquidación', required=True, readonly=True, states=FIELD_STATE)
    note = fields.Text('Observaciones', readonly=True, states=FIELD_STATE)
    line_ids = fields.One2many('hr.liquidation.provision.line', 'liquidation_id', 'Líneas de Provision', required=False, readonly=True, states={'draft': [('readonly', False)], 'open': [('readonly', False)]})
    total_compensation = fields.Float(compute="_get_total", string='Total Indemnización', store=True)
    total_eviction = fields.Float(compute="_get_total", string='Total Deshaucio', store=True)
    total = fields.Float(compute="_get_total", string='Total Liquidación', store=True)
    account_id = fields.Many2one('account.account', 'Cuenta de Gasto', required=False, states={'done': [('readonly', True)]})
    move_id = fields.Many2one('account.move', 'Movimiento Contable', readonly=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirm', 'Confirmado'),
        ('open', 'Aprobado'),
        ('done', 'Pagada'),
    ], 'Estado', index=True, readonly=True, default='draft')
    aged_policy = fields.Selection([
        ('none', 'Ninguna'),
        ('3_anios', 'Aplicar 3 Años'),
        ('all', 'Por cada Año de Servicio incluido Parciales'),
        ('all_total', 'Por cada Año de Servicio Cumplidos'),
        ('all_months', 'Por cada Mes antes de Cumplir 1 Año'),
         ], 'Política de Años de Servicio (Indemnización)', index=True, default='none', required=True, readonly=True, states=FIELD_STATE,)
    percentage_compensation = fields.Float('Porcentaje de Indemnización', digits=dp.get_precision('Account'), required=True, readonly=True, states=FIELD_STATE,)
    percentage_eviction = fields.Float('Porcentaje de Deshaucio', digits=dp.get_precision('Account'), required=True, readonly=True, states=FIELD_STATE,)
    payment_ids = fields.One2many('account.payment', 'hr_liquidation_id', string=u'Pagos Asociados', 
                                  required=False, readonly=False, states={}, help=u"")
    last_payslip_id = fields.Many2one('hr.payslip', string=u'Última Nómina', 
                                      readonly=True, ondelete="restrict") 
    account_analytic_id = fields.Many2one('account.analytic.account', string=u'Cuenta Analítica', 
                                          states={'done': [('readonly', True)]}, 
                                          ondelete="restrict") 
    
    @api.depends(
        'date_end_contract',
                 )
    def _get_sbu_applicable(self):

        for sline in self:
            company = sline.env.user.company_id
            if sline.date_end_contract:
                sbu_value = company.get_sbu(sline.date_end_contract)
                sline.sbu_applicable = sbu_value

    sbu_applicable = fields.Float(u'SBU Aplicable', digits=dp.get_precision('Account'), help=u"") 
    
    
    @api.depends('payment_ids',)
    def _get_payment_count(self):
        for sline in self:
            sline.payment_count = len(sline.payment_ids)
    payment_count = fields.Integer(string='Cuenta de Pagos', 
                                   store=False, compute='_get_payment_count', help=u"")
    
    
    def action_view_payment(self):
        '''
        This function returns an action that display existing delivery orders
        of given sales order ids. It can either be a in a list or in a form
        view, if there is only one delivery order to show.
        '''
        action = self.env.ref('account.action_account_payments_payable').read()[0]
   
        payment = self.mapped('payment_ids')
        if len(payment) > 1:
            action['domain'] = [('id', 'in', payment.ids)]
        elif payment:
            action['views'] = [(self.env.ref('account.view_account_payment_form').id, 'form')]
            action['res_id'] = payment.id
        return action


    @api.onchange(
        'category_id',
        )
    def onchange_category_id(self):
        if self.category_id:
            self.percentage_compensation = self.category_id.percentage_compensation
            self.percentage_eviction = self.category_id.percentage_eviction

    
    def get_lines(self):
        payslip_model = self.env['hr.payslip']
        pline_model = self.env['hr.payslip.line']
        rule_model = self.env['hr.salary.rule']
        line_model = self.env['hr.liquidation.provision.line']
        transaction_model = self.env['hr.scheduled.transaction']
        company = self.env.company

       
        if self.employee_id and self.date_end_contract and self.date_start_contract and self.contract_ids:
            self.line_ids.unlink()
            new_lines = line_model.browse()
            transactions = transaction_model.search([
                ('employee_id', '=', self.employee_id.id),
                ('processed', '=', False),
                ('category_id.code', '=', 'EGRE'),
                ])
            for transaction in transactions:
                new_lines += line_model.create({
                    'liquidation_id': self.id,
                    'type': 'pending_discount',
                    'name': transaction.display_name,
                    'transaction_id': transaction.id,
                    'amount': transaction.amount_pending * -1,
                    })
            transactions = transaction_model.search([
                ('employee_id', '=', self.employee_id.id),
                ('processed', '=', False),
                ('category_id.code', 'in', ['INGR','OINGR']),
                ])
            for transaction in transactions:
                new_lines += line_model.create({
                    'liquidation_id': self.id,
                    'type': 'other',
                    'name': transaction.display_name,
                    'transaction_id': transaction.id,
                    'amount': transaction.amount_pending ,
                    })
            line_names = {
                'fourteenth': u'Décimo Cuarto',
                'thirteenth': u'Décimo Tercero',
                'vacations': 'Vacaciones',
                'iess': 'Aporte Personal IESS',
                'fondo_reserva': 'Fondos de Reserva',
                'last_wage': 'Último Sueldo',
                'other': 'Otro Rubro',
                }
            line_type = {
                'fourteenth': company.rule_fourteenth_id.id ,
                'thirteenth' : company.rule_thirteenth_id.id,
                'vacations': company.rule_vacation_id.id,
                'iess': company.rule_iess_employee_id.id,
                'fondo_reserva': company.rule_fondos_reserva_id.id,
                'last_wage': company.rule_sueldo_id.id,
                'other': False,
                }
            #Buscar las lineas de provisiones
            # import pdb  
            # pdb.set_trace()
            for rule in line_type.keys():
                # import pdb 
                # pdb.set_trace()
                if line_type.get(rule) and rule not in ('iess', 'fondo_reserva', 'last_wage'):
                    if rule == 'fourteenth':
                        plines = pline_model.search([
                            ('employee_id', '=', self.employee_id.id),
                            ('salary_rule_id', '=', line_type.get(rule)),
                            ('provision_liquidated', '=', False),
                            ('provision_pay_from_fourteenth','=',False),
                            ], order="date_from")

                    if rule == 'thirteenth':
                        plines = pline_model.search([
                            ('employee_id', '=', self.employee_id.id),
                            ('salary_rule_id', '=', line_type.get(rule)),
                            ('provision_liquidated', '=', False),('provision_pay_from_thirteenth','=',False),
                            ], order="date_from")

                    if rule == 'vacations':
                        plines = pline_model.search([
                            ('employee_id', '=', self.employee_id.id),
                            ('salary_rule_id', '=', line_type.get(rule)),
                            ('provision_liquidated', '=', False),
                            ('vacations_pay_from','=',False),
                            ], order="date_from")

                    if plines:
                        total = sum([p.total for p in plines])
                        if rule == 'fourteenth':
                            sbu_aplicable = 0
                            sbu_aplicable = company.get_sbu(self.date_end_contract)
                            dia_sbu = sbu_aplicable / 360.0
                            total = sum([l.days_worked for l in plines]) * dia_sbu
                        new_lines += line_model.create({
                            'liquidation_id': self.id,
                            'type': rule,
                            'name': rule_model.browse(line_type.get(rule)).display_name,
                            'rule_id': line_type.get(rule),
                            'amount': total,
                            'payslip_line_ids': [(6, 0, plines.ids)],
                            })
                else:
                    new_lines += line_model.create({
                        'liquidation_id': self.id,
                        'type': rule,
                        'rule_id': line_type.get(rule),
                        'name': line_names.get(rule, 'Otro Valor'),
                        'amount': 0.0,
                        })
            #Se tiene que simular si fuera fin de mes, para calcular todas las lineas

            # import pdb 
            # pdb.set_trace()
            delta = (self.date_end_contract - (self.date_end_contract + relativedelta(day=1))).days
            # end_date_calc = self.date_end_contract + relativedelta(months=-1, day=1, days=-1)
            start_date = self.date_end_contract - relativedelta(days=abs(delta))
            end_date = self.date_end_contract 
            slip_lines = payslip_model.with_context(contract=self.contract_ids[-1].id, all_contracts=True, liquidation=True).get_payslip_lines_simulate(self.employee_id.id, start_date.strftime(DF), end_date.strftime(DF))

            for sline in slip_lines:
                if line_type.get('iess', False) == sline.salary_rule_id.id:
                    for nline in new_lines:
                        if nline.type == 'iess':
                            nline.amount = sline.total
                if line_type.get('fondo_reserva', False) == sline.salary_rule_id.id:
                    for nline in new_lines:
                        if nline.type == 'fondo_reserva':
                            nline.amount = sline.total
                if line_type.get('last_wage', False) == sline.salary_rule_id.id:
                    for nline in new_lines:
                        if nline.type == 'last_wage':
                            nline.amount = sline.total
                if line_type.get('fourteenth', False) == sline.salary_rule_id.id:
                    for nline in new_lines:
                        if nline.type=='fourteenth':
                            nline.amount+=sline.total
                if line_type.get('thirteenth', False) == sline.salary_rule_id.id:
                    for nline in new_lines:
                        if nline.type=='thirteenth':
                            nline.amount+=sline.total
                if line_type.get('vacations', False) == sline.salary_rule_id.id:
                    for nline in new_lines:
                        if nline.type=='vacations':
                            nline.amount+=sline.total





        return True



    # def onchange_employee_id(self):
    #     self._get_sbu_applicable()
        
    @api.onchange(
        'employee_id',
        'date_end_contract',
        )
    def onchange_employee_id(self):
        contract_model = self.env['hr.contract']
        payslip_model = self.env['hr.payslip']
        self._get_sbu_applicable()
        warning = {}
        if self.employee_id:
            payslips = payslip_model.search([
                ('employee_id', '=', self.employee_id.id),
                ('state', '!=', 'draft'),
                ], order="date_from DESC", limit=1)
            if payslips:
                self.last_remuneration = payslips[0].inputs
                self.last_payslip_id = payslips[0].id
            if not payslips:
                warning = {
                        'title': _(u'Advertencia'),
                        'message': _(u'El empleado %s no posee una última nómina disponible para calcular última liquidación, por favor verifique' % (self.employee_id.display_name)),
                        }
            self.contract_ids += self.employee_id.get_no_liquidated_contracts()
            if self.contract_ids:
                contracts = contract_model.search([('id', 'in', self.contract_ids.ids)], order="date_start")
                date_start = False
                date_end = False
                count_no_date_end = 0
                if not payslips and contracts:
                    self.last_remuneration = contracts[-1].wage
                for contract in contracts:
                    current_date_start = contract.date_start
                    if not date_start:
                        date_start = contract.date_start
                    if date_start > current_date_start:
                        date_start = current_date_start
                    if contract.date_end:
                        current_date_end =contract.date_end
                        if not date_end:
                            date_end = contract.date_start
                        if current_date_end > date_end:
                            date_end = current_date_end
                    else:
                        count_no_date_end += 1
                if count_no_date_end > 1:
                    warning = {
                            'title': _(u'Advertencia'),
                            'message': _(u'El empleado %s posee mas de un contrato sin fecha de finalizacion, verifique si estan correctamente configurados' % (self.employee_id.display_name)),
                            }
                    self.employee_id = False
                    self.date_start_contract = False
                    self.date_end_contract = False
                    self.contract_ids = []
                    return {
                        'warning': warning
                        }
                if date_start:
                    self.date_start_contract = date_start
                if date_end and not self.date_end_contract:
                    self.date_end_contract = date_end
                elif not self.date_end_contract:
                    self.date_end_contract = False
            else:
                warning = {
                        'title': _(u'Advertencia'),
                        'message': _(u'El empleado %s no posee contratos disponible para procesar liquidación, por favor verifique' % (self.employee_id.display_name)),
                        }
                self.employee_id = False
                self.date_start_contract = False
                self.date_end_contract = False
                self.contract_ids = []
                return {
                    'warning': warning
                    }
        return {
            'warning': warning
            }
                
    
    def unlink(self):
        for liquidation in self:
            if liquidation.state != 'draft':
                raise UserError(_(u'No puede borrar una liquidación de personal que no este en estado borrador'))
        return super(hrLiquidation, self).unlink()
    
    
    def action_confirm(self):
        seq_model = self.env['ir.sequence']
        for liquidation in self:
            if not liquidation.number:
                liquidation.number = seq_model.next_by_code('hr.liquidation')
        return self.write({
            'state': 'confirm',
            })

    
    def action_draft(self):
        return self.write({
            'state': 'draft',
            })

    
    def action_open(self):
        for liquidation in self:
            for contract in liquidation.contract_ids:
                if not contract.date_end:
                    contract.date_end = liquidation.date_end_contract
                contract.state = 'close'
        return self.write({
            'state': 'open',
            })

    
    def create_payment(self):
        payment_count = len(self.payment_ids)
        if payment_count > 0:
            raise ValidationError(u'Solo puede generar un pago en la presente solicitud')
        else:
            self.ensure_one()
            if not self.account_id:
                raise UserError(_('Debe configurar la cuenta contable del gasto para proceder, verifique la pestaña de contabilidad'))
            for line in self.line_ids:
                if (line.amount + abs(line.difference)) == 0:
                    continue
                if line.type in ('thirteenth', 'fourteenth', 'vacations'):
                    if not line.rule_id and not line.account_id:
                        raise UserError(_('Debe configurar la cuenta contable de la línea "%s" para poder continuar') % (line.display_name))
                    if line.rule_id and not line.rule_id.account_debit:
                        raise UserError(_('Debe configurar la cuenta contable de débito de la regla salarial "%s" para poder continuar') % (line.rule_id.display_name))
                    if line.rule_id and not line.rule_id.account_credit:
                        raise UserError(_('Debe configurar la cuenta contable de crédito de la regla salarial "%s" para poder continuar') % (line.rule_id.display_name))
                if line.type == 'pending_discount':
                    if line.transaction_id and not line.transaction_id.category_transaction_id.account_debit:
                        raise UserError(_('Debe configurar la cuenta contable de débito de el tipo de rubro "%s" para poder continuar') % (line.transaction_id.category_transaction_id.display_name))
                    if line.transaction_id and not line.transaction_id.category_transaction_id.account_credit:
                        raise UserError(_('Debe configurar la cuenta contable de crédito el tipo de rubro "%s" para poder continuar') % (line.transaction_id.category_transaction_id.display_name))
                if line.type == 'other':
                    if not line.account_id:
                        raise UserError(_('Debe configurar la cuenta contable de la línea "%s" para poder continuar') % (line.display_name))
            action = self.env.ref('account.action_account_payments_payable').read()[0]
            action['views'] = [(self.env.ref('account.view_account_payment_form').id, 'form')]
            if not self.employee_id.address_home_id.id:
                raise UserError(_(u'El empleado %s no tiene asignada la empresa para procesar el pago, verifique la configuracion del empleado'))
            ctx = eval(action['context'])
            ctx.update({
                'default_partner_id': self.employee_id.address_home_id.id,
                'default_hr_liquidation_id': self.id,
                'default_employee_id': self.employee_id.id,
                'default_employee': True,
                'default_amount': self.total,
                'default_communication': 'Liquidación de Personal %s' % (self.display_name),
                'default_hr_payment_type':'payment_hr_liquidation',
                'default_account_analytic_id': self.account_analytic_id.id,
                                 })
            action['context'] = ctx
            return action
    
    
    @api.depends(
        'line_ids',
        'line_ids.amount',
        'line_ids.type',
                 )
    def _get_totals(self):
        self.total_d13 = sum([l.amount for l in self.line_ids if l.type == 'thirteenth'])
        self.total_d14 = sum([l.amount for l in self.line_ids if l.type == 'fourteenth'])
        self.total_vacation = sum([l.amount for l in self.line_ids if l.type == 'vacations'])
        self.total_iess = sum([l.amount for l in self.line_ids if l.type == 'iess'])
        self.total_fonda_reserva = sum([l.amount for l in self.line_ids if l.type == 'fondo_reserva'])
        self.total_last_wage = sum([l.amount for l in self.line_ids if l.type == 'last_wage'])
        self.total_pending_discounts = sum([l.amount for l in self.line_ids if l.type == 'pending_discount'])
        self.total_other = sum([l.amount for l in self.line_ids if l.type == 'other'])
    total_d13 = fields.Float(u'Total Decimo Tercero', digits=dp.get_precision('Account'), 
                              store=True, compute='_get_totals', help=u"") 
    total_d14 = fields.Float(u'Total Decimo Tercero', digits=dp.get_precision('Account'), 
                              store=True, compute='_get_totals', help=u"") 
    total_vacation = fields.Float(u'Total Decimo Tercero', digits=dp.get_precision('Account'), 
                              store=True, compute='_get_totals', help=u"") 
    total_iess = fields.Float(u'Total Iess Personal', digits=dp.get_precision('Account'), 
                              store=True, compute='_get_totals', help=u"") 
    total_fondo_reserva = fields.Float(u'Total Fondo Reserva', digits=dp.get_precision('Account'), 
                              store=True, compute='_get_totals', help=u"") 
    total_last_wage = fields.Float(u'Último Sueldo', digits=dp.get_precision('Account'), 
                              store=True, compute='_get_totals', help=u"") 
    total_pending_discounts = fields.Float(u'Total Decimo Tercero', digits=dp.get_precision('Account'), 
                              store=True, compute='_get_totals', help=u"") 
    total_other = fields.Float(u'Total Decimo Tercero', digits=dp.get_precision('Account'), 
                              store=True, compute='_get_totals', help=u"") 


class hrLiquidationProvisionLine(models.Model):
    
    _name = 'hr.liquidation.provision.line'
    
    liquidation_id = fields.Many2one('hr.liquidation', string=u'Liquidacion', 
                                     required=False, readonly=False, states={}, help=u"", ondelete="cascade") 
    name = fields.Char(string=u'Descripcion', index=True, 
                       required=True, readonly=False, states={}, help=u"") 
    type = fields.Selection([
        ('thirteenth','Décimo Tercero'),
        ('fourteenth','Décimo Cuarto'),
        ('vacations','Vacaciones'),
        ('pending_discount','Descuento Pendiente'),
        ('iess','IESS Personal'),
        ('fondo_reserva','Fondos de Reserva'),
        ('last_wage','Último Sueldo'),
        ('other','Otras'),
        ], string='Tipo', 
        readonly=False, required=True, default="other")
    
    payslip_line_ids = fields.Many2many('hr.payslip.line', 'liquidation_line_payslip_line_rel', 
                                        'liquidation_line_id', 'payslip_line_id', string=u'Provisiones Asociadas', states={}, help=u"") 
    
    rule_id = fields.Many2one('hr.salary.rule', string=u'Regla Salarial',
                                required=False, readonly=False, states={}, help=u"", ondelete="restrict")
    transaction_id = fields.Many2one('hr.scheduled.transaction', string=u'Transaccion Programada', 
                                     required=False, readonly=False, states={}, help=u"", ondelete="restrict") 
    account_id = fields.Many2one('account.account', string=u'Cuenta Contable',
                                required=False, readonly=False, states={}, help=u"", ondelete="restrict")
    amount = fields.Float(string=u'Monto Aplicado', digits=dp.get_precision('Account'),
                          required=True, readonly=False, states={}, help=u"") 
    
    @api.depends(
        'amount',
        'payslip_line_ids',
                 )
    def _get_amounts(self):
        for  sline in self:
            sline.provision_amount = sum([abs(p.total) for p in sline.payslip_line_ids])
            sline.difference = sline.provision_amount and (sline.provision_amount - sline.amount)
    provision_amount = fields.Float(string=u'Monto Provisionado', digits=dp.get_precision('Account'),
                                    store=True, compute='_get_amounts', help=u"") 
    difference = fields.Float(u'Diferencia', digits=dp.get_precision('Account'), 
                              store=True, compute='_get_amounts', help=u"") 
    

