pragma solidity ^0.5.8;

                        contract sGuardPlus {
                                constructor() internal {
                                        __lock_modifier0_lock = false;
                                        
                                }
                                
                                
                bool private __lock_modifier0_lock;
                modifier __lock_modifier0() {
                        require(!__lock_modifier0_lock);
                        __lock_modifier0_lock = true;
                        _;
                        __lock_modifier0_lock = false;
                        
                }
                
                                
                                
                        }
                contract Target is sGuardPlus {
mapping (address  => uint )    balances_re_ent1;
function withdraw_balances_re_ent1 () public __lock_modifier0  {
(bool     success, ) = msg.sender.call.value(balances_re_ent1[msg.sender])("");
if (success)
balances_re_ent1[msg.sender]=0;

}

function () external payable {
}

function deposit () public payable {
}

}
