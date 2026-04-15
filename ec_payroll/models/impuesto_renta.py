# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tools.misc import formatLang
from odoo.tools import float_is_zero, float_compare, float_round
from odoo.osv import expression
from collections import OrderedDict
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
from odoo import SUPERUSER_ID
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from lxml import etree
import calendar
import logging
_logger = logging.getLogger(__name__)


class hr_scheduled_transaction_category(models.Model):
    _inherit = 'hr.scheduled.transaction.category'

    apply_report_ir =   fields.Boolean('Para reporte 107')
    sign_report =   fields.Integer('Signo en el reporte', default=False)
    code_report =   fields.Char('Código en reporte ')


    @api.onchange('sign_report')
    def _onchange_sign_report(self):
        if self.sign_report > 0:
            self.sign_report=1
        else:
            self.sign_report=-1


    @api.model_create_multi
    def create(self, vals):
        for v in vals:
            if 'name' in v:
                v['name'] = v['name'].upper()
        result = super(hr_scheduled_transaction_category, self).create(vals)
        return result


    def write(self, vals):
        if 'name' in vals:
            vals.update({'name': vals['name'].upper()})
        result = super(hr_scheduled_transaction_category, self).write(vals)
        return result


class hrRules(models.Model):
    _inherit='hr.salary.rule'

    apply_report_ir =   fields.Boolean('Para reporte 107')
    sign_report =   fields.Integer('Signo en el reporte', default=False)
    code_report =   fields.Char('Código en reporte ')


    api.onchange('sign_report')
    def _onchange_sign_report(self):
        if self.sign_report > 0:
            self.sign_report=1
        else:
            self.sign_report=-1






