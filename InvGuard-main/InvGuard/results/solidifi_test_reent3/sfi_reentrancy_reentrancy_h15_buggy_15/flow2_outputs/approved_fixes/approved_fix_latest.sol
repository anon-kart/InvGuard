pragma solidity ^0.5.7;

contract Target {
    constructor() public payable {}

    mapping(address => uint) balances_re_ent8;

    function withdraw_balances_re_ent8 () public {
           uint amount = balances_re_ent8[msg.sender];
           require(amount > 0, "No balance to withdraw");
           balances_re_ent8[msg.sender] = 0; // State update before external call
           (bool success,) = msg.sender.call.value(amount)("");
           require(success, "Transfer failed");
          }

    function() external payable {}

    function deposit() public payable {
        balances_re_ent8[msg.sender] += msg.value;
    }

}