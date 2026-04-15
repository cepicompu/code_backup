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




class hr_payslip_run(models.Model):

    _inherit = 'hr.payslip.run'

    def unlink(self):

        idsTransaction=[]
        # idTransaction = self.env['hr.scheduled.transaction'].search([('payslip_line_ids','=',self.id)])
        for line in self.slip_ids:
            for li in line.line_ids.filtered(lambda x: x.transaction_id ):
                idsTransaction.append(li.transaction_id.id)

            # idsTransaction.append([x.transaction_id.id for x in line.line_ids.filtered(lambda x: not x.transaction_id )])
        # import pdb 
        # pdb.set_trace()
        res= super(hr_payslip_run, self).unlink()



        if res and idsTransaction:
            for li in self.env['hr.scheduled.transaction'].search([('id','in',idsTransaction)]):
                li.write({'amount_pending':li.amount,'processed':False})


class hr_scheduled_transaction_category(models.Model):
    u'''
    Categoría de Transacción Programada
    '''
    _name = 'hr.scheduled.transaction.category'
    _description = u'Categoría de Transacción Programada'

    name = fields.Char(string=u'Nombre de Categoría de Transacción Programada', index=True, required=True,)
    code = fields.Char(string=u'Código de Categoría de Transacción Programada', index=True, required=True,)
    analytic_account_id = fields.Many2one('account.analytic.account', u'Cuenta Analítica')
    account_tax_id = fields.Many2one('account.tax', u'Impuesto')
    # tax_code_id = fields.Many2one('account.tax.code', u'Código de Impuesto')
    account_debit = fields.Many2one('account.account', u'Cuenta de Débito', domain=[('deprecated', '=', False)])
    account_credit = fields.Many2one('account.account', u'Cuenta de Crédito', domain=[('deprecated', '=', False)])
    partner_id = fields.Many2one('res.partner', string=u'Empresa Asociada',
                                 required=False, readonly=False, states={}, help=u"", ondelete="restrict")
    pay_to_other = fields.Boolean(string=u'Asignar Empresa', readonly=False, states={}, help=u"Use esta opción cuando el movimiento contable debe asignarse la empresa asociada a la regla")
    set_date_maturity_region = fields.Boolean(string=u'Asignar Fecha de Vencimiento', readonly=False, states={}, help=u"Si esta opción esta activa, se asignará segun la región asignada en el contrato al empleado la fecha de vencimiento, particularmente para los décimos")
    no_account = fields.Boolean(string=u'No generar Contabilidad', readonly=False, states={}, help=u"")
    group_move = fields.Boolean(string=u'Agrupar Asiento Contable', readonly=False, states={}, help=u"Por defecto el sistema detalla cada asiento por cada empleado, con esta opción activa")
    active = fields.Boolean(string=u'Activo?', readonly=False, states={}, help=u"", default=True)
    sequence = fields.Integer(string=u'Secuencia',
                              readonly=False, required=False, states={}, help=u"")
    account_payslip = fields.Selection([('credit', 'Acreedora'),
                                        ('debit', 'Deudora')], string='Cuenta en nómina',
                                       help="En la nómina solo considerara la cuenta seleccionada")

    type = fields.Selection([
        ('input', 'Ingreso'),
        ('output', 'Egreso'),
    ], string='Tipo', related="category_id.type",
        readonly=True, required=True, states={}, help=u"")
    mostrar_en_registros = fields.Boolean(string=u'Mostrar en procesos de pagos / solicitud de egreso', readonly=False, states={}, help=u"")
    rule_related_id     =   fields.Many2one('hr.salary.rule',string=u'Regla Relacionada',domain=[('active', '=', True)],)
    category_id = fields.Many2one('hr.salary.rule.category', string=u'Categoría',
                                  required=True, readonly=False, states={}, help=u"", ondelete="restrict",related="rule_related_id.category_id")
    category_code = fields.Char(string=u'Codigo Categoria', index=True,
                                related="category_id.code", store=True)





    @api.onchange('rule_related_id')
    def _onchange_rule_related_id(self):
        if self.rule_related_id:
            self.category_id = self.rule_related_id.category_id
        else:
            self.category_id = None



    _sql_constraints = [('code_uniq', 'unique (code)', _(u'Código de Categoría debe ser único')), ]

