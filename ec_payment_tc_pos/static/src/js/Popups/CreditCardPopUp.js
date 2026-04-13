odoo.define('ec_payment_tc_pos.CreditCardPopUp', function(require) {
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

	class CreditCardInformationPopup extends AbstractAwaitablePopup {
		setup() {
			super.setup();
			this.inputauth = useRef('input-auth');
			this.inputlote = useRef('input-lote');
			this.inputref = useRef('input-ref');
		}
		mounted() {
			this.inputauth.el.focus();
		}

		getValue() {
			var order = this.env.pos.get_order();
			for (var i = 0; i < order.paymentlines.length; i++) {
				if (order.paymentlines[i].cid == order.selected_paymentline.cid) {
					order.paymentlines[i].credit_card_authorization = this.inputauth.el.value;
					order.paymentlines[i].credit_card_lote = this.inputlote.el.value;
					order.paymentlines[i].credit_card_reference = this.inputref.el.value;
				}
			}
			this.confirm();
		}
		cancel() {
			this.confirm();
		}
	}

	CreditCardInformationPopup.template = 'CreditCardInformationPopup';
	CreditCardInformationPopup.defaultProps = {
		confirmText: 'Ok',
		cancelText: 'Cancel',
		title: '',
		body: '',
		list: [],
		startingValue: '',
	};

	Registries.Component.add(CreditCardInformationPopup);

	return CreditCardInformationPopup;
});