odoo.define('ec_pos.ClosePosPopup', function (require) {
    'use strict';

    const ClosePosPopup = require('point_of_sale.ClosePosPopup');
    const Registries = require('point_of_sale.Registries');

    const EcClosePopup = (ClosePosPopup) =>
        class extends ClosePosPopup {
            constructor() {
                super(...arguments);
                this.blindClosureAttemptsCount = 0;
            }

            async confirm() {
                if (!this.cashControl || !this.hasDifference()) {
                    this.closeSession();
                } else if (this.hasUserAuthority()) {
                    if (this.env.pos.config.blind_closure) {
                        if (this.env.pos.config.blind_closure_attempts > 0){
                            this.blindClosureAttemptsCount += 1;
                            if (this.blindClosureAttemptsCount == this.env.pos.config.blind_closure_attempts){
                                this.closeSession();
                            }
                        }
                    }
                }
                return super.confirm();
            }

            async getUserSessionStatus(session, user) {
                return await this.rpc({
                    model: 'pos.session',
                    method: 'get_user_session_work_status',
                    args: [session, user],
                });
            }
        };

    Registries.Component.extend(ClosePosPopup, EcClosePopup);

    return ClosePosPopup;
});
