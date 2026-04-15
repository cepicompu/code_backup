# -*- coding: utf-8 -*-
"""
Wizard simplificado para la creación de reportes del Ministerio de Trabajo.

Su único propósito es recoger los parámetros iniciales, crear el registro
persistente ec.payroll.report y disparar el cálculo.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import calendar
from datetime import date


class WizardMinistryReport(models.TransientModel):
    """Asistente para crear y calcular un reporte de décimos."""

    _name = 'wizard.ministry.report'
    _description = 'Asistente de Reporte Ministerio de Trabajo'

    report_type = fields.Selection([
        ('13th', 'Décimo Tercero'),
        ('14th_sierra', 'Décimo Cuarto - Sierra'),
        ('14th_costa', 'Décimo Cuarto - Costa'),
    ], string='Tipo de Reporte', required=True, default='13th')

    fiscalyear_config_id = fields.Many2one(
        'hr.fiscalyear.config',
        string='Año',
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
    )

    # Solo lectura — para mostrar el período antes de confirmar
    date_start = fields.Date(
        string='Desde',
        compute='_compute_dates',
    )
    date_end = fields.Date(
        string='Hasta',
        compute='_compute_dates',
    )

    @api.depends('report_type', 'fiscalyear_config_id')
    def _compute_dates(self):
        """Muestra el rango de fechas calculado según el tipo y año fiscal."""
        for rec in self:
            if rec.report_type and rec.fiscalyear_config_id and rec.fiscalyear_config_id.fiscalyear_id:
                year = rec.fiscalyear_config_id.fiscalyear_id.date_stop.year
                ds, de = rec._get_date_range(rec.report_type, year)
                rec.date_start = ds
                rec.date_end = de
            else:
                rec.date_start = False
                rec.date_end = False

    def _get_date_range(self, report_type, year):
        """
        Delegado al modelo principal — duplicado aquí para el preview en el wizard.

        :param report_type: str
        :param year: int
        :return: tuple(date, date)
        """
        if report_type == '13th':
            return date(year - 1, 12, 1), date(year, 11, 30)
        elif report_type == '14th_sierra':
            return date(year - 1, 8, 1), date(year, 7, 31)
        elif report_type == '14th_costa':
            last_day_feb = 29 if calendar.isleap(year) else 28
            return date(year - 1, 3, 1), date(year, 2, last_day_feb)
        return False, False

    def action_create_and_calculate(self):
        """
        Crea el registro ec.payroll.report, lanza el cálculo y abre el formulario resultante.

        Retorna una acción que navega al reporte recién creado.
        """
        self.ensure_one()

        if not self.fiscalyear_config_id:
            raise UserError(_('Debe seleccionar un año fiscal.'))

        # Crear la cabecera del reporte
        report = self.env['ec.payroll.report'].create({
            'report_type': self.report_type,
            'fiscalyear_config_id': self.fiscalyear_config_id.id,
            'company_id': self.company_id.id,
        })

        # Calcular (lanza UserError si hay problemas)
        report.action_calculate()

        # Abrir el formulario del reporte recién creado
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reporte de Nómina'),
            'res_model': 'ec.payroll.report',
            'res_id': report.id,
            'view_mode': 'form',
            'target': 'current',
        }
