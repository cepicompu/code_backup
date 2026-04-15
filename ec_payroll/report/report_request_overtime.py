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
import odoo

_logger = logging.getLogger(__name__)


class ReporteRequestOvertime(models.TransientModel):     

    _name = 'report.request.overtime'
     
    
    def getReportRequestOvertimeData(self):
        request_overtime_model = self.env['request.overtime']
        ids = self.env.context.get('active_ids')
        empleados_dict = {}
        # import pdb 
        # pdb.set_trace()
        for overtime_line in request_overtime_model.browse(ids):
            empleados_dict.setdefault(overtime_line.employee_id.id, {
                'total_h_extra': 0.0,
                'total_h_suple': 0.0,
                'total_monto_h_extra': 0.0,
                'total_monto_h_suple': 0.0,
                'nombre_empleado': overtime_line.employee_id.name,
                'cedula': overtime_line.employee_id.identification_id
                })
            empleados_dict[overtime_line.employee_id.id]['total_h_extra'] +=  overtime_line.cant_hours_ext 
            empleados_dict[overtime_line.employee_id.id]['total_h_suple'] +=  overtime_line.cant_hours_suple 
            empleados_dict[overtime_line.employee_id.id]['total_monto_h_extra'] +=  overtime_line.wage_hours_ext 
            empleados_dict[overtime_line.employee_id.id]['total_monto_h_suple'] +=  overtime_line.wage_hours_suple
        return {
            'lines': empleados_dict,
            }
            
class RequestOvertimeParser(models.AbstractModel):    
    
    _name = 'report.ec_payroll.report_request_overtime'

    @api.model
    def _get_report_values(self, docids, data=None):
        # import pdb 
        # pdb.set_trace()
        context = self.env.context.copy()
        if docids:
            context.update({
                'active_id': docids[0],
                'active_ids': docids,
                })
        request_overtime_model = self.env['report.request.overtime']
        return request_overtime_model.with_context(context).getReportRequestOvertimeData()

