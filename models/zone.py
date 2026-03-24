from odoo import fields, models


class DasriZone(models.Model):
    _name = 'dasri.zone'
    _description = 'Zone DASRI'
    _order = 'name'

    name = fields.Char('Nom', required=True)
    code = fields.Char('Code')
    active = fields.Boolean(default=True)
    note = fields.Text('Notes')

    _sql_constraints = [
        ('dasri_zone_name_unique', 'unique(name)', 'Le nom de la zone doit etre unique.'),
    ]
