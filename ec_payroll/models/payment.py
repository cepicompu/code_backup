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

STATES = {'draft': [('readonly', False),]}


class HrAmountPayment(models.Model):

    def getCodigoTrx(self):

        retorno = None
        cr = self._cr
        cr.execute('SELECT max(codigo::int) + 1 FROM hr_account_payment')
        results = cr.fetchone()

        # import pdb
        # pdb.set_trace()
        if results[0]:

            retorno = str(results[0]).zfill(6)
        else:
            retorno = '000001'

        return retorno

    _name = 'hr.account.payment'
    _rec_name = 'codigo'

    codigo = fields.Char('Trx', default=getCodigoTrx)
    tipo_pago = fields.Selection([('anticipo', 'Anticipo'), ('roles', 'Roles')], 'Tipo', required=True,
                                 default='anticipo')
    date_payment = fields.Date('Fecha Pago', required=True)
    communication = fields.Char('Observación')
    journal_id = fields.Many2one('account.journal', 'Forma Pago')
    payslip_run_id = fields.Many2one('hr.payslip.run', 'Rol #')
    request_id = fields.Many2one('request.loan.payment', 'Anticipo #')
    payment_ids = fields.One2many('hr.account.payment.line', 'hr_payment_id', 'Detalle')
    state = fields.Selection([('draft', 'Borrador'), ('done', 'Validado')], 'Estado', required=True, default='draft')

    # @api.multi
    def create_payment(self):
        for line in self.payment_ids:
            self.create_payment_inherit(line)

        if self.payment_ids:
            self.write({'state': 'done'})

    # @api.multi
    def create_payment_inherit(self, line):
        journal = None
        idsPago = None
        pago = self.env['account.payment']
        line_request = self.env['hr.account.payment.line']
        account_payment_id = None
        # import pdb
        # pdb.set_trace()
        # idsContract=self.env['hr.contract'].search([('employee_id', '=', line.employee_id.id)])
        # contract=self.env['hr.contract'].browse(idsContract.id)

        company = self.env.company
        if not company.salarios_account_id:
            raise UserError(_(u'Debe tener configurada la cuenta contable de sueldos para poder continuar'))
        else:

            # if line.employee_id.pay_with_check:
            # 	if not contract.journal_chque_anticipo:
            # 		journal = self.env.company.journal_chque_anticipo
            # 	else:
            # 		journal =contract.journal_chque_anticipo

            # 	account_payment_id=3

            # else:
            # 	if not contract.journal_trans_anticipo:
            # 		journal = self.env.company.journal_trans_anticipo
            # 	else:
            # 		journal= contract.journal_trans_anticipo

            account_payment_id = 2

            # import pdb
            # pdb.set_trace()

            data = {
                'payment_type': 'outbound',
                'payment_date': self.date_payment,
                'communication': self.communication + '(' + self.codigo + ')',
                'partner_type': 'supplier',
                'partner_id': line.employee_id.address_home_id.id,
                'beneficiary': line.employee_id.name,
                'amount': line.amount,
                'journal_id': self.journal_id.id,
                'forma_pago_id': 1,  # SIN UTILIZACION DEL SISTEMA FINANCIERO
                'payment_method_id': account_payment_id,
                'request_salary_id': line.id
            }

            idsPago = pago.create(data)
            # if line.state='done'
            idsPago.post()
            line_request.write({'account_payment_id': idsPago.id})

            return True

    # @api.multi
    def action_get_employee(self):
        # import pdb
        # pdb.set_trace()
        ids_contract = []
        ids_employee = []
        sueldo = 0
        monto_anticipo = 0
        objRoles = self.env['hr.payslip.run']
        objAnticipo = self.env['request.loan.payment']
        # ids_employee = self.env['hr.employee'].search([('active', '=', True)])
        # if self.tipo_carga=='all':
        # ids_contract = self.env['hr.contract'].search([('employee_id', 'in', tuple(ids_employee.ids))])
        # elif self.tipo_carga=='structure' and self.hr_structure:
        # 	ids_contract = self.env['hr.contract'].search([('employee_id', 'in', tuple(ids_employee.ids)),('struct_id', '=', self.hr_structure.id)])

        for line in self.payment_ids:
            line.unlink()

        if self.tipo_pago == 'anticipo':
            for line in objAnticipo.browse(self.request_id.id).line_ids:
                self.env['hr.account.payment.line'].create({'employee_id': line.employee_id.id, 'amount': line.amount,
                                                            'forma_pago': self.journal_id.id, 'state': 'done',
                                                            'hr_payment_id': self.id})

        if self.tipo_pago == 'roles':
            for line in objRoles.browse(self.payslip_run_id.id).slip_ids:
                self.env['hr.account.payment.line'].create(
                    {'employee_id': line.employee_id.id, 'amount': line.payslip_net,
                     'forma_pago': self.journal_id.id, 'state': 'done', 'hr_payment_id': self.id})

    # for line in self.env['hr.contract'].browse(ids_contract.ids):
    # 	# import pdb
    # 	# pdb.set_trace()
    # 	monto_anticipo=self.monto_asignado if self.tipo_anticipo=='permanent' else (self.monto_asignado/100)*line.wage
    # 	# ids=self.create_new_statement(line.employee_id,monto_anticipo)
    # 	# if ids:
    # 	self.env['request.loan.payment.line'].create({'request_id':self.id,'employee_id':line.employee_id.id,'amount':monto_anticipo})
    # 		# 'transaction_id':ids.id,

    # self.state = 'draft'

    # @api.multi
    def write(self, vals):
        # import pdb
        # pdb.set_trace()
        if vals.get('payslip_run_id', False):
            vals['request_id'] = None
            if self.request_id:
                self.request_id.write({'account_payment_id': None})
            self.env['hr.payslip.run'].browse(vals.get('payslip_run_id', False)).write({'account_payment_id': self.id})

        if vals.get('request_id', False):
            vals['payslip_run_id'] = None
            if self.payslip_run_id:
                self.payslip_run_id.write({'account_payment_id': None})
            self.env['request.loan.payment'].browse(vals.get('request_id', False)).write(
                {'account_payment_id': self.id})

        return super(HrAmountPayment, self).write(vals)

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    request_salary_id = fields.Many2one('hr.account.payment.line', ondelete='cascade')

    def _prepare_payment_moves(self):
        # account_details =None
        if self.request_loan_line_id:
            company = self.env.company
            if not company.salarios_account_id:
                raise UserError(_("Debe configurar una cuenta contable de sueldos en los ajustes de Nómina"))

            self.destination_account_id = self.request_loan_line_id.request_id.payment_account_id.id
        res = super(AccountPayment, self)._prepare_payment_moves()

        return res

    def _get_counterpart_move_line_vals(self, invoice=False):

        account = None
        company = self.env.company
        company.salarios_account_id

        if self.request_loan_line_id:
            account = self.request_loan_line_id.request_id.hr_rule.account_debit.id
        elif self.request_salary_id:
            account = company.salarios_account_id.id
        else:
            account = self.destination_account_id.id

        if self.payment_type == 'transfer':
            name = self.name
        else:
            name = ''
            if self.partner_type == 'customer':
                if self.payment_type == 'inbound':
                    name += _("Customer Payment")
                elif self.payment_type == 'outbound':
                    name += _("Customer Credit Note")
            elif self.partner_type == 'supplier':
                if self.payment_type == 'inbound':
                    name += _("Vendor Credit Note")
                elif self.payment_type == 'outbound':
                    name += _("Vendor Payment")
            if invoice:
                name += ': '
                for inv in invoice:
                    if inv.move_id:
                        if inv.number:
                            name += inv.number + ', '
                        else:
                            name += inv.document_number + ', '

                name = name[:len(name) - 2]
        return {
            'name': name,
            'account_id': account,
            'journal_id': self.journal_id.id,
            'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
        }

    rule_id = fields.Many2one('hr.salary.rule', string=u'Rubro', readonly=True, states=STATES)
    category_transaction_id = fields.Many2one('hr.scheduled.transaction.category', domain=[('category_code', 'in', ('EGRE', 'CONT')),('mostrar_en_registros', '=', True)], readonly=True, states=STATES,
                                              string=u'Categoría de Transacción Programada (Recursos Humanos)', ondelete="restrict")
    hr_payment_type = fields.Selection([
        ('normal',u'Usar como Proveedor'),
        ('descuento_rol',u'Descuento al Rol de Pagos'),
        ('pago_nomina',u'Pago de Nómina'),
        ('pago_grupo_nomina',u'Pago de Procesamiento de Nómina'),
        ('payment_hr_liquidation',u'Pago de Liquidación de Personal'),
        ], string=u'Tipo de Pago Recursos Humanos', help=u"", readonly=True, states=STATES, default="normal")
    hr_collection_payment_type = fields.Selection([
        ('normal',u'Usar como Cliente'),
        ('loan_payment',u'Pago de Prestamo / Anticipo'),
        ], string=u'Tipo de Pago Recursos Humanos', help=u"", readonly=True, states=STATES, default="normal")
    slip_id = fields.Many2one('hr.payslip', string=u'Nómina',
                              required=False, readonly=False, states={}, help=u"", ondelete="cascade")
    tipo_desglose = fields.Selection([
        ('one_payment',u'Un Único Registro de Transacción'),
        ('multi_payment', u'Múltiples Registros de Transacción'),
        ], string=u'Tipo de Pago Recursos Humanos', help=u"", readonly=True, states=STATES, default="one_payment")
    cantidad_descuentos = fields.Integer(string=u'Cantidad de Descuentos',
                                         readonly=True, required=False, states=STATES, default=1,help=u"")
    request_egress_id = fields.Many2one('request.egress', string=u'Solucitud de Pago',
                                                  required=False, readonly=False, states={}, help=u"", ondelete="cascade")
    request_loan_payment_id = fields.Many2one('request.loan.payment', string=u'Solucitud de Pago',
                                                  required=False, readonly=False, states={}, help=u"", ondelete="cascade")
    hr_liquidation_id = fields.Many2one('hr.liquidation', string=u'Liquidación de Personal',
                                                  required=False, readonly=False, states={}, help=u"", ondelete="cascade")

    @api.onchange(
        'hr_liquidation_id',
                  )
    def _onchange_hr_liquidation_id(self):
        line_model = self.env['account.payment.line']
        if self.hr_liquidation_id:
            new_lines = line_model.browse()
            if self.hr_liquidation_id.total_compensation > 0:
                new_lines += line_model.new({
                    'name': _('Valor por Indemnización'),
                    'account_id': self.hr_liquidation_id.account_id.id,
                    'amount': self.hr_liquidation_id.total_compensation,
                    })
            if self.hr_liquidation_id.total_eviction > 0:
                new_lines += line_model.new({
                    'name': _('Valor por Deshaucio'),
                    'account_id': self.hr_liquidation_id.account_id.id,
                    'amount': self.hr_liquidation_id.total_eviction,
                    })
            for lline in self.hr_liquidation_id.line_ids:
                if (abs(lline.amount) + abs(lline.difference)) != 0:
                    line_data = {
                        'name': lline.name,
                        'account_id': lline.account_id.id,
                        }
                    adjust_line = {
                        'name': _('Ajuste x Diferencia - %s') % lline.name,
                        }
                    if lline.type in ('thirteenth', 'fourteenth', 'vacation', 'iess', 'fondo_reserva', 'last_wage'):
                        if lline.rule_id:
                            l = line_data.copy()
                            l.update({
                                'account_id': lline.rule_id.account_credit.id,
                                'amount': lline.provision_amount,
                                })
                            if lline.amount != 0 and lline.difference == 0.0:
                                l.update({
                                    'account_id': lline.rule_id.account_debit.id,
                                    'amount': lline.amount,
                                    })
                            new_lines += line_model.new(l)
                            if lline.difference > 0:
                                l = adjust_line.copy()
                                l.update({
                                    'account_id': lline.rule_id.account_debit.id,
                                    'amount': lline.difference * -1,
                                    })
                                new_lines += line_model.new(l)
                            elif lline.difference < 0:
                                l = adjust_line.copy()
                                l.update({
                                    'account_id': lline.rule_id.account_credit.id,
                                    'amount': lline.difference * -1,
                                    })
                                new_lines += line_model.new(l)
                        else:
                            l = line_data.copy()
                            l.update({
                                'amount': lline.amount,
                                })
                            if lline.amount < 0:
                                l.update({
                                    'account_id': lline.rule_id.account_debit.id,
                                    })
                            new_lines += line_model.new(l)
                    if lline.type == 'pending_discount':
                        l = line_data.copy()
                        l.update({
                            'account_id': lline.transaction_id.category_transaction_id.account_debit.id,
                            'amount': lline.amount,
                            })
                        new_lines += line_model.new(l)
                    if lline.type == 'other':
                        l = line_data.copy()
                        l.update({
                            'amount': lline.amount,
                            })
                        new_lines += line_model.new(l)
            if new_lines:
                self.line_ids = new_lines

    @api.onchange(
        'request_loan_payment_id',
                  )
    def _onchange_request_loan_payment_id(self):
        cline_model = self.env['account.payment.hr.collection.register']
        if self.request_loan_payment_id:
            new_lines = cline_model.browse()
            for line in self.request_loan_payment_id.line_ids:
                new_lines += cline_model.new({
                    'transaction_id': line.transaction_id.id,
                    'amount_pending': line.amount_pending,
                    'amount': line.amount,
                    })
            self.collection_register_ids += new_lines


    @api.constrains('cantidad_descuentos',
                    'tipo_desglose',
                    'hr_payment_type',
                    )
    def _check_cantidad_descuentos(self):
        for rec in self:
            if rec.hr_payment_type == 'descuento_rol' and rec.tipo_desglose == 'multi_payment' and rec.cantidad_descuentos <= 0:
                raise UserError(_(u'La cantidad de descuentos debe ser mayor a cero en caso de hacer descuento por rol'))


    @api.depends(
        'partner_id',
        'partner_id.employee_ids',
                 )
    def _get_employee(self):
        self.employee_id = self.partner_id and self.partner_id.employee_ids and self.partner_id.employee_ids[0].id or False
        self.employee = self.partner_id and len(self.partner_id.employee_ids.ids) > 0 or False
    employee = fields.Boolean(string=u'Empleado?', store=False,
                              compute='_get_employee', help=u"")
    employee_id = fields.Many2one('hr.employee', string=u'Empleado Asociado', compute='_get_employee', ondelete="restrict")
    hr_transaction_ids = fields.One2many('hr.scheduled.transaction', 'payment_id', string=u'Transacciones Programadas',
                                         required=False, readonly=False, states={}, help=u"")
    destination_account_id = fields.Many2one('account.account', compute='_compute_destination_account_id', readonly=True)
    collection_register_ids = fields.One2many('account.payment.hr.collection.register', 'payment_id', string=u'Detalle de Anticipos / Prestamos',
                                              required=False, readonly=False, states={}, help=u"")

    @api.onchange('slip_id')
    def _onchange_slip_id(self):
        if self.slip_id and self.slip_id.payslip_net > 0:
            self.amount = self.slip_id.payslip_net

    def _prepare_payment_moves(self):
        if self.slip_id:
            if self.slip_id.payslip_run_id.type_slip_pay=="slip":
                self.destination_account_id=self.env.company.salarios_account_id
            elif self.slip_id.payslip_run_id.type_slip_pay=="holiday":
                self.destination_account_id = self.env.company.rule_vacation_id.account_credit
            elif self.slip_id.payslip_run_id.type_slip_pay == "thirteenth":
                self.destination_account_id = self.env.company.rule_thirteenth_id.account_credit
            elif self.slip_id.payslip_run_id.type_slip_pay == "fourteenth":
                self.destination_account_id = self.env.company.rule_fourteenth_id.account_credit
        res=super(AccountPayment, self)._prepare_payment_moves()

        return res





    @api.depends('reconciled_invoice_ids', 'payment_type', 'partner_type', 'partner_id', 'hr_payment_type', 'category_transaction_id')
    def _compute_destination_account_id(self):
        try:
            company = self.env.company
            if self.reconciled_invoice_ids:
                self.destination_account_id = self.reconciled_invoice_ids[0].account_id.id
            elif self.payment_type == 'transfer':
                if not self.company_id.transfer_account_id.id:
                    raise UserError(_('Transfer account not defined on the company.'))
                self.destination_account_id = self.company_id.transfer_account_id.id
            elif self.partner_id:
                if self.employee:
                    if self.hr_payment_type == 'descuento_rol':
                        if self.category_transaction_id:
                            if not self.category_transaction_id.account_debit:
                                raise UserError(_(u'No se encuentra configurada la cuenta contable de la categoría de transacción %s') % self.category_transaction_id.display_name)
                            else:
                                self.destination_account_id = self.category_transaction_id.account_debit.id
                        else:
                            super(AccountPayment, self)._compute_destination_account_id()
                    elif self.hr_payment_type == 'pago_nomina':
                        if not company.salarios_account_id:
                            raise UserError(_(u'Debe configurar la cuenta general de sueldos de la compañía, configure en Nóminas / Configuración / Configuración'))
                        self.destination_account_id = company.salarios_account_id.id
                    elif self.partner_type == 'customer':
                        self.destination_account_id = self.partner_id.property_account_receivable_id.id
                    elif self.partner_type == 'supplier':
                        self.destination_account_id = self.partner_id.property_account_payable_id.id
                else:
                    if not self.is_advance_payment:
                        if self.partner_type == 'customer':
                            self.destination_account_id = self.partner_id.with_company(self.company_id).property_account_receivable_id.id
                        else:
                            self.destination_account_id = self.partner_id.with_company(self.company_id).property_account_payable_id.id
                    else:
                        super(AccountPayment, self)._compute_destination_account_id()

        except:
            super(AccountPayment, self)._compute_destination_account_id()


    def action_post(self):
        company = self.env.company
        transaction_model = self.env['hr.scheduled.transaction']
        aml_model = self.env['account.move.line']
        res = super(AccountPayment, self).action_post()
        for payment in self:
            if payment.request_loan_payment_id:
                payment.request_loan_payment_id.state = 'done'
            if payment.hr_liquidation_id:
                payment.hr_liquidation_id.state = 'done'
            if payment.employee and payment.payment_type == 'outbound':
                if payment.hr_payment_type == 'descuento_rol':
                    transactions = transaction_model.browse()
                    to_data = {
                        'employee_id': payment.partner_id.employee_ids[0].id,
                        'name': payment.ref,
                        'code': payment.ref,
                        'type': 'output',
                        'date': payment.date,
                        'rule_id': payment.rule_id.id,
                        }
                    if payment.request_egress_id:
                        if payment.request_egress_id.type_discount == 'multi_payment':
                            for line in payment.request_egress_id.request_egress_detail_ids:
                                t_copy = to_data.copy()
                                t_copy.update({
                                    'amount': line.monto,
                                    'name': line.description,
                                    'code': line.description + ' ' + str(payment.id),
                                    'date': line.date,
                                    })
                                transactions += transaction_model.create(t_copy)
                        elif payment.request_egress_id.type_discount == 'one_payment':
                            to_data.update({
                                'amount': payment.amount,
                                'date': payment.request_egress_id.fecha_cobro,
                                })
                            transactions += transaction_model.create(to_data)
                        payment.request_egress_id.state = 'delivered'
                    else:
                        if payment.tipo_desglose == 'multi_payment':
                            amount_original = payment.amount
                            amount_transaction = round(amount_original / payment.cantidad_descuentos, 2)
                            for i in range(payment.cantidad_descuentos):
                                if (i+1) == payment.cantidad_descuentos:
                                    amount_transaction = amount_original
                                t_copy = to_data.copy()
                                t_copy.update({
                                    'amount': amount_transaction,
                                    'code': ' %s %s de %s' % (t_copy.get('code') +' '+ str(payment.id), i + 1, payment.cantidad_descuentos),
                                    'name': ' %s %s de %s' % (t_copy.get('name') +' '+ str(payment.id), i + 1, payment.cantidad_descuentos),
                                    })
                                transactions += transaction_model.create(t_copy)
                                amount_original -= amount_transaction
                        elif payment.tipo_desglose == 'one_payment':
                            to_data.update({
                                'amount': payment.amount,
                                })
                            transactions += transaction_model.create(to_data)
                    if transactions:
                        payment.write({
                            'hr_transaction_ids': [(6, 0, [t.id for t in transactions])]
                            })
                elif payment.hr_payment_type == 'pago_nomina' and payment.slip_id and payment.slip_id.payslip_run_id:
                    if not company.salarios_account_id:
                        raise UserError(_(u'Debe configurar la cuenta general de sueldos de la compañía, configure en Nóminas / Configuración / Configuración'))
                    if company.salarios_account_id.reconcile:
                        amls_to_reconcile = aml_model.search([
                            ('account_id', '=', company.salarios_account_id.id),
                            ('payment_id', '=', payment.id),
                                                 ])
                        amls_to_reconcile += aml_model.search([
                            ('account_id', '=', company.salarios_account_id.id),
                            ('move_id', '=', payment.slip_id.payslip_run_id.move_id.id),
                            ('partner_id', '=', payment.partner_id.id)
                                                               ])
                        if amls_to_reconcile:
                            amls_to_reconcile.reconcile()
        return res


    def cancel(self):
        for payment in self:
            payment.hr_transaction_ids.unlink()
            for line in payment.collection_register_ids:
                if line.transaction_id:
                    for sline in line.transaction_id.payslip_line_ids:
                        if sline.slip_id.state == 'done':
                            raise UserError(_(u'No puede anular este pago ya que se encuentra procesada la transacción %s, debe anular el proceso de nomina si desea proceder con la anulación') % (line.transaction_id.display_name))
            if payment.request_loan_payment_id:
                payment.request_loan_payment_id.state = 'requested'
            if payment.hr_liquidation_id:
                payment.hr_liquidation_id.state = 'open'
        return super(AccountPayment, self).cancel()

    def get_counterpart_lines(self, debit, credit, amount_currency, move, currency_id, invoice_currency):
        aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
        transaction_model = self.env['hr.scheduled.transaction']
        if self.payment_type == 'inbound' and self.hr_collection_payment_type == 'loan_payment':
            #El total de las lineas no puede ser diferente al total de la cabecera
            total_lines = sum([l.amount for l in self.collection_register_ids])
            if float_compare(self.amount, total_lines, precision_digits=2) != 0:
                raise UserError(_(u'El monto total de las lineas %s no puede ser diferente al valor total del pago %s') % (total_lines, self.amount))
            counterpart_aml_dict = self._get_shared_move_line_vals(debit, credit, amount_currency, move.id, False)
            counterpart_aml_dict.update({'currency_id': currency_id})
            counterpart_aml_dict.update({
                'analytic_account_id': self.account_analytic_id.id,
                })
            #No permitir hacer 2 lineas en el mismo pago la misma transaccion
            transactions = transaction_model.browse()
            for line in self.collection_register_ids:
                if line.transaction_id in transactions:
                    raise UserError(_(u'No puede procesar la misma transaccion (%s) más de una ves verifique las lineas procesadas') % (line.transaction_id.display_name))
                transactions |= line.transaction_id
                if float_compare(line.amount, line.amount_pending, precision_digits=2) == 1:
                    raise UserError(_(u'El monto pagado %s no puede se mayor al monto pendiente %s de la transaccion %s') % (line.amount, line.amount_pending, line.transaction_id.display_name))
            for line in self.collection_register_ids:
                aml_data = counterpart_aml_dict.copy()
                if not line.transaction_id.category_transaction_id.account_debit:
                    raise UserError(_(u'No se encuentra configurada la cuenta contable %s del tipo de rubro %s') % (line.transaction_id.category_transaction_id.display_name))
                aml_data.update({
                    'account_id': line.transaction_id.category_transaction_id.account_debit.id,
                    'debit': 0.0,
                    'credit': line.amount,
                    })
                aml_obj.create(aml_data)
        else:
            return super(AccountPayment, self).get_counterpart_lines(debit, credit, amount_currency, move, currency_id, invoice_currency)

