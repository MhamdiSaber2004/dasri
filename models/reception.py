from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DasriReception(models.Model):
    _name = 'dasri.reception'
    _description = 'Reception DASRI'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _sql_constraints = [
        ('mission_unique', 'unique(mission_id)', 'Une seule reception est autorisee par mission.'),
    ]

    name = fields.Char('Reference', required=True, copy=False, readonly=True, default='Nouveau')
    date = fields.Datetime('Date de reception', required=True, default=fields.Datetime.now, tracking=True)
    mission_id = fields.Many2one('dasri.mission', string='Mission', tracking=True, required=True)
    mission_line_id = fields.Many2one('dasri.mission.line', string='Arret de mission', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Etablissement', readonly=True)
    location_id = fields.Many2one('res.partner', string='Site/Adresse', readonly=True)

    bordereau_line_ids = fields.One2many(
        'dasri.reception.bordereau.line',
        'reception_id',
        string='Bordereaux',
    )
    bordereau_count = fields.Integer(string='Bordereau', compute='_compute_bordereau_count', store=True)
    bordereau_weight_total = fields.Float(
        'Poids total bordereaux (KG)',
        compute='_compute_bordereau_weight_total',
        store=True,
    )

    weight_gross = fields.Float('Poids brut (KG)')
    weight_tare = fields.Float('Tare (KG)')
    weight_net = fields.Float('Poids net (KG)', compute='_compute_weight_net', store=True)
    weight_gap = fields.Float('Ecart poids (KG)', compute='_compute_weight_gap', store=True)
    weight_gap_abs = fields.Float('Ecart absolu (KG)', compute='_compute_weight_gap', store=True)
    scale_ref = fields.Char('Reference balance')

    picking_id = fields.Many2one('stock.picking', string='Transfert', readonly=True, copy=False)
    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Type de transfert',
        default=lambda self: self._default_picking_type(),
    )
    stock_location_src_id = fields.Many2one(
        'stock.location',
        string='Emplacement source',
        default=lambda self: self._default_stock_location_src(),
        required=True,
    )
    stock_location_dest_id = fields.Many2one(
        'stock.location',
        string='Emplacement destination',
        default=lambda self: self._default_stock_location_dest(),
        required=True,
    )

    note = fields.Text('Observations')
    line_ids = fields.One2many('dasri.reception.line', 'reception_id', string='Lignes')

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('weighed', 'Pese'),
        ('validated', 'Valide'),
        ('done', 'Termine'),
    ], string='Statut', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('dasri.reception') or '/'
            if vals.get('mission_id'):
                mission = self.env['dasri.mission'].browse(vals['mission_id'])
                if mission.exists():
                    vals['bordereau_line_ids'] = self._prepare_bordereau_lines(mission)
                    self._set_related_fields_from_mission(vals, mission)
        return super().create(vals_list)

    def write(self, vals):
        if any(rec.state == 'done' for rec in self) and not self.env.context.get('allow_done_edit'):
            raise ValidationError("Impossible de modifier une reception terminee.")
        if vals.get('mission_id'):
            mission = self.env['dasri.mission'].browse(vals['mission_id'])
            if mission.exists():
                vals['bordereau_line_ids'] = [(5, 0, 0)] + self._prepare_bordereau_lines(mission)
                self._set_related_fields_from_mission(vals, mission)
        return super().write(vals)

    def action_weighed(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError("La reception doit etre en brouillon pour la pesee.")
            if not rec.weight_gross:
                raise ValidationError("Le poids brut est requis pour la pesee.")
        self.write({'state': 'weighed'})

    def action_validate(self):
        for rec in self:
            if rec.state != 'weighed':
                raise ValidationError("La reception doit etre pesee avant validation.")
            if not rec.line_ids:
                raise ValidationError("Ajoutez au moins une ligne de reception avant validation.")
            if rec.weight_net <= 0:
                raise ValidationError("Le poids net doit etre superieur a 0.")
            if not rec.picking_id:
                rec._create_stock_picking()
        self.write({'state': 'validated'})

    def action_done(self):
        for rec in self:
            if rec.state != 'validated':
                raise ValidationError("La reception doit etre validee avant cloture.")
            rec._validate_stock_picking()
        self.write({'state': 'done'})

    def action_reset_to_draft(self):
        self.with_context(allow_done_edit=True).write({'state': 'draft'})

    @api.depends('weight_gross', 'weight_tare')
    def _compute_weight_net(self):
        for rec in self:
            rec.weight_net = (rec.weight_gross or 0.0) - (rec.weight_tare or 0.0)

    @api.depends('weight_net', 'bordereau_weight_total')
    def _compute_weight_gap(self):
        for rec in self:
            rec.weight_gap = (rec.weight_net or 0.0) - (rec.bordereau_weight_total or 0.0)
            rec.weight_gap_abs = abs(rec.weight_gap)

    @api.depends('bordereau_line_ids')
    def _compute_bordereau_count(self):
        for rec in self:
            rec.bordereau_count = len(rec.bordereau_line_ids)

    @api.depends('bordereau_line_ids.qty_kg')
    def _compute_bordereau_weight_total(self):
        for rec in self:
            rec.bordereau_weight_total = sum(rec.bordereau_line_ids.mapped('qty_kg'))

    @api.constrains('weight_gross', 'weight_tare')
    def _check_weight(self):
        for rec in self:
            if rec.weight_gross and rec.weight_tare and rec.weight_tare > rec.weight_gross:
                raise ValidationError("La tare ne peut pas etre superieure au poids brut.")

    @api.onchange('mission_id')
    def _onchange_mission_id(self):
        for rec in self:
            if rec.mission_id:
                rec.bordereau_line_ids = rec._prepare_bordereau_lines(rec.mission_id)
                partner_ids = rec.bordereau_line_ids.mapped('partner_id')
                location_ids = rec.bordereau_line_ids.mapped('location_id')
                rec.partner_id = partner_ids[0] if len(partner_ids) == 1 else False
                rec.location_id = location_ids[0] if len(location_ids) == 1 else False
            else:
                rec.bordereau_line_ids = [(5, 0, 0)]
                rec.partner_id = False
                rec.location_id = False

    @api.onchange('picking_type_id')
    def _onchange_picking_type_id(self):
        for rec in self:
            if rec.picking_type_id:
                rec.stock_location_src_id = rec.picking_type_id.default_location_src_id
                rec.stock_location_dest_id = rec.picking_type_id.default_location_dest_id

    def _default_picking_type(self):
        return self.env['stock.picking.type'].search([('code', '=', 'incoming')], limit=1)

    def _default_stock_location_src(self):
        picking_type = self._default_picking_type()
        if picking_type and picking_type.default_location_src_id:
            return picking_type.default_location_src_id
        return self.env.ref('stock.stock_location_suppliers', raise_if_not_found=False)

    def _default_stock_location_dest(self):
        picking_type = self._default_picking_type()
        if picking_type and picking_type.default_location_dest_id:
            return picking_type.default_location_dest_id
        return self.env.ref('stock.stock_location_stock', raise_if_not_found=False)

    def _prepare_picking_vals(self):
        self.ensure_one()
        if not self.picking_type_id:
            raise ValidationError("Veuillez choisir un type de transfert.")
        if not self.stock_location_src_id or not self.stock_location_dest_id:
            raise ValidationError("Veuillez definir les emplacements source et destination.")
        partner = self.partner_id
        if not partner and self.bordereau_line_ids:
            partner = self.bordereau_line_ids[0].bordereau_id.partner_id
        return {
            'picking_type_id': self.picking_type_id.id,
            'location_id': self.stock_location_src_id.id,
            'location_dest_id': self.stock_location_dest_id.id,
            'partner_id': partner.id if partner else False,
            'origin': self.name,
        }

    def _prepare_move_vals(self, line):
        if line.qty <= 0:
            raise ValidationError("La quantite doit etre superieure a 0.")
        if line.product_id.type not in ('product', 'consu'):
            raise ValidationError("Le produit doit etre stockable ou consommable.")
        return {
            'name': line.product_id.display_name,
            'product_id': line.product_id.id,
            'product_uom_qty': line.qty,
            'product_uom': line.uom_id.id,
            'location_id': self.stock_location_src_id.id,
            'location_dest_id': self.stock_location_dest_id.id,
        }

    def _create_stock_picking(self):
        self.ensure_one()
        move_lines = [(0, 0, self._prepare_move_vals(line)) for line in self.line_ids]
        if not move_lines:
            raise ValidationError("Ajoutez au moins une ligne de reception.")
        vals = self._prepare_picking_vals()
        vals['move_ids_without_package'] = move_lines
        picking = self.env['stock.picking'].create(vals)
        picking.action_confirm()
        self.picking_id = picking.id
        return picking

    def _validate_stock_picking(self):
        self.ensure_one()
        if not self.picking_id:
            return
        for move in self.picking_id.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
            # Odoo 18 manages done qty through move lines via _set_quantity_done.
            if hasattr(move, 'quantity_done'):
                if move.quantity_done == 0:
                    move.quantity_done = move.product_uom_qty
            elif move.quantity == 0:
                move._set_quantity_done(move.product_uom_qty)
        if self.picking_id.state not in ('done', 'cancel'):
            self.picking_id.button_validate()

    def action_open_bordereaux(self):
        self.ensure_one()
        action = self.env.ref('dasri.action_dasri_bordereau').read()[0]
        if self.mission_id:
            action['domain'] = [('mission_id', '=', self.mission_id.id)]
            action['context'] = {'default_mission_id': self.mission_id.id}
            if self.bordereau_count == 1:
                bordereau = self.env['dasri.bordereau'].search(action['domain'], limit=1)
                action['views'] = [(self.env.ref('dasri.view_dasri_bordereau_form').id, 'form')]
                action['res_id'] = bordereau.id
        return action

    def action_open_mission(self):
        self.ensure_one()
        if not self.mission_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Mission',
            'res_model': 'dasri.mission',
            'view_mode': 'form',
            'res_id': self.mission_id.id,
        }

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('dasri.action_report_dasri_reception').report_action(self)

    def _prepare_bordereau_lines(self, mission):
        bordereaux = self.env['dasri.bordereau'].search([
            ('mission_id', '=', mission.id),
            ('state', '=', 'validated'),
        ])
        return [
            (0, 0, {
                'bordereau_id': b.id,
                'qty_kg': b.qty_kg,
            })
            for b in bordereaux
        ]

    def _set_related_fields_from_mission(self, vals, mission):
        bordereaux = self.env['dasri.bordereau'].search([
            ('mission_id', '=', mission.id),
            ('state', '=', 'validated'),
        ])
        partner_ids = bordereaux.mapped('partner_id').ids
        location_ids = bordereaux.mapped('location_id').ids
        if len(partner_ids) == 1:
            vals['partner_id'] = partner_ids[0]
        if len(location_ids) == 1:
            vals['location_id'] = location_ids[0]


