pragma solidity ^0.5.0;

contract Target {

    mapping(address => uint) balances_re_ent3;

    function withdrawFunds_re_ent3 (uint256 _weiToWithdraw) public {
            require(balances_re_ent3[msg.sender] >= _weiToWithdraw);
            balances_re_ent3[msg.sender] -= _weiToWithdraw;
            (bool success,)= msg.sender.call.value(_weiToWithdraw)("");
            require(success);
        }

    function() external payable {}

    function deposit() public payable {
        balances_re_ent3[msg.sender] += msg.value;
    }

}