pragma solidity >=0.4.22<0.6.0;
contract Target {
	mapping(address => uint) balances_re_ent8;
	function withdraw_balances_re_ent8() public {
	bool success = msg.sender.send(balances_re_ent8[msg.sender]);
	if(success){
	balances_re_ent8[msg.sender] = 0;
	}
	}
	function () payable external {
	}
	function deposit() payable public {
	}
	
}