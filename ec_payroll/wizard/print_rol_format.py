# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
import logging
import json
_logger = logging.getLogger(__name__)


class CenReportHrRollExcel(models.AbstractModel):
    _name = 'report.ec_payroll.cen_report_hr_roll_excel'
    _description = 'Reporte de Nómina'

    def get_report_xls(self, data):
        ec_xlsx = self.env['ec.report.xlsx']
        fp, workbook, worksheet, FORMATS = ec_xlsx.create_workbook("Nomina Fin de Mes")

        model_mid = self.env['hr.payslip.run'].browse(self.env.context.get('payroll_id'))
        current_row = 0

        # Encabezado
        worksheet.write(current_row, 0, "Empresa:", FORMATS.get('bold'))
        worksheet.write(current_row, 1, self.env.company.name)
        current_row += 1

        fecha_nomina = model_mid.date_start.strftime('%d/%m/%Y') if model_mid.date_start else ''
        worksheet.write(current_row, 0, "Fecha de la nómina:", FORMATS.get('bold'))
        worksheet.write(current_row, 1, fecha_nomina)
        current_row += 1

        worksheet.write(current_row, 0, "Fecha de impresión:", FORMATS.get('bold'))
        worksheet.write(current_row, 1, self.env['ec.tools'].get_date_now().strftime('%d/%m/%Y'))
        current_row += 2

        # Cabeceras base
        headers = [
            "Cédula", "Nombre", "Ciudad", "Región", "Departamento", "Días trabajados", "Fecha de salida"
        ]

        cabecera_ingreso = []
        cabecera_egresos = []
        cabecera_contribuciones = []

        for slip in model_mid.slip_ids:
            for line in slip.line_ids:
                rule = line.salary_rule_id
                code = rule.category_id.code
                if rule.appears_on_payslip:
                    if code in ('INGR', 'OING', 'OINGSUB', 'OINGRN', 'OINGR') and not any(c['id'] == rule.id for c in cabecera_ingreso):
                        cabecera_ingreso.append({'name': rule.name, 'sequence': rule.sequence_for_report, 'id': rule.id})
                    elif code in ('EGRE', 'OEGR', 'DED', 'ALW') and not any(c['id'] == rule.id for c in cabecera_egresos):
                        cabecera_egresos.append({'name': rule.name, 'sequence': rule.sequence_for_report, 'id': rule.id})
                    elif code == 'CONT' and not any(c['id'] == rule.id for c in cabecera_contribuciones):
                        cabecera_contribuciones.append({'name': rule.name, 'sequence': rule.sequence_for_report, 'id': rule.id})

        cabecera_ingreso.sort(key=lambda x: x['sequence'])
        cabecera_egresos.sort(key=lambda x: x['sequence'])
        cabecera_contribuciones.sort(key=lambda x: x['sequence'])

        # Añadir cabeceras dinámicas
        headers += [c['name'] for c in cabecera_ingreso]
        headers.append("Total de ingresos")
        headers += [c['name'] for c in cabecera_egresos]
        headers.append("Total de egresos")
        headers.append("Total a recibir")
        headers += [c['name'] for c in cabecera_contribuciones]
        headers += ["Forma de pago", "Cuenta bancaria", "Tipo de cuenta", "Banco de empleado", "Centro de costo"]

        for col, header in enumerate(headers):
            worksheet.write(current_row, col, header, FORMATS.get('title_wrap'))
        current_row += 1

        for slip in sorted(model_mid.slip_ids, key=lambda s: s.employee_id.name):
            emp = slip.employee_id
            contract = slip.contract_id

            centro_costo = ""
            if contract.analytic_distribution:
                for key in contract.analytic_distribution:
                    analytic = self.env['account.analytic.account'].browse(int(key))
                    centro_costo += f"{analytic.name} "

            row = [
                emp.identification_id or '',
                emp.name or '',
                '',  # Ciudad
                contract.region_decimos or '',
                emp.department_id.name or '',
                slip.days_worked,
                contract.date_end.strftime('%d/%m/%Y') if contract.date_end else '',
            ]

            # Datos por regla
            ingresos_total = 0.0
            egresos_total = 0.0
            rule_totals = {line.salary_rule_id.id: line.total for line in slip.line_ids if line.salary_rule_id.appears_on_payslip}

            for cab in cabecera_ingreso:
                val = abs(rule_totals.get(cab['id'], 0.0))
                ingresos_total += val
                row.append(val)

            row.append(ingresos_total)

            for cab in cabecera_egresos:
                val = abs(rule_totals.get(cab['id'], 0.0))
                egresos_total += val
                row.append(val)

            row += [
                egresos_total,
                slip.payslip_net,
            ]

            for cab in cabecera_contribuciones:
                val = abs(rule_totals.get(cab['id'], 0.0))
                row.append(val)

            row += [
                dict(emp._fields['payment_method'].selection).get(emp.payment_method, ''),
                emp.bank_account_id.acc_number or '',
                dict(emp.bank_account_id._fields['type_account'].selection).get(emp.bank_account_id.type_account, ''),
                emp.bank_account_id.bank_id.name or '',
                centro_costo.strip(),
            ]

            for col, val in enumerate(row):
                worksheet.write(current_row, col, val)
            current_row += 1

        worksheet.set_column(0, len(headers), 15)
        worksheet.autofilter(0, 0, current_row - 1, len(headers) - 1)

        return ec_xlsx.get_workbook_binary(fp, workbook)



