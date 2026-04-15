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
import logging
_logger = logging.getLogger(__name__)

class hr_family_burden(models.Model):
    
    
    
    @api.depends('birth_date',)
    def _current_age(self):
        res = {}
        today = False
        if self.env.context.get('date_reference'):
            today = datetime.strptime(self.env.context.get('date_reference', False), DF)
        else:
            today = datetime.now()
        dob = today
        if self.birth_date:
            dob =self.birth_date  #  datetime.strptime(self.birth_date, DF)            
        self.age = today.year - dob.year
    
    _name = 'hr.family.burden'
    
    employee_id = fields.Many2one('hr.employee', u'Empleado', required=False, ondelete="cascade") 
    name = fields.Char(u'Nombres', size=255, required=True,)
    last_name = fields.Char(u'Apellidos', size=255, required=True,)
    is_discapacitado = fields.Boolean(u'Presenta Discapacidad?', required=False)
    discapacidad = fields.Float(u'Porcentaje de Discapacidad')
    birth_date = fields.Date(u'Fecha de Nacimiento')
    relationship = fields.Selection([
        ('mother', u'Mamá'),
        ('father', u'Papá'),
        ('child', u'Hijo'),
        ('wife_husband', u'Esposo(a)'),
        ], u'Parentesco', index=True, required=True)
    age = fields.Integer(string=u'Edad Actual', compute='_current_age', store=False)
    identificacion = fields.Char(u'Identificación',size=20)


    def name_get(self):
        res = []
        for rec in self:
            name = rec.name
            if rec.last_name:
                name = name + " " +rec.last_name 
            res.append((rec.id, name))
        return res
    
    @api.model
    def get_family_burden(self, employee_id):
        """
        calcula la carga familiar por empleado
        las cargas son contadas por separado segun el parentesco con el empleado(hijos, conyuge)
        @param employee_id: int, id del empleado
        @return: dict(k,v):(child,wife_husband,total),(N,.....)
        """
        self.ensure_one()
        employee = self.env['hr.employee'].browse(employee_id)
        #obtener cargas para el empleado
        fburdens = self.search([('employee_id','=',employee_id),])
        cargas = {'child': 0,
                  'wife_husband':0,
                  }
        cargas['wife_husband'] += employee.wife_id and 1 or 0
        for fburden in fburdens:
            #Esta discapacitado no importa la edad
            if fburden.is_discapacitado:
                cargas['child'] += 1
            #Los hijos menores de 18 anios
            elif fburden.relationship == 'child' and int(fburden.age) <= 18:
                cargas['child'] += 1
            #La esposa(o) o conviviente
            elif fburden.relationship == 'wife_husband':
                cargas['wife_husband'] += 1
        cargas['total'] = cargas.get('child',0) + cargas.get('wife_husband',0)
        return cargas
