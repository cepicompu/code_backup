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

class res_partner(models.Model):

    _inherit = 'res.partner'
    
    
    employee_ids = fields.One2many('hr.employee', 'address_home_id', string=u'Empleados Asociados') 
    
    
    def write(self, vals):
        user_model = self.env['res.users']
        if not self.env.context.get('stop_recurtion', False):
            #Deberia poder cambiar los datos de los contactos a pesar de ser empleados
            if self.env.user.has_group('base.group_partner_manager'):
                for rec in self:
                    users = user_model.search([
                        ('partner_id', '=', rec.id),
                        ])
                    if users:
                        users.sudo().with_context(stop_recurtion=True).write(vals)
                    else:
                        self.with_context(stop_recurtion=True).write(vals)
                return True
        return super(res_partner, self).write(vals)
