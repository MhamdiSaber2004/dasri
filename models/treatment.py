from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DasriTreatment(models.Model):
    _name = 'dasri.treatment'
    _description = 'Traitement DASRI'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char('Reference', required=True, copy=False, readonly=True, default='Nouveau')
    date = fields.Datetime('Date', required=True, default=fields.Datetime.now, tracking=True)
    operation_type = fields.Selection([
        ('sorting', 'Tri'),
        ('treatment', 'Traitement'),
        ('destruction', 'Destruction'),
    ], string='Operation', required=True, default='sorting', tracking=True)
    reception_id = fields.Many2one('dasri.reception', string='Reception', required=True, tracking=True)
    incinerator_id = fields.Many2one('dasri.incinerator', string='Incinerateur', tracking=True)
    mission_id = fields.Many2one('dasri.mission', string='Mission', related='reception_id.mission_id', store=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Etablissement', related='reception_id.partner_id', store=True, readonly=True)
    qty_received_kg = fields.Float('Quantite recue (KG)', related='reception_id.weight_net', store=True, readonly=True)
    qty_treated_kg = fields.Float('Quantite traitee (KG)', tracking=True)
    gap_kg = fields.Float('Ecart (KG)', compute='_compute_gap_kg', store=True)
    certificate_ref = fields.Char('Reference certificat', tracking=True)
    certificate_attachment_id = fields.Many2one('ir.attachment', string='Certificat')
    note = fields.Text('Observations')
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('done', 'Termine'),
    ], string='Statut', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('dasri.treatment') or '/'
        return super().create(vals_list)

    @api.depends('qty_received_kg', 'qty_treated_kg')
    def _compute_gap_kg(self):
        for rec in self:
            rec.gap_kg = (rec.qty_received_kg or 0.0) - (rec.qty_treated_kg or 0.0)

    @api.constrains('qty_treated_kg')
    def _check_qty_treated(self):
        for rec in self:
            if rec.qty_treated_kg < 0:
                raise ValidationError("La quantite traitee doit etre positive.")

    @api.constrains('operation_type', 'incinerator_id')
    def _check_incinerator(self):
        for rec in self:
            if rec.operation_type in ('treatment', 'destruction') and not rec.incinerator_id:
                raise ValidationError("Un incinerateur est requis pour le traitement ou la destruction.")

    def action_done(self):
        for rec in self:
            if rec.qty_treated_kg <= 0:
                raise ValidationError("La quantite traitee doit etre superieure a 0.")
            rec.state = 'done'

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('dasri.action_report_dasri_treatment').report_action(self)
