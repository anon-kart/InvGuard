pragma solidity ^0.5.0;

                        contract sGuardPlus {
                                constructor() internal {
                                        
                                        
                                }
                                
                                
                                
                                
                        }
                contract Target  {
mapping (address  => uint )    balances_re_ent3;
function withdrawFunds_re_ent3 (uint256    _weiToWithdraw) public  {
require(balances_re_ent3[msg.sender]>=_weiToWithdraw);
balances_re_ent3[msg.sender]-=_weiToWithdraw;
require(success);
(bool     success, ) = msg.sender.call.value(_weiToWithdraw)("");
}

function () external payable {
}

function deposit () public payable {
}

}
