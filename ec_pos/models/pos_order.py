# -*- encoding: utf-8 -*-
from odoo import models, api, fields
from bs4 import BeautifulSoup
import requests
from odoo.tools.translate import _
from odoo.exceptions import Warning, ValidationError, UserError, AccessError

class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model_create_multi
    def create(self, vals_list):
        res =  super().create(vals_list)
        for order in res:
            order.date_pos = self.env['ec.tools'].get_date_now()
        return res

    def _payment_fields(self, order, ui_paymentline):
        res = super()._payment_fields(order, ui_paymentline)
        res.update({
            'x_payment_reference': ui_paymentline.get('x_payment_reference'),
        })
        return res

    def _compute_is_refund(self):
        for order in self:
            if len(self.mapped('lines.refunded_orderline_id').ids) != 0:
                order.is_refund = True
            else:
                order.is_refund = False

    is_refund = fields.Boolean(string="Es Devolucion", compute='_compute_is_refund')
    date_pos = fields.Date(u'Fecha de pedido')

    def _create_invoice(self, move_vals):
        self.ensure_one()
        if self.config_id.sri_printer_point_id:
            move_vals.update({'printer_id': self.config_id.sri_printer_point_id.id,
                              'document_type': 'electronic',
                              'fiscal_type': 'factura_cliente',
                              })
        if 'move_type' in move_vals:
            if move_vals['move_type'] == 'out_refund':
                journal_id = self.env['account.journal'].search([('credit_note', '=', True),('type','=','sale')], limit=1)
                if not journal_id:
                    raise UserError(_("Debe configurar un diario de Notas de Crédito para Ventas."))
                move_vals.update({'journal_id': journal_id.id})
        res = super(PosOrder, self.with_context(from_pos=True))._create_invoice(move_vals)
        return res

    @api.model
    def get_info_invoice(self, orders):
        invoice_number = False
        invoice_xml_key = False
        sale_shop_street = ""
        sale_shop_detail = ""
        sale_shop_phone = ""
        if len(orders)!=0:
            order = orders[0]
            pos_order = self.env['pos.order'].search([('id', '=', order['id'])])
            if len(pos_order)!= 0:
                pos_order = pos_order[0]
                invoice = self.env['account.move'].search([('ref', '=', pos_order.name)])
                city = invoice.printer_id.shop_id.address_id.city if invoice.printer_id.shop_id.address_id.city else ""
                country = invoice.printer_id.shop_id.address_id.country_id.name if invoice.printer_id.shop_id.address_id.country_id else ""
                if len(invoice) != 0:
                    invoice = invoice[0]
                    invoice_number = invoice.l10n_latam_document_number,
                    invoice_xml_key =  invoice.xml_key
                    sale_shop_street =  invoice.printer_id.shop_id.address_id.street
                    sale_shop_detail = city.upper() + " - " + country.upper()
                    sale_shop_phone =  invoice.shop_id.address_id.phone
        # Fetching Backend Order Name and Picking Name
        backend_name = False
        picking_name = False
        if len(orders) != 0:
            order_id = orders[0]['id']
            pos_order = self.env['pos.order'].browse(order_id)
            if pos_order:
                 backend_name = pos_order.name
                 if pos_order.picking_ids:
                     picking_name = pos_order.picking_ids[0].name
        
        return {'invoice_number': invoice_number,
                'invoice_xml_key': invoice_xml_key,
                'sale_shop_street':sale_shop_street,
                'sale_shop_detail':sale_shop_detail,
                'sale_shop_phone': sale_shop_phone,
                'backend_name': backend_name,
                'picking_name': picking_name,
                }

    @api.model
    def get_ruc_client(self, ref):
        if len(ref) == 13:
            url = 'https://srienlinea.sri.gob.ec/facturacion-internet/consultas/publico/ruc-datos2.jspa?ruc='
            print(url + ref)
            data = requests.get(url + ref)
            if data.status_code != 200:
                return {'ok': False}
            bs = BeautifulSoup(data.text, 'html.parser')
            table = bs.html.body.find('table', {'class', 'formulario'})
            name_data = table.text.split(":\n")[1][:table.text.split(":\n")[1].index("\n")]
            return {'ok':True,'ruc_name':name_data}

    @api.model
    def create_sale_order_from_pos_ui(self, order_data):
        """
        Creates a draft Sale Order from POS UI data for Proforma purposes.
        """
        if not order_data:
            return {'ok': False, 'error': 'No data'}
        
        SaleOrder = self.env['sale.order']
        SaleOrderLine = self.env['sale.order.line']
        Product = self.env['product.product']
        Partner = self.env['res.partner']
        
        # 1. Partner
        partner_id = order_data.get('partner_id')
        if not partner_id:
            # Fallback to a default customer or error? POS usually has a set client or dummy
             # If no client set in POS, check config or use public user
             return {'ok': False, 'error': 'Cliente no establecido en el pedido'}
        
        # 2. Prepare Order Vals
        order_vals = {
            'partner_id': partner_id,
            'state': 'draft',
            'date_order': fields.Datetime.now(),
            'note': 'PROFORMA DESDE PUNTO DE VENTA',
        }
        
        # 3. Create Order
        sale_order = SaleOrder.create(order_vals)
        
        # 4. Create Lines
        lines_data = order_data.get('lines', [])
        for line in lines_data:
            product_id = line.get('product_id')
            qty = line.get('qty', 0.0)
            price_unit = line.get('price_unit', 0.0)
            discount = line.get('discount', 0.0)
            
            product = Product.browse(product_id)
            
            line_vals = {
                'order_id': sale_order.id,
                'product_id': product_id,
                'product_uom_qty': qty,
                'price_unit': price_unit,
                'discount': discount,
                'name': product.name, # Simplified
                'product_uom': product.uom_id.id,
            }
            
            # Taxes (Passed from POS or recalculated?)
            # Easier to let Odoo recalculate based on product/fiscal position
            # If specific taxes are needed, we might need to look them up.
            # Standard logic:
            if product.taxes_id:
                 line_vals['tax_id'] = [(6, 0, product.taxes_id.ids)]
                 
            SaleOrderLine.create(line_vals)
            
        return {
            'ok': True,
            'name': sale_order.name,
            'id': sale_order.id
        }

    number_invoice = fields.Char(related='account_move.l10n_latam_document_number', string="Numero de Factura")
    medianet_ref = fields.Char(string="Referencia Medianet")
    medianet_code = fields.Char(string="Codigo Medianet")
    medianet_date = fields.Date(string="Fecha de Referencia Medianet")
    medianet_hour = fields.Char(string="Hora Medianet")
    medianet_lote = fields.Char(string="Lote de Referencia Medianet")
    medianet_auth = fields.Char(string="Autorizacion de Referencia Medianet")
    medianet_amount = fields.Char(string="Monto de Referencia Medianet")
    medianet_amount_tax = fields.Char(string="Monto de Impuestos de Referencia Medianet")
    medianet_amount_total = fields.Char(string="Monto Total de Referencia Medianet")
