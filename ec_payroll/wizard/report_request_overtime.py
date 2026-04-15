# -*- coding: utf-8 -*-
import calendar
from datetime import date as dt_date

from odoo import fields, models, _
from odoo.exceptions import UserError


MONTH_SELECTION = [
    ('1', 'Enero'),
    ('2', 'Febrero'),
    ('3', 'Marzo'),
    ('4', 'Abril'),
    ('5', 'Mayo'),
    ('6', 'Junio'),
    ('7', 'Julio'),
    ('8', 'Agosto'),
    ('9', 'Septiembre'),
    ('10', 'Octubre'),
    ('11', 'Noviembre'),
    ('12', 'Diciembre'),
]


class RequestOvertimeReportWizard(models.TransientModel):
    _name = 'request.overtime.report.wizard'
    _description = 'Reporte XLSX de Solicitudes de Horas Extras'

    def _default_single_month(self):
        today = fields.Date.context_today(self)
        return str(today.month)

    def _default_start_date(self):
        today = fields.Date.context_today(self)
        return today.replace(day=1)

    def _default_end_date(self):
        today = fields.Date.context_today(self)
        last_day = calendar.monthrange(today.year, today.month)[1]
        return today.replace(day=last_day)

    employee_ids = fields.Many2many('hr.employee', string='Empleados')
    department_ids = fields.Many2many('hr.department', string='Departamentos')
    period_type = fields.Selection(
        selection=[('single', 'Mes único'), ('range', 'Acumulado de meses')],
        string='Tipo de período',
        default='single',
        required=True,
    )
    single_month = fields.Selection(
        selection=MONTH_SELECTION,
        string='Mes',
        default=_default_single_month,
    )
    fiscalyear_config_id = fields.Many2one(
        'hr.fiscalyear.config',
        string='Año',
        domain="[('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, string='Compañía')
    start_date = fields.Date(
        string='Fecha inicial',
        default=_default_start_date,
    )
    end_date = fields.Date(
        string='Fecha final',
        default=_default_end_date,
    )

    def _validate_range(self, date_from, date_to):
        if not date_from or not date_to:
            raise UserError(_('Debe definir la fecha inicial y final.'))
        if date_from > date_to:
            raise UserError(_('La fecha inicial no puede ser mayor a la fecha final.'))

    def _get_period_bounds(self):
        self.ensure_one()
        if self.period_type == 'single':
            if not self.single_month or not self.fiscalyear_config_id:
                raise UserError(_('Debe seleccionar el mes y año a reportar.'))
            month = int(self.single_month)
            year = self.fiscalyear_config_id.fiscalyear_id.date_start.year
            last_day = calendar.monthrange(year, month)[1]
            date_from = dt_date(year, month, 1)
            date_to = dt_date(year, month, last_day)
        else:
            date_from = self.start_date
            date_to = self.end_date
            self._validate_range(date_from, date_to)
        return date_from, date_to

    def action_export_xlsx(self):
        self.ensure_one()
        date_from, date_to = self._get_period_bounds()
        data = {
            'employee_ids': self.employee_ids.ids,
            'department_ids': self.department_ids.ids,
            'date_from': fields.Date.to_string(date_from),
            'date_to': fields.Date.to_string(date_to),
        }
        return self.env.ref('ec_payroll.action_report_request_overtime_xlsx').report_action(self, data=data)
