pragma solidity ^0.8.20;

contract OpenVault {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {}

    function withdrawAll(address payable to) external {
        to.transfer(address(this).balance);
    }
}
