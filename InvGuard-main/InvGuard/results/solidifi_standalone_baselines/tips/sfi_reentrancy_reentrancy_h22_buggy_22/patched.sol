pragma solidity >=0.5.1;
contract Target {
	mapping(address => uint) balances_re_ent17;
	function withdrawFunds_re_ent17(uint256 _weiToWithdraw) public {
	require(balances_re_ent17[msg.sender] >= _weiToWithdraw);
	bool success = msg.sender.send(_weiToWithdraw);
	require(success);
	balances_re_ent17[msg.sender] -= _weiToWithdraw;
	}
	function () payable external {
	}
	function deposit() payable public {
	}
	
}