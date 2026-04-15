# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
import re
from werkzeug import url_encode
import logging
_logger = logging.getLogger(__name__)


class HrExpenseSheet(models.Model):
    
    _inherit = 'hr.expense.sheet' 

    
    def generate_payment(self):
        self.ensure_one()
        payment_model = self.env['account.payment']
        aml_model = self.env['account.move.line']
        amount_payment = sum([s.total_expense for s in self.expense_line_ids])
        lines_data = []
        if not self.paid_journal_id:
            raise UserError(_(u'Debe escoger una forma de pago para poder continuar'))
        for expense in self.expense_line_ids:
            for line in expense.invoice_data_ids:
                if line.type == 'invoice':
                    invoice = line.invoice_line_id.invoice_id
                    if invoice.state == 'draft':
                        raise UserError(_(u'La factura %s se encuentra en estado borrador para proceder con el pago debe de aprobar primero estas facturas') % invoice.display_name)
                    if invoice.state == 'open':
                        account_id = invoice.account_id.id
                        aml = aml_model.browse()
                        for l in invoice.move_id.line_ids:
                            if l.account_id.id == invoice.account_id.id:
                                aml = l
                                break
                        lines_data.append((0,0, {
                            'account_id': account_id,
                            'name': line.description,
                            'partner_id': invoice.commercial_partner_id.id,
                            'invoice_id': invoice.id,
                            'aml_id': aml.id,
                            'amount': line.subtotal,
                            }))
                else:
                    account_id = False
                    if line.product_id:
                        if not line.product_id.property_account_expense_id:
                            raise UserError(_(u'Debe configurar la cuenta por defecto de gastos para el producto de gasto %s') % line.product_id.display_name)
                        account_id = line.product_id.property_account_expense_id.id
                    else:
                        if not self.env.company.default_expense_account_id:
                            raise UserError(_(u'Debe configurar la cuenta por defecto de gastos de empleados'))
                        account_id = self.env.company.default_expense_account_id.id
                    lines_data.append((0,0, {
                        'account_id': account_id,
                        'name': line.description,
                        'partner_id': None,
                        'invoice_id': None,
                        'aml_id': None,
                        'amount': line.subtotal,
                        'account_analytic_id': line.account_analytic_id.id,
                        }))
        payment_data = {
            'partner_id': self.employee_id.address_home_id.id,
            'journal_id': self.paid_journal_id.id,
            'payment_type': 'outbound',
            'payment_method_id': self.payment_method_id.id,
            'check_id': self.check_id.id,
            'city_id': self.city_id.id,
            'date_release': self.date_release,
            'beneficiary': self.beneficiary,
            'payment_date': self.payment_date,
            'partner_type': 'supplier',
            'communication': u'Pago de %s' % self.name,
            'amount': amount_payment,
            'line_ids': lines_data,
            'hr_payment_type': 'normal',
            'currency_id': self.env.company.currency_id.id,
            }
        self.payment_id = payment_model.create(payment_data)
        self.payment_id.post()
        payment = self.payment_id
        # Log the payment in the chatter
        body = (_("A payment of %s %s with the reference <a href='/mail/view?%s'>%s</a> related to your expense %s has been made.") % (payment.amount, payment.currency_id.symbol, url_encode({'model': 'account.payment', 'res_id': payment.id}), payment.name, self.name))
        self.message_post(body=body)
        self.write({
            'state': 'done',
            })
        action = self.env.ref('account.action_account_payments_payable').read()[0]
        action['domain'] = [('id', '=', self.payment_id.id),]
        return action
    
    payment_method_id = fields.Many2one('account.payment.method', string=u'Método de Pago', 
                                        required=False, readonly=True, states={'post': [('readonly', False)]})
    payment_method_code = fields.Char(related='payment_method_id.code',
                                      help="Technical field used to adapt the interface to the payment type selected.", readonly=True)
    paid_journal_id = fields.Many2one('account.journal', string=u'Forma de Pago', 
                                      required=False, readonly=True, 
                                      states={'post': [('readonly', False)]}, 
                                      help=u"", ondelete="restrict") 
    check_id = fields.Many2one('check.note', string=u'Cheque', 
                               required=False, readonly=True, 
                               states={'post': [('readonly', False)]}, 
                               help=u"", ondelete="restrict")
    payment_date = fields.Date(string=u'Fecha de Pago', 
                               readonly=False,
                               states={'post': [('readonly', False)]}, 
                          ) 
    date_release = fields.Date(string=u'Fecha de Postfechado', 
                               readonly=True, 
                               states={'post': [('readonly', False)]}, 
                               )
    type_bank_account = fields.Selection(string=u'Tipo de Cuenta Bancaria', 
                                         related="paid_journal_id.type_bank_account") 
    beneficiary = fields.Char(string=u'Beneficiario', index=True, 
                              required=False, readonly=True, 
                              states={'post': [('readonly', False)]}, help=u"")
    city_id = fields.Many2one('res.partner.canton', string=u'Ciudad de Emisión', 
                              default=lambda self: self.env.company.partner_id.canton_id.id,
                              required=False, readonly=True, 
                              states={'post': [('readonly', False)]}, help=u"")
    
    payment_id = fields.Many2one('account.payment', string=u'Pago Realizado',
                                 required=False, readonly=True, states={}, help=u"", ondelete="cascade") 
    
    
    @api.depends(
        'expense_line_ids',
        'expense_line_ids.total_expense',
                 )
    def _get_totals(self):
        self.total_expense = sum([l.total_expense for l in self.expense_line_ids])
    total_expense = fields.Float(u'Total', digits=dp.get_precision('Account'), 
                                 store=True, compute='_get_totals', help=u"") 

    
    @api.depends(
        'paid_journal_id',
        )
    def _compute_hide_payment_method(self):
        if not self.paid_journal_id:
            self.hide_payment_method = True
            return
        journal_payment_methods = self.paid_journal_id.outbound_payment_method_ids
        self.hide_payment_method = len(journal_payment_methods) == 1 and journal_payment_methods[0].code == 'manual'

    hide_payment_method = fields.Boolean(compute='_compute_hide_payment_method',
        help="Technical field used to hide the payment method if the selected journal has only one available which is 'manual'")

    @api.onchange('paid_journal_id')
    def _onchange_journal(self):
        if self.paid_journal_id:
            payment_methods = self.paid_journal_id.outbound_payment_method_ids
            self.payment_method_id = payment_methods and payment_methods[0] or False
            payment_type = 'outbound'
            return {'domain': {'payment_method_id': [('payment_type', '=', payment_type), ('id', 'in', payment_methods.ids)]}}
        return {}

    
    def action_sheet_move_create(self):
        for line in self.expense_line_ids:
            line.invoice_data_ids.create_invoice()
        if self.payment_mode == 'own_account':
            self.write({'state': 'post'})
        else:
            self.write({'state': 'done'})
        return True


