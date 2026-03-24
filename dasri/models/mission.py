from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DasriMission(models.Model):
    _name = 'dasri.mission'
    _description = 'Mission de Collecte DASRI'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_planned, id'

    name = fields.Char('Référence', required=True, copy=False, readonly=True, default='Nouveau')
    date_planned = fields.Date('Date Planifiée', required=True, default=fields.Date.today, tracking=True)
    planned_start = fields.Datetime('Début Planifié')
    planned_end = fields.Datetime('Fin Planifiée')
    vehicle_id = fields.Many2one('fleet.vehicle', string='Véhicule', tracking=True)
    driver_id = fields.Many2one('hr.employee', string='Chauffeur', tracking=True)
    team_id = fields.Many2one('res.users', string='Équipe/Responsable')
    zone_id = fields.Many2one('dasri.zone', string='Zone', tracking=True)
    zone = fields.Char('Zone/Gouvernorat')
    note = fields.Text('Notes')

    line_ids = fields.One2many('dasri.mission.line', 'mission_id', string='Destinations')
    bordereau_count = fields.Integer(string='Bordereaux', compute='_compute_bordereau_count')

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('planned', 'Planifiée'),
        ('in_progress', 'En Cours'),
        ('done', 'Clôturée'),
        ('cancelled', 'Annulée'),
    ], string='Statut', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('dasri.mission') or '/'
        return super().create(vals_list)

    def action_plan(self):
        for mission in self:
            if not mission.vehicle_id or not mission.driver_id:
                raise ValidationError("Véhicule et chauffeur sont requis pour planifier la mission.")
            mission.state = 'planned'

    def action_start(self):
        for mission in self:
            if mission.state != 'planned':
                raise ValidationError("La mission doit être planifiée avant de démarrer.")
            mission.state = 'in_progress'

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def write(self, vals):
        if any(m.state == 'done' for m in self) and not self.env.context.get('allow_done_edit'):
            raise ValidationError("Impossible de modifier une mission clôturée.")
        return super().write(vals)

    def _compute_bordereau_count(self):
        Bordereau = self.env['dasri.bordereau']
        for mission in self:
            mission.bordereau_count = Bordereau.search_count([('mission_id', '=', mission.id)])

    def action_open_bordereaux(self):
        self.ensure_one()
        action = self.env.ref('dasri.action_dasri_bordereau').read()[0]
        action['domain'] = [('mission_id', '=', self.id)]
        action['context'] = {'default_mission_id': self.id}
        if self.bordereau_count == 1:
            bordereau = self.env['dasri.bordereau'].search(action['domain'], limit=1)
            action['views'] = [(self.env.ref('dasri.view_dasri_bordereau_form').id, 'form')]
            action['res_id'] = bordereau.id
        return action

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('dasri.action_report_dasri_mission').report_action(self)


class DasriMissionLine(models.Model):
    _name = 'dasri.mission.line'
    _description = 'Ligne de Mission DASRI'
    _order = 'sequence, id'

    mission_id = fields.Many2one('dasri.mission', string='Mission', required=True, ondelete='cascade')
    sequence = fields.Integer('Séquence', default=10)
    partner_id = fields.Many2one(
        'res.partner',
        string='Établissement',
        required=True,
        domain=[('is_company', '=', True), ('has_active_dasri_contract', '=', True)],
    )
    location_id = fields.Many2one(
        'res.partner',
        string='Site/Adresse',
        domain="[('parent_id', '=', partner_id)]",
    )
    site_address = fields.Char('Adresse')
    planned_time = fields.Datetime('Horaire Planifié')
    constraint_note = fields.Char('Contraintes')
    state = fields.Selection(related='mission_id.state', string='Statut', store=True, readonly=True)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for line in self:
            if line.partner_id:
                locations = line.partner_id.child_ids.filtered(lambda p: p.type in ('delivery', 'other'))
                if not locations:
                    locations = line.partner_id.child_ids
                line.location_id = locations[:1]
                line.site_address = line.location_id.contact_address if line.location_id else ''

    @api.onchange('location_id')
    def _onchange_location_id(self):
        for line in self:
            if line.location_id:
                line.site_address = line.location_id.contact_address
