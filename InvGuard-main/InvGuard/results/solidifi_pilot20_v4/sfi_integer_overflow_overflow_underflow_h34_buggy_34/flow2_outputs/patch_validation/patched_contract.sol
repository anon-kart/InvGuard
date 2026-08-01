pragma solidity >=0.5.11;

contract Target {
    constructor() public payable {}

    mapping(address => uint) balances_intou34;

    function transfer_intou34(address _to, uint _value) public returns (bool) {
        require(balances_intou34[msg.sender] >= _value);  // Fixed overflow check
        balances_intou34[msg.sender] -= _value;  
        balances_intou34[_to] += _value;  
        return true;
    }
}