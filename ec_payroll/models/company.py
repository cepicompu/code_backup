# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class HrFiscalyearConfig(models.Model):

    _name = "hr.fiscalyear.config"
    _description = "Configuración de Recursos Humanos por Año"
    _rec_name = "fiscalyear_id"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    fiscalyear_id = fields.Many2one("account.fiscalyear", string="Año", required=True)
    sbu = fields.Float("S.B.U.", required=True, help="Sueldo Básico Unificado")
    basic_food = fields.Float("Canasta Básica", required=True, help="Canasta Básica")

    _sql_constraints = [
        (
            "fiscalyear_uniq",
            "unique (company_id, fiscalyear_id)",
            _("Solo puede tener una configuración de SBU por año"),
        ),
    ]

    # @api.model
    # def create(self, vals):

    #     import pdb
    #     pdb.set_trace()

    #     return  super(HrFiscalyearConfig, self).create(vals)


class ResCompany(models.Model):

    _inherit = "res.company"

    hr_fiscalyear_config_ids = fields.One2many(
        "hr.fiscalyear.config",
        "company_id",
        string="Configuraciones Anuales de Recursos Humanos",
        help="",
        copy=True,
    )
    salarios_account_id = fields.Many2one(
        "account.account", string="Cuenta Contable de Sueldos", ondelete="restrict"
    )
    region_decimos = fields.Selection(
        [
            ("costa", "Costa"),
            ("sierra", "Sierra"),
        ],
        string="Regíon para Décimos por Defecto",
        readonly=False,
        required=True,
        states={},
        help="",
        default="costa",
    )
    costa_mes_d14 = fields.Integer(string="Mes de Pago Costa Décimo Cuarto", default=3)
    costa_dia_d14 = fields.Integer(
        string="Día Máximo de Pago Costa Décimo Cuarto", default=15
    )
    sierra_mes_d14 = fields.Integer(
        string="Mes de Pago Sierra Décimo Cuarto", default=8
    )
    sierra_dia_d14 = fields.Integer(
        string="Día Máximo de Pago Sierra Décimo Cuarto", default=15
    )
    expense_account_id = fields.Many2one(
        "account.account", string="Cuenta de Gastos de Empleados por Defecto"
    )
    default_tax_id = fields.Many2one(
        "account.tax",
        string="Impuesto x Defecto Gastos",
        required=False,
        readonly=False,
        states={},
        help="",
        ondelete="cascade",
    )
    tax_expense_ids = fields.Many2many(
        "account.tax",
        "company_expense_taxes_rel",
        "company_id",
        "tax_id",
        string="Impuestos por Defecto",
        states={},
        help="",
    )
    category_transaction_hour_night_id = fields.Many2one(
        "hr.salary.rule",
        string="Regla Horas Nocturnas",
        required=False,
        ondelete="restrict",
    )
    category_transaction_hour_suple_id = fields.Many2one(
        "hr.salary.rule",
        string="Regla Horas Suplemetarias",
        required=False,
        ondelete="restrict",
    )
    category_transaction_hour_extra_id = fields.Many2one(
        "hr.salary.rule",
        string="Regla Horas Extraordinaria",
        required=False,
        ondelete="restrict",
    )
    rule_thirteenth_id = fields.Many2one(
        "hr.salary.rule",
        string="Regla Décimo Tercero",
        required=False,
        ondelete="restrict",
    )
    rule_fourteenth_id = fields.Many2one(
        "hr.salary.rule",
        string="Regla Décimo Cuarto",
        required=False,
        ondelete="restrict",
    )
    rule_vacation_id = fields.Many2one(
        "hr.salary.rule",
        string="Regla Provisión de Vacaciones",
        required=False,
        ondelete="restrict",
    )
    rule_iess_employee_id = fields.Many2one(
        "hr.salary.rule",
        string="Regla Iess Personal",
        required=False,
        ondelete="restrict",
    )
    rule_fondos_reserva_id = fields.Many2one(
        "hr.salary.rule",
        string="Regla Fondos de Reserva",
        required=False,
        ondelete="restrict",
    )
    rule_sueldo_id = fields.Many2one(
        "hr.salary.rule",
        string="Regla Sueldo Bruto",
        required=False,
        ondelete="restrict",
    )
    egress_porcent_max = fields.Float(
        "Porcentaje Máximo a tomar del Sueldo Mensualmente",
        digits=dp.get_precision("Account"),
        default=50,
    )
    egress_num_max_quota = fields.Integer(
        "Máximo Números de Cuotas", digits=dp.get_precision("Account"), default=6
    )
    bank_code = fields.Char(string="Codigo banco")
    bank_id = fields.Many2one("res.partner.bank", string="Banco")
    rule_vacation = fields.Many2one(
        "hr.salary.rule",
        string="Regla Provisión Vacaciones",
        required=False,
        ondelete="restrict",
    )
    rule_pay_vacation = fields.Many2one(
        "hr.scheduled.transaction.category",
        string="Regla Pago de Vacaciones",
        required=False,
        ondelete="restrict",
    )
    code_rule_pay_vacation = fields.Char(
        string="Codigo para pago de Vacaciones", required=False, ondelete="restrict"
    )
    struct_enjoyd_id = fields.Many2one(
        "hr.payroll.structure",
        string="Estructura Vacaciones (Gozadas)",
        required=False,
        ondelete="restrict",
    )

    work_entry_type = fields.Many2one(
        "hr.work.entry.type",
        string="Tipo de Entrada de Trabajo",
        required=False,
        ondelete="restrict",
    )
    vacations_entry_type = fields.Many2one(
        "hr.work.entry.type",
        string="Tipo de Entrada de Vacaciones",
        required=False,
        ondelete="restrict",
    )
    maternity_entry_type = fields.Many2one(
        "hr.work.entry.type",
        string="Tipo de Entrada de Maternidad",
        required=False,
        ondelete="restrict",
    )
    accident_entry_type = fields.Many2one(
        "hr.work.entry.type",
        string="Tipo de Entrada de Accidente",
        required=False,
        ondelete="restrict",
    )
    disease_entry_type = fields.Many2one(
        "hr.work.entry.type",
        string="Tipo de Entrada de Enfermedad",
        required=False,
        ondelete="restrict",
    )

    struct_thirteenth_pay = fields.Many2one(
        "hr.payroll.structure",
        string="Estructura Pago Décimo Tercer Sueldo",
        required=False,
        help="Estrucutura para pago de décimo tercer sueldo anual",
        ondelete="restrict",
    )
    struct_fourteenth_pay = fields.Many2one(
        "hr.payroll.structure",
        string="Estructura Pago Décimo Cuerto Sueldo",
        required=False,
        help="Estructura para pago de décimo cuerto sueldo anual",
        ondelete="restrict",
    )
    month_start_fourteenth = fields.Integer(
        string="Mes incial de cálculo", required=False, default=3
    )
    day_start_fourteenth = fields.Integer(
        string="Día incial de cálculo", required=False, default=1
    )
    month_end_fourteenth = fields.Integer(
        string="Mes final de cálculo", required=False, default=2
    )
    day_end_fourteenth = fields.Integer(
        string="Día incial de cálculo", required=False, default=28
    )

    journal_salary = fields.Many2one(
        "account.journal", "Diario de Pago por Defecto", required=False
    )
    account_employee_cxc = fields.Many2one(
        "account.account", "Cuenta Cobrar Empleado", required=False
    )
    sri_forma_pago = fields.Many2one("sri.forma.pago", "Forma Pago SRI", required=False)
    structure_type_id = fields.Many2one(
        "hr.payroll.structure.type",
        "Tipo de Estructura",
        required=False,
    )
    used_impuesto_renta = fields.Boolean(
        "Calculo de Impuesto a la Renta?", default=False, required=False
    )

    @api.model
    def get_sbu(self, date=False):
        sbu_model = self.env["hr.fiscalyear.config"]
        if not date:
            date = fields.Date.context_today(self)
        sbus = sbu_model.search(
            [
                ("fiscalyear_id.date_start", "<=", date),
                ("fiscalyear_id.date_stop", ">=", date),
                ("company_id", "=", self.id),
            ]
        )
        if not sbus:
            raise UserError(
                _(
                    "Para la fecha %s no existe configurado el S.B.U. por favor configure en Nomina / Configuración / Configuración"
                )
                % (date)
            )
        return sbus[0].sbu
