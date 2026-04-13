# -*- encoding: utf-8 -*-
from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    pos_reference = fields.Char(string="Ref. TPV")

    @api.model
    def _create_picking_from_pos_order_lines(self, location_dest_id, lines, picking_type, partner=False):
        pickings = super(StockPicking, self)._create_picking_from_pos_order_lines(location_dest_id, lines, picking_type, partner)
        if pickings and lines:
            order = lines[0].order_id
            pickings.write({'pos_reference': order.pos_reference})
        return pickings

    @api.model
    def _create_move_from_pos_order_lines(self, lines):
        res = super(StockPicking, self)._create_move_from_pos_order_lines(lines)
        if lines and res:
            _logger.info("DEBUG EC_POS: Transferring notes for %s lines to %s moves", len(lines), len(res))
            
            product_notes = {}
            for line in lines:
                # Use getattr to avoid issues if field is not in specific model registry of the context
                # though it should be.
                note = getattr(line, 'customer_note', False)
                if not note:
                    note = getattr(line, 'note', False)
                
                if note:
                    product_notes[line.product_id.id] = note
                    _logger.info("DEBUG EC_POS: Found note for product %s: %s", line.product_id.name, note)

            for move in res:
                if move.product_id.id in product_notes:
                    move.write({'customer_note': product_notes[move.product_id.id]})
                    _logger.info("DEBUG EC_POS: Updated move %s with note", move.id)

        return res

class StockMove(models.Model):
    _inherit = 'stock.move'

    customer_note = fields.Char(string="Nota Cliente")