class AccountPaymentLine(models.Model):

    _inherit = 'account.payment.line'

    slip_id = fields.Many2one('hr.payslip', string=u'Payslip',
                              required=False, readonly=False, states={}, help=u"", ondelete="restrict")


class AccountPaymentHrCollectionRegister(models.Model):

    _name = 'account.payment.hr.collection.register'


    payment_id = fields.Many2one('account.payment', string=u'Pago Asociado',
                                 required=False, readonly=False, states={}, help=u"", ondelete="cascade")
    transaction_id = fields.Many2one('hr.scheduled.transaction', string=u'Transaccion Programada',
                                     required=False, readonly=False, states={}, help=u"", ondelete="restrict")

    amount_pending = fields.Float(string=u'Monto Pendiente', digits=dp.get_precision('Account'),
                                  required=False, readonly=True, states={}, help=u"")

    amount = fields.Float(string=u'Monto Pagado', digits=dp.get_precision('Account'),
                                  required=False, readonly=False, states={}, help=u"")



    @api.constrains(
        'amount_pending',
        'amount',
                    )
    def _check_function_constraint(self):
        if self.amount > self.amount_pending:
            return UserError(_(u'El monto pagado %s no puede se mayor al monto pendiente %s') % (self.amount, self.amount_pending))
        if self.amount <= 0:
            return UserError(_(u'El monto pagado %s debe ser mayor que cero') % (self.amount))


    @api.onchange('transaction_id')
    def _onchange_transaction_id(self):
        if self.transaction_id:
            self.amount_pending = self.transaction_id.amount_pending
            self.amount = self.transaction_id.amount_pending
        else:
            self.amount_pending = 0