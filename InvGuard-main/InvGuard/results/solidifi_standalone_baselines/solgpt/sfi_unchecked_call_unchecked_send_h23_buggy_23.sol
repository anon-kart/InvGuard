pragma solidity ^0.5.2;

contract Target {

    function bug_unchk_send15() payable public {
        require(address(this).balance >= 1 ether, "Insufficient balance");
        msg.sender.transfer(1 ether);
    }

    function() external payable {}

    function deposit() public payable {}

}