class DasriReceptionBordereauLine(models.Model):
    _name = 'dasri.reception.bordereau.line'
    _description = 'Ligne Reception Bordereau'
    _order = 'id'

    reception_id = fields.Many2one('dasri.reception', string='Reception', required=True, ondelete='cascade')
    bordereau_id = fields.Many2one('dasri.bordereau', string='Bordereau', required=True)
    partner_id = fields.Many2one('res.partner', related='bordereau_id.partner_id', store=True, readonly=True)
    location_id = fields.Many2one('res.partner', related='bordereau_id.location_id', store=True, readonly=True)
    qty_kg = fields.Float('Quantite (KG)')

    @api.constrains('bordereau_id', 'reception_id')
    def _check_bordereau_mission(self):
        for line in self:
            if line.bordereau_id and line.reception_id and line.reception_id.mission_id:
                if line.bordereau_id.mission_id != line.reception_id.mission_id:
                    raise ValidationError("Le bordereau doit appartenir a la meme mission que la reception.")


class DasriReceptionLine(models.Model):
    _name = 'dasri.reception.line'
    _description = 'Ligne Reception DASRI'
    _order = 'id'

    reception_id = fields.Many2one('dasri.reception', string='Reception', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Produit Dechet', required=True)
    uom_id = fields.Many2one('uom.uom', string='Unite', related='product_id.uom_id', store=True, readonly=True)
    qty = fields.Float('Quantite')
    lot_id = fields.Many2one('stock.lot', string='Lot')
