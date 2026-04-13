# -*- coding: utf-8 -*-
from odoo import models, fields

class PosDetails(models.TransientModel):
    _inherit = 'pos.details.wizard'

    show_sales = fields.Boolean(string='Show Sales', default=True)

    def generate_report(self):
        data = {
            'date_start': self.start_date, 
            'date_stop': self.end_date, 
            'config_ids': self.pos_config_ids.ids,
            'show_sales': self.show_sales
        }
        return self.env.ref('point_of_sale.sale_details_report').with_context(show_sales=self.show_sales).report_action([], data=data)

    def generate_excel_report(self):
        data = {
            'date_start': self.start_date, 
            'date_stop': self.end_date, 
            'config_ids': self.pos_config_ids.ids,
            'show_sales': self.show_sales
        }
        return self.env.ref('ec_pos.action_report_saledetails_xlsx').report_action([], data=data)
