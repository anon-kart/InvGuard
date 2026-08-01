pragma solidity ^0.5.0;

contract Target {
    constructor() public payable {}

    mapping(address => uint) balances_re_ent3;

    function withdrawFunds_re_ent3 (uint256 _weiToWithdraw) public {
            require(balances_re_ent3[msg.sender] >= _weiToWithdraw);
            balances_re_ent3[msg.sender] -= _weiToWithdraw; // Move state update before external call
            (bool success,)= msg.sender.call.value(_weiToWithdraw)("");
            require(success);  //bug
        }

    function() external payable {}

    function deposit() public payable {
        balances_re_ent3[msg.sender] += msg.value;
    }

}