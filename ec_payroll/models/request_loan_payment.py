# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _
from datetime import datetime, timedelta, date
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

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter
import io

_STATES = {'draft': [('readonly', False)]}


class ReportXLSPayroll(models.AbstractModel):
    _name = 'report.ec_payroll.report_xls_payroll'

    @api.model
    def create_workbook(self, page_string=''):
        fp = io.BytesIO()
        # crear el reporte en memoria, no en archivo
        workbook = xlsxwriter.Workbook(fp, {'in_memory': True, 'constant_memory': False})
        worksheet = workbook.add_worksheet(page_string)
        FORMATS = {
            'title': workbook.add_format(
                {'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': 'white', 'bg_color': '#0F1570',
                 'border': 1}),
            'border': workbook.add_format({'border': 1}),
            'bold': workbook.add_format({'bold': True, 'text_wrap': True}),
            'single_bold': workbook.add_format({'bold': True}),
            'bold_border': workbook.add_format({'bold': True, 'border': 1}),
            'number': workbook.add_format({'num_format': '#,##0.00'}),
            'number_0f': workbook.add_format({'num_format': '#,##0'}),
            'money': workbook.add_format({'num_format': '$#,##0.00'}),
            'number_bold': workbook.add_format({'num_format': '#,##0.00', 'bold': True}),
            'money_bold': workbook.add_format({'num_format': '$#,##0.00', 'bold': True}),
            'date': workbook.add_format({'num_format': 'dd/mm/yyyy'}),
            'datetime': workbook.add_format({'num_format': 'dd/mm/yyyy h:m:s'}),
            'date_bold': workbook.add_format({'num_format': 'dd/mm/yyyy', 'bold': True}),
            'datetime_bold': workbook.add_format({'num_format': 'dd/mm/yyyy h:m:s', 'bold': True}),
            'merge_center': workbook.add_format({'align': 'center', 'valign': 'vcenter', 'bold': True}),
            'merge_center_single': workbook.add_format({'align': 'center', 'valign': 'vcenter'}),
            'merge_left': workbook.add_format({'align': 'left', 'valign': 'vcenter'}),
            'merge_right': workbook.add_format({'align': 'right', 'valign': 'vcenter', 'bold': True}),
            'aqua': workbook.add_format({'font_color': '#909C9D', 'num_format': '#,##0.00'}),
        }
        return fp, workbook, worksheet, FORMATS

    @api.model
    def get_workbook_binary(self, fp, workbook):
        workbook.close()
        fp.seek(0)
        data = fp.read()
        fp.close()
        return data

    def get_report_xls(self, data):
        fp, workbook, worksheet, FORMATS = self.create_workbook("Comprobante Contable")
        report_format32 = workbook.add_format(
            {'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'font_color': 'black', 'border': 1})
        report_format33 = workbook.add_format(
            {'font_size': 10, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': 'black',
             'bg_color': '#dcdde6', 'border': 1})
        report_format34 = workbook.add_format(
            {'font_size': 10, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': 'black',
             'border': 1})
        report_format4 = workbook.add_format(
            {'font_size': 10, 'bold': True, 'align': 'left', 'valign': 'vcenter', 'font_color': 'black',
             'bg_color': '#dcdde6', 'border': 1})
        report_format5 = workbook.add_format(
            {'font_size': 10, 'align': 'left', 'valign': 'vcenter', 'font_color': 'black', 'border': 1})
        date_format = workbook.add_format(
            {'num_format': 'dd/mm/yyyy', 'font_size': 10,'align': 'left', 'valign': 'vcenter', 'font_color': 'black', 'border': 1})
        current_row = 0
        worksheet.merge_range(current_row, 0,current_row, 13, _('Solicitud de Pago de Anticipo/Prestamo'), report_format33)
        current_row += 1
        worksheet.merge_range(current_row, 0,current_row, 1, _('Transaccion Programada :'), report_format4)
        worksheet.write(current_row, 2, data.rule_id.name, report_format5)
        current_row += 1
        worksheet.merge_range(current_row, 0,current_row, 1, _('Fecha Solicitud: :'), report_format4)
        worksheet.write(current_row, 2, str(data.request_date), report_format5)
        worksheet.write(current_row, 3, _('Usuario que Solicita:'), report_format4)
        worksheet.write(current_row, 4, str(data.request_user_id.name), report_format5)
        current_row += 2

        worksheet.merge_range(current_row, 0, current_row, 7, _('Datos Generales'), report_format33)
        worksheet.write(current_row, 8, _('Total'), report_format4)
        worksheet.merge_range(current_row, 9, current_row, 12, _('Forma de Pago'), report_format33)
        worksheet.write(current_row, 13, _('Otros'), report_format4)
        current_row += 1
        worksheet.write(current_row, 0, _('#'), report_format4)
        worksheet.write(current_row, 1, _('Identificacion'), report_format4)
        worksheet.write(current_row, 2, _('Empleado'), report_format4)
        worksheet.write(current_row, 3, _('Región'), report_format4)
        worksheet.write(current_row, 4, _('Ciudad'), report_format4)
        worksheet.write(current_row, 5, _('Departamento'), report_format4)
        worksheet.write(current_row, 6, _('Dias trabajados'), report_format4)
        worksheet.write(current_row, 7, _('Monto pendiente'), report_format4)
        worksheet.write(current_row, 8, _('Total a recibir'), report_format4)
        worksheet.write(current_row, 9, _('Forma de pago'), report_format4)
        worksheet.write(current_row, 10, _('No. Cta/Cheque'), report_format4)
        worksheet.write(current_row, 11, _('Tipo Cta. Bancaria'), report_format4)
        worksheet.write(current_row, 12, _('Bco. Empleado'), report_format4)
        worksheet.write(current_row, 13, _('Centro de Costo'), report_format4)


        current_row += 1
        totales_pay = 0.00
        count = 0
        for dat in data.line_ids:
            count += 1
            worksheet.write(current_row, 0, count, report_format32)
            worksheet.write(current_row, 1, dat.employee_id.identification_id or ' ', report_format5)
            worksheet.write(current_row, 2, dat.employee_id.name if dat.employee_id else '  ', report_format5)
            region = ' '
            if dat.employee_id.contract_id:
                if dat.employee_id.contract_id.region_decimos == 'costa':
                    region = 'Costa'
                else:
                    region = 'Sierra'
            worksheet.write(current_row, 3, region, report_format5)
            worksheet.write(current_row, 4, dat.employee_id.state_id.name if dat.employee_id.state_id else ' ', report_format5)
            worksheet.write(current_row, 5, dat.employee_id.department_id.name if dat.employee_id.department_id else ' ', report_format5)
            dias = False
            if dat.employee_id.contract_id:
                fecha_contrato = dat.employee_id.contract_id.date_start
                fecha_actual = data.request_date
                dias = (fecha_actual - fecha_contrato) / timedelta(days=1)
            if dias < 15 :
                diasd = dias
            else:
                diasd = 15
            worksheet.write(current_row, 6, diasd, report_format5)
            worksheet.write(current_row, 7, '$ ' + str(abs(dat.amount_pending)), report_format32)
            worksheet.write(current_row, 8, '$ ' + str(abs(dat.amount)), report_format32)
            totales_pay += dat.amount
            forma_p = ' '
            if dat.employee_id.payment_method == 'CUE':
                forma_p = 'Transferencia'
            if dat.employee_id.payment_method == 'EFE':
                forma_p = 'Efectivo'
            if dat.employee_id.payment_method == 'CHE':
                forma_p = 'Cheque'
            worksheet.write(current_row, 9, forma_p, report_format5)
            worksheet.write(current_row, 10, dat.employee_id.bank_account_id.acc_number if dat.employee_id.bank_account_id else ' ', report_format5)
            tipo_cta = ' '
            if dat.employee_id.bank_account_id.type_account == 'savings':
                tipo_cta = 'Ahorros'
            if dat.employee_id.bank_account_id.type_account == 'current':
                tipo_cta = 'Corriente'
            if dat.employee_id.bank_account_id.type_account == 'virtual':
                tipo_cta = 'Virtual'
            worksheet.write(current_row, 11, tipo_cta, report_format5)
            worksheet.write(current_row, 12, dat.employee_id.bank_account_id.bank_id.name if dat.employee_id.bank_account_id else ' ', report_format5)
            centro_costo = ""
            if dat.employee_id.contract_id.analytic_distribution:
                for key in dat.employee_id.contract_id.analytic_distribution:
                    analytic_id = self.env['account.analytic.account'].search([('id', '=', int(key))])
                    centro_costo += analytic_id.name + ", "
            worksheet.write(current_row, 13, centro_costo, report_format5)
            current_row += 1
        worksheet.merge_range(current_row, 0, current_row, 7, _('TOTALES'), report_format33)
        worksheet.write(current_row, 8, '$ ' + str(round(totales_pay,2)), report_format32)

        COLUM_SIZES = [5, 15, 30, 15, 15, 15, 10, 15, 15, 20, 20, 20, 25, 40, 18, 18, 18, 18, 18, 18, 18, 18, 18, 18]
        for position in range(len(COLUM_SIZES)):
            worksheet.set_column(position, position, COLUM_SIZES[position])
        return self.get_workbook_binary(fp, workbook)




class RequestLoanPayment(models.Model):
    '''
    Solicitud de Pago de Anticipo/Prestamo
    '''
    _name = 'request.loan.payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Solicitud de Pago de Anticipo/Prestamo'
    _rec_name = 'number'

    def action_view_request_loan_lines(self):
        self.ensure_one()
        action = self.env.ref('ec_payroll.action_request_loan_line_tree').read()[0]
        action['domain'] = [('request_loan_line_id', 'in', self.line_ids.ids)]
        action['context'] = {'default_request_loan_line_id': self.id}
        return action


    def _get_is_accountant(self):
        for res in self:
            is_accountant = False
            if res.accountant_id:
                if res.accountant_id.id == res.env.user.id:
                    is_accountant = True
            res.is_accountant = is_accountant


    # @api.model
    # def default_get(self, fields):
    #     res = super(RequestLoanPayment, self).default_get(fields)
    #     res["accountant_id"] = False
    #     if self.env.company.accounting_responsible:
    #         res["accountant_id"] = self.env.company.accounting_responsible.id
    #     return res

    number = fields.Char(string='# de Documento', index=True, required=False, readonly=True)
    state = fields.Selection([
        ('draft','Borrador'),
        ('requested','Solicitado'),
        ('done','Realizado'),
    ], string='Estado',
        readonly=True, required=True, default="draft",)
    employee_id = fields.Many2one('hr.employee', string=u'Empleado',
                                  required=True, readonly=True, states=_STATES, help=u"", ondelete="restrict")
    accountant_id = fields.Many2one('res.users', string=u'Contable a Procesar',
                                    required=False, readonly=True, states=_STATES, help=u"", ondelete="restrict")
    request_user_id = fields.Many2one('res.users', string=u'Usuario Solicitante', default=lambda self: self.env.user.id,
                                      required=True, readonly=True, states=_STATES, help=u"", ondelete="cascade")
    request_date = fields.Date(string=u'Fecha de Solicitud', default=fields.Date.today(),
                               readonly=True, required=True, index=True, copy=False, states=_STATES, help=u"")
    payment_ids = fields.One2many('account.payment', 'request_loan_payment_id', string=u'Pagos Asociados',
                                  required=False, readonly=True, states={}, help=u"")

    account_payment_id = fields.Many2one('hr.account.payment', ondelete='restrict')

    @api.onchange("employee_id")
    def obtener_linea(self):
        #if self.employee_id:
        self.line_ids=self._get_employees()

    def _get_available_domain(self):
        if self.employee_id:
            return [('employee_id', '=', self.employee_id.id),("request_id","=",self.ids[0])]
        else:
            return [("request_id","=",self.ids[0])]

    def _get_employees(self):
        if self.line_ids:
            # YTI check dates too
            return self.env['request.loan.payment.line'].search(self._get_available_domain())

    line_ids = fields.One2many('request.loan.payment.line', 'request_id', string=u'Detalle de Solicitud',
                               default=lambda self: self._get_employees(),required=True, readonly=True, states=_STATES, help=u"")
    communication = fields.Char(string=u'Descripción',
                                readonly=True, required=False, help=u"")

    is_accountant = fields.Boolean("Es la persona a procesar?", compute='_get_is_accountant', default=False)


    def write(self, vals):
        if 'employee_id' in vals:
            vals.update({'employee_id': False})
            if "line_ids" in vals:
                vals["line_ids"] = self._get_employees()
        result = super(RequestLoanPayment, self).write(vals)
        return result

    @api.model
    def create(self, vals):
        if 'employee_id' in vals:
            vals["employee_id"]= False
            if "line_ids" in vals:
                vals["line_ids"] = self._get_employees()
        result = super(RequestLoanPayment, self).create(vals)
        return result

    @api.depends(
        'line_ids',
        'line_ids.amount',
    )
    def _get_total_amount(self):
        self.amount = sum([l.amount for l in self.line_ids])
    amount = fields.Float(u'Monto Total', digits=dp.get_precision('Account'),
                          store=True, compute='_get_total_amount', help=u"")


    @api.depends('payment_ids',)
    def _get_payment_count(self):
        self.payment_count = len(self.payment_ids)

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

    def set_draft(self):
        ctx = self.env.context.copy()
        ctx.update({
            'delete_from_payments': True,
        })
        self.state='draft'
        idsScheduled=[]
        for line in self.line_ids:
            if line.transaction_id:
                if line.transaction_id.processed:
                    raise UserError(_(u'No puede eliminar el Anticipo, existe una nómina generada.'))
                idsScheduled.append(line.transaction_id.id)
        if idsScheduled:
            objScheduled = self.env['hr.scheduled.transaction'].browse(idsScheduled)
            objScheduled.with_context(ctx).unlink()

        return True

    def set_cancel(self):

        idsScheduled=[]
        ctx = self.env.context.copy()
        ctx.update({
            'delete_from_payments': True,
        })
        for line in self.line_ids:
            if line.transaction_id:
                if line.transaction_id.processed:
                    raise UserError(_(u'No puede eliminar el Anticipo, existe una nómina generada.'))
                idsScheduled.append(line.transaction_id.id)
        self.env['account.payment'].search([('request_loan_line_id', 'in', tuple(self.line_ids.mapped('id')))]).action_draft()
        self.env['account.payment'].search([('request_loan_line_id', 'in', tuple(self.line_ids.mapped('id')))]).action_cancel()
        # if any(self.env['account.payment'].search([('request_loan_line_id','in',tuple(self.line_ids.mapped('id')))]).filtered(lambda x: x.state == 'posted')) :
        #     raise UserError(_(u'No puede eliminar tiene pagos procesados'))
        # else:
        #     self.env['account.payment'].search([('request_loan_line_id','in',tuple(self.line_ids.mapped('id')))]).write({'state':'cancel','move_name':None,'name':None})
        #     self.env['account.payment'].search([('request_loan_line_id','in',tuple(self.line_ids.mapped('id')))]).unlink()


        # self.line_ids.unlink()
        self.state='draft'
        objScheduled = self.env['hr.scheduled.transaction'].browse(idsScheduled)
        if  objScheduled:
            if self.env['hr.payslip.line'].search([('transaction_id','in',tuple(idsScheduled))]):
                raise UserError(_(u'No puede eliminar el Anticipo, existe una nómina generada.'))

            objScheduled.with_context(ctx).unlink()




    def action_request(self):
        seq_model = self.env['ir.sequence']
        for request in self:
            if not request.line_ids:
                raise ValidationError(u'Debe cargar empleados antes!')
            if not request.number:
                request.number = seq_model.next_by_code('request.loan.payment')
            for line in request.line_ids:
                if line.amount == 0.00:
                    continue
                statement_id = request.create_new_statement(line.employee_id, line.amount, line.observation)
                line.transaction_id = statement_id.id
            request.with_context(from_rrhh=True).post()
            request.write({'payment_date': self.request_date})
        return self.write({
            'state': 'requested',
        })


    def create_payment(self):
        if not self.communication:
            raise ValidationError("Ingrese la Referencia de Pago.")
        payment_count = len(self.payment_ids)
        if payment_count > 0:
            raise ValidationError(u'Solo puede generar un pago en la presente solicitud')
        else:
            self.ensure_one()
            action = self.env.ref('account.action_account_payments').read()[0]
            action['views'] = [(self.env.ref('account.view_account_payment_form').id, 'form')]
            if not self.employee_id.address_home_id.id:
                raise UserError(_(u'El empleado %s no tiene asignada la empresa para procesar el pago, verifique la configuracion del empleado'))
            ctx = eval(action['context'])
            ctx.update({
                'default_partner_id': self.employee_id.address_home_id.id,
                'default_request_loan_payment_id': self.id,
                'default_employee_id': self.employee_id.id,
                'default_employee': True,
                'default_amount': self.amount,
                'default_communication': self.communication,
                'default_hr_collection_payment_type':'loan_payment',
            })
            action['context'] = ctx
            return action


    def unlink(self):
        for request in self:
            if request.state != 'draft':
                raise UserError(_(u'No puede borrar esta solicitud de pago de prestamo / anticipo, que no este en estado en borrador'))
        return super(RequestLoanPayment, self).unlink()

    is_payment_cash_managment = fields.Boolean(string='Es pago por Cash Managment?', default=False)

    line_count = fields.Integer(
        string="Lineas", compute="_compute_lines_count", readonly=True
    )

    def _compute_lines_count(self):
        self.line_count = len(self.line_ids)

    def action_view_lines(self):
        lines = self.mapped("line_ids")
        if len(lines) > 0:
            ctx = self.env['request.loan.payment.line']._context.copy()
            model = 'request.loan.payment.line'
            view_id_tree = self.env.ref('ec_payroll.ec_lineas_anticipo_tree', False)
            view_id_form = self.env.ref('stock.view_picking_form', False)
            context = self._context.copy()
            return {
                'name': _('Lineas de Anticipo'),
                'type': 'ir.actions.act_window',
                'res_model': 'request.loan.payment.line',
                'domain': [("id", "in", lines.ids)],
                'views': [(view_id_tree.id, 'tree')]
            }

    @api.depends('hr_rule')
    def _get_account_from_rule(self):
        for li in self:
            self.payment_account_id = li.hr_rule.account_credit.id if li.hr_rule.account_credit else None

    @api.onchange('type_advance')
    def _get_type_advance(self):
        for res in self:
            if res.type_advance == 'fortnight':
                rule_id = self.env['hr.salary.rule'].search([('code', '=', 'ANTQUINCENA'), ('struct_id', '=', res.hr_structure.id)])
                if len(rule_id) == 0:
                    raise UserError(
                        _(u'No existe la regla de anticipo por quincena, debe crearla con el codigo: ANT-QUIN'))
                res.rule_id = rule_id[0].id

    employee_id = fields.Many2one('hr.employee', string=u'Empleado',
                                  required=False, readonly=False, help=u"", ondelete="restrict")

    @api.depends('payment_journal_id')
    def _compute_payment_method_line_fields(self):
        for pay in self:
            pay.available_payment_method_line_ids = pay.payment_journal_id._get_available_payment_method_lines("outbound")

    available_payment_method_line_ids = fields.Many2many('account.payment.method.line',
                                                         compute='_compute_payment_method_line_fields')

    payment_journal_id = fields.Many2one('account.journal', string='Banco', domain=[('type', '=', 'bank')])
    payment_method_line_id = fields.Many2one('account.payment.method.line',string='Método de Pago')
    payment_account_id = fields.Many2one('account.account', string='Cuenta para pago')
    payment_date = fields.Date(string='Fecha pago', default=fields.Date.today())
    rule_id = fields.Many2one('hr.salary.rule', string=u'Rubro', required=True, readonly=False, help=u"",
                              ondelete="restrict")
    hr_rule = fields.Many2one('hr.scheduled.transaction.category', string=u'Rubro', readonly=False, help=u"",
                              ondelete="restrict")

    type_advance = fields.Selection([
        ('fortnight', 'Quincena'),
        ('thirteenth', u'Décimo Tercero'),
        ('fourteenth', u'Décimo Cuarto'),
    ], string='Tipo de Anticipo', required=True, default=None, )
    tipo_carga = fields.Selection([
        ('structure', 'Por Estructura'),
        ('all', 'Todos'),
    ], string='Carga de Empleados',
        readonly=False, required=True, default="all", )
    hr_structure = fields.Many2one('hr.payroll.structure', string=u'Estructura Salarial', required=True)
    monto_asignado = fields.Float(digits=(7, 2), default=lambda self: self.env.company.egress_porcent_max)
    tipo_anticipo = fields.Selection([
        ('percent', 'Porcentaje'),
        ('permanent', 'Monto Fijo'),
    ], string='Tipo anticipo',
        readonly=False, required=True, default="percent", )

    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company.id)

    forma_pago_id = fields.Many2one('sri.forma.pago', string=u'Forma de Pago por Defecto', ondelete="restrict"
                                    ,default=lambda self: self.env.company.sri_forma_pago, readonly=True)

    def create_payment(self):
        for line in self.line_ids:
            if line.amount > 0.00:
                if self.create_payment_inherit(line):
                    pass
        if self.line_ids:
            self.write({'state': 'done'})

    def post(self):
        """
        Create account move
        """

    def create_payment_inherit(self, line):
        pago = self.env['account.payment']
        line_request = self.env['request.loan.payment.line']
        idsContract = self.env['hr.contract'].search([('employee_id', '=', line.employee_id.id)])
        if len(idsContract) == 0:
            raise UserError(_(u'El empleado no tiene contrato activo') % (line.employee_id.name))
        if len(idsContract) > 1:
            raise UserError(
                _(u'El empleado tiene más de un contrato activo, por favor revisar') % (line.employee_id.name))
        contract = self.env['hr.contract'].browse(idsContract.id)
        if contract and not line.account_payment_id:
            if line.employee_id.pay_with_check or line.employee_id.payment_method == "CHE":
                account_payment_id = 5
            if line.employee_id.payment_method == "CUE":
                account_payment_id = 11
            else:
                account_payment_id = 2
            data = {
                'payment_type': 'outbound',
                'date': self.payment_date,
                'ref': self.communication,
                'partner_type': 'supplier',
                'partner_id': line.employee_id.address_home_id.id,
                'beneficiary': line.employee_id.name,
                'amount': line.amount,
                'journal_id': self.payment_journal_id.id,
                'forma_pago_id': self.payment_journal_id.forma_pago_id.id if self.payment_journal_id.forma_pago_id else self.env.company.forma_pago_id.id,
                'payment_method_line_id': self.payment_method_line_id.id,
                'request_loan_line_id': line.id,
                'direct_to_account_account': True,
                'payment_account_line_ids': [
                    (0, 0, {
                        'account_id': self.company_id.account_fortnight_id.id,
                        'description': 'self.communication',
                        'analytic_distribution': contract.analytic_distribution or {},
                        'amount': line.amount,
                    }),
                ],
            }
            idsPago = pago.create(data)
            idsPago.post()
            line_request.write({'account_payment_id': idsPago.id})
            return True

    @api.model
    def create_new_statement(self, employee, monto_anticipo, observation):
        data = {
            'employee_id': employee.id,
            'rule_id': self.rule_id.id,
            'name': self.rule_id.name + ' ' + employee.name,
            'code': self.rule_id.code + '/' + self.number + '/' + str(self.request_date.strftime('%B')).upper() + '/' + employee.identification_id or str(self.employee.id),
            'date': self.request_date,
            'amount': monto_anticipo,
            'request_loan_line': self.id,
            'observation': observation
        }
        ids = self.env['hr.scheduled.transaction'].create(data)
        return ids

    def action_set_draft(self):
        self.write({'state': 'draft'})


    def print_antic_xls(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url',
                'url': '/download/saveas?model=%(model)s&record_id=%(record_id)s&method=%(method)s&filename=%(filename)s' % {
                    'filename': 'SOLICITUD DE PAGO ANTICIPO/PRESTAMO.xlsx',
                    'model': self._name,
                    'record_id': self.id,
                    'method': 'get_report_data',
                },
                'target': 'new',
                }

    def get_report_data(self):
        data = self
        report_model = self.env['report.ec_payroll.report_xls_payroll']
        return report_model.get_report_xls(data)

    def action_clean_employee(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_(u'No puede limpiar los empleados de una solicitud que no este en estado borrador'))
        if not self.line_ids:
            raise UserError(_(u'No existen empleados en la solicitud'))
        self.line_ids.unlink()

    def action_get_employee(self):
        monto_anticipo = 0
        ids_employee = self.env['hr.employee'].search([('active', '=', True)])
        ids_contract = ids_employee.mapped('contract_ids').filtered(lambda x: x.state == 'open' and x.date_start <= self.request_date and x.struct_id.id == self.hr_structure.id)
        transaction_ids = self.line_ids.mapped('transaction_id')
        self.line_ids.unlink()
        transaction_ids.unlink()
        request_date = self.request_date  # datetime.strptime(self.request_date, "%Y-%m-%d")
        for line in self.env['hr.contract'].browse(ids_contract.ids):
            aditinal_monto = 0
            for line_contract_rule in line.contract_line_rule_ids:
                if line_contract_rule.is_for_advances:
                    aditinal_monto += line_contract_rule.amount
            for type_rule_id in line.type_rule_ids:
                for line_type_rule in type_rule_id.rule_ids:
                    if line_type_rule.is_for_advances:
                        aditinal_monto += line_type_rule.amount
            if line.type_day == 'complete':
                monto_anticipo = self.monto_asignado if self.tipo_anticipo == 'permanent' else (self.monto_asignado / 100) * (line.wage + aditinal_monto)
            elif line.type_day == 'partial':
                monto_anticipo = self.monto_asignado if self.tipo_anticipo == 'permanent' else (self.monto_asignado / 100) * (line.wage + aditinal_monto)
            date_from = line.date_start  # datetime.strptime(line.date_start, "%Y-%m-%d")  # Get contract date
            percentage = 1
            if request_date.month == date_from.month:
                if request_date.year == date_from.year:
                    # Get percentage subtracting 15(fifteen days) from contract day and add 1(16 - date_from.day), then divided by 15
                    percentage = (16 - date_from.day) / 15.0
            # elif request_date.month < date_from.month:
            else:
                percentage = 1  # If contract is major to advance date no consider
            # Otherwise percentage is 1
            monto_anticipo *= percentage
            self.env['request.loan.payment.line'].create({
                'request_id': self.id,
                'employee_id': line.employee_id.id,
                'amount': monto_anticipo,
            })

    def generar_reporte_quincena(self):

        file_data = BytesIO()
        workbook = xlsxwriter.Workbook(file_data)
        name = 'QUINCENA GENERAL DE TRABAJADORES'
        self.xslx_body(workbook)
        workbook.close()
        file_data.seek(0)
        attachment = self.env['ir.attachment'].create({
            'datas': base64.b64encode(file_data.getvalue()),
            'name': name,
            'store_fname': name,
            'type': 'binary',
        })
        url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        # url = "https://erp.cenecuador.edu.ec/web/content/%s?download=true" % (attachment.id)
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def obtener_mes(self, mes):
        meses = ["Enero", "Febrero", "Marzo", "Abril",
                 "Mayo", "Junio", "Julio", "Agosto",
                 "Septiembre", "Octubre", "Novimebre", "Diciembre"]
        return meses[mes - 1]

    def xslx_body(self, workbook):
        for l in self:
            registros_tabla = workbook.add_format(
                {'align': 'center', 'valign': 'vcenter', 'font_size': 11, 'text_wrap': True,
                 'border': True, 'bg_color': '#FFFFFF', 'color': '#0f0000'})
            registros_tabla_numerico = workbook.add_format(
                {'align': 'center', 'valign': 'vcenter', 'font_size': 11, 'text_wrap': True,
                 'border': True, 'bg_color': '#FFFFFF', 'color': '#0f0000', 'num_format': '0.00'})
            bold = workbook.add_format({'bold': True, 'border': False, 'bg_color': '#ffffff', 'color': '#000000'})
            bold.set_font_size(14)
            bold3 = workbook.add_format({'bold': True, 'border': False, 'bg_color': '#ffffff', 'color': '#000000'})
            bold3.set_font_size(12)
            bold2 = workbook.add_format(
                {'align': 'center', 'valign': 'vcenter', 'bold': True, 'font_size': 11, 'bg_color': '#ededed',
                 'color': '#000000', 'text_wrap': True, 'border': True})
            bold2.set_center_across()
            sheet = workbook.add_worksheet("REPORTE DE QUINCENA")
            sheet.insert_image('A1', "any_name.png",
                               {'image_data': BytesIO(base64.b64decode(self.env.company.logo)),
                                'x_scale': 1, 'y_scale': 1, 'align': 'left', 'bg_color': '#ffffff'})

            sheet.merge_range('C2:E2', 'QUINCENA GENERAL DE TRABAJADORES', bold)
            sheet.merge_range('C4:E4', 'Razón Social: ' + str(self.env.company.name), bold3)
            sheet.merge_range('C5:E5', 'RUC: ' + self.env.company.vat, bold3)
            if self.request_date:
                mes = self.obtener_mes(self.request_date.month)
                sheet.merge_range('C6:E6', 'Mes: ' + str(mes) + " " + str(self.request_date.year), bold3)
            # sheet.set_column('A:A', 9)
            # sheet.set_column('B:B', 35)
            # sheet.set_column('C:C', 15)
            # sheet.set_column('D:D', 28)
            # sheet.set_column('E:E', 20)
            # sheet.set_column('F:F', 15)
            # sheet.set_column('G:G', 20)
            # sheet.set_column('H:H', 25)
            # sheet.set_column('I:I', 20)
            # sheet.set_column('J:J', 15)
            # sheet.set_column('K:K', 10)
            # sheet.set_column('L:L', 10)
            # sheet.set_column('M:M', 25)
            sheet.write(10, 0, 'Código', bold2)
            sheet.write(10, 1, 'Nombre', bold2)
            sheet.write(10, 2, 'Identificación', bold2)
            sheet.write(10, 3, 'Forma de Pago', bold2)
            sheet.write(10, 4, 'Banco', bold2)
            sheet.write(10, 5, 'Tipo de Cuenta', bold2)
            sheet.write(10, 6, 'Número de Cuenta', bold2)
            sheet.write(10, 7, 'Sueldo Nominal', bold2)
            sheet.write(10, 8, 'Monto Quincena', bold2)
            sheet.write(10, 9, 'OBSERVACIONES', bold2)
            sheet.freeze_panes(0, 4)
            row = 11
            total_nominal = 0
            total_quincenal = 0
            for line in self.line_ids:
                forma_pago = ""
                tipo_cuenta = ""
                if line.employee_id.type_account == "virtual":
                    tipo_cuenta = "Virtual"
                elif line.employee_id.type_account == "savings":
                    tipo_cuenta = "Ahorro"
                elif line.employee_id.type_account == "current":
                    tipo_cuenta = "Corriente"
                if line.employee_id.payment_method == "CUE":
                    forma_pago = "Depósito a Cuenta"
                elif line.employee_id.payment_method == "CHE" or line.employee_id.pay_with_check:
                    forma_pago = "CHEQUE"
                elif line.employee_id.payment_method == "EFE":
                    forma_pago = "EFECTIVO"
                contrato_id = self.env["hr.contract"].search(
                    [("employee_id", "=", line.employee_id.id), ("state", "=", "open")], limit=1)
                sueldo_nominal = 0
                if contrato_id:
                    if contrato_id.type_day == "complete":
                        sueldo_nominal = contrato_id.wage
                    else:
                        sueldo_nominal = contrato_id.value_for_parcial
                total_nominal += sueldo_nominal
                if line.amount:
                    total_quincenal += line.amount
                elif line.amount_pending:
                    total_quincenal += line.amount_pending
                sheet.write(row, 0, "", registros_tabla)
                sheet.write(row, 1, line.employee_id.name or "", registros_tabla)
                sheet.write(row, 2, line.employee_id.identification_id or "", registros_tabla)
                sheet.write(row, 3, forma_pago, registros_tabla)
                sheet.write(row, 4, line.employee_id.bank_id.name or "", registros_tabla)
                sheet.write(row, 5, tipo_cuenta, registros_tabla)
                sheet.write(row, 6, line.employee_id.account_number or "", registros_tabla)
                sheet.write(row, 7, sueldo_nominal, registros_tabla_numerico)
                sheet.write(row, 8, line.amount or line.amount_pending, registros_tabla_numerico)
                sheet.write(row, 9, line.observation or "", registros_tabla)
                row += 1
            sheet.write(row, 10, "TOTALES", registros_tabla)
            sheet.write(row, 11, total_nominal, registros_tabla)
            sheet.write(row, 12, total_quincenal, registros_tabla)


class RequestLoanPaymentLine(models.Model):

    _name = 'request.loan.payment.line'
    _order = 'employee_id asc'

    request_id = fields.Many2one('request.loan.payment', string=u'Solicitud',
                                 required=False, readonly=False, states={}, help=u"", ondelete="cascade")

    transaction_id = fields.Many2one('hr.scheduled.transaction', string=u'Transaccion Programada',
                                     required=False, readonly=False, states={}, help=u"", )

    amount_pending = fields.Float(string=u'Monto Pendiente', digits=dp.get_precision('Account'),
                                  required=False, readonly=True, states={}, help=u"")

    amount = fields.Float(string=u'Monto Pagado', digits=dp.get_precision('Account'),
                          required=False, readonly=False, states={}, help=u"")
    observation  = fields.Char(string=u'Observaciones')


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

    employee_id = fields.Many2one('hr.employee', string=u'Empleado',
                                  help=u"", ondelete="restrict")
    account_payment_id = fields.Many2one('account.payment', ondelete="restrict")

    def write(self, vals):
        if 'amount' in vals:
            vals.update({'amount': vals["amount"]})
        result = super(RequestLoanPaymentLine, self).write(vals)
        return result

    @api.onchange("amount")
    def actualizar_monto(self):
        for l in self:
            if l.amount:
                self.write({'amount': l.amount})

    def _prepare_move_lines(self, journal):
        data = []

        # Create debit line
        data.append((0, 0, {
            "debit": self.amount,
            "credit": 0.0,
            "account_id": self.request_id.hr_rule.account_debit.id,
            "partner_id": self.employee_id.address_home_id.id,
            "name": "%s - %s" % (self.request_id.number, self.request_id.communication),
        }))

        # Create credit line
        data.append((0, 0, {
            "credit": self.amount,
            "debit": 0.0,
            "account_id": journal.default_credit_account_id.id,
            "partner_id": self.employee_id.address_home_id.id,
            "name": "%s - %s" % (self.request_id.number, self.request_id.communication),
        }))

        return data

    # @api.multi
    def create_move(self):
        account_move_obj = self.env['account.move']
        for line in self:
            contract_id = self.env['hr.contract'].search([('employee_id', '=', line.employee_id.id),
                                                          ('state', '=', 'open')])
            if contract_id and not line.account_payment_id:
                if line.employee_id.pay_with_check:
                    if not contract_id.journal_chque_anticipo:
                        journal = self.env.company.journal_chque_anticipo
                    else:
                        journal = contract_id.journal_chque_anticipo
                else:
                    if not contract_id.journal_trans_anticipo:
                        journal = self.env.company.journal_trans_anticipo
                    else:
                        journal = contract_id.journal_trans_anticipo
            move_id = account_move_obj.create({
                "date": line.request_id.request_date,
                "ref": line.request_id.communication,
                "journal_id": journal.id,
                "line_ids": line._prepare_move_lines(journal)
            })
            line.move_id = move_id.id
            move_id.action_post()

    @api.onchange('transaction_id')
    def _onchange_transaction_id(self):
        if self.transaction_id:
            self.amount_pending = self.transaction_id.amount_pending
            self.amount = self.transaction_id.amount_pending
            self.employee_id = self.transaction_id.employee_id
        else:
            self.amount_pending = 0

class HrScheduleTransaction(models.Model):
    _inherit='hr.scheduled.transaction'

    def unlink(self):
        for li in self:
            if self.env['request.loan.payment.line'].search([('transaction_id','=', li.id)]) and not self.env.context.get('delete_from_payments',False):
                raise ValidationError(u'Transacción tiene un Anticipo asociado, primero elimine el Anticipo')


        return  super(HrScheduleTransaction, self).unlink()