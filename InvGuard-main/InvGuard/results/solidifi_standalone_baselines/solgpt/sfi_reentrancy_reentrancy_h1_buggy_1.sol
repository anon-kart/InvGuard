pragma solidity >=0.4.22 <0.6.0;

contract Target {

    mapping(address => uint) balances_re_ent8;

    function withdraw_balances_re_ent8 () public {
          uint amount = balances_re_ent8[msg.sender];
          require(amount > 0, "No balance to withdraw");
          balances_re_ent8[msg.sender] = 0;
          (bool success,) = msg.sender.call.value(amount)("");
          require(success, "Transfer failed");
    }

    function() external payable {}

    function deposit() public payable {
        balances_re_ent8[msg.sender] += msg.value;
    }

}