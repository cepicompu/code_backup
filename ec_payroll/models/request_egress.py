# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api
from odoo import api, fields, models, tools
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _
from odoo.exceptions import RedirectWarning, UserError, ValidationError,AccessError
from odoo.tools.misc import formatLang
from odoo.tools import float_is_zero, float_compare, float_round
from odoo.osv import expression
from collections import OrderedDict
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
from odoo import SUPERUSER_ID
from odoo.tools.safe_eval import safe_eval as eval
from dateutil.relativedelta import relativedelta
from datetime import datetime, date, time, timedelta
import calendar
from lxml import etree
import logging
_logger = logging.getLogger(__name__)


STATES = {'draft': [('readonly', False)],
          'request': [('readonly', False)],
          'confirm': [('readonly', False)],}






class MailThread(models.AbstractModel):

    _inherit = 'mail.thread'



    def message_track(self, tracked_fields, initial_values):
        """ Track updated values. Comparing the initial and current values of
        the fields given in tracked_fields, it generates a message containing
        the updated values. This message can be linked to a mail.message.subtype
        given by the ``_track_subtype`` method. """

        if not tracked_fields:
            return True

        tracking = dict()
        for record in self:
            tracking[record.id] = record._message_track(tracked_fields, initial_values[record.id])

        for record in self:
            changes, tracking_value_ids = tracking[record.id]
            if not changes:
                continue

            # find subtypes and post messages or log if no subtype found
            subtype = False
            # By passing this key, that allows to let the subtype empty and so don't sent email because partners_to_notify from mail_message._notify will be empty
            if not self._context.get('mail_track_log_only'):
                subtype = record._track_subtype(dict((col_name, initial_values[record.id][col_name]) for col_name in changes))

            # import pdb 
            # pdb.set_trace()
            if subtype and type(subtype)!=str:
                if not subtype.exists():
                    _logger.debug('subtype "%s" not found' % subtype.name)
                    continue
                record.message_post(subtype_id=subtype.id, tracking_value_ids=tracking_value_ids)
            elif tracking_value_ids:
                record._message_log(tracking_value_ids=tracking_value_ids)

        return tracking



