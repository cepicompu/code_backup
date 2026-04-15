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

class AccountInvoice(models.Model):

    _inherit = 'account.move'


    hr_payslip_run_id = fields.Many2one('hr.payslip.run', string=u'Nómina',
                                        required=False, readonly=False, states={}, help=u"", ondelete="restrict")
    expense_id = fields.Many2one('hr.expense', string=u'Gasto',
                                 required=False, readonly=False, states={}, help=u"", ondelete="restrict") 