class HrPrintRollFormat(models.TransientModel):

    _name = 'hr.print.roll.format'

    format_type = fields.Selection([('a3','A3'),('a4','A4')],'Formato Reporte',default="a4")
    type_report = fields.Selection([('excel','Excel'),('pdf','PDF')],'Tipo de Reporte',default="excel")
    id_report = fields.Integer()

    def get_report_data(self):
        data = []
        report_model = self.env['report.ec_payroll.cen_report_hr_roll_excel']
        ctx = self.env.context.copy()
        ctx.update({
            'payroll_id': self.id_report,
        })
        return report_model.with_context(ctx).get_report_xls(data)

    def print_excel_report(self):
        self.ensure_one()
        self.id_report = self.env.context.get('active_id')
        return {'type': 'ir.actions.act_url',
                'url': '/download/saveas?model=%(model)s&record_id=%(record_id)s&method=%(method)s&filename=%(filename)s' % {
                    'filename': 'Reporte Nómina.xlsx',
                    'model': self._name,
                    'record_id': self.id,
                    'method': 'get_report_data',
                },
                'target': 'new',
                }


    def print_pdf_report(self):
        self.ensure_one()
        lead_id = self.env.context.get('active_id')
        model_mid = self.env['hr.payslip.run'].search([('id', '=', lead_id)])
        cabecera = []
        datos = []
        totales = []
        tingresos= 0.00
        totros_ingresos= 0.00
        tingresos_no= 0.00
        tegresos= 0.00
        tcontributions= 0.00
        tpago_neto= 0.00
        tsueldo_nomina= 0.00
        for slip in model_mid.slip_ids:
            for line in slip.line_ids:
                if not any(c['name'] == line.salary_rule_id.name for c in cabecera):
                    cabecera.append({'name':line.salary_rule_id.name,
                                     'sequence':line.salary_rule_id.sequence,
                                     'total':0.00,
                                     'id':line.salary_rule_id.id})
        print(cabecera)
        # cabecera = sorted(cabecera, key=lambda i: i['sequence'])
        for slip in model_mid.slip_ids:
            if not any(c['employee_id'] == slip.employee_id.id for c in datos):
                datos.append({'employee_id': slip.employee_id.id,
                              'employee': slip.employee_id.name,
                              'begin_date': slip.contract_date_start or '' ,
                              'department': slip.employee_id.department_id.name or '' ,
                              'identification': slip.employee_id.identification_id,
                              'word_days': slip.days_worked,
                              'word_hours': slip.worked_days_line_ids[0].number_of_hours,
                              'datos': [],
                              'ingresos': slip.inputs,
                              'otros_ingresos': slip.other_inputs,
                              'ingresos_no': slip.other_inputsn,
                              'egresos': slip.outputs,
                              'pago_neto': slip.payslip_net,
                              'contributions': slip.company_contributions,
                              'sueldo_nomina': slip.wage,
                              })

            index_employee = datos.index(list(filter(lambda x: x['employee_id'] == slip.employee_id.id, datos))[0])
            tingresos += datos[index_employee]['ingresos']
            totros_ingresos += datos[index_employee]['otros_ingresos']
            tingresos_no += datos[index_employee]['ingresos_no']
            tegresos += datos[index_employee]['egresos']
            tcontributions += datos[index_employee]['contributions']
            tpago_neto += datos[index_employee]['pago_neto']
            tsueldo_nomina += datos[index_employee]['sueldo_nomina']
            for line in slip.line_ids:
                if not any(c['name'] == line.name for c in datos[index_employee]['datos']):
                    datos[index_employee]['datos'].append({'name':line.name,
                                                           'total':line.total,
                                                           'sequence':line.sequence,
                                                           'id':line.salary_rule_id.id})
            for cline in cabecera:
                print (cline['name'])
                if not any(cline['name'] == c['name'] for c in datos[index_employee]['datos']):
                    datos[index_employee]['datos'].append({'name': cline['name'],
                                                           'total': 0.00,
                                                           'sequence': cline['sequence'],
                                                           'id': cline['id']})
                index_total = datos[index_employee]['datos'].index(list(filter(lambda x: x['name'] == cline['name'], datos[index_employee]['datos']))[0])
                cline['total'] += datos[index_employee]['datos'][index_total]['total']

            # datito = sorted(datos[index_employee]['datos'], key=lambda i: i['sequence'])
            # datos[index_employee]['datos'] = datito
        totales.append({'tingresos': tingresos,
                        'totros_ingresos': totros_ingresos,
                        'tingresos_no': tingresos_no,
                        'tegresos': tegresos,
                        'tcontributions':tcontributions,
                        'tpago_neto': tpago_neto,
                        'tsueldo_nomina': tsueldo_nomina,
                        })


        data = {
            'cabecera': cabecera,
            'totales': totales,
            'datos': sorted(datos, key=lambda i: i['employee']),
            'current_date': datetime.today(),
            'period': str(model_mid.date_start)+" - "+str(model_mid.date_end),

        }

        if self.format_type=='a4':
            return self.env.ref('ec_payroll.action_report_nomina_departamentos').report_action([], data=data)
        else:
            return self.env.ref('ec_payroll.action_report_nomina_departamentos_a3').report_action([], data=data)

        