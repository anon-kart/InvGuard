pragma solidity ^0.4.24;

contract Rubixi {
    address private creator;
    uint256 public collectedFees;
    uint256 public feePercent = 10;

    modifier onlyowner() {
        require(msg.sender == creator);
        _;
    }

    function DynamicPyramid() public {
        creator = msg.sender;
    }

    function() public payable {
        collectedFees += msg.value * feePercent / 100;
    }

    function collectAllFees() public onlyowner {
        require(collectedFees > 0);
        uint256 amount = collectedFees;
        collectedFees = 0;
        creator.transfer(amount);
    }
}
