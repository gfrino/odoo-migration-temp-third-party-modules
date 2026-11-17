# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import io
from odoo import models
from odoo.tools.pdf import OdooPdfFileReader, OdooPdfFileWriter
class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        data = data or {}
        res = super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids)
        if not res_ids:
            return res
        report = self._get_report(report_ref)
        if report.report_name == 'tw_extend.report_inv_solare':
            invoices = self.env[report.model].browse(res_ids)
            # Determine which invoices need a QR/ISR.
            qr_inv_ids = []
            isr_inv_ids = []
            for invoice in invoices:
                # avoid duplicating existing streams
                if report.attachment_use and report.retrieve_attachment(invoice):
                    continue
                if invoice.l10n_ch_is_qr_valid:
                    qr_inv_ids.append(invoice.id)
                elif invoice.company_id.country_code == 'CH' and getattr(invoice, 'l10n_ch_isr_valid', False):
                    isr_inv_ids.append(invoice.id)
            # Render the additional reports.
            streams_to_append = {}
            if qr_inv_ids:
                qr_res = self._render_qweb_pdf_prepare_streams(
                    'l10n_ch.l10n_ch_qr_report',
                    {
                        **data,
                        'skip_headers': False,
                    },
                    res_ids=qr_inv_ids,
                )
                header = self.env.ref('l10n_ch.l10n_ch_qr_header', raise_if_not_found=False)
                if header:
                    # Make a separated rendering to get the a page containing the company header. Then, merge the qr bill with it.

                    header_res = self._render_qweb_pdf_prepare_streams(
                        'l10n_ch.l10n_ch_qr_header',
                        {
                            **data,
                            'skip_headers': True,
                        },
                        res_ids=qr_inv_ids,
                    )

                    for invoice_id, stream in qr_res.items():
                        qr_pdf = OdooPdfFileReader(stream['stream'], strict=False)
                        header_pdf = OdooPdfFileReader(header_res[invoice_id]['stream'], strict=False)

                        page = header_pdf.pages[0]
                        page.merge_page(qr_pdf.pages[0])

                        output_pdf = OdooPdfFileWriter()
                        output_pdf.add_page(page)
                        new_pdf_stream = io.BytesIO()
                        output_pdf.write(new_pdf_stream)
                        new_pdf_stream.seek(0)
                        streams_to_append[invoice_id] = {'stream': new_pdf_stream}
                else:
                    for invoice_id, stream in qr_res.items():
                        streams_to_append[invoice_id] = stream

            if isr_inv_ids:
                isr_res = self._render_qweb_pdf_prepare_streams('l10n_ch.l10n_ch_isr_report', data, res_ids=isr_inv_ids)
                for invoice_id, stream in isr_res.items():
                    streams_to_append[invoice_id] = stream

            # Add to results
            for invoice_id, additional_stream in streams_to_append.items():
                invoice_stream = res[invoice_id]['stream']
                writer = OdooPdfFileWriter()
                writer.append_pages_from_reader(OdooPdfFileReader(invoice_stream, strict=False))
                writer.append_pages_from_reader(OdooPdfFileReader(additional_stream['stream'], strict=False))
                new_pdf_stream = io.BytesIO()
                writer.write(new_pdf_stream)
                new_pdf_stream.seek(0)
                res[invoice_id]['stream'] = new_pdf_stream
                invoice_stream.close()
                additional_stream['stream'].close()
            # invoices = self.env[report.model].browse(res_ids)
            # # Determine which invoices need a QR/ISR.
            # qr_inv_ids = []
            # isr_inv_ids = []
            # for invoice in invoices:
            #     if invoice.company_id.country_code != 'CH':
            #         continue
            #     if invoice.l10n_ch_is_qr_valid:
            #         qr_inv_ids.append(invoice.id)
            #     elif getattr(invoice, 'l10n_ch_isr_valid', False):
            #         isr_inv_ids.append(invoice.id)
            # # Render the additional reports.
            # streams_to_append = {}
            # if qr_inv_ids:
            #     qr_res = self._render_qweb_pdf_prepare_streams('l10n_ch.l10n_ch_qr_report', data, res_ids=qr_inv_ids)
            #     for invoice_id, stream in qr_res.items():
            #         streams_to_append[invoice_id] = stream
            # if isr_inv_ids:
            #     isr_res = self._render_qweb_pdf_prepare_streams('l10n_ch.l10n_ch_isr_report', data, res_ids=isr_inv_ids)
            #     for invoice_id, stream in isr_res.items():
            #         streams_to_append[invoice_id] = stream
            # # head_res = self._render_qweb_pdf_prepare_streams('l10n_ch.l10n_ch_qr_header', data, res_ids=isr_inv_ids)
            # # for invoice_id, stream in head_res.items():
            # #     streams_to_append[invoice_id] = stream
            #
            # # Add to results
            # for invoice_id, additional_stream in streams_to_append.items():
            #     invoice_stream = res[invoice_id]['stream']
            #     writer = OdooPdfFileWriter()
            #     writer.append_pages_from_reader(OdooPdfFileReader(invoice_stream, strict=False))
            #     writer.append_pages_from_reader(OdooPdfFileReader(additional_stream['stream'], strict=False))
            #     new_pdf_stream = io.BytesIO()
            #     writer.write(new_pdf_stream)
            #     res[invoice_id]['stream'] = new_pdf_stream
            #     invoice_stream.close()
            #     additional_stream['stream'].close()
        return res
