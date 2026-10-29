pragma solidity ^0.4.24;

contract FibonacciLib {
    uint256 public start;
    uint256 public calculatedFibNumber;

    function setStart(uint256 _start) public {
        start = _start;
    }

    function setFibonacci(uint256 n) public {
        calculatedFibNumber = fibonacci(n);
    }

    function fibonacci(uint256 n) internal view returns (uint256) {
        if (n == 0) return start;
        else if (n == 1) return start + 1;
        else return fibonacci(n - 1) + fibonacci(n - 2);
    }
}

contract FibonacciBalance {
    address public fibonacciLibrary;
    uint256 public calculatedFibNumber;
    uint256 public start = 3;
    uint256 public withdrawalCounter;
    bytes4 constant fibSig = bytes4(keccak256("setFibonacci(uint256)"));

    constructor(address _fibonacciLibrary) public payable {
        fibonacciLibrary = _fibonacciLibrary;
    }

    function withdraw() public {
        withdrawalCounter += 1;
        require(fibonacciLibrary.delegatecall(fibSig, withdrawalCounter));
        msg.sender.transfer(calculatedFibNumber * 1 ether);
    }

    function() public {
        require(msg.sig == fibSig);
        require(fibonacciLibrary.delegatecall(msg.data));
    }
}
