pragma solidity ^0.5.11;

contract Target {

    mapping(address => uint) balances_intou26;

    function transfer_intou26(address _to, uint _value) public returns (bool) {
        require(balances_intou26[msg.sender] >= _value);
        balances_intou26[msg.sender] -= _value;
        balances_intou26[_to] += _value;
        return true;
    }

}