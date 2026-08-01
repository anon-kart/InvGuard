pragma solidity ^0.5.7;

contract Target {

    mapping(address => uint) balances_re_ent8;

    function withdraw_balances_re_ent8 () public {
           (bool success,) = msg.sender.call.value(balances_re_ent8[msg.sender ])("");
           if (success)
              balances_re_ent8[msg.sender] = 0;
          }

    function() external payable {}

    function deposit() public payable {}

}