class HrExpense(models.Model):

    _inherit = 'hr.expense'

    invoice_data_ids = fields.One2many('ec.expense.invoice.data', 'cash_expense_id', string=u'Informacion de Gastos',
                                       required=False, readonly=False, states={}, help=u"") 
    invoice_ids = fields.One2many('account.move', 'expense_id', string=u'Facturas', 
                                  required=False, readonly=True, states={}, help=u"") 

    product_id = fields.Many2one('product.product', string='Product', readonly=True, 
                                 states={'draft': [('readonly', False)], 'refused': [('readonly', False)]}, 
                                 domain=[('can_be_expensed', '=', True)], required=False)
    # product_uom_id = fields.Many2one('product.uom', string='Unit of Measure', required=False, 
    #                                  readonly=True, 
    #                                  states={'draft': [('readonly', False)], 'refused': [('readonly', False)]}, 
    #                                  default=lambda self: self.env['product.uom'].search([], limit=1, order='id'))
    unit_amount = fields.Float(string='Unit Price', readonly=True, required=False, 
                               states={'draft': [('readonly', False)], 'refused': [('readonly', False)]}, 
                               digits=dp.get_precision('Product Price'))
    quantity = fields.Float(required=False, readonly=True, 
                            states={'draft': [('readonly', False)], 'refused': [('readonly', False)]}, 
                            digits=dp.get_precision('Product Unit of Measure'), default=1)

    
    @api.depends(
        'invoice_data_ids',
        'invoice_data_ids.subtotal',
                 )
    def _get_totals(self):
        self.total_expense = sum([l.subtotal for l in self.invoice_data_ids])
        self.total_expense_invoice = sum([l.subtotal for l in self.invoice_data_ids if l.type == 'invoice'])
        self.total_expense_no_invoice = sum([l.subtotal for l in self.invoice_data_ids if l.type == 'no_invoice'])


    total_expense_invoice = fields.Float(u'Con Factura', digits=dp.get_precision('Account'), 
                                 store=True, compute='_get_totals', help=u"") 
    total_expense_no_invoice = fields.Float(u'Sin Factura', digits=dp.get_precision('Account'), 
                                 store=True, compute='_get_totals', help=u"") 
    total_expense = fields.Float(u'Total Gastos', digits=dp.get_precision('Account'), 
                                 store=True, compute='_get_totals', help=u"") 

    
    def action_move_create(self):
        return True
    
    
    def _get_context_for_report(self):
        self.ensure_one()
        ctx = self.env.context.copy()
        return ctx

    
    def get_print_expense(self):
        return self.env.ref('ec_payroll.action_report_expense').report_action(self, config=False)


    @api.depends('sheet_id', 'sheet_id.payment_id', 'sheet_id.state')
    def _compute_state(self):
        for expense in self:
            if not expense.sheet_id:
                expense.state = "draft"
            elif expense.sheet_id.state == "cancel":
                expense.state = "refused"
            elif not expense.sheet_id.payment_id:
                expense.state = "reported"
            else:
                expense.state = "done"



