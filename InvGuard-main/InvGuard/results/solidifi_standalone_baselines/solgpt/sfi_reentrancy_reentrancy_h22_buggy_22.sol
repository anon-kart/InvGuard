pragma solidity >=0.5.1;

contract Target {

    mapping(address => uint) balances_re_ent17;

    function withdrawFunds_re_ent17 (uint256 _weiToWithdraw) public {
            require(balances_re_ent17[msg.sender] >= _weiToWithdraw);
            balances_re_ent17[msg.sender] -= _weiToWithdraw;
            (bool success,)=msg.sender.call.value(_weiToWithdraw)("");
            require(success);
        }

    function() external payable {}

    function deposit() public payable {
        balances_re_ent17[msg.sender] += msg.value;
    }

}