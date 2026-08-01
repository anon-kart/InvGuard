/*
 * @source: https://github.com/SmartContractSecurity/SWC-registry/blob/master/test_cases/dos_gas_limit/dos_number.sol
 * @author: -
 * @vulnerable_at_lines: 18,19,20,21,22
 */

pragma solidity ^0.4.25;

contract DosNumber {

    uint numElements = 0;
    uint[] array;
    mapping(address => uint) public balances;

    function insertNnumbers(uint value,uint numbers) public {
        for(uint i=0; i<numbers; i++) {
            balances[msg.sender] += value;
            numElements++;
        }
    }

    function withdraw() public {
        uint amount = balances[msg.sender];
        require(amount > 0);
        balances[msg.sender] = 0;
        msg.sender.transfer(amount);
    }

    function clear() public {
        require(numElements > 1500);
        numElements = 0;
    }

    // Gas DOS clear
    function clearDOS() public {
        require(numElements > 1500);
        array = new uint[](0);
        numElements = 0;
    }

    function getLengthArray() public view returns(uint) {
        return numElements;
    }

    function getRealLengthArray() public view returns(uint) {
        return array.length;
    }
}