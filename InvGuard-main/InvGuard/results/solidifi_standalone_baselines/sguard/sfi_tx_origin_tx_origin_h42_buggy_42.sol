contract sGuard{
  
}
pragma solidity ^0.5.11;

contract Target  is sGuard {

    address public owner;

    constructor() public {
        owner = msg.sender;
    }

    function withdrawAll_txorigin2(address payable _recipient,address owner_txorigin2) public {
            require(msg.sender == owner_txorigin2);
            _recipient.transfer(address(this).balance);
        }

    function() external payable {}

    function deposit() public payable {}

}