class request_egress(models.Model):
    '''
        Solicitud de Egreso
    '''
    _name='request.egress'

    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'number'
    _description = 'Solicitud de Horas Extras'

    number = fields.Char(string=u'Número de orden', index=True, required=False, readonly=True, states={}, help=u"",track_visibility='onchange')
    request_date= fields.Date(string=u'Fecha de Solicitud', default=fields.Date.today(),
                              readonly=True, required=True, index=True, copy=False, states=STATES, help=u"")
    employee_id = fields.Many2one('hr.employee', string=u'Empleado',
                                  required=True, readonly=True, help=u"", states=STATES,  ondelete="restrict",track_visibility='onchange')
    user_applicant_id = fields.Many2one('res.users', string=u'Usuario solicitante', default=lambda self: self.env.user.id,
                                        required=True, readonly=True,  help=u"", states=STATES, ondelete="restrict")
    communication = fields.Char(string=u'Descripción',
                                readonly=True, required=True, states=STATES, help=u"")
    state = fields.Selection([
        ('draft','Borrador'),
        ('request','Solicitado'),
        ('confirm','Confirmado'),
        ('done','Aprobado'),
        ('delivered','Entregado'),
        ('rejected','Rechazado'),
    ], string='Estados', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')

    amount = fields.Float(u'Monto', digits=dp.get_precision('Account'), readonly=True, required=False, states=STATES,  help=u"")
    type_discount = fields.Selection([
        ('one_payment','Un solo descuento'),
        ('multi_payment','Varios descuentos'),
    ], string='Forma de Descuento',
        readonly=True,  required=True, states=STATES, help=u"", default="multi_payment")
    numbers_discount = fields.Integer(string=u'Cantidad de Descuentos',
                                      readonly=True, required=False, states=STATES ,help=u"")
    contract_id = fields.Many2one('hr.contract', string=u'Contrato',
                                  required=True, readonly=True, states=STATES ,help=u"", ondelete="restrict")
    struct_id = fields.Many2one('hr.payroll.structure', string=u'Estructura Salarial', related='contract_id.struct_id',readonly=True)
    rule_id = fields.Many2one("hr.salary.rule", "Rubro", domain=[('category_id.code', 'in', ('EGRE', 'OEGR','CONT'))],)
    rubro_id = fields.Many2one('hr.scheduled.transaction.category', string=u'Rubro', domain=[('category_code', 'in', ('EGRE', 'OEGR','CONT')),('mostrar_en_registros', '=', True)],
                               readonly=True,states=STATES,  help=u"", ondelete="restrict")
    request_egress_detail_ids = fields.One2many('request.egress.detail', 'request_egress_id', string=u'Detalle Sol. Egreso',
                                                required=False, readonly=True,states={'draft': [('readonly', False)],'request': [('readonly', False)]},  help=u"")

    egress_porcent_max = fields.Float(u'Porcentaje Máximo', digits=dp.get_precision('Account'),
                                      readonly=True,states=STATES, default=lambda self: self.env.company.egress_porcent_max)
    egress_num_max_quota = fields.Integer(u'Máximo Números de Cuotas', digits_compute=dp.get_precision('Account'),
                                          readonly=True,states=STATES, default=lambda self: self.env.company.egress_num_max_quota)
    fecha_cobro = fields.Date(string=u'Fecha para Descuento',
                              readonly=True, required=False, index=True, copy=False, states=STATES, help=u"")
    manager_id = fields.Many2one('res.users', 'Aprobador',
                                 readonly=True,
                                 states=STATES,
                                 track_visibility='onchange')
    reject_reason = fields.Text(string=u'Razón de rechazo', required=False, readonly=False, states=STATES, help=u"")

    def _get_is_accountant(self):
        for res in self:
            is_accountant = False
            if res.manager_id:
                if res.manager_id.id == res.env.user.id:
                    is_accountant = True
            res.is_accountant = is_accountant



    is_accountant = fields.Boolean("Es la persona a procesar?", compute='_get_is_accountant', default=False)



    # def _track_subtype(self, init_values):
    #     for rec in self:
    #         if 'state' in init_values and rec.state == 'confirm':
    #             return 'ec_payroll.mt_request_egress_to_approve'
    #         elif 'state' in init_values and rec.state == 'done':
    #             return 'ec_payroll.mt_request_egress_approved'
    #         elif 'state' in init_values and rec.state == 'rejected':
    #             return 'ec_payroll.mt_request_egress_rejected'
    #     return super(request_egress, self)._track_subtype(init_values)


    @api.constrains('amount')
    def _check_amount(self):
        if self.amount < 1:
            raise ValidationError(u'El monto debe ser mayor a cero.')


    @api.constrains(
        'numbers_discount',
        'type_discount',
        'amount',
        'contract_id',
        'egress_porcent_max',
        'egress_num_max_quota',
    )
    def _check_numbers_discount(self):
        if self.type_discount == 'multi_payment':
            if self.numbers_discount < 2:
                raise ValidationError(u'El número de descuentos tiene que ser mayor a 1.')
            if self.egress_num_max_quota < 1:
                raise ValidationError(u'Debe configurar el número maximo de cuotas.')
            if self.numbers_discount > self.egress_num_max_quota:
                raise ValidationError(u'El número de cuotas %s debe ser mayor a %s.' % (self.numbers_discount, self.egress_num_max_quota))
        else:
            porcent_max_wage = self.contract_id.wage * (self.egress_porcent_max / 100)
            if self.amount > porcent_max_wage:
                raise ValidationError(_(u'El monto solicitado %s no puede ser mayor que esta permitido a descontar mensualmente %s.') % (self.amount, '%.2f' % (porcent_max_wage)))

    @api.onchange(
        'employee_id',
        'request_date',
    )
    def _onchange_employee_request(self):
        payslip_model = self.env['hr.payslip']
        self.manager_id=False
        if self.employee_id:
            current_employee =  self.employee_id
            if current_employee and current_employee.parent_id and current_employee.parent_id.user_id:
                self.manager_id=current_employee.parent_id.user_id.id
            else:
                self.manager_id = False
        if self.employee_id and self.request_date:
            request_date = fields.Date.from_string(self.request_date)
            date_to = request_date + relativedelta(day=1, months=+1, days=-1)
            date_from = request_date + relativedelta(day=1)
            contracts = payslip_model.get_contract(self.employee_id, date_from, date_to)
            if contracts:
                self.contract_id = contracts[0]
            else:
                self.contract_id = False
                return {
                    'warning': {
                        'title': _(u'Advertencia'),
                        'message': _(u'No se encontro Contrato Activo para el empleado %s en la fecha %s') % (self.employee_id.display_name, self.request_date),
                    }
                }


    def generate_lines_quote(self):
        for egress in self:
            request_date = fields.Date.from_string(egress.request_date)
            date_to = request_date + relativedelta(day=1, months=+1, days=-1)
            egress.request_egress_detail_ids.unlink()
            wage_original = egress.amount
            num_disc = egress.numbers_discount
            if egress.type_discount == 'one_payment':
                num_disc = 1
            amount_quotes = round(egress.amount / num_disc, 2)
            t_copy = {}
            count_month = 0
            request_egress_detail_model = self.env['request.egress.detail']
            transactions = request_egress_detail_model.browse()
            for i in range(num_disc):
                if (i+1) == num_disc:
                    amount_quotes = wage_original
                count_month = i + 1
                date_to_2 = date_to + relativedelta(day=1, months=count_month+ 1, days=-1)
                t_copy.update({
                    'date': date_to_2,
                    'monto': amount_quotes,
                    'description':' %s %s de %s' % (egress.rule_id.name, i + 1, num_disc),
                    'request_egress_id':egress.id,
                })
                transactions += request_egress_detail_model.create(t_copy)
                wage_original -= amount_quotes
        return True

    # @api.model
    # def create(self, vals):
    #     # request = super(request_egress, self).with_context(mail_track_log_only=True).create(vals)
    #     # if vals.get('manager_id'):
    #     #     request.message_subscribe_users(user_ids=[request.manager_id.id])
    #     # if vals.get('employee_id'):
    #     #     request.message_subscribe_users(user_ids=[request.employee_id.user_id.id])
    #     return super(request_egress, self).with_context(mail_track_log_only=True).create(vals)

    # 
    # def write(self, vals):
    #     # res = super(request_egress, self).with_context(mail_track_log_only=True).write(vals)
    #     # for request in self:
    #     #     if vals.get('manager_id'):
    #     #         request.message_subscribe_users(user_ids=[request.manager_id.id])
    #     #     if vals.get('employee_id'):
    #     #         if request.employee_id.user_id:
    #     #             request.message_subscribe_users(user_ids=[request.employee_id.user_id.id])
    #     return super(request_egress, self).with_context(mail_track_log_only=True).write(vals)


    def action_draft(self):
        self.state = 'draft'


    def action_request(self):
        if not self.number:
            seq_model = self.env['ir.sequence']
            for secuencia in self:
                secuencia.number = seq_model.next_by_code('request.egress')
        self.state = 'request'


    def action_confirm(self):
        self.state = 'confirm'


    def action_done(self):
        # wage_maximo = 0
        # for line in self.request_egress_detail_ids:
        #     wage_maximo += line.monto
        # if wage_maximo > self.amount:
        #     raise ValidationError(u'La suma de los montos en las cuotas supera al monto solicitado.')
        # if wage_maximo < self.amount:
        #     raise ValidationError(u'La suma de los montos en las cuotas es menor al monto solicitado.')
        self.state = 'done'


    def action_rejected(self):
        if self.reject_reason:
            self.state = 'rejected'
        else:
            raise UserError(_(u"Desccribir razón de rechazo"))

    payment_ids= fields.One2many('account.payment', 'request_egress_id', string=u'Pago',
                                 required=False, readonly=False, states={}, help=u"")


    @api.depends('payment_ids')
    def _get_total_pago(self):
        self.payment_count = len(self.payment_ids)

    payment_count = fields.Integer(string=u'# de Pagos',
                                   store=True, compute='_get_total_pago', help=u"")


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


    def action_delivered(self):
        payment_count = len(self.payment_ids)
        if payment_count > 0:
            raise ValidationError(u'Solo puede generar un pago en la presente solicitud')
        else:
            self.ensure_one()
            wage_maximo = 0
            if self.type_discount == 'multi_payment':
                for line in self.request_egress_detail_ids:
                    wage_maximo += line.monto
                # if (wage_maximo > self.amount) or (wage_maximo < self.amount):
                #     raise ValidationError(u'La suma de los montos en cuotas no coincide con el monto solicitado.')
            action = self.env.ref('account.action_account_payments_payable').read()[0]
            action['views'] = [(self.env.ref('account.view_account_payment_form').id, 'form')]
            if not self.employee_id.address_home_id.id:
                raise UserError(_(u'El empleado %s no tiene asignada la empresa para procesar el pago, verifique la configuracion del empleado'))
            ctx = eval(action['context'])
            ctx.update({
                'default_company_id_id': self.env.company.id,
                'default_partner_id': self.employee_id.address_home_id.id,
                'default_request_egress_id': self.id,
                'default_employee_id': self.employee_id.id,
                'default_employee': True,
                'default_hr_payment_type': 'descuento_rol',
                'default_category_transaction_id': self.rubro_id.id,
                'default_amount': self.amount,
                'default_tipo_desglose': self.type_discount,
                'default_ref': self.communication,
                'default_cantidad_descuentos': self.numbers_discount,
                'default_rule_id': self.rule_id.id,
            })
            action['context'] = ctx
            return action


    def action_to_delivered(self):
        payment_count = len(self.payment_ids)
        if payment_count > 0:
            self.state = 'delivered'
        else:
            raise UserError(_(u'Tiene que generar un pago para pasar a Entregado el estado.'))


    def unlink(self):
        for request in self:
            if request.state != 'draft':
                raise UserError(_(u'No puede borrar esta solicitud de egreso, que no este en estado en borrador'))
        return super(request_egress, self).unlink()


class request_egress_detail(models.Model):
    _name = 'request.egress.detail'
    request_egress_id = fields.Many2one('request.egress', string=u'Solicitud de Egreso',
                                        required=False, readonly=False, states={}, help=u"", ondelete="cascade")
    date = fields.Date(string=u'Fecha', readonly=False, required=False, index=True, copy=False, states={}, help=u"")
    monto = fields.Float(u'Monto', digits=dp.get_precision('Account'), readonly=False, required=False, states={}, help=u"")
    description = fields.Char(string=u'Descripcion', index=True, required=False, readonly=False, states={}, help=u"")
    from_egress = fields.Selection([('thirteenth', u'Décimo Tercero'),
                                    ('fourteenth', u'Décimo Cuarto'),
                                    ('utility ', u'Utilidad'),], string=u'Origen de Egreso')

    @api.depends(
        'request_egress_id.contract_id',
        'request_egress_id.employee_id',
        'date',
        'monto',
    )
    def _slip_value(self):
        payslip_model = self.env['hr.payslip']

        for line in self:
            if line.request_egress_id.contract_id and line.request_egress_id.employee_id:
                request_date = fields.Date.from_string(line.date)
                date_from = (request_date + relativedelta(day=1)).strftime(DF)
                date_to = (request_date + relativedelta(day=1, months=+1, days=-1)).strftime(DF)
                slip_lines = payslip_model.get_payslip_lines_simulate(line.request_egress_id.employee_id.id, date_from, date_to)
                total_inputs = sum([l.total for l in slip_lines.filtered(lambda r: r.category_id.code in ('INGR', 'OINGR', 'OINGRN'))])
                total_outputs = sum([l.total for l in slip_lines.filtered(lambda r: r.category_id.type == 'output')])
                line.slip_value = total_inputs + total_outputs
                line.net_value = line.slip_value - line.monto
    slip_value = fields.Float(u'Sueldo Proyectado', digits=dp.get_precision('Account'),
                              store=False, compute='_slip_value', help=u"")
    net_value = fields.Float(u'Sueldo Final Proyectado', digits=dp.get_precision('Account'),
                             store=False, help=u"")
    # slip_value = fields.Float(u'Sueldo Proyectado', digits=dp.get_precision('Account'), 
    #                           store=False,  help=u"")  
    # net_value = fields.Float(u'Sueldo Final Proyectado', digits=dp.get_precision('Account'), 
    #                           store=False, help=u"")     


    