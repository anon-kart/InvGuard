pragma solidity ^0.4.24;

contract GuessTheRandomNumber {
    struct Bet {
        uint8 n;
        uint256 blockNumber;
    }

    mapping(address => Bet) public bets;

    constructor() public payable {
        require(msg.value == 1 ether);
    }

    function guess(uint8 n) public payable {
        require(msg.value == 1 ether);
        require(bets[msg.sender].blockNumber == 0);
        bets[msg.sender] = Bet(n, block.number + 1);
    }

    function settle() public {
        Bet memory b = bets[msg.sender];
        require(b.blockNumber != 0 && block.number > b.blockNumber);
        delete bets[msg.sender];
        if (block.number - b.blockNumber > 255) {
            return;
        }
        uint8 answer = uint8(keccak256(abi.encodePacked(blockhash(b.blockNumber), msg.sender)));
        if (b.n == answer) {
            msg.sender.transfer(2 ether);
        }
    }
}
