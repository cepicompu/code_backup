# -*- coding: utf-8 -*-
import json
from datetime import datetime
from odoo.exceptions import UserError
from odoo import api, fields, models, tools, _
try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter


class ReportEmployeeSimplifiedWizard(models.TransientModel):
    _name = 'report.employee.simplified.wizard'
    _description = 'Wizard para Reporte Simplificado de Empleados'

    selected_employee = fields.Selection(
        [('open', 'Activos'), ('close', 'Inactivos'), ('all', 'Todos')],
        string=u'Tipo de Reporte',
        default='open',
        required=True
    )

    def print_xls_report(self):
        """Generar reporte en Excel con los campos solicitados"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/download/saveas?model=%(model)s&record_id=%(record_id)s&method=%(method)s&filename=%(filename)s' % {
                'filename': 'Reporte_Empleados.xlsx',
                'model': self._name,
                'record_id': self.id,
                'method': 'get_xlsx_report_binary',
            },
            'target': 'new',
        }

    def get_xlsx_report_binary(self):
        """Generar el archivo Excel y retornarlo como binario"""
        if self.selected_employee == 'open':
            contracts = self.env['hr.contract'].search([('state', '=', 'open')])
        elif self.selected_employee == 'close':
            contracts = self.env['hr.contract'].search([('state', '=', 'close')])
        else:
            contracts = self.env['hr.contract'].search([])

        report = []

        for contract in contracts:
            employee = contract.employee_id

            # Sexo
            gender = 'Otro'
            if employee.gender == 'male':
                gender = 'Hombre'
            elif employee.gender == 'female':
                gender = 'Mujer'
            
            # Fecha de salida - usar hasattr para verificar si el campo existe
            departure_date = ''
            if employee.contract_id:
                if employee.contract_id.date_end:
                    departure_date = str(employee.contract_id.date_end)

            # Banco
            bank_name = employee.bank_id.name if employee.bank_id else ''
            
            # Ciudad / Estado
            city = employee.state_id.name if employee.state_id else ''
            
            # Región
            region = employee.region if hasattr(employee, 'region') and employee.region else ''
            
            # Fecha de inicio
            start_date = ''
            if employee.contract_id:
                if employee.contract_id.date_start:
                    start_date = str(employee.contract_id.date_start)

            report.append({
                'identification': employee.identification_id or '',
                'department': contract.department_id.name or '',
                'full_name': employee.name or '',
                'position': contract.job_id.name or '',
                'salary': contract.wage or 0.0,
                'start_date': start_date,
                'departure_date': departure_date,
                'gender': gender,
                'birth_date': str(employee.birthday) if employee.birthday else '',
                'city': city,
                'address': employee.street or '',
                'phone': employee.mobile_phone or '',
                'bank': bank_name,
                'account_number': employee.account_number or '',
                'email': employee.work_email or '',
                'personal_email': getattr(employee, 'email_private', '') or '',
                'analytic_account': self._format_contract_analytics(contract),
                'region': region,
            })

        # Ordenar por nombre completo
        report = sorted(report, key=lambda x: x['full_name'])

        # Usar ec.report.xlsx para crear el workbook
        ec_xlsx = self.env['ec.report.xlsx']
        fp, workbook, worksheet, FORMATS = ec_xlsx.create_workbook('EMPLEADOS')

        # Formatos
        title_format = workbook.add_format({
            'font_size': 14,
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_color': 'white',
            'bg_color': '#0F1570',
            'border': 1
        })

        header_format = workbook.add_format({
            'font_size': 10,
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_color': 'white',
            'bg_color': '#0F1570',
            'border': 1,
            'text_wrap': True
        })

        data_format = workbook.add_format({
            'border': 1,
            'valign': 'top',
            'text_wrap': True
        })

        money_format = workbook.add_format({
            'border': 1,
            'num_format': '#,##0.00',
            'valign': 'top'
        })

        # Título
        if self.selected_employee == 'open':
            title = u'LISTADO DE EMPLEADOS ACTIVOS - ' + str(datetime.now().strftime('%d/%m/%Y'))
        elif self.selected_employee == 'close':
            title = u'LISTADO DE EMPLEADOS INACTIVOS - ' + str(datetime.now().strftime('%d/%m/%Y'))
        else:
            title = u'LISTADO DE EMPLEADOS - ' + str(datetime.now().strftime('%d/%m/%Y'))

        worksheet.merge_range(0, 0, 0, 17, title, title_format)

        # Encabezados
        headers = [
            'Identificación',
            'Departamento',
            'Nombre Completo',
            'Cargo',
            'Sueldo',
            'Fecha de Ingreso',
            'Fecha de Salida',
            'Sexo',
            'Fecha de Nacimiento',
            'Ciudad',
            'Dirección',
            'Número de Teléfono',
            'Banco',
            'Número de Cuenta',
            'Correo',
            'Correo Personal',
            'Cuenta Analítica',
            'Región'
        ]

        for col, header in enumerate(headers):
            worksheet.write(2, col, header, header_format)

        # Datos
        row = 3
        for item in report:
            worksheet.write(row, 0, item['identification'], data_format)
            worksheet.write(row, 1, item['department'], data_format)
            worksheet.write(row, 2, item['full_name'], data_format)
            worksheet.write(row, 3, item['position'], data_format)
            worksheet.write(row, 4, item['salary'], money_format)
            worksheet.write(row, 5, item['start_date'], data_format)
            worksheet.write(row, 6, item['departure_date'], data_format)
            worksheet.write(row, 7, item['gender'], data_format)
            worksheet.write(row, 8, item['birth_date'], data_format)
            worksheet.write(row, 9, item['city'], data_format)
            worksheet.write(row, 10, item['address'], data_format)
            worksheet.write(row, 11, item['phone'], data_format)
            worksheet.write(row, 12, item['bank'], data_format)
            worksheet.write(row, 13, item['account_number'], data_format)
            worksheet.write(row, 14, item['email'], data_format)
            worksheet.write(row, 15, item['personal_email'], data_format)
            worksheet.write(row, 16, item['analytic_account'], data_format)
            worksheet.write(row, 17, item['region'], data_format)
            row += 1

        # Ajustar ancho de columnas
        column_widths = [18, 20, 30, 25, 15, 18, 18, 12, 18, 18, 30, 18, 25, 18, 30, 30, 25, 15]
        for col, width in enumerate(column_widths):
            worksheet.set_column(col, col, width)

        # Cerrar y retornar el archivo
        workbook.close()
        fp.seek(0)
        return fp.read()

    def _format_contract_analytics(self, contract):
        """Retornar etiqueta legible para la distribución analítica del contrato"""
        if not contract:
            return ''
        distribution = contract.analytic_distribution or {}
        if isinstance(distribution, str):
            try:
                distribution = json.loads(distribution)
            except ValueError:
                distribution = {}
        labels = []
        if distribution:
            for distribution_key, percentage in distribution.items():
                model_name = 'account.analytic.account'
                record_id = distribution_key
                if isinstance(distribution_key, str) and ',' in distribution_key:
                    model_name, record_id = distribution_key.split(',', 1)
                try:
                    record_id = int(record_id)
                except (TypeError, ValueError):
                    continue
                if model_name != 'account.analytic.account':
                    continue
                account = self.env[model_name].browse(record_id)
                if not account.exists():
                    continue
                label = account.display_name
                if percentage:
                    label = '%s (%s%%)' % (label, percentage)
                labels.append(label)
        elif contract.analytic_account_id:
            labels.append(contract.analytic_account_id.display_name)
        return ', '.join(labels)
