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

class hr_payroll_config_settings(models.TransientModel):

    _inherit = 'res.config.settings'

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    hr_fiscalyear_config_ids = fields.One2many(related="company_id.hr_fiscalyear_config_ids", string=u'Configuraciones Anuales de Recursos Humanos',readonly=False)
    region_decimos = fields.Selection([
        ('costa','Costa'),
        ('sierra','Sierra'),
    ], string=u'Regíon para Décimos por Defecto', related="company_id.region_decimos",readonly=False)
    costa_mes_d14 = fields.Integer(string=u'Mes de Pago Costa Décimo Cuarto', related="company_id.costa_mes_d14",readonly=False)
    costa_dia_d14 = fields.Integer(string=u'Día Máximo de Pago Costa Décimo Cuarto', related="company_id.costa_dia_d14",readonly=False)
    sierra_mes_d14 = fields.Integer(string=u'Mes de Pago Sierra Décimo Cuarto', related="company_id.sierra_mes_d14",readonly=False)
    sierra_dia_d14 = fields.Integer(string=u'Día Máximo de Pago Sierra Décimo Cuarto', related="company_id.sierra_dia_d14",readonly=False)
    salarios_account_id = fields.Many2one('account.account', string=u'Cuenta Contable de sueldos', related="company_id.salarios_account_id",
                                          ondelete="restrict",readonly=False)
    expense_account_id = fields.Many2one('account.account', string=u'Cuenta de Gastos de Empleados por Defecto', default_model='account.account',
                                         related="company_id.expense_account_id",readonly=False)
    tax_expense_ids = fields.Many2many(related="company_id.tax_expense_ids",
                                       domain=[('type_tax_use','=','purchase'), ('type_ec', '=', 'iva')],
                                       string=u'Impuestos por Defecto', states={}, help=u"", default_model='account.tax',readonly=False)
    category_transaction_hour_night_id = fields.Many2one('hr.salary.rule', string=u'Regla Horas Nocturnas', related="company_id.category_transaction_hour_night_id",readonly=False)
    category_transaction_hour_suple_id = fields.Many2one('hr.salary.rule', string=u'Regla Horas Suplemetarias', related="company_id.category_transaction_hour_suple_id",readonly=False)
    category_transaction_hour_extra_id = fields.Many2one('hr.salary.rule', string=u'Regla Horas Extraordinaria', related="company_id.category_transaction_hour_extra_id",readonly=False)
    rule_thirteenth_id = fields.Many2one('hr.salary.rule', string=u'Regla Décimo Tercero', required=False, ondelete="restrict", related="company_id.rule_thirteenth_id",readonly=False)
    rule_fourteenth_id = fields.Many2one('hr.salary.rule', string=u'Regla Décimo Cuarto', required=False, ondelete="restrict", related="company_id.rule_fourteenth_id",readonly=False)
    rule_vacation_id = fields.Many2one('hr.salary.rule', string=u'Regla Provisión de Vacaciones', required=False, ondelete="restrict", related="company_id.rule_vacation_id",readonly=False)
    rule_iess_employee_id = fields.Many2one('hr.salary.rule', string=u'Regla Iess Personal', required=False, related="company_id.rule_iess_employee_id",readonly=False)
    rule_fondos_reserva_id = fields.Many2one('hr.salary.rule', string=u'Regla Fondos de Reserva', required=False, related="company_id.rule_fondos_reserva_id",readonly=False)
    rule_sueldo_id = fields.Many2one('hr.salary.rule', string=u'Regla Sueldo Bruto', required=False, related="company_id.rule_sueldo_id",readonly=False)
    egress_porcent_max = fields.Float(u'Porcentaje Máximo a tomar del Sueldo Mensualmente', related="company_id.egress_porcent_max" ,readonly=False)
    egress_num_max_quota = fields.Integer(u'Maximo Números de Cuotas', related="company_id.egress_num_max_quota",readonly=False)

    rule_vacation = fields.Many2one('hr.salary.rule', string=u'Regla Provisión Vacaciones', required=False, related="company_id.rule_vacation",readonly=False)
    rule_pay_vacation = fields.Many2one('hr.scheduled.transaction.category', string=u'Regla Pago de Vacaciones',
                                        required=False, related="company_id.rule_pay_vacation", readonly=False)

    code_rule_pay_vacation =  fields.Char(string=u'Codigo para pago de Vacaciones', required=False,related="company_id.code_rule_pay_vacation",readonly=False)
    struct_enjoyd_id    = fields.Many2one('hr.payroll.structure',string=u'Estructura Vacaciones (Gozadas)', required=False,related="company_id.struct_enjoyd_id",readonly=False)


    work_entry_type =fields.Many2one('hr.work.entry.type',string=u'Tipo de Entrada de Trabajo',required=False,readonly=False,related="company_id.work_entry_type" )
    vacations_entry_type=fields.Many2one('hr.work.entry.type',string=u'Tipo de Entrada de Vacaciones',required=False,readonly=False, related="company_id.vacations_entry_type")
    maternity_entry_type =fields.Many2one('hr.work.entry.type',string=u'Tipo de Entrada de Maternidad',required=False,readonly=False,related="company_id.maternity_entry_type")
    accident_entry_type = fields.Many2one('hr.work.entry.type', string=u'Tipo de Entrada de Accidente', required=False, readonly=False, related="company_id.accident_entry_type")
    disease_entry_type=fields.Many2one('hr.work.entry.type',string=u'Tipo de Entrada de Enfermedad',required=False,readonly=False, related="company_id.disease_entry_type")

    struct_thirteenth_pay = fields.Many2one('hr.payroll.structure', string=u'Estructura Pago Décimo Tercer Sueldo', related="company_id.struct_thirteenth_pay",readonly=False,required=False, help=u"Estrucutura para pago de décimo tercer sueldo anual",
                                            ondelete="restrict")
    struct_fourteenth_pay = fields.Many2one('hr.payroll.structure', string=u'Estructura Pago Décimo Cuerto Sueldo', related="company_id.struct_fourteenth_pay",readonly=False,required=False, help=u"Estructura para pago de décimo cuerto sueldo anual",
                                            ondelete="restrict")
    month_start_fourteenth=fields.Integer(string=u'Mes incial de cálculo',required=False, related="company_id.month_start_fourteenth",readonly=False,default=3)
    day_start_fourteenth=fields.Integer(string=u'Día incial de cálculo',required=False, related="company_id.day_start_fourteenth",readonly=False,default=1)
    month_end_fourteenth=fields.Integer(string=u'Mes final de cálculo',required=False, related="company_id.month_end_fourteenth",readonly=False,default=2)
    day_end_fourteenth=fields.Integer(string=u'Día incial de cálculo',required=False, related="company_id.day_end_fourteenth",readonly=False,default=28)

    journal_salary = fields.Many2one('account.journal','Diario de Pago por Defecto',required=False,related="company_id.journal_salary",readonly=False)
    account_employee_cxc = fields.Many2one('account.account','Cuenta Cobrar Empleado', required=False,related="company_id.account_employee_cxc",readonly=False)
    sri_forma_pago = fields.Many2one('sri.forma.pago','Forma Pago SRI', required=False,related="company_id.sri_forma_pago",readonly=False)
    structure_type_id = fields.Many2one('hr.payroll.structure.type', 'Tipo de Estructura', required=False,related="company_id.structure_type_id",readonly=False)
    used_impuesto_renta = fields.Boolean('Calculo de Impuesto a la Renta?', default=False, required=False,related="company_id.used_impuesto_renta",readonly=False)

    # @api.model
    # def write(self, vals):
    #     if 'hr_fiscalyear_config_ids' in vals:
    #         import pdb 
    #         pdb.set_trace()
    #     return super(hr_payroll_config_settings, self).write(vals)



    @api.constrains(
        'egress_porcent_max',
        'egress_num_max_quota',
    )
    def _check_egress_values(self):
        if self.egress_num_max_quota < 2:
            raise ValidationError(u'El número de descuentos para nómina tiene que ser mayor a 1.')
        if self.egress_porcent_max <= 1:
            raise ValidationError(u'El porcentaje máximo no puede ser menor o igual que 1.')
        if self.egress_porcent_max > 100:
            raise ValidationError(u'El porcentaje máximo no puede ser mayor que 100.')

    def get_journal_salary(self):
        return self.journal_salary

    def get_account_employee_cxc(self):
        return self.account_employee_cxc

    def get_sri_forma_pago(self):
        return self.sri_forma_pago