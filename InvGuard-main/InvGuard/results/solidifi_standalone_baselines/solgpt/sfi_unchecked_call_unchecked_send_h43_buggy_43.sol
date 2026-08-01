pragma solidity ^0.5.0;

contract Target {

    function bug_unchk_send8() payable public {
        require(address(this).balance >= 1 ether, "Insufficient balance");
        (bool success, ) = msg.sender.call.value(1 ether)("");
        require(success, "Transfer failed");
    }

    function() external payable {}

    function deposit() public payable {}

}