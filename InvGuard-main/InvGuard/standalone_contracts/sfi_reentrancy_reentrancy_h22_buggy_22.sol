pragma solidity >=0.5.1 <0.6.0;

contract Target {
    constructor() public payable {}

    mapping(address => uint) balances_re_ent17;

    function withdrawFunds_re_ent17 (uint256 _weiToWithdraw) public {
            require(balances_re_ent17[msg.sender] >= _weiToWithdraw);
            // limit the withdrawal
            (bool success,)=msg.sender.call.value(_weiToWithdraw)("");
            require(success);  //bug
            balances_re_ent17[msg.sender] -= _weiToWithdraw;
        }

    function() external payable {}

    function deposit() public payable {
        balances_re_ent17[msg.sender] += msg.value;
    }

}