class hr_scheduled_transaction(models.Model):
    u'''
    Transacción Programada
    '''
    _name = 'hr.scheduled.transaction'
    _description = u'Transaccion Programada'

    name = fields.Char(string=u'Nombre de Transacción Programada', index=True, required=True)
    code = fields.Char(string=u'Código de Transacción Programada', index=True, required=False)
    rule_id = fields.Many2one('hr.salary.rule', string=u'Rubro', required=True, ondelete="restrict")
    payment_id = fields.Many2one('account.payment', string=u'Pago Relacionado',required=False, readonly=True, states={}, help=u"", ondelete="cascade")
    employee_id = fields.Many2one('hr.employee', string=u'Empleado', required=True, ondelete="restrict")
    contract_id = fields.Many2one('hr.contract', string=u'Contrato', related="employee_id.contract_id", ondelete="restrict")
    struct_id = fields.Many2one('hr.payroll.structure', string=u'Estructura Salarial', related="contract_id.struct_id", ondelete="restrict")


    category_id = fields.Many2one('hr.salary.rule.category', store=True,string=u'Categoría', related="category_transaction_id.category_id", ondelete="restrict")
    category_transaction_id = fields.Many2one('hr.scheduled.transaction.category', string=u'Tipo de Rubro', ondelete="restrict")

    date = fields.Date(string=u'Fecha para Procesar', required=True, index=True, copy=False, help=u"Fecha en que se va a anexar dentro de los calculos de nómina")
    amount = fields.Float(u'Monto', readonly=False, required=True, states={}, help=u"")
    type = fields.Selection([
        ('input', 'Ingreso'),
        ('output', 'Egreso'),
    ], string=u'Tipo', readonly=True)
    overtime_id = fields.Many2one('request.overtime', string=u'Solicitud de Horas Extras',required=False, readonly=True, states={}, help=u"", ondelete="cascade")
    payslip_line_ids = fields.One2many('hr.payslip.line', 'transaction_id', string=u'Líneas de Nóminas',required=False, readonly=True, states={}, help=u"",)
    collection_register_ids = fields.One2many('account.payment.hr.collection.register', 'transaction_id', string=u'Pagos de Anticipo / Prestamo',required=False, readonly=True, states={}, help=u"")
    hr_liquidation_line_ids = fields.One2many('hr.liquidation.provision.line', 'transaction_id', string=u'Líneas de Liquidación',required=False, readonly=True, states={}, help=u"")
    observation  = fields.Char(string=u'Observaciones')
    hours = fields.Float('Horas Laboradas',help=u"Solo para calculo de horas extras")
    company_id = fields.Many2one('res.company', string=u'Compañía', required=True, default=lambda self: self.env.company)



    def name_get(self):
        res = []
        for rec in self:
            name = '%s (%s)' % (rec.name, rec.date)
            res.append((rec.id, name))
        return res


    def unlink(self):
        sline_model = self.env['hr.payslip.line']
        for transaction in self:
            if transaction.processed:
                slines = sline_model.search([('transaction_id', '=', self.id)])
                raise UserError(_(u'No puede borrar una transacción programada que ya se encuentra procesada en nómina, debe revertir la nómina "%s" asociada') % (slines.slip_id.display_name))
            if transaction.overtime_id:
                raise UserError(_(u'No puede borrar una transacción programada que ya se encuentra procesada en solicitud de horas extras: "%s" asociada.') % (self.overtime_id.display_name))
        return super(hr_scheduled_transaction, self).unlink()


    @api.constrains('amount',)
    def _check_amount(self):
        if self.amount <= 0:
            raise UserError(_(u'El monto de la transacción programada %s debe ser mayor que cero') % self.display_name)
        if self.payment_id:
            total_transactions = 0.0
            for transaction in self.payment_id.hr_transaction_ids:
                total_transactions += transaction.amount
            if self.payment_id.hr_transaction_ids and total_transactions != self.payment_id.amount:
                raise UserError(_(u'El monto total de las transacciones programadas %s no puede ser diferente al monto %s del pago asociado %s') % (total_transactions, self.payment_id.amount, self.payment_id.display_name))



    @api.depends(
        'payslip_line_ids',
        'payslip_line_ids.slip_id.state',
        'collection_register_ids',
        'collection_register_ids.payment_id.state',
        'hr_liquidation_line_ids',
        'hr_liquidation_line_ids.liquidation_id.state',
        'amount',
    )
    def _get_processed(self):
        # import pdb
        # pdb.set_trace()
        processed = False
        for line in self:
            line.amount_pending = line.amount - (sum([abs(p.total) for p in line.payslip_line_ids if p.slip_id.state == 'done' ]) + \
                                                 sum([abs(c.amount) for c in line.collection_register_ids if c.payment_id.state in ('posted', 'send', 'reconciled')]) + \
                                                 sum([abs(c.amount) for c in line.hr_liquidation_line_ids if c.liquidation_id.state in ('open', 'done')]))
            if line.amount > 0:
                processed = line.amount_pending <= 0
            else:
                processed = False
        self.processed = processed

    amount_pending = fields.Float(u'Monto Pendiente', digits=dp.get_precision('Account'),
                                  store=True, compute='_get_processed', help=u"")

    processed = fields.Boolean(string=u'Procesado?', store=True,
                               compute='_get_processed', help=u"")

    _sql_constraints = [('code_uniq', 'check(1=1)', _(u'Código de Categoría debe ser único')), ]

    def _get_wage_hours_suple(self,hours,employee_id):
        contract_id=self.env['hr.employee'].browse(employee_id).contract_id
        if contract_id.hour_value > 0:
            if contract_id.type_day == 'partial':
                cantidad_horas_suple = ((contract_id.value_for_parcial) / contract_id.contracted_hours) * hours
                return cantidad_horas_suple * 1.5
            else:
                cantidad_horas_suple = hours * contract_id.hour_value
                return cantidad_horas_suple * 1.5

    def _get_wage_hours_ext(self,hours,employee_id):
        contract_id=self.env['hr.employee'].browse(employee_id).contract_id
        if contract_id.hour_value > 0:
            if contract_id.type_day == 'partial':
                cantidad_horas_ext = ((contract_id.value_for_parcial) / contract_id.contracted_hours) * hours
                return cantidad_horas_ext * 2.0
            else:
                cantidad_horas_ext = hours * contract_id.hour_value
                return cantidad_horas_ext * 2.0

    def _get_wage_hours_night(self,hours,employee_id):
        contract_id=self.env['hr.employee'].browse(employee_id).contract_id
        if contract_id.hour_value > 0:
            if contract_id.type_day == 'partial':
                cantidad_horas_night = ((contract_id.value_for_parcial) / contract_id.contracted_hours) * hours
                return cantidad_horas_night * 0.25
            else:
                cantidad_horas_night = hours * contract_id.hour_value
                return cantidad_horas_night * 0.25

    @api.model
    def create(self, vals):
        if not 'code' in vals:
            code = str(fields.Datetime.now())
            if 'employee_id' in vals:
                employee_id = self.env['hr.employee'].browse(vals['employee_id'])
                rule_id = self.env['hr.salary.rule'].browse(vals['rule_id'])
                code += code + "-" + str(employee_id.id) + "-" + str(rule_id.code)
            vals.update({'code': code})
        rule_id = vals.get('rule_id',None)
        employee_id = vals.get('employee_id',None)
        extra = self.env.company.category_transaction_hour_extra_id.id if self.env.company.category_transaction_hour_extra_id else None
        suple = self.env.company.category_transaction_hour_suple_id.id if self.env.company.category_transaction_hour_suple_id else None
        night = self.env.company.category_transaction_hour_night_id.id if self.env.company.category_transaction_hour_night_id else None
        if employee_id:
            if rule_id:
                if rule_id==extra:
                    vals['hours']=vals['amount']
                    vals['amount']=self._get_wage_hours_ext(vals['amount'],employee_id)
                if rule_id==suple:
                    vals['hours']=vals['amount']
                    vals['amount']=self._get_wage_hours_suple(vals['amount'],employee_id)
                if rule_id==night:
                    vals['hours']=vals['amount']
                    vals['amount']=self._get_wage_hours_night(vals['amount'],employee_id)
        res = super(hr_scheduled_transaction, self).create(vals)
        return res


