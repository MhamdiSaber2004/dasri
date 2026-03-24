from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    dasri_contract_ids = fields.One2many('dasri.contract', 'partner_id', string='Contrats DASRI')
    dasri_contract_count = fields.Integer(string='Contrats DASRI', compute='_compute_dasri_contract_count')
    has_active_dasri_contract = fields.Boolean(
        string='Contrat DASRI Actif',
        compute='_compute_has_active_dasri_contract',
        store=True,
    )

    def action_open_dasri_contracts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Contrats DASRI',
            'res_model': 'dasri.contract',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    @api.depends('dasri_contract_ids')
    def _compute_dasri_contract_count(self):
        counts = self.env['dasri.contract'].read_group(
            [('partner_id', 'in', self.ids)],
            ['partner_id'],
            ['partner_id'],
        )
        mapped = {item['partner_id'][0]: item['partner_id_count'] for item in counts}
        for partner in self:
            partner.dasri_contract_count = mapped.get(partner.id, 0)

    @api.depends('dasri_contract_ids.state')
    def _compute_has_active_dasri_contract(self):
        for partner in self:
            partner.has_active_dasri_contract = any(
                contract.state == 'active' for contract in partner.dasri_contract_ids
            )
