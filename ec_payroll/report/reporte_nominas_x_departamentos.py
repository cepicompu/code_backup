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
import pandas as pd
import numpy as np

_logger = logging.getLogger(__name__)

from functools import partial
from odoo.tools.misc import formatLang
from odoo.tools.misc import format_date

class report_reporte_nomina_departamentos(models.AbstractModel):
    
    _name = 'report.ec_payroll.report_nomina_departamentos'


    @api.model
    def get_details(self, cabecera=False,  data=False, current_date=False, period=False, totales=False):
        return {'vals': data,
                'cabecera': cabecera,
                'current_date': current_date,
                'period': period,
                'totales': totales,
                'currency_id': self.env.company.currency_id,
                }

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        data.update(self.get_details(data['cabecera'], data['datos'], data['current_date'], data['period'], data['totales']))
        return data

class report_reporte_nomina_departamentos_a3(models.AbstractModel):
    
    _name = 'report.ec_payroll.report_nomina_departamentos_a3'

    @api.model
    def get_details(self, cabecera=False, data=False, current_date=False, period=False,
                    totales=False):
        return {'vals': data,
                'cabecera': cabecera,
                'current_date': current_date,
                'period': period,
                'totales': totales,
                'currency_id': self.env.company.currency_id,
                }

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        data.update(self.get_details(data['cabecera'], data['datos'], data['current_date'],
                                     data['period'], data['totales']))
        return data