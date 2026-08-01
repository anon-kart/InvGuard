pragma solidity ^0.5.2;

contract Target {
    constructor() public payable {}

    function bug_unchk_send15() payable public{
          msg.sender.transfer(1 ether);}

    function() external payable {}

    function deposit() public payable {}

}
