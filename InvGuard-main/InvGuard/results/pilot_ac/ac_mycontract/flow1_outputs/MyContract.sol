pragma solidity ^0.4.24;

contract MyContract {

    address owner;

    function MyContract() public {
        owner = msg.sender;
    }

    function sendTo(address receiver, uint amount) public {
        // <yes> <report> ACCESS_CONTROL
        require(tx.origin == owner);
        receiver.transfer(amount);
    }

}
