pragma solidity ^0.5.0;

contract Target {

    mapping(address => uint) balances_intou22;

    function transfer_intou22(address _to, uint _value) public returns (bool) {
        require(balances_intou22[msg.sender] >= _value);
        balances_intou22[msg.sender] -= _value;
        balances_intou22[_to] += _value;
        return true;
    }

}