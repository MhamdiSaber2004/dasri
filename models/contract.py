from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DasriContract(models.Model):
    _name = 'dasri.contract'
    _description = 'Contrat de Collecte DASRI'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Référence', required=True, copy=False, readonly=True, default='Nouveau')
    partner_id = fields.Many2one('res.partner', string='Établissement' , domain=[('is_company', '=', True)], required=True, tracking=True)
    partner_count = fields.Integer(string='Établissement', compute='_compute_partner_count')

    date_start = fields.Date('Date Début', required=True, default=fields.Date.today)
    date_end = fields.Date('Date Fin')
    periodicity = fields.Selection([
        ('monthly', 'Mensuel'),
        ('weekly', 'Hebdomadaire'),
        ('daily', 'Quotidien'),
        ('on_demand', 'Sur Demande'),
    ], string='Périodicité', default='monthly', required=True)

    pricing_type = fields.Selection([
        ('weight', 'Au Poids (KG)'),
        ('trip', 'Au Passage'),
        ('mixed', 'Mixte')
    ], string='Mode de Facturation', default='weight', required=True)

    price_kg = fields.Float('Prix par KG')
    price_trip = fields.Float('Prix par Passage')
    monthly_min = fields.Float('Minimum Mensuel')
    terms = fields.Text('Conditions')
    hospital_signatory_name = fields.Char('Nom du signataire hopital', tracking=True)
    hospital_signatory_role = fields.Char('Fonction du signataire hopital', tracking=True)
    hospital_signature = fields.Binary('Signature hopital', attachment=True, copy=False)
    hospital_signed_on = fields.Datetime('Date signature hopital', readonly=True, copy=False, tracking=True)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'dasri_contract_attachment_rel',
        'contract_id',
        'attachment_id',
        string='Annexes',
        help='Pièces jointes liées au contrat.',
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('suspended', 'Suspendu'),
        ('closed', 'Clôturé')
    ], string='Statut', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('dasri.contract') or '/'
        return super().create(vals_list)

    def action_sign(self):
        for rec in self:
            rec._check_hospital_signature_data()
            rec.write({
                'state': 'active',
                'hospital_signed_on': fields.Datetime.now(),
            })

    def action_activate(self):
        for rec in self:
            if not rec.hospital_signed_on:
                raise ValidationError("Le contrat doit etre signe par l etablissement avant activation.")
            rec.state = 'active'

    def action_suspend(self):
        self.state = 'suspended'

    def action_close(self):
        self.state = 'closed'

    def action_reset_to_draft(self):
        self.with_context(allow_signed_contract_edit=True).write({
            'state': 'draft',
            'hospital_signed_on': False,
        })

    def action_open_invoice_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Facturation Mensuelle',
            'res_model': 'dasri.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contract_id': self.id,
            },
        }

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('dasri.action_report_dasri_contract').report_action(self)

    def action_open_partner(self):
        self.ensure_one()
        if not self.partner_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Établissement',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'res_id': self.partner_id.id,
        }

    def _compute_partner_count(self):
        for contract in self:
            contract.partner_count = 1 if contract.partner_id else 0

    def _check_hospital_signature_data(self):
        self.ensure_one()
        if not self.hospital_signatory_name or not self.hospital_signatory_role or not self.hospital_signature:
            raise ValidationError(
                "Le nom, la fonction et la signature du representant de l etablissement sont obligatoires."
            )

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for contract in self:
            if contract.date_end and contract.date_end < contract.date_start:
                raise ValidationError("La date de fin doit être postérieure à la date de début.")

    @api.constrains('pricing_type', 'price_kg', 'price_trip')
    def _check_pricing(self):
        for contract in self:
            if contract.pricing_type == 'weight' and not contract.price_kg:
                raise ValidationError("Le prix par KG est requis pour une tarification au poids.")
            if contract.pricing_type == 'trip' and not contract.price_trip:
                raise ValidationError("Le prix par passage est requis pour une tarification au passage.")
            if contract.pricing_type == 'mixed' and (not contract.price_kg or not contract.price_trip):
                raise ValidationError("Les prix par KG et par passage sont requis pour une tarification mixte.")

    def write(self, vals):
        locked_fields = {
            'partner_id', 'date_start', 'date_end', 'periodicity', 'pricing_type',
            'price_kg', 'price_trip', 'monthly_min', 'terms', 'attachment_ids',
            'hospital_signatory_name', 'hospital_signatory_role', 'hospital_signature',
        }
        if locked_fields.intersection(vals) and any(
            rec.hospital_signed_on for rec in self
        ) and not self.env.context.get('allow_signed_contract_edit'):
            raise ValidationError("Impossible de modifier un contrat deja signe par l etablissement.")
        return super().write(vals)

    @api.model
    def _get_applicable_contract(self, partner, on_date=False):
        if not partner:
            return self.browse()
        if not on_date:
            on_date = fields.Date.context_today(self)
        domain = [
            ('partner_id', '=', partner.id),
            ('state', '=', 'active'),
            ('date_start', '<=', on_date),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', on_date),
        ]
        return self.search(domain, order='date_start desc, id desc', limit=1)
