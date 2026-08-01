/*
 * @source: https://github.com/SmartContractSecurity/SWC-registry/blob/master/test_cases/dos_gas_limit/dos_number.sol
 * @author: -
 * @vulnerable_at_lines: 18,19,20,21,22
 */

pragma solidity ^0.4.25;

contract DosNumber {

    uint numElements = 0;
    uint[] array;

    function insertNnumbers(uint value,uint numbers) public {

        // Avoid unbounded storage writes/growth that can make clearDOS run out of gas
        require(numElements + numbers >= numElements);
        numElements += numbers;
    }

    function clear() public {
        require(numElements>1500);
        numElements = 0;
    }

    // Gas DOS clear
    function clearDOS() public {

        // number depends on actual gas limit
        require(numElements>1500);
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


// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `DosNumber` has a no-arg constructor (or implicit constructor).
contract Target is DosNumber {
    constructor() DosNumber() {}
}
