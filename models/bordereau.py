from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DasriBordereau(models.Model):
    _name = 'dasri.bordereau'
    _description = 'Bordereau DASRI'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _sql_constraints = [
        ('mission_line_unique', 'unique(mission_line_id)', 'Un seul bordereau est autorise par arret de mission.'),
    ]

    name = fields.Char('Numéro', required=True, copy=False, readonly=True, default='Nouveau')
    partner_id = fields.Many2one(
        'res.partner',
        string='Établissement',
        required=True,
        domain=[('is_company', '=', True), ('has_active_dasri_contract', '=', True)],
        tracking=True,
    )
    location_id = fields.Many2one(
        'res.partner',
        string='Site/Adresse',
        domain="[('parent_id', '=', partner_id)]",
    )
    mission_id = fields.Many2one('dasri.mission', string='Mission', required=True)
    mission_line_id = fields.Many2one(
        'dasri.mission.line',
        string='Arrêt de Mission',
        required=True,
        domain="[('mission_id', '=', mission_id)]",
    )
    date = fields.Date('Date', required=True, default=fields.Date.today, tracking=True)
    contract_id = fields.Many2one(
        'dasri.contract',
        string='Contrat',
        domain="[('partner_id', '=', partner_id), ('state', '=', 'active')]",
    )
    waste_type = fields.Selection([
        ('dasri', 'DASRI'),
        ('other', 'Autres Déchets'),
    ], string='Type de Déchets', default='dasri', required=True)
    waste_product_id = fields.Many2one(
        'product.product',
        string='Categorie de dechet',
        domain=[('type', 'in', ['product', 'consu'])],
        tracking=True,
    )
    qty_kg = fields.Float('Quantité (KG)')
    site_address = fields.Char('Adresse')
    note = fields.Text('Observations')
    hospital_signatory_name = fields.Char('Nom du signataire hopital', tracking=True)
    hospital_signatory_role = fields.Char('Fonction du signataire hopital', tracking=True)
    hospital_signature = fields.Binary('Signature hopital', attachment=True, copy=False)
    hospital_signed_on = fields.Datetime('Date signature hopital', readonly=True, copy=False, tracking=True)
    reception_line_ids = fields.One2many(
        'dasri.reception.bordereau.line',
        'bordereau_id',
        string='Receptions',
    )
    reception_count = fields.Integer(string='Receptions', compute='_compute_reception_count')
    contract_count = fields.Integer(string='Contrats', compute='_compute_contract_count')
    invoice_id = fields.Many2one('account.move', string='Facture', readonly=True, copy=False)

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('signed', 'Signé'),
        ('validated', 'Validé'),
        ('archived', 'Archivé'),
    ], string='Statut', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('dasri.bordereau') or '/'
            if vals.get('mission_line_id'):
                line = self.env['dasri.mission.line'].browse(vals['mission_line_id'])
                if line.exists():
                    vals.setdefault('mission_id', line.mission_id.id)
                    vals.setdefault('partner_id', line.partner_id.id)
                    vals.setdefault('location_id', line.location_id.id)
                    vals.setdefault('site_address', line.site_address or '')
            self._set_contract_from_vals(vals)
        return super().create(vals_list)

    def action_sign(self):
        for rec in self:
            rec._check_hospital_signature_data()
            rec.write({
                'state': 'signed',
                'hospital_signed_on': fields.Datetime.now(),
            })

    def action_validate(self):
        self.write({'state': 'validated'})

    def action_archive(self):
        self.write({'state': 'archived'})

    def action_reset_to_draft(self):
        self.with_context(allow_archived_edit=True, allow_signed_bordereau_edit=True).write({
            'state': 'draft',
            'hospital_signed_on': False,
        })

    def write(self, vals):
        if any(b.state == 'archived' for b in self) and not self.env.context.get('allow_archived_edit'):
            raise ValidationError("Impossible de modifier un bordereau archivé.")
        locked_fields = {
            'partner_id', 'location_id', 'mission_id', 'mission_line_id', 'date',
            'contract_id', 'waste_type', 'waste_product_id', 'qty_kg', 'site_address',
            'note', 'hospital_signatory_name', 'hospital_signatory_role', 'hospital_signature',
        }
        if locked_fields.intersection(vals) and any(
            b.hospital_signed_on for b in self
        ) and not self.env.context.get('allow_signed_bordereau_edit'):
            raise ValidationError("Impossible de modifier un bordereau deja signe par l etablissement.")
        if vals.get('mission_line_id'):
            line = self.env['dasri.mission.line'].browse(vals['mission_line_id'])
            if line.exists():
                vals.setdefault('mission_id', line.mission_id.id)
                vals.setdefault('partner_id', line.partner_id.id)
                vals.setdefault('location_id', line.location_id.id)
                vals.setdefault('site_address', line.site_address or '')
        self._set_contract_from_vals(vals)
        return super().write(vals)

    def _check_hospital_signature_data(self):
        self.ensure_one()
        if not self.hospital_signatory_name or not self.hospital_signatory_role or not self.hospital_signature:
            raise ValidationError(
                "Le nom, la fonction et la signature du representant de l etablissement sont obligatoires."
            )

    def _set_contract_from_vals(self, vals):
        if vals.get('contract_id'):
            return
        partner_id = vals.get('partner_id')
        if not partner_id and vals.get('mission_line_id'):
            line = self.env['dasri.mission.line'].browse(vals['mission_line_id'])
            if line.exists():
                partner_id = line.partner_id.id
        if not partner_id:
            return
        partner = self.env['res.partner'].browse(partner_id)
        bill_date = vals.get('date') or fields.Date.context_today(self)
        contract = self.env['dasri.contract']._get_applicable_contract(partner, bill_date)
        if contract:
            vals['contract_id'] = contract.id

    def _compute_reception_count(self):
        for rec in self:
            rec.reception_count = len(rec.reception_line_ids.mapped('reception_id'))

    def _compute_contract_count(self):
        Contract = self.env['dasri.contract']
        for rec in self:
            rec.contract_count = Contract.search_count([('partner_id', '=', rec.partner_id.id)]) if rec.partner_id else 0

    def action_open_reception(self):
        self.ensure_one()
        action = self.env.ref('dasri.action_dasri_reception').read()[0]
        reception_ids = self.reception_line_ids.mapped('reception_id')
        if reception_ids:
            action['domain'] = [('id', 'in', reception_ids.ids)]
            if len(reception_ids) == 1:
                action['views'] = [(self.env.ref('dasri.view_dasri_reception_form').id, 'form')]
                action['res_id'] = reception_ids.id
        else:
            action['context'] = {
                'default_mission_id': self.mission_id.id,
            }
        return action

    def action_open_contracts(self):
        self.ensure_one()
        action = self.env.ref('dasri.action_dasri_contract').read()[0]
        if self.partner_id:
            action['domain'] = [('partner_id', '=', self.partner_id.id)]
            action['context'] = {'default_partner_id': self.partner_id.id}
            count = self.env['dasri.contract'].search_count(action['domain'])
            if count == 1:
                contract = self.env['dasri.contract'].search(action['domain'], limit=1)
                action['views'] = [(self.env.ref('dasri.view_dasri_contract_form').id, 'form')]
                action['res_id'] = contract.id
        return action

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('dasri.action_report_dasri_bordereau').report_action(self)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for rec in self:
            if rec.partner_id:
                locations = rec.partner_id.child_ids.filtered(lambda p: p.type in ('delivery', 'other'))
                if not locations:
                    locations = rec.partner_id.child_ids
                rec.location_id = locations[:1]

    @api.onchange('mission_id')
    def _onchange_mission_id(self):
        for rec in self:
            if rec.mission_id:
                rec.mission_line_id = False
                rec.partner_id = False
                rec.location_id = False
                rec.site_address = ''
                used_line_ids = self.search([
                    ('mission_id', '=', rec.mission_id.id),
                    ('id', '!=', rec.id),
                    ('mission_line_id', '!=', False),
                ]).mapped('mission_line_id').ids
                return {
                    'domain': {
                        'mission_line_id': [
                            ('mission_id', '=', rec.mission_id.id),
                            ('id', 'not in', used_line_ids),
                        ]
                    }
                }

    @api.onchange('mission_line_id')
    def _onchange_mission_line_id(self):
        for rec in self:
            if rec.mission_line_id:
                rec.mission_id = rec.mission_line_id.mission_id
                rec.partner_id = rec.mission_line_id.partner_id
                rec.location_id = rec.mission_line_id.location_id
                rec.site_address = rec.mission_line_id.site_address or ''
                rec.contract_id = self.env['dasri.contract']._get_applicable_contract(rec.partner_id, rec.date)

    @api.onchange('partner_id', 'date')
    def _onchange_partner_or_date(self):
        for rec in self:
            if rec.partner_id:
                rec.contract_id = self.env['dasri.contract']._get_applicable_contract(rec.partner_id, rec.date)

    @api.onchange('waste_product_id')
    def _onchange_waste_product_id(self):
        for rec in self:
            if rec.waste_product_id:
                rec.waste_type = 'dasri'

    @api.constrains('mission_line_id')
    def _check_unique_mission_line(self):
        for rec in self:
            if rec.mission_line_id:
                dup = self.search_count([
                    ('id', '!=', rec.id),
                    ('mission_line_id', '=', rec.mission_line_id.id),
                ])
                if dup:
                    raise ValidationError("Cet arret de mission a deja un bordereau.")

    @api.constrains('contract_id', 'partner_id')
    def _check_contract_partner(self):
        for rec in self:
            if rec.contract_id and rec.partner_id and rec.contract_id.partner_id != rec.partner_id:
                raise ValidationError("Le contrat doit appartenir au meme etablissement que le bordereau.")
