from odoo import fields, models


class DasriIncinerator(models.Model):
    _name = 'dasri.incinerator'
    _description = 'Incinerateur DASRI'
    _order = 'name'

    name = fields.Char('Reference', required=True)
    code = fields.Char('Code')
    capacity_kg = fields.Float('Capacite (KG)')
    active = fields.Boolean(default=True)
    note = fields.Text('Notes')

    _sql_constraints = [
        ('dasri_incinerator_name_unique', 'unique(name)', 'La reference de l incinerateur doit etre unique.'),
    ]
