# -*- coding: utf-8 -*-
from odoo import models, api

class ReportSaleDetails(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'

    @api.model
    def get_sale_details(self, date_start=False, date_stop=False, config_ids=False, session_ids=False, show_sales=True):
        res = super(ReportSaleDetails, self).get_sale_details(date_start, date_stop, config_ids, session_ids)
        
        res['show_sales'] = show_sales
        
        if not show_sales:
            res['products'] = []
            res['products_info'] = {}
            res['taxes'] = []
            res['refund_products'] = []
            res['refund_info'] = {}
            res['refund_taxes'] = []
        
        # Group payments by name without considering the session
        grouped_payments = {}
        for payment in res.get('payments', []):
            name = payment.get('name')
            if name not in grouped_payments:
                grouped_payments[name] = {
                    'name': name,
                    'total': 0.0,
                }
            grouped_payments[name]['total'] += payment.get('total', 0.0)
            
        # Convert dictionary back to list
        res['grouped_payments'] = list(grouped_payments.values())
        
        # Add fallback for empty category names
        for category in res.get('products', []):
            if not category.get('name') or category.get('name') == 'False':
                category['name'] = 'Sin Categoría'

        for category in res.get('refund_products', []):
            if not category.get('name') or category.get('name') == 'False':
                category['name'] = 'Sin Categoría'
        
        return res
