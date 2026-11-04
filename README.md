# odoo-migration-temp-third-party-modules

Su questa repo privata mettiamo tutti i moduli che migriamo durante le migrazioni che sono originariamente moduli di terze parti come OCA o altri sviluppatori, e li migriamo temporaneamente fino a quando non escono versioni ufficiali dello stesso modulo.

Una volta che il modulo ufficiale da parte degli sviluppatori di terze parti viene rilasciato, si dovrà eliminare il modulo da questa repo transitoria e installare sull'Odoo dove stiamo lavorando il modulo ufficiale.

Un ramo per versione di Odoo (`20.0`, …). I moduli **nostri** (`tw_*`) non vanno qui: stanno in `extra-addons-tw`.

## Moduli presenti — ramo 20.0

Stato verificato il 2026-11-04: nessuno è ancora presente nei rami 20.0 ufficiali di OCA (`partner-contact`, `project`, `web`, `spreadsheet`, `server-brand`, `website`, `server-ux`, `server-tools`).

| Modulo | Origine | Base del porting |
| --- | --- | --- |
| `partner_firstname` | OCA/partner-contact | 19.0, `ec30dcf74b574fbbaa45487aca0bd2448aee2725` |
| `project_parent`, `project_stage_extra_info` | OCA/project | 19.0, `73535e7d724197aaa047a4322aea5cf15a9e5f84` |
| `project_role` | OCA/project | 18.0, `4ce1bfe6981bdd4e43fd93c9feb53c359798e9a5` |
| `project_list` | OCA/project | copia OCA installata sulla versione 16 |
| `web_chatter_position`, `web_remember_tree_column_width` | OCA/web | 19.0, `678831b2028a0f90b336cdfcc8201d763102bb38` |
| `spreadsheet_dashboard_purchase_stock_oca` | OCA/spreadsheet | 19.0, `4237c0486215cf702b75210e385388535a4913e8` |
| `website_debranding` | OCA | porting dalla versione installata |
| `web_access_rule_buttons`, `web_widget_child_selector`, `web_widget_model_viewer`, `web_widget_open_tab` | OCA (con modifiche ticinoWEB) | porting dalla versione installata |

Autori e licenze originali restano quelli dichiarati nei rispettivi moduli.

## Quando esce la versione ufficiale

1. Installa il modulo ufficiale sull'Odoo dove lavoriamo (percorso `/mnt/extra-addons` o OCA).
2. Togli il modulo da questa repo (`git rm -r <modulo>`) e aggiorna la tabella sopra.
3. Se avevamo modifiche nostre, valuta una PR a monte o un piccolo modulo `tw_*` che estende quello ufficiale.
