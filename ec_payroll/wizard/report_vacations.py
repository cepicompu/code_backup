import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
from odoo import api, fields, models, tools, _
from odoo.tools import date_utils, io
try:
    from odoo.tools.misc import xlsxwriter, workbook
except ImportError:
    import xlsxwriter
import io


class reportDeduction(models.AbstractModel):
    _name = 'report.ec_payroll_advance.report_vacations'

    @api.model
    def get_details(self, data=False, employee_type=False, current_date=False):
        return {'employee_type': employee_type,
                'vals': data,
                'current_date': current_date,
                'currency_id': self.env.company.currency_id,
                }

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        data.update(self.get_details(data['reporte'], data['employee_type'], data['current_date']))
        return data


class reportVacationsWizard(models.TransientModel):
    _name = 'report.vacations.wizard'

    def print_pdf_report(self):
        return
        # employees = self.env['hr.employee'].search([('employee_type', '=', self.employee_type)])
        # # employees = self.env['hr.request.vacations'].search([('employee_id.employee_type', '=', self.employee_type)])
        # report = []
        # data = {}
        # for exp in employees:
        #     state = 'Borrador'
        #     if exp.state=='send':
        #         state = 'Enviado'
        #     if exp.state=='done':
        #         state = 'Aprobado'
        #     if exp.state=='pay':
        #         state = 'Pagado'
        #     report.append({'employee': str(exp.employee_id.name.upper()),
        #                    'identification': str(exp.employee_id.identification_id),
        #                    'state': state,
        #                    'holidays': str(''),# hay que ver que desarolla harry
        #                    'period': str(''),# igual
        #                    })
        # report = sorted(report, key=lambda i: i['employee'])
        # data.update({'reporte': report,
        #              'current_date': datetime.today(),
        #              })
        # return self.env.ref('ec_payroll_advance.action_report_vacations').report_action([], data=data)
    	


    def print_xls_report(self):
        # employees = self.env['hr.employee'].search([('employee_type', '=', self.employee_type)])
        employees = self.env['hr.request.vacations'].search([('employee_id.employee_type', '=', self.employee_type)])
        report = []
        data = {}
        for exp in employees:
            employee_type = 'ACADÉMICO'
            if exp.employee_id.employee_type == 'admin':
                employee_type = 'ADMINISTRATIVO'
            state = 'Borrador'
            if exp.state == 'send':
                state = 'Enviado'
            if exp.state == 'done':
                state = 'Aprobado'
            if exp.state == 'pay':
                state = 'Pagado'
            report.append({'employee': str(exp.employee_id.name.upper()),
                           'identification': str(exp.employee_id.identification_id),
                           'employee_type': str(employee_type),
                           'state': state,
                           'holidays': str(''),  # hay que ver que desarolla harry
                           'period': str(''),  # igual
                           })
        report = sorted(report, key=lambda i: i['employee'])
        data.update({'reporte': report,
                     'employee_type': employee_type,
                     'current_date': datetime.today(),
                     })
        return {
            'type': 'ir_actions_xlsx_download',
            'data': {'model': 'report.vacations.wizard',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Reporte de Vacaciones',
                     }
        }



    def get_xlsx_report(self, data, response):
        docids=None
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        bold = workbook.add_format({'bold': True})
        middle = workbook.add_format({'bold': True, 'top': 1})
        left = workbook.add_format({'left': 1, 'top': 1, 'bold': True})
        right = workbook.add_format({'right': 1, 'top': 1})
        top = workbook.add_format({'top': 1})
        report_format = workbook.add_format({'font_size': 14, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': 'black', 'bg_color': '#dcdde6',
                 'border': 1})
        report_format2 = workbook.add_format({'font_size': 10, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': 'black','bg_color': '#dcdde6',
             'border': 1})
        rounding = self.env.company.currency_id.decimal_places or 2
        lang_code = self.env.user.lang or 'en_US'
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        decimal_format =  workbook.add_format({'num_format': '#,##0.00'}),

        sheet = workbook.add_worksheet('REPORTE DE VACACIONES')
        headers={}
       
        sheet.write(2, 0, _('Empleado'), report_format2)
        sheet.write(2, 1, _('Identificación'), report_format2)
        sheet.write(2, 2, _('Clasificación'), report_format2)
        sheet.write(2, 3, _('Estado'), report_format2)
        sheet.write(2, 4, _('Días de Vacaciones'), report_format2)
        sheet.write(2, 5, _('Periodo'), report_format2)
        sheet.merge_range(0, 0, 0, 5, _('REPORTE DE VACACIONES DE TRABAJADORES ' + str(data['employee_type']) + ' - ' + str(data['current_date'])), report_format)
        obj = self.env['report.ec_payroll_advance.report_vacations']._get_report_values(docids,data)

        for line in obj:
            r=line

        row=3
        if obj:
            for lrow in obj['vals']:  
                sheet.write(row, 0, lrow['employee'], )
                sheet.write(row, 1, lrow['identification'], )
                sheet.write(row, 2, lrow['employee_type'], )
                sheet.write(row, 3, lrow['state'], )
                sheet.write(row, 4, lrow['holidays'], )
                sheet.write(row, 5, lrow['period'], )
                row+=1

        COLUM_SIZES = [35, 18, 25, 20, 18, 35, 35, 15]
        for position in range(len(COLUM_SIZES)):
            sheet.set_column(position, position, COLUM_SIZES[position])
        
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
