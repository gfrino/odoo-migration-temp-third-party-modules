import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

MAX_BODY = 4 * 1024 * 1024
MAX_ORDERS = 100


class LittleInkaKpiController(http.Controller):
    """Endpoint for the WooCommerce websites of the sedi (child theme Little Inka, inc/odoo-kpi.php).

    Authentication: «Authorization: Bearer <key of the sede>». The key is created in Odoo on the
    sede form and only its SHA-256 is stored. Plain HTTP routes with a JSON body, so the same code
    works whatever the JSON-RPC route type of the Odoo version.
    """

    def _reply(self, payload, status=200):
        return request.make_json_response(payload, status=status)

    def _authenticate(self):
        header = request.httprequest.headers.get("Authorization", "")
        key = header[7:].strip() if header.lower().startswith("bearer ") else ""
        return request.env["tw.littleinka.kpi.sede"].sudo()._from_key(key)

    def _body(self):
        raw = request.httprequest.get_data(cache=False, as_text=False)
        if len(raw) > MAX_BODY:
            return None
        try:
            data = json.loads(raw or b"{}")
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    def _site(self, sede, data):
        site = str(data.get("site") or "")[:255]
        if site.startswith(("http://", "https://")) and sede.website_url != site:
            sede.sudo().website_url = site

    @http.route("/tw_littleinka_kpi/v1/ping", type="http", auth="public", methods=["POST"], csrf=False, save_session=False)
    def ping(self, **_kw):
        sede = self._authenticate()
        if not sede:
            return self._reply({"ok": False, "error": "Chiave non valida o sede disattivata."}, 401)
        data = self._body() or {}
        self._site(sede, data)
        return self._reply({"ok": True, "sede": sede.name})

    @http.route("/tw_littleinka_kpi/v1/orders", type="http", auth="public", methods=["POST"], csrf=False, save_session=False)
    def orders(self, **_kw):
        sede = self._authenticate()
        if not sede:
            return self._reply({"ok": False, "error": "Chiave non valida o sede disattivata."}, 401)
        data = self._body()
        if data is None or not isinstance(data.get("orders"), list):
            return self._reply({"ok": False, "error": "Contenuto non valido."}, 400)
        if len(data["orders"]) > MAX_ORDERS:
            return self._reply({"ok": False, "error": f"Al massimo {MAX_ORDERS} ordini per invio."}, 413)
        self._site(sede, data)
        try:
            results = request.env["tw.littleinka.kpi.order"].sudo()._receive(sede, data["orders"])
        except Exception:
            _logger.exception("Little Inka KPI: orders of sede %s not saved", sede.id)
            request.env.cr.rollback()
            return self._reply({"ok": False, "error": "Errore nel salvataggio su Odoo."}, 500)
        return self._reply({"ok": True, "received": sum(1 for r in results if r["ok"]), "results": results})