class hr_impuesto_renta_referencia(models.Model):
    '''
    Open ERP Model
    '''
    _name = 'hr.impuesto.renta.referencia'
    _description = 'hr.impuesto.renta.referencia'

    percentage = fields.Float('Porcentaje de Execedente', digits=dp.get_precision('Account'), required=True)
    desde = fields.Float('Fraccion Basica', digits=dp.get_precision('Account'), required=True)
    hasta = fields.Float('Exceso Hasta', digits=dp.get_precision('Account'), required=True)
    impuesto_fraccion = fields.Float('Impuesto a la fraccion basica', required=True)
    fiscalyear_id = fields.Many2one('account.fiscalyear', 'Periodo Fiscal', required=True)

    _rec_name = 'percentage'

    @api.model
    def _get_level(self, monto=0.0, date=False):
        if not date:
            date = fields.Date.context_today(self)
        criteria = [('fiscalyear_id.date_stop','>=',date),('fiscalyear_id.date_start','<=',date)]
        for level in self.search(criteria):
            #es un nivel final del listado
            if level.desde > 0 and level.hasta == 0:
                if monto >= level.desde:
                    return level.id
            #es un nivel inicial del periodo
            if level.hasta > 0 and level.desde == 0:
                if monto < level.hasta:
                    return level.id
            #Es un nivel intermedio
            if level.hasta > 0 and level.desde > 0:
                if monto < level.hasta and monto >= level.desde:
                    return level.id
        return False

    @api.model
    def get_monto_retencion_mes(self,employee_id, monto=0.0, date=False):
        mes = date.month
        year = date.year
        # para pruebas IR
        if employee_id.id==12770:
            a = 1
        contract_id = self.env['hr.contract'].search([('employee_id','=',employee_id.id)])
        if len(contract_id)!=0:
            contract_id = contract_id[0]
        else:
            raise UserError(_(u'El empleado no tiene un contrato activo'))
        valor_rebaja = 0

        mes_start = 0
        if contract_id.date_start.year == year:
            mes_start = contract_id.date_start.month - 1

        fiscalyear_id = self.env['account.fiscalyear'].search([('name','=',date.year)])
        if len(fiscalyear_id)!=0:
            fiscalyear_id = fiscalyear_id[0]
        else:
            raise UserError(_(u'No esta configurado correctamente el año fiscal'))
        sbu = self.env['hr.fiscalyear.config'].search([('fiscalyear_id', '=', fiscalyear_id.id)])
        if len(sbu)!=0:
            sbu = sbu[0]
        else:
            raise UserError(_(u'No esta configurado correctamente el SBU'))

        renta_acumulated = 0.00
        h_ext = 0.00
        IrAcumulated = self.env['payroll.provision'].search([('month', '<', mes),
                                                             ('year', '=', year),
                                                             ('name', '=', employee_id.id)])
        for irac in IrAcumulated:
            renta_acumulated += irac.impuesto_renta
            h_ext += irac.h_50
            h_ext += irac.h_100
            h_ext += irac.h_noct

        # buscar horas extras del mes actual:
        day_calendar = calendar.monthrange(year,mes)
        day_calendar = day_calendar[1]
        date_start = datetime.strptime(str(year)+"-"+str(mes)+"-"+str(1), "%Y-%m-%d").date()
        date_end = datetime.strptime(str(year)+"-"+str(mes)+"-"+str(day_calendar), "%Y-%m-%d").date()
        o_ingrs = self.env['hr.scheduled.transaction'].search([('date','>=',date_start),
                                                               ('date','<=',date_end),
                                                               ('type','=','input'),
                                                               ('employee_id','=',employee_id.id)])
        for o_ingr in o_ingrs:
            if o_ingr.category_id.code == 'OINGR':
                h_ext += o_ingr.amount
        sueldo_basico = sbu.sbu
        mesesproyectar = 12 - (mes)
        if contract_id.type_day=="complete":
            sueldo_base=contract_id.wage
        else:
            sueldo_base=contract_id.value_for_parcial
        salariodevengado = sueldo_base * (mes-mes_start)
        totalingresos = salariodevengado + (sueldo_base * mesesproyectar) + h_ext
        aporteiessanual = totalingresos * (9.45/100)
        fondos_reserva = round((((salariodevengado * (8.33)) / 100) * 12),2)
        conf_impuest_renta = self.env['hr.impuesto.renta.referencia'].search([('fiscalyear_id','=',fiscalyear_id.id)])
        # baseimponible = totalingresos - aporteiessanual - exoneraciondiscapacidad - exoneracionterceraedad
        baseimponible = totalingresos - aporteiessanual
        fraccionbasica = 0.00
        impuestofraccionbasica = 0.00
        impuestofraccionexcedente = 0.00
        for configuracion in conf_impuest_renta:
            if (baseimponible >= configuracion.desde and baseimponible < configuracion.hasta) or (baseimponible >= configuracion.desde and configuracion.hasta == 0):
                fraccionbasica = configuracion.desde
                impuestofraccionbasica = configuracion.impuesto_fraccion
                impuestofraccionexcedente = configuracion.percentage
        impuestorentacalculo = (((baseimponible - fraccionbasica) * impuestofraccionexcedente) / 100 + impuestofraccionbasica)
        # impuestorentacalculo = impuestorentacalculo.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        gastos_personales = 0.00
        gastos_personales_empleados = self.env['hr.tabla.ir.deducible.empleado'].search([('fiscalyear_id','=',fiscalyear_id.id),
                                                                                         ('employee_id','=',employee_id.id)])
        for gasto in gastos_personales_empleados:
            gastos_personales +=  gasto.monto_deducir
        fraccion_desgravada_de_ir = round(((11722) * (2.13)),2)
        canasta_basica = round(((sbu.basic_food) * (7)),2)
        ingresos_brutos = totalingresos + salariodevengado + sueldo_basico + fondos_reserva

        cargasnumero = len(employee_id.family_burden_ids)
        if cargasnumero > 5:
            cargasnumero = 5
        cargasFamiliares =self.env['hr.ir.cargas.trabajadores'].search([('numerocargas','=',cargasnumero)])
        for cargaFamiliar in cargasFamiliares:
            valor_rebaja = cargaFamiliar.rebajamaxima
            if gastos_personales < cargaFamiliar.gastosdeducible:
                valor_rebaja = cargaFamiliar.rebajamaxima * (gastos_personales / cargaFamiliar.gastosdeducible)

        impuestorenta = (impuestorentacalculo) - (valor_rebaja)

        mesdivision = 12
        if mes == 1:
            mesdivision = mesdivision
        else:
            mesdivision = mesdivision - (mes - 1)

        impuestorenta = impuestorenta - renta_acumulated
        anticipoimpuestorenta = round((impuestorenta / mesdivision),2)
        if impuestorenta <= 0.00:
            anticipoimpuestorenta = 0

        return anticipoimpuestorenta

    @api.model
    def get_monto_retencion_anual(self, monto=0.0, date=False):
        '''A esta funcion debe pasarse el valor despues de la retencion del iess del anio
        '''
        retencion = 0.0
        if not date:
            date = fields.Date.context_today(self)
        #Se pasa el valor multiplicado por 12 debido a que se necesita calcular la proyeccion anual
        level_id = self._get_level(monto, date)
        if level_id:
            level = self.browse(level_id)
            retencion = (((monto - level.desde) * (level.percentage/100)) + level.impuesto_fraccion)
        return retencion

