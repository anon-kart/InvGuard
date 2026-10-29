pragma solidity ^0.4.24;

contract CounterMinus {
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

    function version() public pure returns (uint256) {
        return 2;
    }
}
