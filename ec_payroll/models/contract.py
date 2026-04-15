# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api, tools, _
import odoo.addons.decimal_precision as dp
import logging
from odoo.tools import html2plaintext, html_escape
from odoo.http import serialize_exception as _serialize_exception
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
from collections import defaultdict
import pytz


_logger = logging.getLogger(__name__)

# class MailChannel(models.Model):
#     _inherit = 'mail.channel'

#     def _define_command_lead(self):
#         return {'help': _('Alertas de terminación de Contratos')}

#     def _execute_send_notifications(self, **kwargs):
#         partner = self.env.user.partner_id
#         key = kwargs['body']
#         channel_partners = self.env['mail.channel.partner'].search([
#             ('partner_id', '!=', partner.id),
#             ('channel_id', '=', self.id)], limit=1
#         )
#         if key.strip() == '/lead':
#             msg = self._define_command_lead()['help']
#         else:
#             lead = self._convert_visitor_to_lead(partner, channel_partners, key)
#             msg = _('Created a new lead: <a href="#" data-oe-id="%s" data-oe-model="crm.lead">%s</a>') % (lead.id, html_escape(lead.name))
#         self._send_transient_message(partner, msg)

# def _convert_visitor_to_lead(self, partner, channel_partners, key):
#     description = ''.join(
#         '%s: %s\n' % (message.author_id.name or self.anonymous_name, message.body)
#         for message in self.channel_message_ids.sorted('id')
#     )
#     utm_source = self.env.ref('crm_livechat.utm_source_livechat', raise_if_not_found=False)
#     lead = self.env['crm.lead'].create({
#         'name': html2plaintext(key[5:]),
#         'partner_id': channel_partners.partner_id.id,
#         'user_id': None,
#         'team_id': None,
#         'description': html2plaintext(description),
#         'referred': partner.name,
#         'source_id': utm_source and utm_source.id,
#     })
#     lead._onchange_partner_id()
#     return lead






class ContractType(models.Model):

    _name = 'hr.contract.type'
    _description = 'Contract Type'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre', required=True)
    allow_notifications = fields.Boolean(string=u'Recibir notificaciones de contratos')
    sequence = fields.Integer(help="Gives the sequence when displaying a list of Contract.", default=10)
    is_eventual = fields.Boolean(string=u'Es eventual?')
    dias_prueba = fields.Integer(help="Coloque los días de Prueba.", string="Días de Prueba")
    periodo_eventual = fields.Integer(help="Tiempo de Contrato.", string="Tiempo de Contrato")
    calculate_date_end = fields.Boolean(string=u'Calcular fecha contrato prueba?')


class HrContractTypeRule(models.Model):
    _name = 'hr.contract.type.rule'

    name = fields.Char(string='Nombre', required=True)
    structure_id = fields.Many2one('hr.payroll.structure', string='Estructura Salarial')
    rule_ids = fields.One2many('hr.contract.type.rule.line', 'contract_type_rule_id', string='Reglas Salariales')


class HrContractRule(models.Model):
    _name = 'hr.contract.type.rule.line'

    rule_id = fields.Many2one('hr.salary.rule', string='Reglas Salariales', domain=[('active', '=', True),('struct_id','=','contract_type_rule_id.struct_id')])
    amount = fields.Float("Monto")
    is_for_advances = fields.Boolean("Es para Adelantos")
    active = fields.Boolean("Activo", default=True)
    contract_type_rule_id = fields.Many2one('hr.contract.type.rule', string='Reglas')
    struct_id = fields.Many2one('hr.payroll.structure', string='Estructura Salarial', related='contract_type_rule_id.structure_id')


class HrContractLineRule(models.Model):
    _name = 'hr.contract.line.rule'

    rule_id = fields.Many2one('hr.salary.rule', string='Reglas Salariales')
    amount = fields.Float("Monto")
    is_for_advances = fields.Boolean("Es para Adelantos")
    active = fields.Boolean("Activo", default=True)
    contract_id = fields.Many2one('hr.contract', string='Contrato')
    struct_id = fields.Many2one('hr.payroll.structure', string='Estructura Salarial', related='contract_id.struct_id')


class HrTypeSlip(models.Model):
    _name = 'hr.type.slip'
    _description = 'Tipo de Rol'

    name = fields.Char(string='Nombre', required=True)

