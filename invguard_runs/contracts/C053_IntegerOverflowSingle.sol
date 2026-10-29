pragma solidity ^0.4.24;

contract IntegerOverflowSingle {
    uint256 public count = 1;

    function addToBalance(uint256 input) public {
        count += input;
    }

    function subFromBalance(uint256 input) public {
        count -= input;
    }

    function mulBalance(uint256 input) public {
        count *= input;
    }
}
