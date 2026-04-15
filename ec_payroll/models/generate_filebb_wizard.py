# -*- coding: utf-8 -*-

import base64
import time
import calendar
from datetime import date, datetime
from odoo import models, api, fields
from odoo.exceptions import UserError

MONTHS = [
            ('01', 'Enero'),
            ('02', 'Febrero'),
            ('03', 'Marzo'),
            ('04', 'Abril'),
            ('05', 'Mayo'),
            ('06', 'Junio'),
            ('07', 'Julio'),
            ('08', 'Agosto'),
            ('09', 'Septiembre'),
            ('10', 'Octubre'),
            ('11', 'Noviembre'),
            ('12', 'Diciembre'),
          ]

TODAY = date.today()


def get_last_day(year, month):
    """
    :param month: number of the month
    :return: The number of the last day in the month
    """
    value = calendar.monthrange(year, int(month))
    return value[1]


class GenerateFilebbWizard(models.TransientModel):

    _name = 'ecu_hr.generate.filebb.wizard'

    def clean_data(self, data):
        non_asciis = [
            ('ñ', 'n'), ('á', 'a'), ('í', 'i'), ('ó', 'o'), ('ú', 'u'), ('é', 'e'),
            ('Ñ', 'N'), ('Á', 'A'), ('Í', 'I'), ('Ó', 'O'), ('Ú', 'U'), ('É', 'E'),
            ('\n', '\r\n')
        ]
        for non_ascii in non_asciis:
            data = str(data).replace(*non_ascii)
        return data

    
    def create_report(self):
        """
        function called from buttons

        """
        name = "NCR"+time.strftime("%Y%m%d")+'0Z_01'.zfill(4)+'.txt'
        if not self.env.context.get('terceros'):
            self.generate_txt_report()
            return {
                'type': 'ir.actions.act_url',
                'url': '/download/saveas?model=ecu_hr.generate.filebb.wizard&record_id=%s&method=generate_txt_report&field=datas&filename=%s' % (self.id,  name),
                'target': 'new',
            }
        if self.env.context.get('terceros'):
            self.generate_txt_report_third()
            return {
                'type': 'ir.actions.act_url',
                'url': '/download/saveas?model=ecu_hr.generate.filebb.wizard&record_id=%s&method=generate_txt_report_third&field=datas&filename=%s' % (self.id,  name),
                'target': 'new',
            }

    def generate_txt_report_third(self):
        if self.type == 'advance':
            return [self.generate_payroll_advance(third_payment=True)]
        elif self.type == 'payslip':
            return [self.generate_payroll_payslip(third_payment=True)]
        elif self.type == 'fourteenth':
            return [self.generate_payroll_payslip(third_payment=True)]
        elif self.type == 'thirteenth':
            return [self.generate_payroll_payslip(third_payment=True)]
        elif self.type == 'holiday':
            return [self.generate_payroll_payslip(third_payment=True)]


    def generate_txt_report(self):
        if self.type == 'advance':
            return [self.generate_payroll_advance()]
        elif self.type == 'payslip':
            return [self.generate_payroll_payslip()]
        
    months = fields.Selection(MONTHS, string="Mes")
    type = fields.Selection([
        ('advance', 'Anticipo'),
        ('payslip', 'Nómina'),
        ('thirteenth','Décimo Tercero'),
        ('fourteenth','Décimo Cuarto'),
        ('holiday','Vacaciones'),
    ], 'Tipo', select=True, required=True)
    type_say = fields.Selection([
        ('3', 'Tercero'),
        ('4', 'Cuarto')
    ], 'Tipo Decimo', select=True)
    utilidad_id = fields.Many2one('ec_payroll_additional.utilidades', 'Periodo Utilidad', readonly=True)
    year = fields.Selection([(str(num), str(num)) for num in range((datetime.now().year - 5), datetime.now().year + 1)],
                            'Periodo', required=True)

    @api.model
    def default_get(self, fields_list=None):
        res = super(GenerateFilebbWizard, self).default_get(fields_list=fields_list)
        res['type'] = 'advance'
        res['year'] = int(datetime.now().year)
        if self.env.context.get('is_utilidades'):
            res['utilidad_id'] = self.env.context.get('active_id')
            res['type'] = 'utilidad'
        return res

    def _nombre_funcion(self, key, name, type_ref, identification_id, passport_id, acc_number, state,
                        amount_total, concepto, tipo, codigo_banco, codigo_banco_empleado, employee_id=None):
        # import pdb 
        # pdb.set_trace()
        afile = []
        afile.insert(1, "BZDET")  # A001
        afile.insert(2, str(key).zfill(6))  # A002
        afile.insert(3, identification_id[:14].ljust(18))  # A003
        if not type_ref:
            type_ref='cedula'
            # msg = "El Empleado %s No tiene Identificacion y Pasaporte" % name
            # raise UserError(msg)
        if employee_id:
            if not identification_id:
                identification_id = employee_id.address_home_id.ref
        afile.insert(4, type_ref[0].upper()[0])  # A004
        afile.insert(5, identification_id[:14].ljust(14))  # A005
        afile.insert(6, self.clean_data(name[:60]).ljust(60))  # A006
        afile.insert(7, employee_id.payment_method or 'CUE')  # A007
        afile.insert(8, "001")  # A008
        if employee_id.payment_method != 'EFE':
            if not codigo_banco_empleado:
                raise UserError("No tiene asignado un codigo bancario en el empleado %s. Favor agregar el Codigo de identificacion bancaria" % employee_id.name)
            afile.insert(9, codigo_banco_empleado)  # A009
            if state == "current":
                afile.insert(10, "03")  # A010
            elif state == "savings":
                afile.insert(10, "04")  # A010

            if acc_number:
                acc_number = str(acc_number)
                afile.insert(11, acc_number.ljust(20))  # A011
            else:
                msg = u"El Empleado %s No tiene Cuenta Bancaria Configurada " % name
                raise UserError(msg)
        else:
            afile.insert(9, " " * 2)
            afile.insert(10, " " * 2)
            afile.insert(11, " " * 20)
        afile.insert(12, "1")  # A012
        afile.insert(13, str("{0:.2f}".format(amount_total)).replace(".", "").zfill(15))  # A013
        afile.insert(14, concepto.ljust((60-len(concepto))+len(concepto)))  # 014
        afile.insert(15, '0'*15)  # A015
        afile.insert(16, '0'*15)  # A016
        afile.insert(17, '0'*15)  # A017
        afile.insert(18, '0'*20)  # A018
        afile.insert(19, ' '*10)  # A019
        afile.insert(20, ' '*50)  # A020
        afile.insert(21, ' '*50)  # A021
        afile.insert(22, ' '*20)  # A022
        if not employee_id.third_payment:
            afile.insert(23, "RPA")  # A023
        else:
            afile.insert(23, "TER")  # A023; pagos a terceros
        afile.insert(24, ' '*10)  # A024
        afile.insert(25, ' '*10)  # A025
        afile.insert(26, ' '*10)  # A026
        afile.insert(27, ' '*1)  # A027

        if codigo_banco:
            afile.insert(28, str(codigo_banco).zfill(5))  # A028
        else:
            msg = u"La empresa no tiene asignado un codigo del Banco  "
            raise UserError(msg)
        afile.insert(29, str(codigo_banco).zfill(6))  # A029
        if tipo == "pylist":
            afile.insert(30, "RPA")  # A030
        elif tipo == "advance":
            afile.insert(30, "RPA")  # A030
        elif tipo == "tercero":
            afile.insert(30, "RPA")  # A030
        elif tipo == "cuarto":
            afile.insert(30, "RPA")  # A030
        elif tipo == "utilidad":
            afile.insert(30, "RPA")  # A030
        return ''.join(afile)


    def _datos_company(self,amount,fecha):
        cadena_empresa = ""
        cadena_empresa += "C2X" + self.env.company.bank_id.acc_number + self.env.company.name + "     " + "C" + str(
            "%.2f" % amount).replace('.', '').rjust(15, '0')
        cadena_empresa += str(fecha.year) + str(fecha.month) + str(fecha.day) + "000001"
        return cadena_empresa

    def _generate_txt_bank_electr(self, identificacion, amount,name, email, mobile):
        cadena_empresa=""
        cadena = ''
        cadena+="D2X"+identificacion.rjust(10, '0')+name[:17].ljust(17,' ')+"C"+"                    "+"N"+str("%.2f" % amount).replace('.', '').rjust(15, '0')
        cadena+="             "+email.upper()+"        "+mobile.rjust(10, '0')
        return cadena


    def _generate_txt_bank(self, type_account,account_number, employee_bank_id, bank_id, amount,name, type_identification, identification_id):
        cadena = ''
        # TIPOS DE CUENTA
        cadena += "A" if type_account == 'savings' else "C"
        # NUMERO DE CUENTA BANCO DE GUAYAQUIL
        cadena += account_number.rjust(10, '0') if employee_bank_id == bank_id else "0000000000"
        # VALOR
        cadena += str("%.2f" % amount).replace('.', '').rjust(15, '0') if amount else "000000000000000"
        # MOTIVO
        cadena += "0Z" if len("0Z") == 2 else "  "
        # TIPO DE NOTA: Y=CREDITO
        cadena += "Y"
        # AGENCIA: 01 MATRIZ O 06 SUC. MAYOR
        cadena += "01"
        # CÓDIGO BANCO DESTINO PARA EL PAGO INTERBANCARIO
        codigobancodestino = "  "
        if employee_bank_id:
            if not employee_bank_id == bank_id:
                if employee_bank_id.bic:
                    codigobancodestino = int(employee_bank_id.bic)
        cadena += str(codigobancodestino) if len(str(codigobancodestino)) == 2 else "  "
        # NÚMERO DE CUENTA OTROS BANCOS
        cadena += account_number.rjust(18, '0') if not employee_bank_id == bank_id else "                  "
        # NOMBRE DEL TITULAR DE LA CUENTA OTROS BANCOS
        cadena += name[:18].ljust(18,' ') if name else "                "
        # NUEVO MOTIVO
        cadena += "0Z" if len("0Z") == 3 else "   "
        # EMAIL
        # cadena += trabajador.persona.email.ljust(30,' ').upper() if trabajador.persona.email else "                              "
        # CELULAR
        # cadena += trabajador.persona.movil.rjust(10, '0') if trabajador.persona.movil else "          "
        # BANCO DESTINO PARA EL PAGO INTERBANCARIO
        if not len(str(codigobancodestino)) == 3:
            if employee_bank_id == bank_id:
                codigobancodestino = ""
            else:
                codigobancodestino = "   "
        cadena += codigobancodestino
        # TIPO IDENTIFICACION BENEFICIARIO
        tipoidentificacion = "C"
        if type_identification == "pasaporte":
            tipoidentificacion = "P"
        cadena += tipoidentificacion if not employee_bank_id == bank_id else ""
        # NÚMERO DE IDENTIFICACION BENEFICIARIO
        cadena += identification_id.rjust(10,'0') + "   " if not employee_bank_id == bank_id and identification_id else ""

        return cadena
    
    def generate_payroll_advance(self, third_payment=False):
        # import pdb 
        # pdb.set_trace()
        month = self.months
        hr = []
        advance_model = self.env['request.loan.payment']
        key = 0
        year = int(self.year)
        last_day = "{}-{}-{}".format(year, month, get_last_day(year, month))
        first_day = "{}-{}-{}".format(year, month, '01')
        hr_advance = advance_model.search([('request_date', '<=', last_day),
                                           ('request_date', '>=', first_day), ('state', '!=', 'draft'),
                                           ('hr_rule.code', '=', 'ANT-QUIN')], limit=1)
        for hr_ad in hr_advance:
            for line in hr_ad.line_ids:
                if not line.employee_id.bank_id:
                    raise UserError("El empleado %s, no tiene cuenta bancaria configurada" % line.employee_id.name)
        if self.employee_type=="rol_electronico":
            monto=0
            for line in hr_advance.line_ids.filtered(lambda x: x.employee_id.bank_id and (
                    x.employee_id.employee_type == self.employee_type or not self.employee_type)).sorted(
                lambda x: x.employee_id.name):
                monto+=line.amount
            hr.append(self._datos_company(monto,hr_advance.request_date))
            for line in hr_advance.line_ids.filtered(lambda x: x.employee_id.bank_id and (
                    x.employee_id.employee_type == self.employee_type or not self.employee_type)).sorted(
                lambda x: x.employee_id.name):
                emp = line.employee_id
                hr.append(self._generate_txt_bank_electr(emp.identification_id,line.amount,emp.name,emp.work_email,emp.mobile_phone))
        else:
            for line in hr_advance.line_ids.filtered(lambda x: x.employee_id.bank_id and (x.employee_id.employee_type == self.employee_type or not self.employee_type) ).sorted(lambda x: x.employee_id.name):
                key += 1
                employee = line.employee_id
                if employee.bank_id:
                    hr.append(self._generate_txt_bank(employee.type_account, employee.account_number,
                                                      employee.bank_id, self.env.company.bank_id.bank_id,
                                                      line.amount, employee.name, employee.tipo_identificacion, employee.identification_id))
        if not hr:
            msg = "No hay anticipos registrados con estos parametros"
            raise UserError(msg)
        return '\r\n'.join(hr)

    def generate_payroll_payslip(self, third_payment=False,type_slip=False):
        month = self.months
        payslip_model = self.env['hr.payslip']
        hp = []
        key = 0
        year = int(self.year)
        last_day = "{}-{}-{}".format(year, month, get_last_day(year, month))
        first_day = "{}-{}-{}".format(year, month, '01')
        hr_payslips = payslip_model.search([('date_to', '<=', last_day), ('date_from', '>=', first_day)]) #,('state', '=', 'done')
        
        # import pdb
        # pdb.set_trace()
        for hr_py in hr_payslips:
            if not hr_py.employee_id.bank_id:
                raise UserError("El empleado %s, no tiene cuenta bancaria configurada" % hr_py.employee_id.name)
        for hr_py in hr_payslips.filtered(lambda x: x.employee_id.bank_id and (x.employee_id.employee_type == self.employee_type or not self.employee_type) ).sorted(lambda x: x.employee_id.name):
            key += 1
            employee = hr_py.employee_id
            if employee.bank_id:
                hp.append(self._generate_txt_bank(employee.type_account, employee.account_number,
                                                  employee.bank_id, self.env.company.bank_id.bank_id,
                                                  hr_py.payslip_net, employee.name, employee.tipo_identificacion, employee.identification_id))

        if not hp:
            msg = "No hay nomina registrados con estos parametros"
            raise UserError(msg)
        return '\r\n'.join(hp)