class impuestoRentaCargas(models.Model):
    '''
    Open ERP Model
    '''
    _name = 'hr.ir.cargas.trabajadores'
    _description="Valor de Retención por cargas"

    numerocargas = fields.Integer(string="Número de Cargas")
    numerocanastas = fields.Integer(string="Número de Canastas")
    gastosdeducible = fields.Float(string="Gastos Deducibles")
    rebajamaxima = fields.Float(string="Rebaja Máxima")

class hr_tabla_deducibles_impuesto_renta_referencia(models.Model):
    '''
    Open ERP Model 
    '''
    _name = 'hr.tabla.ir.deducible'
    _rec_name='tipo_gasto'


    fiscalyear_id   =   fields.Many2one('account.fiscalyear', 'Periodo Fiscal', required=True)
    tipo_gasto      =   fields.Selection([('Vivienda', 'Vivienda'),
                                          ('Alimentacion', 'Alimentación'),
                                          ('Educacion', 'Educación'),
                                          ('Vestimenta','Vestimenta'),
                                          ('Salud','Salud'),
                                          ('Enf_raras','Enfermedades Raras, Catastrófica o Huérfanas'),
                                          ('Turismo','Turismo')],'Tipo de Gasto')
    code_report =   fields.Char('Código en reporte IR')
    monto_maximo    =   fields.Float('Monto Máximo')
    porcentaje = fields.Float('Porcentaje',digits=(16,4))

    _sql_constraints = [('code_deducibles', 'unique (fiscalyear_id, tipo_gasto)', _('El código de gasto y año fiscal deben ser únicos!')), ]

    def get_monto(self,date):
        # import pdb 
        # pdb.set_trace()
        anio=date.year
        return sum(self.search([('fiscalyear_id.name','=',str(anio))]).mapped('monto_maximo'))

    def get_monto_tipo_gasto(self,date,tipo_gasto):
        # import pdb 
        # pdb.set_trace()
        anio=date.year
        return sum(self.search([('fiscalyear_id.name','=',str(anio)),('tipo_gasto','=',tipo_gasto)]).mapped('monto_maximo'))


class HrDeducibleEmployee(models.Model):
    _name = 'hr.deducible.employee'
    _description = 'Proyección de Gastos Personales'


    fiscalyear_id   =   fields.Many2one('account.fiscalyear', 'Periodo Fiscal', required=True)
    employee_id = fields.Many2one('hr.employee', 'Empleado')
    lines = fields.One2many("hr.tabla.ir.deducible.empleado", 'hr_deducile_employee_id')

class hr_tabla_deducibles_ir_empleado(models.Model):
    '''
    Open ERP Model
    '''
    _name = 'hr.tabla.ir.deducible.empleado'



    fiscalyear_id   =   fields.Many2one('account.fiscalyear', 'Periodo Fiscal', required=True)
    tipo_gasto      =   fields.Selection([('Vivienda', 'Vivienda'),
                                          ('Alimentacion', 'Alimentación'),
                                          ('Educacion', 'Educación'),
                                          ('Vestimenta','Vestimenta'),
                                          ('Salud','Salud'),
                                          ('Enf_raras', 'Enfermedades Raras, Catastrófica o Huérfanas'),
                                          ('Turismo','Turismo')],'Tipo de Gasto')
    monto_deducir   =   fields.Float('Monto Máximo')
    employee_id     =   fields.Many2one('hr.employee','Empleado')
    hr_deducile_employee_id =  fields.Many2one("hr.deducible.employee")


    _sql_constraints = [('code_deducibles_emp', 'unique (fiscalyear_id, tipo_gasto, employee_id)', _('El código de gasto, año fiscal y empleado deben ser únicos!')), ]



    def get_monto(self,employee,date):
        anio=date.year
        return sum(self.search([('employee_id','=',employee.id),('fiscalyear_id.name','=',str(anio))]).mapped('monto_deducir'))


    def get_monto_employee_tipo_gasto(self,employee,date):
        anio=date.year
        total_deducir=0
        ir_deducibles=self.env['hr.tabla.ir.deducible']
        maximo_rubro=0
        for line in self.search([('employee_id','=',employee.id),('fiscalyear_id.name','=',str(anio))]):
            maximo_rubro=ir_deducibles.get_monto_tipo_gasto(date,line.tipo_gasto)
            if line.monto_deducir<=maximo_rubro:
                total_deducir+=line.monto_deducir
            if maximo_rubro <=line.monto_deducir:
                total_deducir+=maximo_rubro
        return maximo_rubro
