odoo.define('ec_payment_medianet_pos.Medianet', function(require) {
	"use strict";

	var core = require('web.core');
//	const { useState, useRef } = owl.hooks;
	const { useState, useRef } = owl;
	const { useListener } = require("@web/core/utils/hooks");
	const PosComponent = require('point_of_sale.PosComponent');
	const Registries = require('point_of_sale.Registries');
	const AbstractAwaitablePopup = require('point_of_sale.AbstractAwaitablePopup');
	var QWeb = core.qweb;

	var _t = core._t;

	class MedianetInformationPopup extends AbstractAwaitablePopup {
		setup() {
			super.setup();
			var order = this.env.pos.get_order();
			this.inputauth = useRef('input-auth');
			this.inputlote = useRef('input-lote');
			this.inputref = useRef('input-ref');
			this.inputinteres = useRef('input-selected');
			this.inputmgracia = useRef('input-mgracia');

		}
		mounted() {
			this.inputauth.el.focus();
		}
		send_trama_medianet(order){
			self = this;
			return this.rpc({
				model: 'ec.medianet.transaction',
				method: 'send_trama_medianet',
				args:[order.export_as_JSON(),self.inputinteres.el.value],
			}, {async: true}).then((result) => {
				if(result.state){
					self.inputref.el.value = result.data.referencia;
					self.inputlote.el.value = result.data.lote;
					self.inputauth.el.value = result.data.autorizacion;
					var order = self.env.pos.get_order();
					for (var i = 0; i < order.paymentlines.length; i++) {
						if (order.paymentlines[i].cid == order.selected_paymentline.cid) {
							order.paymentlines[i].medianet_authorization = result.data.autorizacion;
							order.paymentlines[i].medianet_lote = result.data.lote;
							order.paymentlines[i].medianet_reference = result.data.referencia
							order.paymentlines[i].trama = result.data.trama
							order.paymentlines[i].have_deferred = result.data.have_deferred
							order.paymentlines[i].month_interest = result.data.month_interest
							order.paymentlines[i].month_interest_free = result.data.month_interest_free
							order.paymentlines[i].with_interest = result.data.with_interest
						}
					}
				}
				else{
					self.showPopup('ErrorPopup', {
						title: _t('Error'),
						body: result.mensaje || _t('Error con Trama Medianet.'),
					});
				}
			})
		}
		async getDatos(){
			this.confirm();
		}
		async sendTrama(){
			var order = this.env.pos.get_order();
			if (order.medianet_authorization){
				this.env.pos.db.notification('danger',_t('Ya se enviaron los datos de Medianet.'));
			}
			else {
				var data_medianet = await this.send_trama_medianet(order);
			}
		}
		cancel() {
			this.confirm();
		}
	}

	MedianetInformationPopup.template = 'MedianetInformationPopup';
	MedianetInformationPopup.defaultProps = {
		confirmText: 'Ok',
		cancelText: 'Cancel',
		title: '',
		body: '',
		list: [],
		startingValue: '',
	};

	Registries.Component.add(MedianetInformationPopup);

	return MedianetInformationPopup;
});