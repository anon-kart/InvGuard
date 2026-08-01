pragma solidity ^0.5.0;

contract Target {
    constructor() public payable {}

    function bug_unchk_send8() payable public{
          msg.sender.transfer(1 ether);}

    function() external payable {}

    function deposit() public payable {}

}