class HrContract(models.Model):

    _inherit = 'hr.contract'

    def _generate_work_entries(self, date_start, date_stop, force=False):
        # Generate work entries between 2 dates (datetime.datetime)
        # This method considers that the dates are correctly localized
        # based on the target timezone
        # assert isinstance(date_start, datetime)
        # assert isinstance(date_stop, datetime)
        self = self.with_context(tracking_disable=True)
        canceled_contracts = self.filtered(lambda c: c.state == 'cancel')
        if canceled_contracts:
            raise UserError(
                _("Sorry, generating work entries from cancelled contracts is not allowed.") + '\n%s' % (
                    ', '.join(canceled_contracts.mapped('name'))))
        vals_list = []
        self.write({'last_generation_date': fields.Date.today()})

        intervals_to_generate = defaultdict(lambda: self.env['hr.contract'])
        # In case the date_generated_from == date_generated_to, move it to the date_start to
        # avoid trying to generate several months/years of history for old contracts for which
        # we've never generated the work entries.
        self.filtered(lambda c: c.date_generated_from == c.date_generated_to).write({
            'date_generated_from': date_start,
            'date_generated_to': date_start,
        })
        utc = pytz.timezone('UTC')
        for contract in self:
            contract_tz = (contract.resource_calendar_id or contract.employee_id.resource_calendar_id).tz
            tz = pytz.timezone(contract_tz) if contract_tz else pytz.utc
            contract_start = tz.localize(fields.Datetime.to_datetime(contract.date_start)).astimezone(utc).replace(tzinfo=None)
            contract_stop = datetime.combine(fields.Datetime.to_datetime(contract.date_end or datetime.max.date()),datetime.max.time())
            if contract.date_end:
                contract_stop = tz.localize(contract_stop).astimezone(utc).replace(tzinfo=None)
            if date_start > contract_stop or date_stop < contract_start:
                continue
            date_start_work_entries = max(date_start, contract_start)
            date_stop_work_entries = min(date_stop, contract_stop)
            if force:
                intervals_to_generate[(date_start_work_entries, date_stop_work_entries)] |= contract
                continue

            # For each contract, we found each interval we must generate
            # In some cases we do not want to set the generated dates beforehand, since attendance based work entries
            #  is more dynamic, we want to update the dates within the _get_work_entries_values function
            is_static_work_entries = contract.has_static_work_entries()
            last_generated_from = min(contract.date_generated_from, contract_stop)
            if last_generated_from > date_start_work_entries:
                if is_static_work_entries:
                    contract.date_generated_from = date_start_work_entries
                intervals_to_generate[(date_start_work_entries, last_generated_from)] |= contract

            last_generated_to = max(contract.date_generated_to, contract_start)
            if last_generated_to < date_stop_work_entries:
                if is_static_work_entries:
                    contract.date_generated_to = date_stop_work_entries
                intervals_to_generate[(last_generated_to, date_stop_work_entries)] |= contract

        for interval, contracts in intervals_to_generate.items():
            date_from, date_to = interval
            vals_list.extend(contracts._get_work_entries_values(date_from, date_to))

        if not vals_list:
            return self.env['hr.work.entry']

        return self.env['hr.work.entry'].create(vals_list)


    def _get_reference_from_name(self):

        if self.env.context.get('default_employee_id',False):
            return self.env['hr.employee'].browse(self.env.context.get('default_employee_id',False)).name

        return None

    region_decimos = fields.Selection([
        ('costa', 'Costa'),
        ('sierra', 'Sierra'),
    ], string=u'Regíon para Décimos por Defecto',
        readonly=False, required=True, states={}, help=u"", default="costa")
    thirteenth_payment = fields.Selection([
        ('payment_employee', 'Pagar Mensualizado'),
        ('accumulated', 'Acumular'),
        ('no', 'No aplica'),
    ], string=u'Política Décimo Tercero',
        readonly=False, required=True, states={}, default="payment_employee")
    fourteenth_payment = fields.Selection([
        ('payment_employee', 'Pagar Mensualizado'),
        ('accumulated', 'Acumular'),
        ('no', 'No aplica'),
    ], string=u'Política Décimo Cuarto',
        readonly=False, required=True, states={}, default="payment_employee")
    reserve_payment = fields.Selection([
        ('payment_employee', 'Pagar Mensualizado'),
        ('accumulated', 'Acumular'),
        ('no', 'No aplica'),
    ], string=u'Política Fondos de Reserva',
        readonly=False, required=True, states={}, default="payment_employee")
    tipo_salario_neto = fields.Selection([
        ('1','SIN sistema de salario neto'),
        ('2','CON sistema de salario neto'),
    ], 'Sistema de salario neto', required=False, readonly=False, default="1")
    contract_line_rule_ids = fields.One2many('hr.contract.line.rule', 'contract_id', string='Reglas Salariales')
    salary_rule_ids = fields.Many2many('hr.salary.rule', string='Reglas Salariales')
    struct_id = fields.Many2one('hr.payroll.structure','Estructura Salarial',required=True)
    type_day = fields.Selection([('complete','Jornada Completa'),('partial','Jornada Parcial')],string=u'Tipo de Jornada',required=True)
    partial_hours= fields.Float(string=u'Horas Mensuales')
    value_for_parcial = fields.Float(string=u'Valor Mensual Parcial',)
    name = fields.Char('Contract Reference', required=True,default=_get_reference_from_name)
    days_iess = fields.Float(string=u'Días IESS')
    contracted_hours = fields.Float(string=u'Horas Contratadas')
    type_rule_ids = fields.Many2many('hr.contract.type.rule',
                                     'hr_contract_type_rule_rel',
                                     'contract_id',
                                     'contract_type_rule_id',
                                     string='Reglas Salariales')
    type_slip = fields.Many2one('hr.type.slip', string='Tipo de Rol')
    business_contract = fields.Boolean(string='Contrato del Giro del Negocio', help=u"Para pago Fondos de reserva desde el 1 día para el personal de Limpieza")
    define_date_reserve_payment = fields.Boolean(string='Definir Fecha para Pago de Fondos de Reserva')
    date_reserve_payment = fields.Date(string='Fecha para Pago de Fondos de Reserva')
    marital_extension = fields.Boolean(string='Extensión Conyugal')

    @api.onchange('date_start','contract_type_id')
    def onchange_datestart(self):
        if self.contract_type_id.calculate_date_end:
            dias=self.contract_type_id.dias_prueba
            self.trial_date_end= self.date_start +  relativedelta(days=dias)
        elif self.contract_type_id.is_eventual:
            dias = self.contract_type_id.periodo_eventual
            self.date_end = self.date_start + relativedelta(days=dias)
        else:
            self.trial_date_end=None
            self.date_end=None


    @api.onchange('value_for_parcial','partial_hours')
    def onchange_value(self):
        if self.type_day and self.contracted_hours>0:
            self.wage=(self.value_for_parcial*240) /self.contracted_hours

    @api.onchange('contracted_hours')
    def onchange_hours(self):
        if self.contracted_hours:
            self.partial_hours=self.contracted_hours

    @api.onchange('contracted_hours')
    def onchange_days(self):
        if self.type_day and self.contracted_hours>0:
            self.days_iess=self.contracted_hours/8


    @api.depends('wage', 'resource_calendar_id','value_for_parcial','days_iess')
    def _get_partial_values(self):
        for one in self:
            if one.type_day=='complete':
                dias_considerado=30.0
                horas_consideradas=240
                sueldo_considerado=one.wage
            else:
                dias_considerado=one.days_iess
                horas_consideradas = one.contracted_hours
                sueldo_considerado = one.value_for_parcial
            one.daily_value =0
            if dias_considerado!=0:
                one.daily_value = sueldo_considerado / dias_considerado
            if one.resource_calendar_id:
                one.total_hours_day =  one.resource_calendar_id.hours_per_day
                if one.total_hours_day > 8:
                    one.total_hours_day = 8
                if one.total_hours_day!=0 and dias_considerado!=0:
                    one.hour_value = sueldo_considerado / (one.total_hours_day * dias_considerado)
                else:
                    one.hour_value = sueldo_considerado / 240
            else:
                one.total_hours_day = 8
                if one.total_hours_day > 8:
                    one.total_hours_day = 8
                if one.total_hours_day!=0:
                    one.hour_value = sueldo_considerado / (one.total_hours_day * 30)
                else:
                    one.hour_value = sueldo_considerado / 240

    daily_value = fields.Float(u'Valor x Día', digits=dp.get_precision('Payroll Daily'), store=True,
                               compute='_get_partial_values', help=u"")
    total_hours_day = fields.Float(u'Horas x Día', digits=dp.get_precision('Payroll Daily'), store=True,
                                   compute='_get_partial_values', help=u"")
    hour_value = fields.Float(u'Valor x Hora', digits=dp.get_precision('Payroll Daily'), store=True,
                              compute='_get_partial_values', help=u"")
    hr_liquidation_ids = fields.Many2many('hr.liquidation', 'hr_liquidation_contract_rel', 'contract_id',
                                          'liquidation_id', string=u'Liquidaciones de Personal',
                                          required=False, readonly=False, states={}, help=u"")




    def get_contracts_expiring(self):
        days_warning=20
        days_total = 365
        today = datetime.datetime.today()
        dtToday = datetime.date(today.year, today.month, today.day)
        idsContract=self


        for line in self.search([('state','=', 'open'),('contract_type_id.allow_notifications','=',True)]):
            if (days_total - (dtToday - line.date_start).days)<=days_warning:
                # line.send_notificacions()
                idsContract+=line

        if idsContract:
            [x.send_notificacions() for x in idsContract]
            self.env['mail.contract.expire'].search([]).unlink()
            for line in idsContract:
                obj=self.env['mail.contract.expire'].create({'contract_type':line.type_id.name,'employee':line.employee_id.name,'date_start':datetime.datetime.strftime(line.date_start, '%d/%m/%Y')})
                obj.send_mail_notification()

    def send_notificacions(self):
        try:

            channel_odoo_bot_users = '%s, %s , %s' % (self.name, self.env.user.name, datetime.datetime.today())
            channel_obj = self.env['mail.channel']
            channel_id = channel_obj.search([('name', 'like', channel_odoo_bot_users)])
            if not channel_id:
                channel_id = channel_obj.create({
                    'name': channel_odoo_bot_users,
                    'email_send': False,
                    'channel_type': 'chat',
                    'public': 'private',
                    'channel_partner_ids': [(4, self.hr_responsible_id.partner_id.id)]
                })
            channel_id.message_post(
                subject="Recordatorio Contratos por Expirar",
                body="Contrato de %s, por expirar el %s " % (self.name,datetime.datetime(self.date_start.year,self.date_start.month,self.date_start.day)+  relativedelta(years=1)),
                message_type='comment',
                subtype='mail.mt_comment',
            )

            # % (yesterday.strftime('%d-%m-%Y'))
        except Exception as e:
            _logger.critical(e)

    # def action_send_link(self):
    #     self.get_contracts_expiring()

    def _cron_send_cotnracts_expiring(self):
        self.get_contracts_expiring()





    @api.depends('hr_liquidation_ids',)
    def _get_hr_liquidation_count(self):
        self.hr_liquidation_count = len(self.hr_liquidation_ids)
    hr_liquidation_count = fields.Integer(string='Cuenta de Liquidaciones de Personal', store=False,
                                          compute='_get_hr_liquidation_count', help=u"")


    def name_get(self):
        res = []
        for rec in self:
            name = '%s - %s' % (rec.employee_id.display_name, rec.name)
            res.append((rec.id, name))
        return res


    def get_all_structures(self):
        """
        @return: the structures linked to the given contracts, ordered by hierachy (parent=False first,
                 then first level children and so on) and without duplicata
        """

        structure_type_id = self.env.context.get('structure_type', False)
        structures = self.mapped('struct_id').filtered(lambda x: x.type_id.id==structure_type_id)
        # structures = self.mapped('struct_id')
        # import pdb 
        # pdb.set_trace()

        if not structures:
            return []
        # YTI TODO return browse records
        return list(set(structures.ids))


class mailContractsExpire(models.Model):
    _name='mail.contract.expire'
    _description= 'Contratos Expirados'

    contract_type   =   fields.Char(string='Tipo de Contrato')
    employee        =   fields.Char(u'Empleado')
    date_start      =   fields.Char(u'Fecha Inicio Contrato')


    def send_mail_notification(self):


        email_template = self.env.ref('ec_payroll.contract_finish_template')
        # template = self.env['mail.template'].browse(email_template.id)
        email_template.send_mail(self.id, force_send=True,  email_values={'email_to': 'rofer06@gmail.com',
                                                                          'email_cc': 'desipro.sistemas@gmail.com' ,
                                                                          'email_from': 'info@cenecuador.edu.ec'})
