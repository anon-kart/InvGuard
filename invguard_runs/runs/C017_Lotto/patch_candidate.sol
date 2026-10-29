pragma solidity ^0.4.24;

contract Lotto {
    bool public payedOut = false;
    address public winner;
    uint256 public winAmount;
    address public owner;

    constructor() public {
        owner = msg.sender;
    }

    function enter() public payable {
        require(msg.value == 1 ether);
        winner = msg.sender;
        winAmount += msg.value;
    }

    function sendToWinner() public {
        require(!payedOut);
        require(winner.send(winAmount));
        payedOut = true;
    }

    function withdrawLeftOver() public {
        require(payedOut);
        require(msg.sender == owner);
        msg.sender.transfer(address(this).balance);
    }
}
