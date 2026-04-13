odoo.define('ec_pos.pos_partner', function (require) {

    const { _t } = require('web.core');
    const PartnerDetailsEdit = require('point_of_sale.PartnerDetailsEdit');
    const Registries = require('point_of_sale.Registries');
    var rpc = require('web.rpc');

    const { onMounted, useState, onWillUnmount } = owl;

    const EcPartnerDetailsEdit = PartnerDetailsEdit => class extends PartnerDetailsEdit {
        async searchEcCi_Ruc(event) {
            console.log("ENTRA AL BOTÓN")
            let processedChanges = {};
            for (let [key, value] of Object.entries(this.changes)) {
                if (this.intFields.includes(key)) {
                    processedChanges[key] = parseInt(value) || false;
                } else {
                    processedChanges[key] = value;
                }
            }
            if ((!this.props.partner.vat && !processedChanges.vat) ||
                processedChanges.vat === '') {
                return this.showPopup('ErrorPopup', {
                    title: _t('Debe ingresar la identificación!!'),
                });
            }
            var current_ref = this.el.getElementsByClassName("detail client-ref");
            var self = this;
            if (current_ref.length > 0) {
                rpc.query({
                    model: 'pos.order',
                    method: 'get_ruc_client',
                    args: [current_ref[0].value]
                }).then(function (result_dict) {
                    var current_name = self.el.getElementsByClassName("detail client-name");
                    if (current_name.length > 0) {
                        if (result_dict.ok) {
                            current_name[0].value = result_dict.ruc_name;
                        }
                        else {
                            return self.showPopup('ErrorPopup', {
                                title: _t('no se ha encontrado la identificación'),
                            });
                        }
                    }
                }).catch(function (error) {
                    return self.showPopup('ErrorPopup', {
                        title: _t('no se ha encontrado la identificación'),
                    });
                })
            }
        }

        setup() {
            super.setup();
            this.intFields = ["country_id", "state_id", "property_product_pricelist"];
            const partner = this.props.partner;
            this.changes = useState({
                id: partner.id || false,
                name: partner.name || "",
                street: partner.street || "",
                city: partner.city || "",
                zip: partner.zip || "",
                state_id: partner.state_id && partner.state_id[0],
                country_id: partner.country_id && partner.country_id[0],
                lang: partner.lang || "",
                email: partner.email || "",
                phone: partner.phone || "",
                mobile: partner.mobile || "",
                barcode: partner.barcode || "",
                vat: partner.vat || "",
                l10n_latam_identification_type_id: partner.l10n_latam_identification_type_id && partner.l10n_latam_identification_type_id[0],
                property_product_pricelist: this.getDefaultPricelist(partner),
            });

            onMounted(() => {
                this.env.bus.on("save-partner", this, this.saveChanges);
            });

            onWillUnmount(() => {
                this.env.bus.off("save-partner", this);
            });
        }

        async saveChanges() {
            let processedChanges = {};
            for (let [key, value] of Object.entries(this.changes)) {
                if (this.intFields.includes(key)) {
                    processedChanges[key] = parseInt(value) || false;
                } else {
                    processedChanges[key] = value;
                }
            }

            if (this.props.partner.vat == '9999999999999') {
                return this.showPopup('ErrorPopup', {
                    title: _t('No puede modificar el consumidor Final!!!!'),
                });
            }

            if ((!this.props.partner.name && !processedChanges.name) ||
                processedChanges.name === '') {
                return this.showPopup('ErrorPopup', {
                    title: _t('El nombre del Cliente es requerido'),
                });
            }
            if ((!this.props.partner.l10n_latam_identification_type_id && !processedChanges.l10n_latam_identification_type_id) ||
                processedChanges.l10n_latam_identification_type_id === '') {
                return this.showPopup('ErrorPopup', {
                    title: _t('Debe ingresar el tipo de Identificación!!'),
                });
            }
            if ((!this.props.partner.vat && !processedChanges.vat) ||
                processedChanges.vat === '') {
                return this.showPopup('ErrorPopup', {
                    title: _t('Debe ingresar la identificación!!'),
                });
            }

            let vat = processedChanges.vat || this.props.partner.vat;
            let partnerId = this.props.partner.id;

            if (vat) {
                try {
                    let isDuplicate = await rpc.query({
                        model: 'res.partner',
                        method: 'check_vat_pos',
                        args: [vat, partnerId],
                    });
                    if (isDuplicate) {
                        return this.showPopup('ErrorPopup', {
                            title: _t('Error de Validación'),
                            body: _t('Ya existe un cliente con esta identificación.'),
                        });
                    }
                } catch (error) {
                    console.error("Error checking VAT uniqueness", error);
                    return this.showPopup('ErrorPopup', {
                        title: _t('Error de Conexión'),
                        body: _t('No se pudo verificar la identificación. Revise su conexión.'),
                    });
                }
            }

            this.trigger('save-changes', { processedChanges });
        }
    };
    Registries.Component.extend(PartnerDetailsEdit, EcPartnerDetailsEdit);

    return PartnerDetailsEdit;
});
