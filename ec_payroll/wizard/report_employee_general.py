import json
from datetime import datetime
from odoo.exceptions import UserError
from odoo import api, fields, models, tools, _
from odoo.tools import date_utils, io
try:
    from odoo.tools.misc import xlsxwriter, workbook
except ImportError:
    import xlsxwriter
import io



class reportEmployeeGeneral(models.AbstractModel):
    _name = 'report.ec_payroll_advance.report_employee_general'

    @api.model
    def get_details(self, data=False, current_date=False):
        return {'vals': data,
                'currency_id': self.env.company.currency_id,
                'current_date': current_date,
                }

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        data.update(self.get_details(data['reporte'], data['current_date']))
        return data



class reportEmployeeGeneralkWizard(models.TransientModel):
    _name = 'report.employee.account.general.wizard'


    start_date  = fields.Date('Fecha Inicial')
    end_date = fields.Date('Fecha Final')
    selected_employee = fields.Selection([('open','Activos'),('close','Inactivos')],u'Tipo de Reporte',
                                         default='open', required=True)



    def print_pdf_report(self):
        if self.selected_employee == 'open':
            contracts = self.env['hr.contract'].search([('state','=','open')])
        else:
            contracts = self.env['hr.contract'].search([('state','=','close')])
        report = []
        data = {}
        for exp in contracts:
            iess_day = 0.00
            contract_salary = 0.00
            if exp.type_day=='complete' and exp.daily_value>0.00:
                iess_day = round((exp.wage / exp.daily_value), 2)
                contract_salary = round((exp.wage), 2)
            if exp.type_day=='partial' and exp.daily_value>0.00:
                iess_day = round((exp.value_for_parcial / exp.daily_value), 2)
                contract_salary = round((exp.value_for_parcial), 2)
            has_disability = 'NO'
            percent_disability = 0.00
            disability = ' '
            if exp.employee_id.is_discapacitado:
                has_disability = 'SI'
                percent_disability = exp.employee_id.discapacidad
                disability = exp.employee_id.type_disability_id.name
            thirteenth= 'Acumula'
            if exp.thirteenth_payment=='payment_employee':
                thirteenth = 'Pago Mensualizado'
            fourteenth= 'Acumula'
            if exp.fourteenth_payment=='payment_employee':
                fourteenth = 'Pago Mensualizado'
            reserve= 'Acumula'
            if exp.reserve_payment=='payment_employee':
                reserve = 'Pago Mensualizado'
            contract_time = 160.00
            workday = 'Completa'
            if exp.type_day!='complete':
                contract_time = exp.partial_hours
                workday = 'Parcial'
            payment_method = 'Deposito a Cuenta'
            payment_type = 'Ahorros'
            if exp.employee_id.type_account == 'current':
                payment_type = 'Corriente'
            if exp.employee_id.type_account == 'virtual':
                payment_type = 'Virtual'
            if exp.employee_id.payment_method == 'CHE':
                payment_method = 'Cheque'
            if exp.employee_id.payment_method == 'EFE':
                payment_method = 'Efectivo'
            gender = 'Otro'
            if exp.employee_id.gender=='male':
                gender = 'Hombre'
            if exp.employee_id.gender=='female':
                gender = 'Mujer'
            civil_status = 'Soltero(a)'
            if exp.employee_id.marital=='married':
                civil_status = 'Casado(a)'
            if exp.employee_id.marital=='widower':
                civil_status = 'Viudo(a)'
            if exp.employee_id.marital=='divorced':
                civil_status = 'Divorciado(a)'
            if exp.employee_id.marital=='cohabitant':
                civil_status = 'Cohabitante Legal'
            departure_date = ' '
            if exp.employee_id.service_termination_date:
                departure_date = str(exp.employee_id.service_termination_date)
            report.append({'id': exp.id,
                           'employee': str(exp.name.upper()),
                           'identification': str(exp.employee_id.identification_id),
                           'cargo': str(exp.job_id.name),
                           'gender': str(gender),
                           'department': str(exp.department_id.name),
                           'sede': str(exp.employee_id.sede_id.name),
                           'ccostos': str(''),
                           'begin_date': str(exp.employee_id.service_start_date),
                           'type_contract': str(exp.type_id.name),
                           'iess_days': iess_day,
                           'departure_date': departure_date,
                           'departure_motive': str(' '), #hay que ver como se hace este
                           'has_disability':has_disability,
                           'percent_disability':percent_disability,
                           'disability':disability,
                           'contract_salary':contract_salary,
                           'thirteenth':thirteenth,
                           'fourteenth':fourteenth,
                           'reserve':reserve,
                           'contract_time': contract_time,
                           'workday': workday,
                           'immediate_boss': str(exp.employee_id.parent_id.name.upper()),

                           'payment_method': payment_method,
                           'payment_type': payment_type,
                           'bank': str(exp.employee_id.bank_id.name.upper()),
                           'bank_number': str(exp.employee_id.account_number),

                           'address_home': exp.employee_id.direccion_domicilio or ' ',
                           'cell_phone': exp.employee_id.telefono_movil or ' ',
                           'phone': exp.employee_id.phone or  ' ',
                           'birth_date': str(exp.employee_id.birthday),
                           'birth_age': str(exp.employee_id.age),
                           'birth_month': str(exp.employee_id.birthday.month),
                           'type_blood': str(exp.employee_id.blood_group),
                           'emailp': exp.employee_id.user_id.email or ' ',
                           'country': exp.employee_id.country_id.name or ' ',
                           'state_country': exp.employee_id.state_id.name or ' ',
                           'region': exp.employee_id.region.upper() or ' ',
                           'civil_status': civil_status,



                           })
        report = sorted(report, key=lambda i: i['employee'])
        data.update({'reporte': report,
                     'current_date': datetime.now(),
                     })
        return self.env.ref('ec_payroll_advance.action_report_employee_general').report_action([], data=data)
    	


    def print_xls_report(self):
        if self.selected_employee == 'open':
            contracts = self.env['hr.contract'].search([('state', '=', 'open')])
        else:
            contracts = self.env['hr.contract'].search([('state', '=', 'close')])
        report = []
        data = {}
        for exp in contracts:
            iess_day = 0.00
            contract_salary = 0.00
            if exp.type_day == 'complete' and exp.daily_value > 0.00:
                iess_day = round((exp.wage / exp.daily_value), 2)
                contract_salary = round((exp.wage), 2)
            if exp.type_day == 'partial' and exp.daily_value > 0.00:
                iess_day = round((exp.value_for_parcial / exp.daily_value), 2)
                contract_salary = round((exp.value_for_parcial), 2)
            has_disability = 'NO'
            percent_disability = 0.00
            disability = ' '
            if exp.employee_id.is_discapacitado:
                has_disability = 'SI'
                percent_disability = exp.employee_id.discapacidad
                disability = exp.employee_id.type_disability_id.name
            thirteenth = 'Acumula'
            if exp.thirteenth_payment == 'payment_employee':
                thirteenth = 'Pago Mensualizado'
            fourteenth = 'Acumula'
            if exp.fourteenth_payment == 'payment_employee':
                fourteenth = 'Pago Mensualizado'
            reserve = 'Acumula'
            if exp.reserve_payment == 'payment_employee':
                reserve = 'Pago Mensualizado'
            contract_time = 160.00
            workday = 'Completa'
            if exp.type_day != 'complete':
                contract_time = exp.partial_hours
                workday = 'Parcial'
            payment_method = 'Deposito a Cuenta'
            payment_type = 'Ahorros'
            if exp.employee_id.type_account == 'current':
                payment_type = 'Corriente'
            if exp.employee_id.type_account == 'virtual':
                payment_type = 'Virtual'
            if exp.employee_id.payment_method == 'CHE':
                payment_method = 'Cheque'
            if exp.employee_id.payment_method == 'EFE':
                payment_method = 'Efectivo'
            gender = 'Otro'
            if exp.employee_id.gender == 'male':
                gender = 'Hombre'
            if exp.employee_id.gender == 'female':
                gender = 'Mujer'
            civil_status = 'Soltero(a)'
            if exp.employee_id.marital == 'married':
                civil_status = 'Casado(a)'
            if exp.employee_id.marital == 'widower':
                civil_status = 'Viudo(a)'
            if exp.employee_id.marital == 'divorced':
                civil_status = 'Divorciado(a)'
            if exp.employee_id.marital == 'cohabitant':
                civil_status = 'Cohabitante Legal'
            departure_date = ' '
            if exp.employee_id.service_termination_date:
                departure_date = str(exp.employee_id.service_termination_date)
            report.append({'id': exp.id,
                           'employee': str(exp.name.upper()),
                           'identification': str(exp.employee_id.identification_id),
                           'cargo': str(exp.job_id.name),
                           'gender': str(gender),
                           'department': str(exp.department_id.name),
                           'sede': str(exp.employee_id.sede_id.name),
                           'ccostos': str(''),
                           'begin_date': str(exp.employee_id.service_start_date),
                           'type_contract': str(exp.type_id.name),
                           'iess_days': iess_day,
                           'departure_date': departure_date,
                           'departure_motive': str(' '), #hay que ver como se hace este
                           'has_disability':has_disability,
                           'percent_disability':percent_disability,
                           'disability':disability,
                           'contract_salary':contract_salary,
                           'thirteenth':thirteenth,
                           'fourteenth':fourteenth,
                           'reserve':reserve,
                           'contract_time': contract_time,
                           'workday': workday,
                           'immediate_boss': str(exp.employee_id.parent_id.name.upper()),

                           'payment_method': payment_method,
                           'payment_type': payment_type,
                           'bank': str(exp.employee_id.bank_id.name.upper()),
                           'bank_number': str(exp.employee_id.account_number),

                           'address_home': exp.employee_id.direccion_domicilio or ' ',
                           'cell_phone': exp.employee_id.telefono_movil or ' ',
                           'phone': exp.employee_id.phone or  ' ',
                           'birth_date': str(exp.employee_id.birthday),
                           'birth_age': str(exp.employee_id.age),
                           'birth_month': str(exp.employee_id.birthday.month),
                           'type_blood': str(exp.employee_id.blood_group),
                           'emailp': exp.employee_id.user_id.email or ' ',
                           'country': exp.employee_id.country_id.name or ' ',
                           'state_country': exp.employee_id.state_id.name or ' ',
                           'region': exp.employee_id.region.upper() or ' ',
                           'civil_status': civil_status,

                           })
        report = sorted(report, key=lambda i: i['employee'])
        data.update({'reporte': report,
                     'current_date': datetime.now(),
                     })
        return {
            'type': 'ir_actions_xlsx_download',
            'data': {'model': 'report.employee.account.general.wizard',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Reporte de Empleados',
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

        sheet = workbook.add_worksheet('LISTADO DE EMPLEADOS')
        headers={}

       
        sheet.write(2, 0, _('ID'), report_format2)
        sheet.write(2, 1, _('Identificación'), report_format2)
        sheet.write(2, 2, _('Empleado'), report_format2)
        sheet.write(2, 3, _('Cargo'), report_format2)
        sheet.write(2, 4, _('Sexo'), report_format2)
        sheet.write(2, 5, _('Clasificación'), report_format2)
        sheet.write(2, 6, _('Departamento'), report_format2)
        sheet.write(2, 7, _('Sede'), report_format2)

        sheet.write(2, 8, _('C.Costos'), report_format2)
        sheet.write(2, 9, _('F.Ingreso'), report_format2)
        sheet.write(2, 10, _('T.Contrato'), report_format2)
        sheet.write(2, 11, _('Días IESS'), report_format2)
        sheet.write(2, 12, _('Fecha Baja'), report_format2)
        sheet.write(2, 13, _('Motivo Salida'), report_format2)

        sheet.write(2, 14, _('Tiene Discapacidad?'), report_format2)
        sheet.write(2, 15, _('Discapacidad'), report_format2)
        sheet.write(2, 16, _('%Disc.'), report_format2)
        sheet.write(2, 17, _('Sueldo Contrato'), report_format2)
        sheet.write(2, 18, _('Acum. 13ero.'), report_format2)
        sheet.write(2, 19, _('Acum. 14to'), report_format2)
        sheet.write(2, 20, _('Acum. F.Reserva'), report_format2)
        sheet.write(2, 21, _('Horas Contrato'), report_format2)
        sheet.write(2, 22, _('Jornada'), report_format2)
        sheet.write(2, 23, _('Jefe Inmediato'), report_format2)

        sheet.write(2, 24, _('Forma Pago'), report_format2)
        sheet.write(2, 25, _('Tipo Cuenta'), report_format2)
        sheet.write(2, 26, _('Banco'), report_format2)
        sheet.write(2, 27, _('#Cuenta'), report_format2)

        sheet.write(2, 28, _('Dirección'), report_format2)
        sheet.write(2, 29, _('Teléfono'), report_format2)
        sheet.write(2, 30, _('Celular'), report_format2)
        sheet.write(2, 31, _('Estado Civil'), report_format2)
        sheet.write(2, 32, _('F.Nacimiento'), report_format2)
        sheet.write(2, 33, _('Edad'), report_format2)
        sheet.write(2, 34, _('Mes Cumple.'), report_format2)
        sheet.write(2, 35, _('Tipo Sangre'), report_format2)
        sheet.write(2, 36, _('Correo Personal'), report_format2)
        sheet.write(2, 37, _('País Nac'), report_format2)
        sheet.write(2, 38, _('Provincia'), report_format2)
        sheet.write(2, 39, _('Región'), report_format2)
        if data['employee_type'] == 'open':
            sheet.merge_range(0, 0, 0, 39, _(u'LISTADO DE EMPLEADOS ACTIVOS - '+ str(data['current_date'])), report_format)
        else:
            sheet.merge_range(0, 0, 0, 39, _(u'LISTADO DE EMPLEADOS INACTIVOS - '+ str(data['current_date'])), report_format)
        
        obj = self.env['report.ec_payroll_advance.report_employee_general']._get_report_values(docids,data)
        for line in obj:
            r=line

        row=3
        if obj:
            for lrow in obj['vals']:  
                sheet.write(row, 0, lrow['id'], )
                sheet.write(row, 1, lrow['identification'], )
                sheet.write(row, 2, lrow['employee'], )
                sheet.write(row, 3, lrow['cargo'], )
                sheet.write(row, 4, lrow['gender'], )
                sheet.write(row, 5, lrow['clasificacion'], )
                sheet.write(row, 6, lrow['department'], )
                
                sheet.write(row, 7, lrow['sede'], )
                sheet.write(row, 8, lrow['ccostos'], )

                sheet.write(row, 9, lrow['begin_date'], )
                sheet.write(row, 10, lrow['type_contract'], )
                sheet.write(row, 11,lrow['iess_days'], )
                sheet.write(row, 12, lrow['departure_date'], )

                sheet.write(row, 13, lrow['departure_motive'], )

                sheet.write(row, 14, lrow['has_disability'], )
                sheet.write(row, 15, lrow['disability'], )

                sheet.write(row, 16, lrow['percent_disability'] , )
                sheet.write(row, 17, lrow['contract_salary'], )
                sheet.write(row, 18, lrow['thirteenth'], )
                sheet.write(row, 19, lrow['fourteenth'], )
                sheet.write(row, 20, lrow['reserve'], )
                sheet.write(row, 21, lrow['contract_time'], )
                sheet.write(row, 22, lrow['workday'], )
                sheet.write(row, 23, lrow['immediate_boss'], )
                sheet.write(row, 24, lrow['payment_method'], )
                sheet.write(row, 25, lrow['payment_type'], )
                sheet.write(row, 26, lrow['bank'], )
                sheet.write(row, 27, lrow['bank_number'], )
                sheet.write(row, 28, lrow['address_home'], )
                sheet.write(row, 29, lrow['phone'], )
                sheet.write(row, 30, lrow['cell_phone'] )
                sheet.write(row, 31, lrow['civil_status'], )
                sheet.write(row, 32, lrow['birth_date'], )
                sheet.write(row, 33, lrow['birth_age'],)
                sheet.write(row, 34, lrow['birth_month'], )
                sheet.write(row, 35, lrow['type_blood'], )
                sheet.write(row, 36, lrow['emailp'], )
                sheet.write(row, 37, lrow['country'], )
                sheet.write(row, 38, lrow['state_country'], )
                sheet.write(row, 39, lrow['region'], )
                row += 1

        COLUM_SIZES = [10, 15, 35, 18, 15, 25, 25, 15, 20, 20, 20, 10, 20, 35, 15, 25, 15, 18, 18, 18, 18, 18, 18, 25, 18, 18, 25, 25, 25, 15, 15, 15, 15, 15, 15, 15, 25, 15, 15, 15]
        for position in range(len(COLUM_SIZES)):
            sheet.set_column(position, position, COLUM_SIZES[position])
        
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()

