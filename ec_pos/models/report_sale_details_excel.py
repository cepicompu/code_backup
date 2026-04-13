# -*- coding: utf-8 -*-
from odoo import models

class PosSaleDetailsExcelReport(models.AbstractModel):
    _name = 'report.ec_pos.report_saledetails_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, wizards):
        show_sales = data.get('show_sales', True)
        # We fetch the exact same dictionary used by the PDF report
        report_data = self.env['report.point_of_sale.report_saledetails'].get_sale_details(
            date_start=data.get('date_start'),
            date_stop=data.get('date_stop'),
            config_ids=data.get('config_ids'),
            session_ids=data.get('session_ids'),
            show_sales=show_sales
        )

        sheet = workbook.add_worksheet('Sales Details')
        
        # Formats
        bold = workbook.add_format({'bold': True})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3'})
        money_format = workbook.add_format({'num_format': '#,##0.00'})
        title_format = workbook.add_format({'bold': True, 'font_size': 14})

        # Top section
        row = 0
        sheet.write(row, 0, 'Sales Details', title_format)
        row += 2

        if report_data.get('date_start') and report_data.get('date_stop'):
            sheet.write(row, 0, 'From:')
            sheet.write(row, 1, str(report_data['date_start']))
            sheet.write(row, 2, 'To:')
            sheet.write(row, 3, str(report_data['date_stop']))
            row += 2

        # Products Sub-section
        if report_data.get('products'):
            sheet.write(row, 0, 'Sales', title_format)
            row += 1
            sheet.write_row(row, 0, ['Product Category', 'Product', 'Quantity', 'Total'], header_format)
            row += 1
            
            for category in report_data.get('products', []):
                sheet.write(row, 0, category.get('name', ''), bold)
                sheet.write(row, 2, category.get('qty', 0), bold)
                sheet.write(row, 3, category.get('total', 0.0), money_format)
                row += 1
                for line in category.get('products', []):
                    internal_reference = f"[{line['code']}] " if line.get('code') else ''
                    sheet.write(row, 1, f"{internal_reference}{line.get('product_name', '')}")
                    sheet.write(row, 2, line.get('quantity', 0))
                    sheet.write(row, 3, line.get('total_paid', 0.0), money_format)
                    row += 1
            
            # Products Total
            sheet.write(row, 0, 'Total', bold)
            products_info = report_data.get('products_info', {})
            sheet.write(row, 2, products_info.get('qty', 0), bold)
            sheet.write(row, 3, products_info.get('total', 0.0), money_format)
            row += 2

        # Taxes Sub-section
        if report_data.get('taxes'):
            sheet.write(row, 0, 'Taxes on sales', title_format)
            row += 1
            sheet.write_row(row, 0, ['Name', 'Tax Amount', 'Base Amount'], header_format)
            row += 1
            for tax in report_data.get('taxes', []):
                sheet.write(row, 0, tax.get('name', ''))
                sheet.write(row, 1, tax.get('tax_amount', 0.0), money_format)
                sheet.write(row, 2, tax.get('base_amount', 0.0), money_format)
                row += 1
            row += 1

        # Refunds Sub-section
        if report_data.get('refund_products'):
            sheet.write(row, 0, 'Refunds', title_format)
            row += 1
            sheet.write_row(row, 0, ['Product Category', 'Product', 'Quantity', 'Total'], header_format)
            row += 1
            for category in report_data.get('refund_products', []):
                sheet.write(row, 0, category.get('name', ''), bold)
                sheet.write(row, 2, category.get('qty', 0), bold)
                sheet.write(row, 3, category.get('total', 0.0), money_format)
                row += 1
                for line in category.get('products', []):
                    internal_reference = f"[{line['code']}] " if line.get('code') else ''
                    sheet.write(row, 1, f"{internal_reference}{line.get('product_name', '')}")
                    sheet.write(row, 2, line.get('quantity', 0))
                    sheet.write(row, 3, line.get('total_paid', 0.0), money_format)
                    row += 1
            
            # Refunds Total
            sheet.write(row, 0, 'Total', bold)
            refund_info = report_data.get('refund_info', {})
            sheet.write(row, 2, refund_info.get('qty', 0), bold)
            sheet.write(row, 3, refund_info.get('total', 0.0), money_format)
            row += 2
            
        # Taxes Refunds Sub-section
        if report_data.get('refund_taxes'):
            sheet.write(row, 0, 'Taxes on refunds', title_format)
            row += 1
            sheet.write_row(row, 0, ['Name', 'Tax Amount', 'Base Amount'], header_format)
            row += 1
            for tax in report_data.get('refund_taxes', []):
                sheet.write(row, 0, tax.get('name', ''))
                sheet.write(row, 1, tax.get('tax_amount', 0.0), money_format)
                sheet.write(row, 2, tax.get('base_amount', 0.0), money_format)
                row += 1
            row += 1

        # Payments Sub-section
        grouped_payments = report_data.get('grouped_payments') or report_data.get('payments', [])
        if grouped_payments:
            sheet.write(row, 0, 'Payments', title_format)
            row += 1
            sheet.write_row(row, 0, ['Name', 'Total'], header_format)
            row += 1
            for payment in grouped_payments:
                sheet.write(row, 0, payment.get('name', ''))
                sheet.write(row, 1, payment.get('total', 0.0), money_format)
                row += 1
            row += 1
            
        # Invoices Sub-section
        if report_data.get('invoiceList'):
            sheet.write(row, 0, 'Invoices', title_format)
            row += 1
            sheet.write_row(row, 0, ['Name', 'Date', 'Order reference', 'Total'], header_format)
            row += 1
            for invoiceSession in report_data.get('invoiceList', []):
                if invoiceSession.get('invoices'):
                    for invoice in invoiceSession['invoices']:
                        sheet.write(row, 0, invoice.get('name', ''))
                        sheet.write(row, 1, invoice.get('date', ''))
                        sheet.write(row, 2, invoice.get('order_ref', ''))
                        sheet.write(row, 3, invoice.get('total', 0.0), money_format)
                        row += 1
            sheet.write(row, 0, 'Total', bold)
            sheet.write(row, 3, report_data.get('invoiceTotal', 0.0), money_format)
            row += 2
            
        # Session Control
        sheet.write(row, 0, 'Session Control', title_format)
        row += 1
        
        total_paid = report_data.get('currency', {}).get('total_paid', 0.0)
        sheet.write(row, 0, 'Total:', bold)
        sheet.write(row, 1, total_paid, money_format)
        row += 1
        
        sheet.write(row, 0, 'Number of transactions:', bold)
        sheet.write(row, 1, report_data.get('nbr_orders', 0))
        row += 2
        
        payments_original = report_data.get('payments', [])
        if payments_original and report_data.get('state') in ('closed', 'multiple'):
            sheet.write_row(row, 0, ['Name', '', 'Expected', 'Counted', 'Difference'], header_format)
            row += 1
            for method in payments_original:
                if method.get('count'):
                    sheet.write(row, 0, method.get('name', ''), bold)
                    sheet.write(row, 2, method.get('final_count', 0.0), money_format)
                    sheet.write(row, 3, method.get('money_counted', 0.0), money_format)
                    sheet.write(row, 4, method.get('money_difference', 0.0), money_format)
                    row += 1
                    for move in method.get('cash_moves', []):
                        sheet.write(row, 1, move.get('name', ''))
                        sheet.write(row, 2, move.get('amount', 0.0), money_format)
                        row += 1
            row += 1

        # Resize columns for better readability
        sheet.set_column(0, 0, 25)
        sheet.set_column(1, 1, 35)
        sheet.set_column(2, 2, 15)
        sheet.set_column(3, 4, 15)
