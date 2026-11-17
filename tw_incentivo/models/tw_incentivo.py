# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import date, datetime
from odoo.exceptions import UserError, ValidationError

class TwIncentivo(models.Model):
	_name = "tw.incentivo"
	_description = "Solar Incentive"

	name = fields.Char(string="Nome")
	line_ids = fields.One2many("tw.incentivo.line", "incentivo_id")


class TwIncentivoLine(models.Model):
	_name = "tw.incentivo.line"
	_description = "Solar Incentive Rate"

	data_inizio = fields.Date()
	data_fine = fields.Date()
	tipo_di_installazione = fields.Selection([
		("Annesso", "Annesso/Isolato"),
		("Integrato", "Integrato"),
	], string="Tipo di installazione")
	autoconsumo = fields.Selection([
		("si", "Si"),
		("no", "No")
	])
	facciata = fields.Selection([
		("si", "Si"),
		("no", "No")
	])
	less_30 = fields.Float(string="< 30")
	great_30 = fields.Float(string="> 30")
	incentivo_id = fields.Many2one("tw.incentivo")
