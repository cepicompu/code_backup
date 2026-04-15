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



class reportAdvantageSocial(models.AbstractModel):
    _name = 'report.ec_payroll_advance.report_advantage_social'

  
    def _get_amount_rule(self,data,rules,employee_id):
        objpayslip=None
      
        if data['not_range']:
            objpayslip=sorted(self.env['hr.payslip.line'].search([('employee_id','=',employee_id),('salary_rule_id','=',rules)]).filtered(lambda x: 
                         x.slip_id.state == 'done' and abs(x.total) > 0),key=lambda x:x.create_date)
        else:
            objpayslip=sorted(self.env['hr.payslip.line'].search([('employee_id','=',employee_id),('salary_rule_id','=',rules),('date_from', '>=', data['start_date']),('date_to', '<=', data['end_date'])]).filtered(lambda x: 
                        x.slip_id.state == 'done' and abs(x.total) > 0),key=lambda x:x.create_date)

        return sum([x.total for x in objpayslip]) or 0.00
        




    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        vals = []
        objpayslip=None
        company = self.env.company


        rule_thirteenth_id=company.rule_thirteenth_id.id 
        rule_fourteenth_id=company.rule_fourteenth_id.id 
        
        rule_vacation_id=company.rule_vacation.id
       
    
        # ,'|','|',('thirteenth_payment','=','accumulated'),('fourteenth_payment','=','accumulated'),
        #             ('reserve_payment','=', 'accumulated')
        for oline in self.env['hr.contract'].search([('state','=','open')]):
            values={}
            values['contract_id']=oline
            values['amount_13']=round(self._get_amount_rule(data,rule_thirteenth_id,oline.employee_id.id),2)
            values['amount_14'] = round(self._get_amount_rule(data,rule_fourteenth_id,oline.employee_id.id),2)
            values['amount_vacations']=round(self._get_amount_rule(data,rule_vacation_id,oline.employee_id.id),2)
               
            vals.append(values)
        data.update({'vals':vals})
        return data

class reportAdvantageSocialWizard(models.TransientModel):
    _name = 'report.advantage.social.wizard'

    not_range = fields.Boolean('Sin Rango de Fecha', default=True)
    start_date  = fields.Date('Fecha Inicial')
    end_date = fields.Date('Fecha Final')



    def print_pdf_report(self):

    	data = {
            'not_range' :   self.not_range,
            'start_date':   self.start_date,
            'end_date'	:   self.end_date,
        }
    	return self.env.ref('ec_payroll_advance.action_report_advantage_social').report_action([], data=data)
    	


    def print_xls_report(self):
    	# date_from = datetime.strptime(str(self.date_from), "%Y-%m-%d")
     #    date_to = datetime.strptime(str(self.date_to), "%Y-%m-%d")
     #    if date_from:
     #        if date_from > date_to:
     #            raise UserError("Fecha debe ser menor a la fecha final")
        data = {
            'not_range' :   self.not_range,
            'start_date':   self.start_date,
            'end_date'  :   self.end_date,
        }
        return {
            'type': 'ir_actions_xlsx_download',
            'data': {'model': 'report.advantage.social.wizard',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Reporte Bneficios Sociales',
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
        decimal_format =  workbook.add_format({'num_format': '#,##0.00'})

        sheet = workbook.add_worksheet('REPORTE BENEFICIOS SOCIALES')
        headers={}
       
        sheet.write(3, 0, _('Empleado'), report_format2)
        sheet.write(3, 1, _('F.Contrato'), report_format2)
        sheet.write(3, 2, _('Décomo Tercero'), report_format2)
        sheet.write(3, 3, _('Décimo Cuarto'), report_format2)
        sheet.write(3, 4, _('Vacaciones'), report_format2)


        headers={'employee':0,'contract':1,'d13':2,'d14':3,'vac':4}

        sheet.merge_range(0, 0, 0, 4, _('REPORTE DE BENEFICIOS SOCIALES'), report_format)
        

        obj = self.env['report.ec_payroll_advance.report_advantage_social']._get_report_values(docids,data)

        for line in obj:
            r=line

        row=3
        if obj:
            for lrow in obj['vals']:  
                row+=1         
              
                sheet.write(row, headers['employee'], lrow['contract_id'].employee_id.name, )
                sheet.write(row, headers['contract'], lrow['contract_id'].date_start, )
                sheet.write(row, headers['d13'], lrow['amount_13'], )
                sheet.write(row, headers['d14'], lrow['amount_14'], )
                sheet.write(row, headers['vac'], lrow['amount_vacations'], )
        
        for line in headers.values():
            sheet.set_column(0,line, 18)
        
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
