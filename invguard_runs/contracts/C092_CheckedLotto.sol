pragma solidity ^0.4.24;

contract CheckedLotto {
    bool public payedOut = false;
    address public winner;
    uint256 public winAmount;

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
}