class HrExpenseInvoiceData(models.Model):

    _inherit = 'ec.expense.invoice.data'

    
    # @api.constrains(
    #     'document_number', 
    #     'authorization_third_id', 
    #     'date_invoice',
    #     'type')
    # def _check_document_number(self):
    #     if self.type != 'invoice': return True
    #     auth_s_model = self.env['sri.authorization.supplier']
    #     doc_model = self.env['sri.type.document']
    #     if self.document_number:
    #         padding_auth = "1,9"
    #         if self.authorization_third_id and self.authorization_third_id.padding > 0:
    #             padding_auth = self.authorization_third_id.padding
    #         cadena='(\d{3})+\-(\d{3})+\-(\d{%s})' % (padding_auth)
    #         if not self.foreign and not re.match(cadena, self.document_number):
    #             raise ValidationError(_(u"The número de documento no es correcto, debe ser de la forma 00X-00X-000XXXXXX, X es un número"))
    #         if self.document_type == 'normal' and self.authorization_third_id:
    #             if not auth_s_model.check_number_document('in_invoice', self.document_number, self.authorization_third_id, self.date_invoice, False, self.foreign):
    #                 raise ValidationError(_(u"Ya existe otro documento con el mismo número"))
    #         auth_s_model.validate_unique_document_partner('in_invoice', self.document_number, self.partner_id.id, False, self.foreign)
    #         doc_model.validate_unique_value_document('in_invoice', self.document_number, self.env.company.id, False)

    # @api.model
    # def _get_default_tax_support(self):
    #     company = self.env.company
    #     support_tax_rec = company['default_in_invoice_id']
    #     return support_tax_rec


    # expense_id = fields.Many2one('hr.expense', string=u'Gasto', required=True, readonly=False, states={}, help=u"",
    #                              ondelete="cascade")
    # document_number = fields.Char(u'Número de Documento', size=17, required=False, index=True, help=u"",)
    # date_invoice = fields.Date(string=u'Fecha de Factura', readonly=False, required=False, index=True, copy=False,
    #                            states={}, help=u"")
    # type = fields.Selection([
    #     ('invoice', 'Factura'),
    #     ('no_invoice', 'Gasto sin Factura'),
    #     ], string='Tipo de Gasto', 
    #     readonly=False, required=True) 
    # invoice_line_id = fields.Many2one('account.move.line', string=u'Linea de Factura', 
    #                                   required=False, readonly=False, states={}, help=u"", ondelete="cascade") 
    # partner_id = fields.Many2one('res.partner', string=u'Proveedor', 
    #                              required=False, readonly=False, states={}, help=u"", ondelete="cascade") 
    # foreign = fields.Boolean(u'Empresa Extranjera?', readonly=True, related='partner_id.foreign', help=u"",)
    # document_type = fields.Selection([
    #     ('normal',u'Normal'),
    #     ('electronic',u'Electrónico'),
    #     ], string='Tipo de Documento', 
    #     readonly=False, required=False, states={}, help=u"") 
    # authorization_third_id = fields.Many2one('sri.authorization.supplier', 
    #                                          u'Autorización de Tercero', ondelete="restrict", help=u"",)
    # electronic_authorization = fields.Char(u'Autorización Electrónica', size=49)
    # description = fields.Char(string=u'Descripción', index=True, 
    #                           required=True, readonly=False, states={}, help=u"") 
    # product_id = fields.Many2one('product.product', string=u'Producto', domain=[('can_be_expensed', '=', True)], ondelete="restrict") 
    # quantity = fields.Float(u'Cantidad', 
    #                         digits=dp.get_precision('Product Unit of Measure'), 
    #                         readonly=False, required=True, states={}, help=u"", default=1) 
    # price_unit = fields.Float(u'Precio Unitario', 
    #                         digits=dp.get_precision('Product Price'), 
    #                         readonly=False, required=True, states={}, help=u"")
    # # tax_ids = fields.Many2many('account.tax',
    # #     'rel_account_tax_expense', 'expense_line_id', 'tax_id',
    # #     default=lambda self: self.env.company.default_tax_expense_ids and self.env.company.default_tax_expense_ids.ids or [],
    # #     string=u'Impuestos', domain=[('type_tax_use','=','purchase')])
    # tax_ids = fields.Many2many('account.tax', 'rel_account_tax_expense_account',
    #     'account_id', 'tax_id', string='Impuestos', context={'append_type_to_tax_name': True})
    # account_analytic_id = fields.Many2one('account.analytic.account',
    #     string=u'Cuenta Analítica')
    # tax_support_id = fields.Many2one('sri.tax.support', u'Sustento Tributario', default=_get_default_tax_support, help=u"",)
    # analytic_tag_ids = fields.Many2many('account.analytic.tag', string=u'Etiqueta Analítica')

    
    # @api.depends(
    #     'quantity',
    #     'price_unit',
    #     'tax_ids',
    #     'type',
    #              )
    # def _get_subtotal(self):
    #     currency = self.env.company.currency_id
    #     tax_model = self.env['account.tax']
    #     ret_iva_tax = tax_model.browse()
    #     ret_renta_tax = tax_model.browse()
    #     iva_tax = tax_model.browse()
    #     taxes = False
    #     for tax in self.tax_ids:
    #         if tax.type_ec == 'iva':
    #             iva_tax |= tax
    #         if tax.type_ec == 'retencion_renta':
    #             ret_renta_tax |= tax
    #         if tax.type_ec == 'retencion_iva':
    #             ret_iva_tax |= tax
    #     if self.tax_ids and self.type == 'invoice':
    #         taxes = self.tax_ids.compute_all(self.price_unit, currency, self.quantity, product=None, partner=self.partner_id)
    #     self.subtotal = taxes['total_included'] if taxes else self.quantity * self.price_unit
    #     if iva_tax:
    #         taxes = iva_tax.compute_all(self.price_unit, currency, self.quantity, product=None, partner=self.partner_id)
    #         self.subtotal_iva = sum([t['amount'] for t in taxes['taxes']])
    #     if ret_iva_tax:
    #         taxes = ret_iva_tax.compute_all(self.price_unit, currency, self.quantity, product=None, partner=self.partner_id)
    #         self.subtotal_retencion_iva = sum([t['amount'] for t in taxes['taxes']])
    #     if ret_renta_tax:
    #         taxes = ret_renta_tax.compute_all(self.price_unit, currency, self.quantity, product=None, partner=self.partner_id)
    #         self.subtotal_retencion_renta = sum([t['amount'] for t in taxes['taxes']])
    # subtotal_iva = fields.Float(u'IVA', 
    #                         digits=dp.get_precision('Account'), 
    #                         store=True, compute='_get_subtotal', help=u"") 
    # subtotal_retencion_iva = fields.Float(u'Retención IVA', 
    #                         digits=dp.get_precision('Account'), 
    #                         store=True, compute='_get_subtotal', help=u"") 
    # subtotal_retencion_renta = fields.Float(u'Retención I.R.', 
    #                         digits=dp.get_precision('Account'), 
    #                         store=True, compute='_get_subtotal', help=u"") 
    # subtotal = fields.Float(u'Subtotal', 
    #                         digits=dp.get_precision('Account'), 
    #                         store=True, compute='_get_subtotal', help=u"") 

    @api.onchange(
                  'product_id',
                  'type',
                  )
    def onchange_product_id(self):
        if self.product_id and self.type == 'invoice':
            fpos = self.partner_id.property_account_position_id
            if fpos:
                self.tax_ids = fpos.map_tax(self.product_id.supplier_taxes_id.filtered(lambda r: r.company_id.id == self.env.company.id))
            else:
                self.tax_ids = self.product_id.supplier_taxes_id.ids

    @api.onchange(
                  'document_type',
                  'authorization_third_id',
                  'type',
                  'partner_id',
                  'invoice_date',
                  'document_number',
                  )
    def onchange_number_in(self):
        domain = {}
        warning = {}
        auth_supplier_model = self.env['sri.authorization.supplier']
        invoice_date = self.invoice_date
        if not self.invoice_date:
            invoice_date = fields.Date.context_today(self)
        if self.document_type == 'electronic':
            self.authorization_third_id = None
            return {}
        invoice_type_aux = 'in_invoice'
        auth_type = 'invoice'
        if self.env.context.get('documento_no_sri', False):
            return {}
        if self.partner_id:
            if self.partner_id.foreign:
                return {}
        document_number = self.document_number
        if self.authorization_third_id and self.partner_id and not self.document_number:
            auth = self.authorization_third_id
            #si el numero esta completo, verificar si la autorizacion seleccionada es valida para el numero ingresado
            #si es valida no cambiar el numero, 
            #pero si no es valida, cambiar el numero para que el usuario ingrese el numero correcto para la autorizacion seleccionada
            is_valid = True
            try:
                agency, printer_point, sequence = document_number.split("-")
                auth_supplier_model.check_number_document(invoice_type_aux, self.document_number, auth, self.invoice_date, 
                                                          self.ids and self.ids[0] or False, auth.partner_id.foreign)
            except:
                is_valid = False
            if not is_valid:
                self.document_number = "%s-%s-" % (auth.agency, auth.printer_point)
            return {}
        if self.document_number and self.document_type == 'electronic' and self.partner_id:
            #si es electronico y ya tengo agencia y punto de impresion, completar el numero
            number_data = self.document_number.split('-') 
            if len(number_data) == 3:
                try:
                    number_last = int(number_data[2])
                except:
                    warning = {'title': 'Advertencia!!!',
                               'message': _(u"The número de documento no es correcto, debe ser de la forma 00X-00X-000XXXXXX, X es un número")
                               }
                    number_last = False
                if number_last:
                    #cuando deberia ser el padding(9 por defecto)
                    document_number = "%s-%s-%s" % (number_data[0], number_data[1], auth_supplier_model.fill_padding(number_last, 9))
                    self.document_number = document_number 
                    #validar la duplicidad de documentos electronicos
                    auth_supplier_model.validate_unique_document_partner(invoice_type_aux, self.document_number, self.partner_id.id, self.id, self.foreign)
            else:
                warning = {'title': 'Advertencia!!!',
                           'message': _(u"The número de documento no es correcto, debe ser de la forma 00X-00X-000XXXXXX, X es un número")
                           }
            return {'domain':domain, 'warning': warning}
        if self.document_number and not self.partner_id and self.type:
            self.document_number = ''
            warning = {
                       'title': _(u'Advertencia!!!'),
                       'message':_(u'Usted debe seleccionar primero la empresa para proceder con esta acción'),
                       }
            return {'domain':domain, 'warning': warning}
        auth_data = auth_supplier_model.get_supplier_authorizations(auth_type, self.partner_id.id, self.document_number, invoice_date)
        #si hay multiples autorizaciones, pero una de ellas es la que el usuario ha seleccionado, tomar esa autorizacion
        #xq sino, nunca se podra seleccionar una autorizacion
        if auth_data.get('multi_auth', False):
            if self.authorization_third_id and self.authorization_third_id.id in auth_data.get('auth_ids', []) and self.document_number:
                auth_use = self.authorization_third_id
                number_data = self.document_number.split('-')
                number_to_check = ''
                if len(number_data) == 3:
                    number_to_check = number_data[2]
                elif len(number_data) == 1:
                    try:
                        number_to_check = str(int(number_data[0]))
                    except:
                        pass
                if number_to_check and int(number_to_check) >= auth_use.first_sequence and int(number_to_check) <= auth_use.last_sequence:
                    document_number = auth_use.agency + '-' + auth_use.printer_point + '-' + auth_supplier_model.fill_padding(number_to_check, auth_use.padding)
                    self.document_number = document_number
                    #si hay ids pasar el id para validar sin considerar el documento actual
                    auth_supplier_model.check_number_document(invoice_type_aux, document_number, auth_use, invoice_date, self.id, self.foreign)
                    #Si ya escogio una autorizacion, ya deberia dejar de mostrar el mensaje
                    if auth_data.get('message'): auth_data.update({'message': ''})
                else:
                    self.document_number = ''
                    #Si ya escogio una autorizacion, ya deberia dejar de mostrar el mensaje
                    if auth_data.get('message'): auth_data.update({'message': ''})
            else:
                self.document_number = ''
            if auth_data.get('message',''):
                warning = {
                           'title': _(u'Advertencia!!!'),
                           'message':auth_data.get('message',''),
                           }
            return {'domain':domain, 'warning': warning}
        if not auth_data.get('auth_ids', []):
            if auth_data.get('message',''):
                warning = {
                           'title': _(u'Advertencia!!!'),
                           'message':auth_data.get('message',''),
                           }
            return {'domain':domain, 'warning': warning}
        else:
            auth_ids = auth_data.get('auth_ids', [])
            if auth_ids:
                self.document_number = auth_data.get('res_number', '')
                self.authorization_third_id = auth_ids[0]
        #si el numero esta ingresado, validar duplicidad
        document_number = auth_data.get('res_number', '')
        if self.document_number and len(document_number.split('-')) == 3 and auth_ids:
            auth = auth_supplier_model.browse(auth_ids[0])
            #si hay ids pasar el id para validar sin considerar el documento actual
            auth_supplier_model.check_number_document(invoice_type_aux, document_number, auth, invoice_date, self.id, self.foreign)
        return {'domain':domain, 'warning': warning}
    
    
    def create_invoice(self):
        invoice_model = self.env['account.move']
        for line in self:
            if line.type != 'invoice': continue
            account_id = False
            if line.product_id:
                if not line.product_id.property_account_expense_id:
                    raise UserError(_(u'Debe configurar la cuenta por defecto de gastos para el producto de gasto %s') % line.product_id.display_name)
                account_id = line.product_id.property_account_expense_id.id
            else:
                if not self.env.company.default_expense_account_id:
                    raise UserError(_(u'Debe configurar la cuenta por defecto de gastos de empleados'))
                account_id = self.env.company.default_expense_account_id.id
            #Busco si fue ingresada por contabilidad la factura
            invoice_finded = invoice_model.search([
                ('type', '=', 'in_invoice'),
                ('partner_id', '=', line.partner_id.id),
                ('document_number', '=', line.document_number),
                ])
            if invoice_finded:
                new_invoice = invoice_finded[0]
                line.expense_id.write({
                    'invoice_ids': [(4, new_invoice.id)],
                    })
                #agregando una nueva linea en la misma factura
                for iline in new_invoice.invoice_line_ids:
                    other_line = self.search([('invoice_line_id', '=', iline.id)])
                    if other_line:
                        new_iline = self.env['account.move.line'].create({
                            'invoice_id': new_invoice.id,
                            'name': line.description,
                            'origin': line.expense_id.name,
                            'account_id': account_id,
                            'price_unit': line.price_unit,
                            'quantity': line.quantity,
                            'discount': 0.0,
                            'invoice_line_tax_ids': line.tax_ids and [(6, 0, line.tax_ids.ids)] or [],
                            'account_analytic_id': line.account_analytic_id.id,
                            'product_id': line.product_id.id,
                            })
                        line.write({
                            'invoice_line_id': new_iline.id,
                            })
                        new_invoice.button_reset_taxes()
                continue
            invoice_data = {
                'document_type': line.document_type,
                'authorization_third_id': line.authorization_third_id.id,
                'electronic_authorization': line.electronic_authorization,
                'date': line.date,
                'document_number' : line.document_number,
                'name': line.description,
                'origin': line.expense_id.name,
                'type': 'in_invoice',
                'reference': False,
                'account_id': line.partner_id.property_account_payable_id.id,
                'partner_id': line.partner_id.id,
                'partner_shipping_id': line.partner_id.id,
                'invoice_line_ids': [(0, 0, {
                    'name': line.description,
                    'origin': line.expense_id.name,
                    'account_id': account_id,
                    'price_unit': line.price_unit,
                    'quantity': line.quantity,
                    'discount': 0.0,
                    'invoice_line_tax_ids': line.tax_ids and [(6, 0, line.tax_ids.ids)] or [],
                    'account_analytic_id': line.account_analytic_id.id,
                    'product_id': line.product_id.id,
                })],
                'currency_id': self.env.company.currency_id.id,
                'fiscal_position_id': line.partner_id.property_account_position_id.id,
                'tax_support_id': line.tax_support_id.id,
                }
            new_invoice = invoice_model.create(invoice_data)
            line.expense_id.write({
                'invoice_ids': [(4, new_invoice.id)],
                })
            line.write({
                'invoice_line_id': new_invoice.invoice_line_ids[0].id,
                })
        return True

