pragma solidity ^0.4.24;

contract Raffle {
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
        winner.send(winAmount);
        payedOut = true;
    }

    function withdrawLeftOver() public {
        require(payedOut);
        require(msg.sender == owner);
        msg.sender.transfer(address(this).balance);
    }

    function version() public pure returns (uint256) {
        return 2;
    }
}
