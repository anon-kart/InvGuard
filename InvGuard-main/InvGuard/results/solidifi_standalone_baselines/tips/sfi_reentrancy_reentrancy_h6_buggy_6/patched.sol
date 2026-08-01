pragma solidity ^0.5.8;
contract Target {
	mapping(address => uint) balances_re_ent1;
	function withdraw_balances_re_ent1() public {
	bool success = msg.sender.send(balances_re_ent1[msg.sender]);
	if(success){
	balances_re_ent1[msg.sender] = 0;
	}
	}
	function () payable external {
	}
	function deposit() payable public {
	}
	
}