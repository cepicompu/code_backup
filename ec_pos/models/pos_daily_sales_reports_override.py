# -*- coding: utf-8 -*-
from odoo import models, api

class ReportSaleDetails(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'

    @api.model
    def get_sale_details(self, date_start=False, date_stop=False, config_ids=False, session_ids=False, show_sales=None):
        if show_sales is None:
            show_sales = self.env.context.get('show_sales', True)
        
        res = super(ReportSaleDetails, self).get_sale_details(date_start, date_stop, config_ids, session_ids)
        
        res['show_sales'] = show_sales
        
        if not show_sales:
            res['products'] = []
            res['products_info'] = {}
            res['taxes'] = []
            res['refund_products'] = []
            res['refund_info'] = {}
            res['refund_taxes'] = []
        
        return res