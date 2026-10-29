pragma solidity ^0.4.24;

contract DosNumber {
    uint256 public numElements = 0;
    uint256[] public array;

    function insertNnumbers(uint256 value, uint256 numbers) public {
        require(numbers <= 100);
        for (uint256 i = 0; i < numbers; i++) {
            if (numElements == array.length) {
                array.length += 1;
            }
            array[numElements++] = value;
        }
    }

    function clear() public {
        require(numElements > 1500);
        numElements = 0;
    }

    function clearDOS() public {
        require(numElements > 1500);
        numElements = 0;
    }

    function getLengthArray() public view returns (uint256) {
        return numElements;
    }

    function getRealLengthArray() public view returns (uint256) {
        return array.length;
    }
}
