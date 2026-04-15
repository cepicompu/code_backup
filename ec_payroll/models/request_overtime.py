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
from dateutil.relativedelta import relativedelta
from datetime import datetime, date, time, timedelta
import calendar
from lxml import etree
import logging
_logger = logging.getLogger(__name__)


STATES = { 'draft': [('readonly', False)],}

class request_overtime(models.Model):

    _name='request.overtime'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'number'
    _description = 'Solicitud de Horas Extras'
    _order = "employee_id"

    number = fields.Char(string=u'Número de orden', index=True, required=False, readonly=True, states={}, help=u"")
    date_from = fields.Date(string=u'Fecha inicial', track_visibility='always',
                            readonly=True, required=False, index=True, copy=False, states=STATES, help=u"")
    date_to = fields.Date(string=u'Fecha Final',  track_visibility='always',
                          readonly=True, required=False, index=True, copy=False, states=STATES, help=u"")
    employee_id = fields.Many2one('hr.employee', string=u'Empleado', track_visibility='onchange',
                                  required=False, readonly=True, states=STATES, help=u"", ondelete="cascade")
    recibido_id = fields.Many2one('hr.employee', string=u'Recibido', track_visibility='onchange',
                                  required=False, readonly=True, states=STATES, help=u"", ondelete="cascade")
    state = fields.Selection([
        ('draft','Borrador'),
        ('request','Solicitado'),
        ('done','Aprobado'),
        ('rejected','Rechazado'),
    ], string='Estado',
        readonly=False, required=False, default ='draft',states=STATES, help=u"",track_visibility='onchange')
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company.id)

    @api.model
    def create(self, values):
        contract_id = self.env['hr.contract'].search([('employee_id','=',values['employee_id'])])
        if len(contract_id)==0:
            raise UserError(_(u'El empleado no tiene un contrato activo'))
        values.update({'date_to': values['date_from'],
                       'contract_id': contract_id[0].id})
        #pasar el contacto como seguidor para temas de notificaciones
        if values.get('emoloyee_id', False):
            message_follower_ids = values.get('message_follower_ids', [])  or []  # webclient can send None or False
            new_follower = (4,values['employee_id'])
            if new_follower not in message_follower_ids:
                message_follower_ids.append(new_follower)
                values['message_follower_ids'] = message_follower_ids
        new_requisition_hour = super(request_overtime, self).create(values)

        return new_requisition_hour


    def write(self, vals):
        if vals.get('employee_id'):
            employee = self.env['hr.employee'].browse(vals['employee_id'])

        return super(request_overtime, self).write(vals)

    aprobador_id = fields.Many2one('hr.employee', string=u'Aprobador', track_visibility='onchange',
                                   required=False, readonly=True, states=STATES, help=u"", ondelete="cascade")
    reason = fields.Text(string=u'Razon', required=False, readonly=True, states=STATES, help=u"")
    activitie_infor = fields.Text(string=u'Informacion de Actividades', required=False, readonly=True, states=STATES, help=u"")
    department_id = fields.Many2one('hr.department', string=u'Departamento', related ="employee_id.department_id",
                                    required=False, readonly=True, states=STATES, help=u"", ondelete="cascade")
    cant_hours_ext = fields.Float(u'Cant. Horas Extraordinaria 100%',
                                  digits=dp.get_precision('Account'), readonly=True, required=False, states=STATES, help=u"")
    cant_hours_suple = fields.Float(u'Cant. Horas Suplementarias 50%',
                                    digits=dp.get_precision('Account'), readonly=True, required=False, states=STATES, help=u"")
    cant_hours_night = fields.Float(u'Cant. Horas Nocturas',
                                    digits=dp.get_precision('Account'), readonly=True, required=False, states=STATES, help=u"")
    hr_transaction_ids = fields.Many2many('hr.scheduled.transaction', 'overtime_transaction_rel',
                                          'overtime_id', 'transaction_id', string=u'Transacciones Programadas', states=STATES, help=u"",readonly=True)
    contract_id = fields.Many2one('hr.contract', string=u'Contrato', compute="_get_contract",
                                  required=False, readonly=True, states=STATES, help=u"", ondelete="cascade")

    @api.depends('employee_id')
    def _get_contract(self):
        for record in self:
            record.contract_id = False
            if record.employee_id:
                contract = self.env['hr.contract'].search(
                    [('employee_id', '=', record.employee_id.id)],
                    limit=1,
                )
                record.contract_id = contract.id if contract else False


    # @api.constrains('cant_hours_ext', 'cant_hours_suple' )
    # def _check_cant_hours(self):
    #     if not self.cant_hours_ext and not self.cant_hours_suple:
    #         raise ValidationError(u'Debe ingresar horas extraordinarias o horas suplementarias')
    #     if self.cant_hours_ext <= 0 and self.cant_hours_suple <= 0:
    #         raise ValidationError(u'El Número de horas debe ser mayor a 0')

    @api.constrains('date_from', 'date_to' )
    def _check_date(self):
        if self.date_from > self.date_to:
            raise ValidationError(u'La fecha inicial no puede ser mayor a la fecha final.')

    @api.depends('cant_hours_suple')
    def _get_wage_hours_suple(self):
        if self.contract_id.hour_value > 0:
            if self.contract_id.type_day == 'partial':
                cantidad_horas_suple = ((self.contract_id.value_for_parcial) / self.contract_id.contracted_hours) * self.cant_hours_suple
                self.wage_hours_suple = cantidad_horas_suple * 1.5
            else:
                cantidad_horas_suple = self.cant_hours_suple * self.contract_id.hour_value
                self.wage_hours_suple = cantidad_horas_suple * 1.5

    @api.depends('cant_hours_ext')
    def _get_wage_hours_ext(self):
        if self.contract_id.hour_value > 0:
            if self.contract_id.type_day == 'partial':
                cantidad_horas_ext = ((self.contract_id.value_for_parcial)/self.contract_id.contracted_hours) *  self.cant_hours_ext
                self.wage_hours_ext = cantidad_horas_ext * 2.0
            else:
                cantidad_horas_ext = self.cant_hours_ext * self.contract_id.hour_value
                self.wage_hours_ext = cantidad_horas_ext * 2.0

    @api.depends('cant_hours_night')
    def _get_wage_hours_night(self):
        for li in self:
            if li.contract_id.hour_value > 0:
                if li.contract_id.type_day == 'partial':
                    cantidad_horas_night = ((li.contract_id.value_for_parcial) / li.contract_id.contracted_hours) * li.cant_hours_night
                    li.wage_hours_night = cantidad_horas_night * 0.25
                else:
                    cantidad_horas_night = li.cant_hours_night * li.contract_id.hour_value
                    li.wage_hours_night = cantidad_horas_night * 0.25

    wage_hours_ext = fields.Float(u'Monto de Horas Extraordinaria 100%', compute="_get_wage_hours_ext",
                                  readonly=False, required=False, states={}, help=u"", store=True)
    wage_hours_suple = fields.Float(u'Monto de Horas Suplementarias 50%', compute="_get_wage_hours_suple",
                                    readonly=False, required=False, states={}, help=u"",store=True)
    wage_hours_night = fields.Float(u'Monto de Horas Nocturas', compute="_get_wage_hours_night",
                                    readonly=False, required=False, states={}, help=u"",store=True)

    #Boton Inteligente Método
    transaction_ids = fields.One2many('hr.scheduled.transaction', 'overtime_id', string=u'Transacciones programadas',
                                      required=False, readonly=False, states=STATES, help=u"")

    @api.depends('transaction_ids')
    def _get_total_transaccion(self):
        self.trasaccion_count = len(self.transaction_ids)
    trasaccion_count = fields.Integer(string=u'# Transaccion programada',
                                      store=False, compute='_get_total_transaccion', help=u"")

    def action_view_transaction(self):
        self.ensure_one()
        transactions = self.mapped('transaction_ids')
        action = self.env.ref('ec_payroll.action_hr_scheduled_transaction_inputs_view').read()[0]
        action['domain'] = [('id', '=', transactions.ids)]
        return action


    def action_draft(self):
        self.state = 'draft'


    def action_request(self):
        if not self.number:
            seq_model = self.env['ir.sequence']
            for secuencia in self:
                secuencia.number = seq_model.next_by_code('request.overtime')
        self.state = 'request'


    def action_done(self):
        for rec in self:
            scheduled_transaction_model = self.env['hr.scheduled.transaction']
            if rec.wage_hours_ext:
                if not  self.env.company.category_transaction_hour_extra_id:
                    raise ValidationError(u'Debe configurar la regla extraordinaria en compañía')
                new_scheduled_transaction_extr = scheduled_transaction_model.create({
                    'overtime_id': rec.id,
                    'employee_id': rec.employee_id.id,
                    'rule_id':  self.env.company.category_transaction_hour_extra_id.id,
                    'name': rec.reason if rec.reason else self.env.company.category_transaction_hour_extra_id.name,
                    'code': _(u'Cod. Hora Extraordinaria %s') % str(rec.number),
                    'date': rec.date_from,
                    'amount': rec.cant_hours_ext,
                    'type': 'input'
                })
                rec.write({'transaction_ids': [(4, new_scheduled_transaction_extr.id)],})
            if rec.wage_hours_suple:
                if not self.env.company.category_transaction_hour_suple_id:
                    raise ValidationError(u'Debe configurar la regla suplementaria en compania')
                new_scheduled_transaction_suple = scheduled_transaction_model.create({
                    'overtime_id': rec.id,
                    'employee_id': rec.employee_id.id,
                    'rule_id': self.env.company.category_transaction_hour_suple_id.id,
                    'name': rec.reason if rec.reason else self.env.company.category_transaction_hour_suple_id.name,
                    'code': _(u'Cod. Hora Suplementaria %s') % str(rec.number),
                    'date': rec.date_from,
                    'amount': rec.cant_hours_suple,
                    'type': 'input'
                })
                rec.write({'transaction_ids': [(4, new_scheduled_transaction_suple.id)], })
            if rec.wage_hours_night:
                if not  self.env.company.category_transaction_hour_night_id:
                    raise ValidationError(u'Debe configurar la regla nocturna en compania')
                new_scheduled_transaction_night = scheduled_transaction_model.create({
                    'overtime_id': rec.id,
                    'employee_id': rec.employee_id.id,
                    'rule_id':  self.env.company.category_transaction_hour_night_id.id,
                    'name': rec.reason if rec.reason else self.env.company.category_transaction_hour_night_id.name,
                    'code': _(u'Cod. Hora Nocturna %s') % str(rec.number),
                    'date': rec.date_from,
                    'amount': rec.cant_hours_night,
                    'type': 'input'
                })
                rec.write({'transaction_ids': [(4, new_scheduled_transaction_night.id)], })
            rec.state = 'done'



    def action_rejected(self):
        self.state = 'rejected'

      
                        
