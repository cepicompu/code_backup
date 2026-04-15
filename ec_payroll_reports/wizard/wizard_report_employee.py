from odoo import api, fields, models

class WizardReportEmployee(models.TransientModel):
    _name = 'wizard.report.employee.custom'
    _description = 'Asistente de Reporte de Empleados'

    date_start = fields.Date(string='Fecha Inicio', required=True, default=fields.Date.context_today)
    date_end = fields.Date(string='Fecha Fin', required=True, default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)

    def print_report(self):
        """
        Método para generar el reporte (Excel/PDF) o devolver una acción.
        """
        # Aquí iría la lógica para llamar al reporte
        return {'type': 'ir.actions.act_window_close'}
